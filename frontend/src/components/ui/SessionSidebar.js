'use client';
import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useChatStore } from '@/store/chatStore';

export default function SessionSidebar({ onSessionSelect }) {
  const { 
    sessions, 
    currentSessionId, 
    setSessions,
    removeSession,
    addLog 
  } = useChatStore();
  
  // Load sessions from API on component mount
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const response = await fetch('http://localhost:5000/api/sessions?type=idea&limit=10');
        if (response.ok) {
          const data = await response.json();
          setSessions(data.sessions || []);
          addLog({
            type: 'info',
            message: 'Loaded previous sessions'
          });
        } else {
          throw new Error('Failed to load sessions');
        }
      } catch (error) {
        addLog({
          type: 'error',
          message: `Error loading sessions: ${error.message}`
        });
      }
    };
    
    fetchSessions();
  }, [setSessions, addLog]);
  
  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation(); // Prevent session selection
    
    if (!confirm('Are you sure you want to delete this session? This action cannot be undone.')) {
      return;
    }
    
    try {
      const response = await fetch(`http://localhost:5000/api/sessions/${sessionId}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        removeSession(sessionId);
        addLog({
          type: 'info',
          message: `Deleted session: ${sessionId.substring(0, 8)}`
        });
      } else {
        throw new Error('Failed to delete session');
      }
    } catch (error) {
      addLog({
        type: 'error',
        message: `Error deleting session: ${error.message}`
      });
    }
  };
  
  return (
    <div className="h-full bg-white border-r border-gray-200 flex flex-col">
      <div className="p-6 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-800 mb-2">Idea Development</h3>
        <p className="text-sm text-gray-600">Craft innovative concepts</p>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4">
        <h4 className="text-xs uppercase text-gray-600 mb-4 pb-2 border-b border-gray-200">
          Recent Sessions
        </h4>
        
        {sessions.length === 0 ? (
          <p className="text-gray-600 italic text-center py-4">No previous sessions found</p>
        ) : (
          <AnimatePresence>
            <ul>
              {sessions.map(session => {
                const formattedDate = new Date(session.created_at).toLocaleString();
                
                return (
                  <motion.li
                    key={session.session_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{ duration: 0.3 }}
                    className={`py-3 px-4 mb-2 rounded-lg cursor-pointer transition-all duration-300 ${
                      currentSessionId === session.session_id 
                        ? 'bg-blue-50 border-l-4 border-primary' 
                        : 'bg-gray-100 hover:bg-gray-200'
                    }`}
                    onClick={() => onSessionSelect(session.session_id)}
                  >
                    <div className="session-content">
                      <div className="text-gray-800 font-medium mb-1 truncate">
                        {session.name || `Session ${session.session_id.substring(0, 8)}`}
                      </div>
                      <div className="flex justify-between items-center">
                        <div className="text-xs text-gray-600">{formattedDate}</div>
                        <button
                          className="text-red-500 hover:text-red-700 transition-colors duration-300"
                          title="Delete Session"
                          onClick={(e) => handleDeleteSession(e, session.session_id)}
                        >
                          <i className="fas fa-trash-alt"></i>
                        </button>
                      </div>
                    </div>
                  </motion.li>
                );
              })}
            </ul>
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}