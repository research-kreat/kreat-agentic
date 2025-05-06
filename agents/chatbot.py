from pymongo import MongoClient
from dotenv import load_dotenv
import os, uuid
from datetime import datetime
import logging
from bson import ObjectId
from crewai import Agent, Task, Crew, Process
import json
import time
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "kraft_db")

class ChatBot:
    def __init__(self, socket_instance=None):
        """
        Initialize the ChatBot with MongoDB integration, socket support, and CrewAI agent
        
        Args:
            socket_instance: Optional SocketIO instance for real-time updates
        """
        # Set up MongoDB connection for storing conversation history (just for reference)
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        self.conversation_history = self.db.conversation_history
        
        # Store socket instance for real-time updates
        self.socket = socket_instance
        
        # Initialize CrewAI agent
        self.setup_agent()
        
        # Keep conversation memory indexed by session_id
        self.memory_cache = {}
        
        logger.info("ChatBot initialized with MongoDB and CrewAI agent")

    def setup_agent(self):
        """Set up a dynamic CrewAI agent that can handle multiple task types"""
        
        # Single versatile agent that can handle all tasks
        self.dynamic_agent = Agent(
            role="KRAFT Innovation Assistant",
            goal="Help users develop innovative concepts and creative solutions to problems",
            backstory="""You are a versatile AI assistant specialized in innovation and creativity.
            You excel at brainstorming, analyzing problems, developing ideas, and creating
            implementation strategies. You help users think outside the box while maintaining
            a practical approach to turning concepts into reality.""",
            verbose=True,
            llm="azure/gpt-4o-mini",  # Using the same model as before
            memory=True  # Enable memory for the agent
        )
        
        logger.info("CrewAI agent configured successfully")

    def create_task(self, task_type, user_message, session_id):
        """
        Create a specific task based on the task type
        
        Args:
            task_type (str): Type of task to create
            user_message (str): User's message
            session_id (str): Session ID for the conversation
            
        Returns:
            Task: CrewAI task object
        """
        # Get conversation memory for this session
        conversation_history = self.get_conversation_memory(session_id)
        
        # Format memory for context
        context = "\n\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in conversation_history])
        
        # Define task descriptions based on task type
        task_descriptions = {
            "idea": f"""
                Help the user develop their innovative concept or creative idea.
                
                User Message: "{user_message}"
                
                Previous Conversation Context:
                {context}
                
                Your task is to:
                1. Understand the user's idea or creative concept
                2. Ask clarifying questions if needed
                3. Suggest enhancements, variations, or novel approaches
                4. Help overcome creative blocks
                5. Provide constructive feedback that preserves the user's vision
                
                Respond conversationally as if you're a helpful brainstorming partner.
                """,
                
            "problem": f"""
                Help the user define and explore their challenge.
                
                User Message: "{user_message}"
                
                Previous Conversation Context:
                {context}
                
                Your task is to:
                1. Understand the problem the user is facing
                2. Help them articulate it more clearly if needed
                3. Break down complex problems into manageable parts
                4. Identify root causes and potential approach angles
                5. Guide the user through a structured problem-solving process
                
                Respond conversationally as a helpful problem-solving partner.
                """,
                
            "possibility": f"""
                Help the user explore potential solutions to their challenge.
                
                User Message: "{user_message}"
                
                Previous Conversation Context:
                {context}
                
                Your task is to:
                1. Generate multiple solution approaches
                2. Explore the benefits and limitations of each
                3. Help the user combine different solution elements
                4. Encourage creative and unconventional thinking
                5. Provide a structured way to evaluate options
                
                Respond conversationally as a helpful solution-exploring partner.
                """,
                
            "implementation": f"""
                Help the user develop an implementation strategy.
                
                User Message: "{user_message}"
                
                Previous Conversation Context:
                {context}
                
                Your task is to:
                1. Break down the implementation into concrete steps
                2. Identify resources, tools, and skills needed
                3. Help anticipate and plan for potential challenges
                4. Suggest ways to test and validate the implementation
                5. Provide a realistic timeline and milestones
                
                Respond conversationally as a practical implementation advisor.
                """
        }
        
        # Default to idea task if type not found
        description = task_descriptions.get(task_type, task_descriptions["idea"])
        
        # Create and return the task
        return Task(
            description=description,
            agent=self.dynamic_agent,
            expected_output="Conversational response that helps the user with their request"
            # Removed the context parameter as it's causing validation errors
        )

    def create_session(self, session_type="idea", name=None):
        """
        Create a new chat session
        
        Args:
            session_type (str): Type of session (idea, problem, etc.)
            name (str): Optional name for the session
            
        Returns:
            dict: Session information including ID
        """
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        current_time = datetime.utcnow()
        
        # Create session document
        session = {
            "session_id": session_id,
            "type": session_type,
            "name": name or f"New {session_type.capitalize()} Session",
            "created_at": current_time,
            "updated_at": current_time,
            "message_count": 0,
            "status": "active",
            "messages": []  # Store messages directly in the document
        }
        
        # Insert into database
        result = self.conversation_history.insert_one(session)
        
        # Log creation
        logger.info(f"Created new session: {session_id}")
        
        # Create a JSON-safe copy
        session_copy = session.copy()
        
        # Add the _id field as a string
        session_copy["_id"] = str(result.inserted_id)
        
        # Convert datetime objects to ISO format strings for JSON serialization
        session_copy["created_at"] = session_copy["created_at"].isoformat()
        session_copy["updated_at"] = session_copy["updated_at"].isoformat()
        
        # Emit socket event if socket available
        if self.socket:
            self.socket.emit("new_session_created", session_copy)
        
        # Initialize empty memory for this session
        self.memory_cache[session_id] = []
        
        return session_copy

    def get_session(self, session_id):
        """
        Get session information by ID
        
        Args:
            session_id (str): Session ID to retrieve
            
        Returns:
            dict: Session information or None if not found
        """
        session = self.conversation_history.find_one({"session_id": session_id})
        
        if session:
            # Create a copy to avoid modifying the original document
            session_copy = session.copy()
            
            # Convert ObjectId to string for JSON serialization
            if "_id" in session_copy:
                session_copy["_id"] = str(session_copy["_id"])
                
            # Convert datetime objects to ISO strings
            for key in ["created_at", "updated_at"]:
                if key in session_copy and isinstance(session_copy[key], datetime):
                    session_copy[key] = session_copy[key].isoformat()
            
            # Remove messages from session info when returning it
            if "messages" in session_copy:
                del session_copy["messages"]
                
            return session_copy
        
        return None

    def get_sessions(self, session_type=None, limit=10, skip=0):
        """
        Get list of sessions, optionally filtered by type
        
        Args:
            session_type (str): Optional session type to filter by
            limit (int): Maximum number of sessions to return
            skip (int): Number of sessions to skip (for pagination)
            
        Returns:
            list: List of session documents
        """
        query = {}
        if session_type:
            query["type"] = session_type
            
        # Query database with sorting and pagination
        cursor = self.conversation_history.find(query).sort(
            "updated_at", -1  # Sort by most recent
        ).skip(skip).limit(limit)
        
        # Convert to list and prepare for JSON serialization
        sessions = []
        for session in cursor:
            # Create a JSON-safe copy
            session_copy = session.copy()
            
            # Convert ObjectId to string
            if "_id" in session_copy:
                session_copy["_id"] = str(session_copy["_id"])
                
            # Convert datetime objects to ISO strings    
            for key in ["created_at", "updated_at"]:
                if key in session_copy and isinstance(session_copy[key], datetime):
                    session_copy[key] = session_copy[key].isoformat()
            
            # Remove messages array to keep response smaller
            if "messages" in session_copy:
                del session_copy["messages"]
                    
            sessions.append(session_copy)
            
        return sessions

    def get_messages(self, session_id, after=None, limit=100):
        """
        Get messages for a specific session from database
        (This is only for UI display, not for feeding into CrewAI)
        
        Args:
            session_id (str): Session ID to get messages for
            after: Optional timestamp or index to only get messages after
            limit (int): Maximum number of messages to return
            
        Returns:
            list: List of message documents
        """
        session = self.conversation_history.find_one({"session_id": session_id})
        
        if not session or "messages" not in session:
            return []
            
        messages = session["messages"]
        
        # Apply filtering if after parameter is provided
        if after is not None:
            try:
                # If after is an index
                if isinstance(after, str) and after.isdigit():
                    after_index = int(after)
                    messages = [msg for msg in messages if msg.get("index", 0) > after_index]
                # If after is a timestamp
                else:
                    messages = [msg for msg in messages if msg.get("timestamp", "") > after]
            except:
                # If parsing fails, return all messages
                pass
                
        # Apply limit
        messages = messages[-limit:] if len(messages) > limit else messages
        
        # Convert timestamps to ISO strings if they're datetime objects
        message_copies = []
        for msg in messages:
            msg_copy = msg.copy()
            if "timestamp" in msg_copy and isinstance(msg_copy["timestamp"], datetime):
                msg_copy["timestamp"] = msg_copy["timestamp"].isoformat()
            message_copies.append(msg_copy)
                
        return message_copies

    def get_conversation_memory(self, session_id):
        """
        Get the conversation memory for a session
        
        Args:
            session_id (str): Session ID to get memory for
            
        Returns:
            list: List of memory messages
        """
        # Make sure memory is initialized for this session
        if session_id not in self.memory_cache:
            self.memory_cache[session_id] = []
            
        return self.memory_cache[session_id]

    def add_message(self, session_id, role, content):
        """
        Add a message to a session in database and memory cache
        
        Args:
            session_id (str): Session ID to add message to
            role (str): Role of the message sender (user/assistant/system)
            content (str): Message content
            
        Returns:
            dict: Added message document
        """
        # Get current timestamp
        timestamp = datetime.utcnow()
        
        # Find the session
        session = self.conversation_history.find_one({"session_id": session_id})
        
        if not session:
            logger.error(f"Session not found: {session_id}")
            return None
            
        # Get current message count
        message_count = len(session.get("messages", []))
        
        # Create message document
        message = {
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "index": message_count  # Zero-based index for ordering
        }
        
        # Add to messages array and update count/timestamp in database
        # This is just for reference/history, not for feeding into CrewAI
        result = self.conversation_history.update_one(
            {"session_id": session_id},
            {
                "$push": {"messages": message},
                "$set": {"updated_at": timestamp},
                "$inc": {"message_count": 1}
            }
        )
        
        if result.modified_count == 0:
            logger.error(f"Failed to add message to session {session_id}")
            return None
        
        # Add message to memory cache if it's a user or assistant message
        if role in ["user", "assistant"]:
            # Make sure memory is initialized for this session
            if session_id not in self.memory_cache:
                self.memory_cache[session_id] = []
                
            # Add new message to memory
            self.memory_cache[session_id].append({
                "role": role,
                "content": content
            })
            
        # Convert timestamps to ISO format for JSON serialization
        message_copy = message.copy()
        message_copy["timestamp"] = message_copy["timestamp"].isoformat()
        
        logger.info(f"Added {role} message to session {session_id}")
        
        return message_copy

    def clear_session(self, session_id):
        """
        Clear all messages from a session in database and memory cache
        
        Args:
            session_id (str): Session ID to clear
            
        Returns:
            bool: True if successful, False otherwise
        """
        timestamp = datetime.utcnow()
        
        # Clear messages array and reset message count in database
        result = self.conversation_history.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "messages": [],
                    "message_count": 0,
                    "updated_at": timestamp
                }
            }
        )
        
        # Clear memory cache for this session
        self.memory_cache[session_id] = []
        
        if result.modified_count > 0:
            logger.info(f"Cleared messages from session {session_id}")
            
            # Emit socket event if socket available
            if self.socket:
                session = self.get_session(session_id)
                if session:
                    self.socket.emit("session_update", session)
                    
            return True
        
        return False
        
    def clean_text(self, text):
        """Clean and normalize text for better processing"""
        if not text:
            return ""
        text = str(text)
        text = re.sub(r'\s+', ' ', text)  # Replace multiple whitespaces with single space
        text = text.replace('\r\n', '\n').replace('\r', '\n')  # Normalize line breaks
        return text.strip()  # Remove leading/trailing whitespace

    def process_with_crew(self, session_id, user_message, session_type):
        """
        Process message using CrewAI agent with a single task
        
        Args:
            session_id (str): Session ID for the conversation
            user_message (str): User's message
            session_type (str): Type of session (idea, problem, etc.)
            
        Returns:
            str: Generated response
        """
        # Create appropriate task based on session type
        task = self.create_task(session_type, user_message, session_id)
        
        # Create and execute CrewAI crew with just one task
        try:
            crew = Crew(
                agents=[self.dynamic_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True
            )
            
            # Log beginning of processing
            logger.info(f"CrewAI processing started for session {session_id}")
            if self.socket:
                self.socket.emit("console_log", {
                    "type": "info",
                    "message": f"Processing message with AI agent...",
                    "session_id": session_id
                })
            
            # Run the crew without passing explicit inputs (session_id is already in task description)
            result = crew.kickoff()
            
            # Clean up and return the result
            return str(result).strip()
            
        except Exception as e:
            logger.error(f"Error in CrewAI processing: {str(e)}")
            return f"I'm sorry, I encountered an issue while processing your message. Please try again."

    def process_chat(self, session_id, user_message):
        """
        Process a user message and generate a response using CrewAI
        
        Args:
            session_id (str): Session ID for the conversation
            user_message (str): User's message
            
        Returns:
            dict: Response from the assistant
        """
        # Log the incoming message
        logger.info(f"Processing message in session {session_id}")
        
        # Store the user message in database (for reference only)
        self.add_message(session_id, "user", user_message)
        
        # Get session info
        session = self.get_session(session_id)
        session_type = session.get("type", "idea") if session else "idea"
        
        # Send typing indicator via socket if available
        if self.socket:
            self.socket.emit("typing_indicator", {
                "session_id": session_id,
                "is_typing": True
            })
        
        try:
            # Process with CrewAI
            response = self.process_with_crew(session_id, user_message, session_type)
            
            # Add the assistant's response to the conversation in database (for reference only)
            assistant_message = self.add_message(session_id, "assistant", response)
            
            # Stop typing indicator
            if self.socket:
                self.socket.emit("typing_indicator", {
                    "session_id": session_id,
                    "is_typing": False
                })
                
                # Send response via socket
                self.socket.emit("chat_response", {
                    "session_id": session_id,
                    "response": response,
                    "timestamp": assistant_message["timestamp"] if assistant_message else datetime.utcnow().isoformat()
                })
            
            # Return the response
            return {
                "response": response,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error in chat processing: {str(e)}")
            
            # Stop typing indicator
            if self.socket:
                self.socket.emit("typing_indicator", {
                    "session_id": session_id,
                    "is_typing": False
                })
            
            # Add error message to conversation
            error_message = f"I'm sorry, there was an error processing your request. Please try again."
            self.add_message(session_id, "system", error_message)
            
            return {
                "error": str(e),
                "response": error_message,
                "session_id": session_id
            }
            
    def close(self):
        """
        Close MongoDB connection
        """
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")