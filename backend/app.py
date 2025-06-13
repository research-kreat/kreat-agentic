from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import uuid
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import logging
import json
from helpers.global_helper import sanitize_response

# Import our block handlers
from block_agents.idea_block import IdeaBlockHandler
from block_agents.problem_block import ProblemBlockHandler
from block_agents.possibility_block import PossibilityBlockHandler
from block_agents.concept_block import ConceptBlockHandler
from block_agents.needs_block import NeedsBlockHandler
from block_agents.opportunity_block import OpportunityBlockHandler
from block_agents.outcome_block import OutcomeBlockHandler
from block_agents.moonshot_block import MoonshotBlockHandler
from utils_agents.block_classifier import classify_user_input


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI")
MONGO_KRAFT_DB = os.getenv("MONGO_KRAFT_DB")
client = MongoClient(MONGO_URI)
db = client[MONGO_KRAFT_DB]

# Collections
flow_collection = db.flow_status
history_collection = db.conversation_history
blocks_collection = db.blocks

# Block handler mapping
block_handlers = {
    "idea": IdeaBlockHandler,
    "problem": ProblemBlockHandler,
    "possibility": PossibilityBlockHandler,
    "concept": ConceptBlockHandler,
    "needs": NeedsBlockHandler,
    "opportunity": OpportunityBlockHandler,
    "outcome": OutcomeBlockHandler,
    "moonshot": MoonshotBlockHandler,
    "general": IdeaBlockHandler  # Use IdeaBlockHandler for general chat as fallback
}

# Standard flow steps for all block types in the correct order
STANDARD_FLOW_STEPS = [
    "title",
    "abstract", 
    "stakeholders",
    "tags",
    "assumptions",
    "constraints",
    "risks",
    "areas",
    "impact",
    "connections",
    "classifications",
    "think_models"
]

