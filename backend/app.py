from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import uuid
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import logging

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

# Block handler mapping
block_handlers = {
    "idea": IdeaBlockHandler,
    "problem": ProblemBlockHandler,
    "possibility": PossibilityBlockHandler,
    "concept": ConceptBlockHandler,
    "needs": NeedsBlockHandler,
    "opportunity": OpportunityBlockHandler,
    "outcome": OutcomeBlockHandler,
    "moonshot": MoonshotBlockHandler
}

@app.route('/api/analysis_of_block', methods=['POST'])
def analyze_block():
    """
    Main endpoint for block analysis and conversation flow
    """
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    # Get user input and block_id if available
    user_input = data.get('message', '')
    block_id = data.get('block_id')
    
    # If no block_id, this is a new conversation, so classify and create
    if not block_id:
        # Classify the user input
        block_type, confidence = classify_user_input(user_input)
        
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
        
        # Initialize appropriate handler
        if block_type in block_handlers:
            handler_class = block_handlers[block_type]
            handler = handler_class(db, block_id, user_id)
            
            # Get initial response
            response = handler.initialize_block(user_input)
            
            # Store assistant response in history
            history_collection.insert_one({
                "user_id": user_id,
                "block_id": block_id,
                "role": "assistant",
                "message": response["suggestion"],
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
    
    # If block_id exists, continue conversation
    else:
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
            
            # Process the message
            response = handler.process_message(user_input, flow_data["flow_status"])
            
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
                del response["updated_flow_status"]
            
            # Store assistant response in history
            history_collection.insert_one({
                "user_id": user_id,
                "block_id": block_id,
                "role": "assistant",
                "message": response.get("suggestion", ""),
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)