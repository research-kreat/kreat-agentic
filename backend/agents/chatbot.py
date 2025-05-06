# This is the fixed implementation for the chatbot.py file
from pymongo import MongoClient
from datetime import datetime
import logging
import os
import uuid
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from queue import Queue
import threading

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
        """Initialize the ChatBot with MongoDB, socket support, and CrewAI agent"""
        # Set up MongoDB connection
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        self.conversation_history = self.db.conversation_history
        
        # Store socket instance for real-time updates
        self.socket = socket_instance
        
        # Initialize CrewAI agent
        self.dynamic_agent = Agent(
            role="KRAFT Innovation Assistant",
            goal="Help users develop innovative concepts and creative solutions to problems",
            backstory="""You are a versatile AI assistant specialized in innovation and creativity.
            You excel at brainstorming, analyzing problems, developing ideas, and creating
            implementation strategies. You help users think outside the box while maintaining
            a practical approach to turning concepts into reality.""",
            verbose=True,
            llm=LLM(
                model="azure/gpt-4o-mini",
                temperature=0.7,
                stream=True,
                callbacks=[self._token_callback]  # Add callback for token streaming
            ),
            memory=True
        )
        
        # Keep conversation memory indexed by session_id
        self.memory_cache = {}
        
        # Dictionary to store token queues for active streaming sessions
        self.token_queues = {}
        
        logger.info("ChatBot initialized with MongoDB and CrewAI agent")

    def _token_callback(self, token, **kwargs):
        """Callback function for CrewAI to handle token streaming"""
        # Get current session ID from thread local storage
        current_session_id = getattr(threading.current_thread(), "session_id", None)
        
        if current_session_id and current_session_id in self.token_queues:
            # Put token in the queue
            self.token_queues[current_session_id].put(token)
            
            # Also emit via socket if available for real-time updates
            if self.socket:
                self.socket.emit("token_update", {
                    "session_id": current_session_id,
                    "token": token
                })

    def _format_for_json(self, data):
        """Convert MongoDB document to JSON-safe format"""
        if not data:
            return None
            
        data_copy = data.copy()
        
        # Convert ObjectId to string
        if "_id" in data_copy:
            data_copy["_id"] = str(data_copy["_id"])
            
        # Convert datetime objects to ISO strings
        for key in ["created_at", "updated_at", "timestamp"]:
            if key in data_copy and isinstance(data_copy[key], datetime):
                data_copy[key] = data_copy[key].isoformat()
                
        return data_copy

    def create_session(self, session_type="idea", name=None):
        """Create a new chat session"""
        session_id = str(uuid.uuid4())
        current_time = datetime.utcnow()
        
        session = {
            "session_id": session_id,
            "type": session_type,
            "name": name or f"New {session_type.capitalize()} Session",
            "created_at": current_time,
            "updated_at": current_time,
            "message_count": 0,
            "status": "active",
            "messages": []
        }
        
        result = self.conversation_history.insert_one(session)
        logger.info(f"Created new session: {session_id}")
        
        session_copy = self._format_for_json(session)
        
        # Add the _id field as a string
        session_copy["_id"] = str(result.inserted_id)
        
        # Emit socket event if socket available
        if self.socket:
            self.socket.emit("new_session_created", session_copy)
        
        # Initialize empty memory for this session
        self.memory_cache[session_id] = []
        
        return session_copy

    def get_session(self, session_id):
        """Get session information by ID"""
        session = self.conversation_history.find_one({"session_id": session_id})
        
        if not session:
            return None
            
        session_copy = self._format_for_json(session)
        
        # Remove messages from session info when returning it
        if "messages" in session_copy:
            del session_copy["messages"]
                
        return session_copy

    def get_sessions(self, session_type=None, limit=10, skip=0):
        """Get list of sessions, optionally filtered by type"""
        query = {}
        if session_type:
            query["type"] = session_type
            
        cursor = self.conversation_history.find(query).sort(
            "updated_at", -1
        ).skip(skip).limit(limit)
        
        sessions = []
        for session in cursor:
            session_copy = self._format_for_json(session)
            
            # Remove messages array to keep response smaller
            if "messages" in session_copy:
                del session_copy["messages"]
                    
            sessions.append(session_copy)
            
        return sessions

    def get_messages(self, session_id, after=None, limit=100):
        """Get messages for a specific session from database"""
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
                pass
                
        # Apply limit
        messages = messages[-limit:] if len(messages) > limit else messages
        
        # Convert timestamps to ISO strings
        return [self._format_for_json(msg) for msg in messages]

    def delete_session(self, session_id):
        """Delete a session completely from the database"""
        result = self.conversation_history.delete_one({"session_id": session_id})
        
        if result.deleted_count > 0:
            # Also clear from memory cache
            if session_id in self.memory_cache:
                del self.memory_cache[session_id]
                
            logger.info(f"Deleted session {session_id}")
            
            # Emit socket event if socket available
            if self.socket:
                self.socket.emit("session_deleted", {"session_id": session_id})
                
            return True
        
        return False

    def add_message(self, session_id, role, content):
        """Add a message to a session in database and memory cache"""
        timestamp = datetime.utcnow()
        
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
            "index": message_count
        }
        
        # Add to messages array and update count/timestamp in database
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
            if session_id not in self.memory_cache:
                self.memory_cache[session_id] = []
                
            self.memory_cache[session_id].append({
                "role": role,
                "content": content
            })
            
        logger.info(f"Added {role} message to session {session_id}")
        
        return self._format_for_json(message)

    def clear_session(self, session_id):
        """Clear all messages from a session in database and memory cache"""
        timestamp = datetime.utcnow()
        
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
        if session_id in self.memory_cache:
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

    def create_task(self, task_type, user_message, session_id):
        """Create a specific task based on the task type"""
        # Get limited conversation memory (only 6 most recent messages)
        if session_id in self.memory_cache:
            memory = self.memory_cache[session_id][-6:] if len(self.memory_cache[session_id]) > 6 else self.memory_cache[session_id]
            
            # Format memory in the specified format
            formatted_chat = "OLD CHAT:\n"
            for msg in memory:
                role = "USER" if msg['role'] == 'user' else "YOU"
                formatted_chat += f"{role}: \"{msg['content']}\"\n"
        else:
            formatted_chat = ""
        
        # Task descriptions dictionary
        task_descriptions = {
            "idea": f"""
                Help the user develop their innovative concept or creative idea.
                
                User Message: "{user_message}"
                
                {formatted_chat}
                
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
                
                {formatted_chat}
                
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
                
                {formatted_chat}
                
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
                
                {formatted_chat}
                
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
        
        return Task(
            description=description,
            agent=self.dynamic_agent,
            expected_output="Conversational response that helps the user with their request"
        )

    def process_chat(self, session_id, user_message):
        """Process a user message and generate a response using CrewAI"""
        logger.info(f"Processing message in session {session_id}")
        
        # Store the user message in database
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
            # Create a token queue for this session
            self.token_queues[session_id] = Queue()
            
            # Process with CrewAI
            task = self.create_task(session_type, user_message, session_id)
            
            # Create and execute CrewAI crew
            crew = Crew(
                agents=[self.dynamic_agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True
            )
            
            logger.info(f"CrewAI processing started for session {session_id}")
            if self.socket:
                self.socket.emit("console_log", {
                    "type": "info",
                    "message": "Processing message with AI agent...",
                    "session_id": session_id
                })
            
            def stream_generator():
                # Store all tokens for saving the complete response later
                collected_tokens = []
                
                # Create and start the crew process in a separate thread
                def process_crew():
                    try:
                        # Set thread-local session ID for the token callback
                        threading.current_thread().session_id = session_id
                        
                        # Start the crew process
                        response = crew.kickoff()
                        logger.info(f"CrewAI completed for session {session_id}: {response}")
                    except Exception as e:
                        logger.error(f"Error in crew kickoff: {str(e)}")
                    finally:
                        # Signal the end of streaming by putting None in the queue
                        self.token_queues[session_id].put(None)
                
                # Start the processing thread
                crew_thread = threading.Thread(target=process_crew)
                crew_thread.daemon = True
                crew_thread.start()
                
                # Read tokens from the queue until we get a None (signal for end)
                while True:
                    token = self.token_queues[session_id].get()
                    if token is None:
                        break
                    
                    # Collect token for the full response
                    collected_tokens.append(token)
                    
                    # Yield token for streaming
                    yield token
                    
                    # Mark the task as done in the queue
                    self.token_queues[session_id].task_done()
                
                # Save the complete response to database
                full_response = "".join(collected_tokens)
                self.save_streamed_response(session_id, full_response)
                
                # Clean up the token queue for this session
                if session_id in self.token_queues:
                    del self.token_queues[session_id]
            
            # Return the streaming generator and session_id
            return stream_generator(), session_id
            
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
            
            # Clean up the token queue for this session
            if session_id in self.token_queues:
                del self.token_queues[session_id]
            
            # Return error
            def error_generator():
                yield error_message
                
            return error_generator(), session_id
            
    def save_streamed_response(self, session_id, response_text):
        """Save the full streamed response to the database after streaming is complete"""
        if not response_text.strip():
            logger.warning(f"Empty response for session {session_id}, not saving to database")
            return None
            
        logger.info(f"Saving complete response ({len(response_text)} chars) to database for session {session_id}")
        return self.add_message(session_id, "assistant", response_text)
            
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")