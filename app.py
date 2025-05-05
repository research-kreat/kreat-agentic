from flask import Flask, request, jsonify, render_template
from agent.chatbot import ChatBot
from dotenv import load_dotenv
from flask_socketio import SocketIO
import logging
import json
import time
from flask_cors import CORS
from datetime import datetime
import os

# Initialize Flask app and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'kraft-development-key')
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize the chatbot
chatbot = ChatBot(socket_instance=socketio)

#________________SOCKET.IO EVENT HANDLERS_________________

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    socketio.emit('status', {'message': 'Connected to KRAFT server'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

@socketio.on('join_session')
def handle_join_session(data):
    """Handle client joining a specific chat session"""
    session_id = data.get('session_id')
    if not session_id:
        return
        
    logger.info(f'Client joined session: {session_id}')
    socketio.emit('session_update', chatbot.get_session(session_id))

#___________________SESSION MANAGEMENT API____________________

@app.route('/api/sessions/new', methods=['POST'])
def create_new_session():
    """Create a new chat session"""
    data = request.json
    session_type = data.get('type', 'idea')
    name = data.get('name')
    
    session = chatbot.create_session(session_type, name)
    
    return jsonify(session), 200

@app.route('/api/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session details and messages"""
    session = chatbot.get_session(session_id)
    
    if not session:
        return jsonify({'error': 'Session not found'}), 404
        
    messages = chatbot.get_messages(session_id)
    
    return jsonify({
        'session': session,
        'messages': messages
    }), 200

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get list of sessions with optional filtering"""
    session_type = request.args.get('type')
    limit = int(request.args.get('limit', 10))
    skip = int(request.args.get('skip', 0))
    
    sessions = chatbot.get_sessions(session_type, limit, skip)
    
    return jsonify({
        'sessions': sessions,
        'count': len(sessions)
    }), 200

@app.route('/api/sessions/<session_id>/rename', methods=['POST'])
def rename_session(session_id):
    """Rename a session"""
    data = request.json
    name = data.get('name')
    
    if not name:
        return jsonify({'error': 'Name is required'}), 400
        
    success = chatbot.rename_session(session_id, name)
    
    if not success:
        return jsonify({'error': 'Failed to rename session'}), 404
        
    return jsonify({
        'success': True,
        'session_id': session_id,
        'name': name
    }), 200

@app.route('/api/sessions/<session_id>/clear', methods=['POST'])
def clear_session(session_id):
    """Clear all messages from a session"""
    success = chatbot.clear_session(session_id)
    
    if not success:
        return jsonify({'error': 'Failed to clear session'}), 404
        
    return jsonify({
        'success': True,
        'session_id': session_id
    }), 200

@app.route('/api/sessions/<session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    """Get messages for a session with optional pagination"""
    after = request.args.get('after')
    limit = int(request.args.get('limit', 100))
    
    messages = chatbot.get_messages(session_id, after, limit)
    
    return jsonify({
        'session_id': session_id,
        'messages': messages,
        'count': len(messages)
    }), 200

@app.route('/api/sessions/<session_id>/heartbeat', methods=['POST'])
def update_session_heartbeat(session_id):
    """Update the last active timestamp for a session"""
    success = chatbot.update_session_heartbeat(session_id)
    
    if not success:
        return jsonify({'error': 'Session not found'}), 404
        
    return jsonify({
        'success': True,
        'session_id': session_id,
        'timestamp': datetime.utcnow().isoformat()
    }), 200

#___________________CHAT API____________________

@app.route('/api/chat', methods=['POST'])
def process_chat():
    """Process a chat message and get a response"""
    data = request.json
    message = data.get('message')
    session_id = data.get('session_id')
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
        
    if not session_id:
        return jsonify({'error': 'Session ID is required'}), 400
        
    # Check if session exists
    session = chatbot.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    # Process message and get response
    result = chatbot.process_chat(session_id, message)
    
    return jsonify(result), 200

#___________________SPARK BLOCKS API____________________

@app.route('/api/spark/problem', methods=['POST'])
def process_problem():
    """Process a problem statement and generate insights"""
    data = request.json
    problem = data.get('problem')
    session_id = data.get('session_id')
    
    if not problem:
        return jsonify({'error': 'Problem statement is required'}), 400
        
    # Create a new session if not provided
    if not session_id:
        session = chatbot.create_session('problem', 'Problem Analysis')
        session_id = session['session_id']
    
    # Store the problem statement
    chatbot.add_message(session_id, 'user', problem)
    
    # TODO: Implement problem analysis logic
    # For now, use the chatbot to process it
    result = chatbot.process_chat(session_id, f"Analyze this problem: {problem}")
    
    return jsonify({
        'session_id': session_id,
        'problem': problem,
        'analysis': result['response']
    }), 200

@app.route('/api/spark/possibility', methods=['POST'])
def process_possibility():
    """Process a possibility and generate potential solutions"""
    data = request.json
    possibility = data.get('possibility')
    session_id = data.get('session_id')
    
    if not possibility:
        return jsonify({'error': 'Possibility statement is required'}), 400
        
    # Create a new session if not provided
    if not session_id:
        session = chatbot.create_session('possibility', 'Possibility Analysis')
        session_id = session['session_id']
    
    # Store the possibility statement
    chatbot.add_message(session_id, 'user', possibility)
    
    # TODO: Implement possibility analysis logic
    # For now, use the chatbot to process it
    result = chatbot.process_chat(
        session_id, 
        f"Explore this possibility and suggest potential directions: {possibility}"
    )
    
    return jsonify({
        'session_id': session_id,
        'possibility': possibility,
        'exploration': result['response']
    }), 200

@app.route('/api/spark/idea', methods=['POST'])
def process_idea():
    """Process an idea and provide development suggestions"""
    data = request.json
    idea = data.get('idea')
    session_id = data.get('session_id')
    
    if not idea:
        return jsonify({'error': 'Idea statement is required'}), 400
        
    # Create a new session if not provided
    if not session_id:
        session = chatbot.create_session('idea', 'Idea Development')
        session_id = session['session_id']
    
    # Store the idea statement
    chatbot.add_message(session_id, 'user', idea)
    
    # TODO: Implement idea development logic
    # For now, use the chatbot to process it
    result = chatbot.process_chat(
        session_id, 
        f"Help me develop this idea with specific action steps: {idea}"
    )
    
    return jsonify({
        'session_id': session_id,
        'idea': idea,
        'development': result['response']
    }), 200

@app.route('/api/spark/moonshot', methods=['POST'])
def process_moonshot():
    """Process a moonshot (Ideal Final Result) idea"""
    data = request.json
    moonshot = data.get('moonshot')
    session_id = data.get('session_id')
    
    if not moonshot:
        return jsonify({'error': 'Moonshot statement is required'}), 400
        
    # Create a new session if not provided
    if not session_id:
        session = chatbot.create_session('moonshot', 'Moonshot (IFR) Analysis')
        session_id = session['session_id']
    
    # Store the moonshot statement
    chatbot.add_message(session_id, 'user', moonshot)
    
    # TODO: Implement moonshot analysis logic
    # For now, use the chatbot to process it
    result = chatbot.process_chat(
        session_id, 
        f"Analyze this moonshot idea (Ideal Final Result) and suggest steps to move toward it: {moonshot}"
    )
    
    return jsonify({
        'session_id': session_id,
        'moonshot': moonshot,
        'analysis': result['response']
    }), 200

#___________________BUILD BLOCKS API____________________

@app.route('/api/build/needs', methods=['POST'])
def process_needs():
    """Process needs assessment"""
    data = request.json
    needs = data.get('needs')
    session_id = data.get('session_id')
    
    if not needs:
        return jsonify({'error': 'Needs statement is required'}), 400
        
    # Create a new session if not provided
    if not session_id:
        session = chatbot.create_session('needs', 'Needs Assessment')
        session_id = session['session_id']
    
    # Store the needs statement
    chatbot.add_message(session_id, 'user', needs)
    
    # Process with chatbot
    result = chatbot.process_chat(
        session_id, 
        f"Analyze these needs and provide a structured assessment: {needs}"
    )
    
    return jsonify({
        'session_id': session_id,
        'needs': needs,
        'assessment': result['response']
    }), 200

@app.route('/api/build/opportunity', methods=['POST'])
def process_opportunity():
    """Process opportunity assessment"""
    data = request.json
    opportunity = data.get('opportunity')
    session_id = data.get('session_id')
    
    if not opportunity:
        return jsonify({'error': 'Opportunity statement is required'}), 400
        
    # Create a new session if not provided
    if not session_id:
        session = chatbot.create_session('opportunity', 'Opportunity Analysis')
        session_id = session['session_id']
    
    # Store the opportunity statement
    chatbot.add_message(session_id, 'user', opportunity)
    
    # Process with chatbot
    result = chatbot.process_chat(
        session_id, 
        f"Analyze this opportunity and provide market potential insights: {opportunity}"
    )
    
    return jsonify({
        'session_id': session_id,
        'opportunity': opportunity,
        'analysis': result['response']
    }), 200

@app.route('/api/build/concept', methods=['POST'])
def process_concept():
    """Process concept development"""
    data = request.json
    concept = data.get('concept')
    session_id = data.get('session_id')
    
    if not concept:
        return jsonify({'error': 'Concept statement is required'}), 400
        
    # Create a new session if not provided
    if not session_id:
        session = chatbot.create_session('concept', 'Concept Development')
        session_id = session['session_id']
    
    # Store the concept statement
    chatbot.add_message(session_id, 'user', concept)
    
    # Process with chatbot
    result = chatbot.process_chat(
        session_id, 
        f"Develop this concept into a structured solution with clear components: {concept}"
    )
    
    return jsonify({
        'session_id': session_id,
        'concept': concept,
        'development': result['response']
    }), 200

@app.route('/api/build/outcome', methods=['POST'])
def process_outcome():
    """Process outcome analysis"""
    data = request.json
    outcome = data.get('outcome')
    session_id = data.get('session_id')
    
    if not outcome:
        return jsonify({'error': 'Outcome statement is required'}), 400
        
    # Create a new session if not provided
    if not session_id:
        session = chatbot.create_session('outcome', 'Outcome Analysis')
        session_id = session['session_id']
    
    # Store the outcome statement
    chatbot.add_message(session_id, 'user', outcome)
    
    # Process with chatbot
    result = chatbot.process_chat(
        session_id, 
        f"Analyze this outcome and provide measurement frameworks: {outcome}"
    )
    
    return jsonify({
        'session_id': session_id,
        'outcome': outcome,
        'analysis': result['response']
    }), 200

#___________________TEMPLATE ROUTES____________________

@app.route('/')
def home():
    """Render the home page"""
    return render_template('index.html')

@app.route('/idea')
def idea_page():
    """Render the idea development page"""
    return render_template('idea.html')

@app.route('/problem')
def problem_page():
    """Render the problem analysis page"""
    return render_template('problem.html')

@app.route('/possibility')
def possibility_page():
    """Render the possibility exploration page"""
    return render_template('possibility.html')

@app.route('/moonshot')
def moonshot_page():
    """Render the moonshot (IFR) page"""
    return render_template('moonshot.html')

@app.route('/needs')
def needs_page():
    """Render the needs assessment page"""
    return render_template('needs.html')

@app.route('/opportunity')
def opportunity_page():
    """Render the opportunity analysis page"""
    return render_template('opportunity.html')

@app.route('/concept')
def concept_page():
    """Render the concept development page"""
    return render_template('concept.html')

@app.route('/outcome')
def outcome_page():
    """Render the outcome analysis page"""
    return render_template('outcome.html')

@app.route('/history')
def history_page():
    """Render the session history page"""
    return render_template('history.html')

@app.route('/feedback')
def feedback_page():
    """Render the feedback page"""
    return render_template('feedback.html')

# Legacy routes for backward compatibility
@app.route('/chatbot')
def chatbot_page():
    """Redirect to idea page (new name for chatbot)"""
    return render_template('idea.html')

#___________________MAIN____________________

if __name__ == '__main__':
    logger.info("Starting KRAFT server...")
    
    # Register cleanup handler to close MongoDB connections
    import atexit
    atexit.register(chatbot.close)
    
    # Start the server
    socketio.run(app, debug=True, host='0.0.0.0', allow_unsafe_werkzeug=True)