@app.route('/api/analyze', methods=['POST'])
def analyze_general_chat():
    """
    Endpoint for general chat that classifies the input and creates a new block
    """
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    # Get user input
    user_input = data.get('message', '')
    
    # Classify the user input
    try:
        block_type, confidence, is_greeting, classification_message = classify_user_input(user_input)
    except ValueError as e:
        # Handle case where classifier returns old format (without classification_message)
        block_type, confidence, is_greeting = classify_user_input(user_input)
        classification_message = f"Great! I've identified this as a {block_type} type. Let's explore it further."
    
    # Create a new block ID
    block_id = str(uuid.uuid4())
    
    # Initialize flow status with standard steps in the correct order
    flow_status = {
        "user_id": user_id,
        "block_id": block_id,
        "block_type": block_type,
        "initial_input": user_input,
        "flow_status": {step: False for step in STANDARD_FLOW_STEPS},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Store in MongoDB
    flow_collection.insert_one(flow_status)
    
    # Store user message in history
    history_collection.insert_one({
        "user_id": user_id,
        "block_id": block_id,
        "role": "user",
        "message": user_input,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    # Store block in blocks collection
    blocks_collection.insert_one({
        "block_id": block_id,
        "user_id": user_id,
        "type": block_type,
        "name": f"New {block_type.capitalize()} Block",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    # Initialize appropriate handler
    if block_type in block_handlers:
        handler_class = block_handlers[block_type]
        handler = handler_class(db, block_id, user_id)
        
        # Get initial response
        response = handler.initialize_block(user_input)
        
        # Sanitize response to ensure plain text
        response = sanitize_response(response)
        
        # If it's identified as a greeting, we need to handle it differently
        if response.get("identified_as") == "greeting":
            greeting_message = response.get("greeting_response")
            
            # Store assistant response in history
            history_collection.insert_one({
                "user_id": user_id,
                "block_id": block_id,
                "role": "assistant",
                "message": greeting_message,
                "result": response,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            
            return jsonify({
                "block_id": block_id,
                "block_type": block_type,
                "confidence": confidence,
                "response": {
                    "suggestion": greeting_message
                }
            })
        else:
            # For non-greeting messages, use the classification and suggestion directly
            suggestion = response.get("suggestion", "")
            classification_msg = response.get("classification_message", "")
            
            # Store assistant response in history
            history_collection.insert_one({
                "user_id": user_id,
                "block_id": block_id,
                "role": "assistant",
                "message": f"{classification_msg}\n\n{suggestion}",
                "result": response,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            
            # Following the standard flow, first message is classification and suggestion
            return jsonify({
                "block_id": block_id,
                "block_type": block_type,
                "confidence": confidence,
                "response": {
                    "suggestion": suggestion,
                    "classification_message": classification_msg
                }
            })
    else:
        return jsonify({'error': f'Unsupported block type: {block_type}'}), 400
    
    
@app.route('/api/analysis_of_block', methods=['POST'])
def analyze_existing_block():
    """
    Enhanced endpoint for continuing conversation with an existing block
    Uses improved history retention and context awareness
    """
    data = request.json
    user_id = data.get('user_id')
    block_id = data.get('block_id')
    
    if not user_id or not block_id:
        return jsonify({'error': 'user_id and block_id are required'}), 400
    
    # Get user input
    user_input = data.get('message', '')
    
    # Fetch flow status
    flow_data = flow_collection.find_one({"block_id": block_id, "user_id": user_id})
    
    if not flow_data:
        return jsonify({'error': 'Block not found'}), 404
    
    block_type = flow_data.get("block_type")
    
    # Store user message in history
    history_collection.insert_one({
        "user_id": user_id,
        "block_id": block_id,
        "role": "user",
        "message": user_input,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    # Get appropriate handler
    if block_type in block_handlers:
        handler_class = block_handlers[block_type]
        handler = handler_class(db, block_id, user_id)
        
        # Process the message with improved history utilization
        response = handler.process_message(user_input, flow_data["flow_status"])
        
        # Sanitize response to ensure plain text
        response = sanitize_response(response)
        
        # If it's identified as a greeting, handle it appropriately
        if response.get("identified_as") == "greeting":
            greeting_message = response.get("greeting_response")
            
            # Store assistant response in history
            history_collection.insert_one({
                "user_id": user_id,
                "block_id": block_id,
                "role": "assistant",
                "message": greeting_message,
                "result": response,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            
            return jsonify({
                "block_id": block_id,
                "block_type": block_type,
                "response": {
                    "suggestion": greeting_message
                }
            })
        else:
            # Update flow status if needed
            if "updated_flow_status" in response:
                flow_collection.update_one(
                    {"block_id": block_id, "user_id": user_id},
                    {"$set": {
                        "flow_status": response["updated_flow_status"],
                        "updated_at": datetime.utcnow()
                    }}
                )
                
                # Keep a copy before removing it from response
                updated_flow_status = response["updated_flow_status"].copy()
                
                # Remove internal flow status from response before sending to client
                response.pop("updated_flow_status", None)
            
            # Get the suggestion for the message content
            suggestion = response.get("suggestion", "")
            
            # Get the current step content if any (with improved title/abstract context)
            current_step = None
            for step in STANDARD_FLOW_STEPS:
                if step in response and response[step] is not None:
                    current_step = step
                    # Format data for display
                    if isinstance(response[step], (list, dict)):
                        if isinstance(response[step], list):
                            # Keep lists as is, without additional formatting
                            pass
                        elif isinstance(response[step], dict):
                            # Format dict for display as list
                            formatted_items = []
                            for k, v in response[step].items():
                                formatted_items.append(f"{k}: {v}")
                            response[step] = formatted_items
            
            # Create a clean message for display
            display_message = suggestion
            if current_step is not None and current_step in response:
                # If we're working with text content (title or abstract)
                if current_step in ["title", "abstract"]:
                    display_message = f"{response[current_step]}\n\n{suggestion}"
                # For lists of items
                elif isinstance(response[current_step], list):
                    items_text = "\n".join([f"• {item}" for item in response[current_step]])
                    display_message = f"{items_text}\n\n{suggestion}"
                # For other data types
                else:
                    display_message = f"{response[current_step]}\n\n{suggestion}"
            
            # Store assistant response in history with full context
            history_collection.insert_one({
                "user_id": user_id,
                "block_id": block_id,
                "role": "assistant",
                "message": display_message,
                "result": response,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            
            # Return a JSON-compatible response
            return jsonify({
                "block_id": block_id,
                "block_type": block_type,
                "response": response
            })
    else:
        return jsonify({'error': f'Unsupported block type: {block_type}'}), 400


@app.route('/api/blocks', methods=['GET'])
def get_blocks():
    """
    Get blocks for a user
    """
    user_id = request.args.get('user_id')
    block_type = request.args.get('type', 'all')
    limit = int(request.args.get('limit', 10))
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    # Build query
    query = {"user_id": user_id}
    if block_type != 'all':
        query["type"] = block_type
    
    # Fetch blocks from database
    blocks = list(blocks_collection.find(
        query,
        {'_id': 0}
    ).sort("created_at", -1).limit(limit))
    
    return jsonify({
        "blocks": blocks
    })

@app.route('/api/blocks/<block_id>', methods=['GET'])
def get_block(block_id):
    """
    Get a specific block and its messages
    """
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    # Fetch block from database
    block = blocks_collection.find_one(
        {"block_id": block_id, "user_id": user_id},
        {'_id': 0}
    )
    
    if not block:
        return jsonify({'error': 'Block not found'}), 404
    
    # Fetch messages for this block
    messages = list(history_collection.find(
        {"block_id": block_id, "user_id": user_id},
        {'_id': 0, 'user_id': 0, 'block_id': 0}
    ).sort("created_at", 1))  # Sort chronologically (oldest first)
    
    # Sanitize message content to ensure plain text
    for message in messages:
        if 'message' in message:
            message['message'] = sanitize_response(message['message'])
    
    return jsonify({
        "block": block,
        "messages": messages
    })

@app.route('/api/blocks/<block_id>', methods=['DELETE'])
def delete_block(block_id):
    """
    Delete a block and all its messages
    """
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    # Delete block
    blocks_collection.delete_one({"block_id": block_id, "user_id": user_id})
    
    # Delete flow status
    flow_collection.delete_one({"block_id": block_id, "user_id": user_id})
    
    # Delete messages
    history_collection.delete_many({"block_id": block_id, "user_id": user_id})
    
    return jsonify({
        "success": True,
        "message": "Block deleted successfully"
    })

@app.route('/api/blocks/<block_id>/clear', methods=['POST'])
def clear_block(block_id):
    """
    Clear messages for a block
    """
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    # Delete messages
    history_collection.delete_many({"block_id": block_id, "user_id": user_id})
    
    # Reset flow status to match standard flow
    flow_collection.update_one(
        {"block_id": block_id, "user_id": user_id},
        {"$set": {
            "flow_status": {step: False for step in STANDARD_FLOW_STEPS},
            "updated_at": datetime.utcnow()
        }}
    )
    
    # Add system message
    history_collection.insert_one({
        "user_id": user_id,
        "block_id": block_id,
        "role": "system",
        "message": "Chat cleared. What's on your mind?",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    return jsonify({
        "success": True,
        "message": "Block cleared successfully"
    })

@app.route('/api/blocks/new', methods=['POST'])
def create_new_block():
    """
    Create a new block
    """
    data = request.json
    user_id = data.get('user_id')
    block_type = data.get('type', 'general')
    name = data.get('name', f'New {block_type.capitalize()} Block')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    # Create a new block ID
    block_id = str(uuid.uuid4())
    
    # Initialize flow status with standard steps in the correct order
    flow_status = {
        "user_id": user_id,
        "block_id": block_id,
        "block_type": block_type,
        "initial_input": "",
        "flow_status": {step: False for step in STANDARD_FLOW_STEPS},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Store in MongoDB
    flow_collection.insert_one(flow_status)
    
    # Store block in blocks collection
    blocks_collection.insert_one({
        "block_id": block_id,
        "user_id": user_id,
        "type": block_type,
        "name": name,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    # Add welcome message based on block type - making it more conversational
    welcome_messages = {
        "idea": "Welcome! What innovative ideas would you like to explore today?",
        "problem": "Welcome! What problem would you like to tackle today?",
        "possibility": "Welcome! What possibilities would you like to explore today?",
        "moonshot": "Welcome! What ambitious vision would you like to develop today?",
        "needs": "Welcome! What needs would you like to identify today?",
        "opportunity": "Welcome! What opportunities would you like to discover today?",
        "concept": "Welcome! What concept would you like to develop today?",
        "outcome": "Welcome! What outcomes would you like to evaluate today?",
        "general": "Welcome! How can I help with your creative thinking today?"
    }
    
    welcome_msg = welcome_messages.get(block_type, "Welcome! How can I assist you today?")
    
    history_collection.insert_one({
        "user_id": user_id,
        "block_id": block_id,
        "role": "system",
        "message": welcome_msg,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })
    
    return jsonify({
        "block_id": block_id,
        "block_type": block_type,
        "name": name,
        "created_at": datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)