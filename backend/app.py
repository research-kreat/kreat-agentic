from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import uuid
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import logging
import json
from helpers.general import sanitize_response

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
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

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
    block_type, confidence, is_greeting = classify_user_input(user_input)
    
    # Create a new block ID
    block_id = str(uuid.uuid4())
    
    # Initialize flow status
    flow_status = {
        "user_id": user_id,
        "block_id": block_id,
        "block_type": block_type,
        "initial_input": user_input,
        "flow_status": {
            "title": False,
            "abstract": False,
            "stakeholders": False,
            "tags": False,
            "assumptions": False,
            "constraints": False,
            "risks": False,
            "aspects_implications": False,
            "impact": False,
            "connections": False,
            "classifications": False,
            "think_models": False
        },
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
            # For non-greeting messages, use the suggestion directly
            suggestion = response.get("suggestion", "")
            
            # Store assistant response in history
            history_collection.insert_one({
                "user_id": user_id,
                "block_id": block_id,
                "role": "assistant",
                "message": suggestion,
                "result": response,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            
            return jsonify({
                "block_id": block_id,
                "block_type": block_type,
                "confidence": confidence,
                "response": response
            })
    else:
        return jsonify({'error': f'Unsupported block type: {block_type}'}), 400

@app.route('/api/analysis_of_block', methods=['POST'])
def analyze_existing_block():
    """
    Endpoint for continuing conversation with an existing block
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
    
    # Limit history to only the last 10 messages before adding this one
    history_items = list(history_collection.find(
        {"block_id": block_id, "user_id": user_id}
    ).sort("created_at", -1).limit(10))
    
    # Delete oldest messages if there are more than 10
    if len(history_items) >= 10:
        keep_ids = [item["_id"] for item in history_items]
        history_collection.delete_many({
            "block_id": block_id, 
            "user_id": user_id,
            "_id": {"$nin": keep_ids}
        })
    
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
        
        # Process the message
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
                
                # Remove this from response as it's internal
                internal_updated_flow = response.pop("updated_flow_status", None)
            
            # Get the suggestion for the message content
            suggestion = response.get("suggestion", "")
            
            # If suggestion is a JSON string, convert it to proper JSON
            if isinstance(suggestion, str) and (suggestion.startswith('{') or suggestion.startswith('[')):
                try:
                    json_obj = json.loads(suggestion)
                    response["suggestion"] = json.dumps(json_obj, indent=2)
                except:
                    # If not valid JSON, leave as is
                    pass
            
            # Store assistant response in history
            history_collection.insert_one({
                "user_id": user_id,
                "block_id": block_id,
                "role": "assistant",
                "message": suggestion,
                "result": response,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            
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
    
    # Fetch messages for this block (limit to 10 most recent)
    messages = list(history_collection.find(
        {"block_id": block_id, "user_id": user_id},
        {'_id': 0, 'user_id': 0, 'block_id': 0, 'result': 0}
    ).sort("created_at", -1).limit(10))
    
    # Sort chronologically (oldest first)
    messages.reverse()
    
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
    
    # Reset flow status
    flow_collection.update_one(
        {"block_id": block_id, "user_id": user_id},
        {"$set": {
            "flow_status": {
                "title": False,
                "abstract": False,
                "stakeholders": False,
                "tags": False,
                "assumptions": False,
                "constraints": False,
                "risks": False,
                "aspects_implications": False,
                "impact": False,
                "connections": False,
                "classifications": False,
                "think_models": False
            },
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
    
    # Initialize flow status
    flow_status = {
        "user_id": user_id,
        "block_id": block_id,
        "block_type": block_type,
        "initial_input": "",
        "flow_status": {
            "title": False,
            "abstract": False,
            "stakeholders": False,
            "tags": False,
            "assumptions": False,
            "constraints": False,
            "risks": False,
            "aspects_implications": False,
            "impact": False,
            "connections": False,
            "classifications": False,
            "think_models": False
        },
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
        "idea": "Hi there! Let's explore some innovative ideas together. What's on your mind?",
        "problem": "Hi! I'm here to help you think through challenges. What problem are you working on?",
        "possibility": "Hey there! Let's explore what might be possible. What are you curious about?",
        "moonshot": "Hi! I'm here for the big, bold ideas. What ambitious thought are you exploring?",
        "needs": "Hello! Let's talk about key needs and requirements. What are you focusing on?",
        "opportunity": "Hi there! Let's explore promising opportunities together. What's caught your attention?",
        "concept": "Hello! I'm here to help develop concepts and solutions. What are you working on?",
        "outcome": "Hi! Let's talk about outcomes and results. What are you hoping to achieve?",
        "general": "Hello! I'm here to help with creative thinking. What's on your mind today?"
    }
    
    welcome_msg = welcome_messages.get(block_type, "Hi there! What's on your mind today?")
    
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