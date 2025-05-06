from flask import Flask, request, jsonify, Response, stream_with_context
from agents.chatbot import ChatBot
from dotenv import load_dotenv
from flask_socketio import SocketIO
import logging
from flask_cors import CORS
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

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session completely"""
    success = chatbot.delete_session(session_id)
    
    if not success:
        return jsonify({'error': 'Failed to delete session'}), 404
        
    return jsonify({
        'success': True,
        'session_id': session_id,
        'message': 'Session deleted successfully'
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

#___________________CHAT API____________________

@app.route('/api/chat', methods=['GET', 'POST'])
def process_chat():
    """Process a chat message and get a streaming response"""
    # Extract message and session_id from either GET or POST request
    if request.method == 'POST':
        data = request.json
        message = data.get('message')
        session_id = data.get('session_id')
    else:  # GET
        message = request.args.get('message')
        session_id = request.args.get('session_id')
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
        
    if not session_id:
        return jsonify({'error': 'Session ID is required'}), 400
        
    # Check if session exists
    session = chatbot.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    # Process message with streaming support
    streaming_response, session_id = chatbot.process_chat(session_id, message)
    
    full_response = ""
    
    def generate():
        nonlocal full_response
        
        for chunk in streaming_response:
            full_response += chunk
            chunk_json = {"chunk": chunk, "session_id": session_id}
            yield f"data: {jsonify(chunk_json).get_data(as_text=True)}\n\n"
            
        # Save the full response to the database
        chatbot.save_streamed_response(session_id, full_response)
        
        # Send the 'done' signal
        yield f"data: {jsonify({'chunk': '[DONE]', 'session_id': session_id}).get_data(as_text=True)}\n\n"
        
        # Emit socket event for typing indicator
        socketio.emit("typing_indicator", {
            "session_id": session_id,
            "is_typing": False
        })
    
    # Return streaming response
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

#___________________MAIN____________________

if __name__ == '__main__':
    logger.info("Starting KRAFT server...")
    
    # Register cleanup handler to close MongoDB connections
    import atexit
    atexit.register(chatbot.close)
    
    # Start the server
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)