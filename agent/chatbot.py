from crewai import Agent, Task, Crew, Process
from pymongo import MongoClient
from dotenv import load_dotenv
import os, json, re, uuid
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

class ChatBot:
    def __init__(self, socket_instance=None):
        """
        Initialize the ChatBot with MongoDB integration and socket support
        
        Args:
            socket_instance: Optional SocketIO instance for real-time updates
        """
        # Set up MongoDB connection
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        self.sessions_collection = self.db.sessions
        self.messages_collection = self.db.conversation_history
        
        # Set up CrewAI agent
        self.agent = Agent(
            role="Idea Development Assistant",
            goal="Guide users in developing innovative ideas and concepts",
            backstory="You're a creative and knowledgeable assistant specializing in idea development. You help users explore possibilities, refine concepts, and overcome creative blocks.",
            verbose=True,
            llm=os.getenv("model")
        )
        
        # Store socket instance for real-time updates
        self.socket = socket_instance
        
        logger.info("ChatBot initialized with MongoDB and CrewAI")

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
        
        # Create session document
        session = {
            "session_id": session_id,
            "type": session_type,
            "name": name or f"New {session_type.capitalize()} Session",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "message_count": 0,
            "status": "active"
        }
        
        # Insert into database
        self.sessions_collection.insert_one(session)
        
        # Log creation
        logger.info(f"Created new session: {session_id}")
        
        # Emit socket event if socket available
        if self.socket:
            self.socket.emit("new_session_created", session)
        
        return session

    def get_session(self, session_id):
        """
        Get session information by ID
        
        Args:
            session_id (str): Session ID to retrieve
            
        Returns:
            dict: Session information or None if not found
        """
        session = self.sessions_collection.find_one({"session_id": session_id})
        
        if session:
            # Convert ObjectId to string for JSON serialization
            if "_id" in session:
                session["_id"] = str(session["_id"])
                
            # Convert datetime objects to ISO strings
            for key in ["created_at", "updated_at"]:
                if key in session and isinstance(session[key], datetime):
                    session[key] = session[key].isoformat()
        
        return session

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
        cursor = self.sessions_collection.find(query).sort(
            "updated_at", -1  # Sort by most recent
        ).skip(skip).limit(limit)
        
        # Convert to list and prepare for JSON serialization
        sessions = []
        for session in cursor:
            # Convert ObjectId to string
            if "_id" in session:
                session["_id"] = str(session["_id"])
                
            # Convert datetime objects to ISO strings    
            for key in ["created_at", "updated_at"]:
                if key in session and isinstance(session[key], datetime):
                    session[key] = session[key].isoformat()
                    
            sessions.append(session)
            
        return sessions

    def rename_session(self, session_id, name):
        """
        Rename a session
        
        Args:
            session_id (str): Session ID to rename
            name (str): New name for the session
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not name:
            return False
            
        result = self.sessions_collection.update_one(
            {"session_id": session_id},
            {"$set": {"name": name, "updated_at": datetime.utcnow()}}
        )
        
        success = result.modified_count > 0
        
        if success and self.socket:
            # Get updated session and emit event
            session = self.get_session(session_id)
            if session:
                self.socket.emit("session_update", session)
                
        return success

    def get_messages(self, session_id, after_index=None, limit=100):
        """
        Get messages for a specific session
        
        Args:
            session_id (str): Session ID to get messages for
            after_index (int): Only get messages after this index
            limit (int): Maximum number of messages to return
            
        Returns:
            list: List of message documents
        """
        query = {"session_id": session_id}
        
        # If after_index provided, only get newer messages
        if after_index is not None:
            query["index"] = {"$gt": int(after_index)}
            
        # Query database with sorting
        cursor = self.messages_collection.find(query).sort(
            "timestamp", 1  # Sort by oldest first for proper ordering
        ).limit(limit)
        
        # Convert to list and prepare for JSON serialization
        messages = []
        for msg in cursor:
            # Convert ObjectId to string
            if "_id" in msg:
                msg["_id"] = str(msg["_id"])
                
            # Convert timestamp to ISO string if needed
            if "timestamp" in msg and isinstance(msg["timestamp"], datetime):
                msg["timestamp"] = msg["timestamp"].isoformat()
                
            messages.append(msg)
            
        return messages

    def add_message(self, session_id, role, content):
        """
        Add a message to a session
        
        Args:
            session_id (str): Session ID to add message to
            role (str): Role of the message sender (user/assistant/system)
            content (str): Message content
            
        Returns:
            dict: Added message document
        """
        # Verify session exists
        session = self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return None
            
        # Get current message count for indexing
        message_count = self.messages_collection.count_documents({"session_id": session_id})
        
        # Create message document
        message = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow(),
            "index": message_count  # Zero-based index for ordering
        }
        
        # Insert into database
        result = self.messages_collection.insert_one(message)
        message["_id"] = str(result.inserted_id)
        message["timestamp"] = message["timestamp"].isoformat()
        
        # Update session document with new count and timestamp
        self.sessions_collection.update_one(
            {"session_id": session_id},
            {
                "$set": {"updated_at": datetime.utcnow()},
                "$inc": {"message_count": 1}
            }
        )
        
        logger.info(f"Added {role} message to session {session_id}")
        
        return message

    def clear_session(self, session_id):
        """
        Clear all messages from a session
        
        Args:
            session_id (str): Session ID to clear
            
        Returns:
            bool: True if successful, False otherwise
        """
        result = self.messages_collection.delete_many({"session_id": session_id})
        
        if result.deleted_count > 0:
            # Reset message count in session
            self.sessions_collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "message_count": 0,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"Cleared {result.deleted_count} messages from session {session_id}")
            
            # Emit socket event if socket available
            if self.socket:
                session = self.get_session(session_id)
                if session:
                    self.socket.emit("session_update", session)
                    
            return True
        
        return False

    def process_chat(self, session_id, message_text):
        """
        Process a user message and generate a response
        
        Args:
            session_id (str): Session ID for the conversation
            message_text (str): User's message
            
        Returns:
            dict: Response from the assistant
        """
        # Log the incoming message
        logger.info(f"Processing message in session {session_id}")
        
        # Store the user message
        self.add_message(session_id, "user", message_text)
        
        # Send typing indicator via socket if available
        if self.socket:
            self.socket.emit("typing_indicator", {
                "session_id": session_id,
                "is_typing": True
            })
        
        # Get recent conversation history for context (up to 10 messages)
        recent_messages = self.get_messages(session_id, limit=10)
        
        # Format conversation history for the AI
        conversation_context = ""
        for msg in recent_messages:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            conversation_context += f"{prefix}: {msg['content']}\n\n"
        
        # Create AI task with conversation context
        chat_task = Task(
            description=(
                "You are an Idea Development Assistant helping with creative thinking.\n\n"
                "Conversation history:\n"
                "{conversation_context}\n\n"
                "User's latest message:\n"
                "{message}\n\n"
                "1. Respond helpfully to the user's message.\n"
                "2. Provide useful, creative, and actionable suggestions.\n"
                "3. Consider both practical implementation and innovative possibilities.\n\n"
                "Respond in a conversational, helpful manner focused on idea development."
            ),
            expected_output="A helpful and creative response to the user's message.",
            agent=self.agent,
            context={
                "conversation_context": conversation_context,
                "message": message_text
            }
        )
        
        # Create crew with single agent
        crew = Crew(
            agents=[self.agent],
            tasks=[chat_task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            # Process the user's message and get a response
            result = str(crew.kickoff()).strip()
            
            # Add the assistant's response to the conversation
            assistant_message = self.add_message(session_id, "assistant", result)
            
            # Stop typing indicator
            if self.socket:
                self.socket.emit("typing_indicator", {
                    "session_id": session_id,
                    "is_typing": False
                })
                
                # Send response via socket
                self.socket.emit("chat_response", {
                    "session_id": session_id,
                    "response": result,
                    "timestamp": assistant_message["timestamp"]
                })
            
            # Return the response
            return {
                "response": result,
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

    def update_session_heartbeat(self, session_id):
        """
        Update the last active timestamp for a session
        
        Args:
            session_id (str): Session ID to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        result = self.sessions_collection.update_one(
            {"session_id": session_id},
            {"$set": {"updated_at": datetime.utcnow()}}
        )
        
        return result.modified_count > 0
        
    def close(self):
        """
        Close MongoDB connection
        """
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")