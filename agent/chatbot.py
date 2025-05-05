from pymongo import MongoClient
from dotenv import load_dotenv
import os, uuid
from datetime import datetime
import logging
from bson import ObjectId

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
        Initialize the ChatBot with MongoDB integration and socket support
        
        Args:
            socket_instance: Optional SocketIO instance for real-time updates
        """
        # Set up MongoDB connection
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        # Use a single collection for all session data
        self.messages_collection = self.db.conversation_history
        
        # Store socket instance for real-time updates
        self.socket = socket_instance
        
        logger.info("ChatBot initialized with MongoDB")

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
            "messages": []  # Store messages directly in the session document
        }
        
        # Insert into database
        result = self.messages_collection.insert_one(session)
        
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
        
        return session_copy

    def get_session(self, session_id):
        """
        Get session information by ID
        
        Args:
            session_id (str): Session ID to retrieve
            
        Returns:
            dict: Session information or None if not found
        """
        session = self.messages_collection.find_one({"session_id": session_id})
        
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
        cursor = self.messages_collection.find(query).sort(
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
        Get messages for a specific session
        
        Args:
            session_id (str): Session ID to get messages for
            after: Optional timestamp or index to only get messages after
            limit (int): Maximum number of messages to return
            
        Returns:
            list: List of message documents
        """
        session = self.messages_collection.find_one({"session_id": session_id})
        
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
        # Get current timestamp
        timestamp = datetime.utcnow()
        
        # Find the session
        session = self.messages_collection.find_one({"session_id": session_id})
        
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
        
        # Add to messages array and update count/timestamp
        result = self.messages_collection.update_one(
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
            
        # Convert timestamps to ISO format for JSON serialization
        message_copy = message.copy()
        message_copy["timestamp"] = message_copy["timestamp"].isoformat()
        
        logger.info(f"Added {role} message to session {session_id}")
        
        return message_copy

    def clear_session(self, session_id):
        """
        Clear all messages from a session
        
        Args:
            session_id (str): Session ID to clear
            
        Returns:
            bool: True if successful, False otherwise
        """
        timestamp = datetime.utcnow()
        
        # Clear messages array and reset message count
        result = self.messages_collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "messages": [],
                    "message_count": 0,
                    "updated_at": timestamp
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Cleared messages from session {session_id}")
            
            # Emit socket event if socket available
            if self.socket:
                session = self.get_session(session_id)
                if session:
                    self.socket.emit("session_update", session)
                    
            return True
        
        return False

    def process_chat(self, session_id, user_message):
        """
        Process a user message and generate a response
        
        Args:
            session_id (str): Session ID for the conversation
            user_message (str): User's message
            
        Returns:
            dict: Response from the assistant
        """
        # Log the incoming message
        logger.info(f"Processing message in session {session_id}")
        
        # Store the user message
        self.add_message(session_id, "user", user_message)
        
        # Send typing indicator via socket if available
        if self.socket:
            self.socket.emit("typing_indicator", {
                "session_id": session_id,
                "is_typing": True
            })
        
        try:
            # Simple response generator (placeholder for actual AI processing)
            # In a real implementation, this would call out to an LLM API or use a local model
            response = "I'm sorry, I cannot assist with that right now."
            
            # Add a small delay to simulate processing time
            import time
            time.sleep(1)
            
            # Add the assistant's response to the conversation
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