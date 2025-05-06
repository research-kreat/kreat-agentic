'use client';
import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Message from './Message';
import ChatInput from './ChatInput';
import { useChatStore } from '../../store/chatStore';

export default function ChatInterface() {
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  
  // Extract all state from the store at the top level to maintain hook consistency
  const currentSessionId = useChatStore(state => state.currentSessionId);
  const messageHistory = useChatStore(state => state.messageHistory);
  const isTyping = useChatStore(state => state.isTyping);
  const addMessage = useChatStore(state => state.addMessage);
  const addLog = useChatStore(state => state.addLog);
  const setIsTyping = useChatStore(state => state.setIsTyping);
  const clearMessages = useChatStore(state => state.clearMessages);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messageHistory, isTyping]);

  // Handle sending a message
  const handleSendMessage = async (content) => {
    if (!currentSessionId || !content.trim()) return;

    // Add user message to chat
    const userMessage = {
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    };
    addMessage(userMessage);

    // Set typing indicator
    setIsTyping(true);

    try {
      // Send message to API
      const response = await fetch(`http://localhost:5000/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: content,
          session_id: currentSessionId
        })
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const data = await response.json();
      
      // Add assistant's response to chat
      addMessage({
        role: 'assistant',
        content: data.response,
        timestamp: new Date().toISOString()
      });
      
      addLog({
        type: 'info',
        message: 'Received response from assistant'
      });
      
    } catch (error) {
      console.error('Error sending message:', error);
      
      // Add error message
      addMessage({
        role: 'system',
        content: `Error: ${error.message}. Please try again.`,
        timestamp: new Date().toISOString(),
        error: true
      });
      
      addLog({
        type: 'error',
        message: `Error sending message: ${error.message}`
      });
    } finally {
      setIsTyping(false);
    }
  };

  // Handle clearing the chat
  const handleClearChat = () => {
    if (!currentSessionId) return;
    
    if (messageHistory.length > 1) {
      if (!confirm('Are you sure you want to clear this chat? This cannot be undone.')) {
        return;
      }
    }

    // Clear messages locally
    clearMessages();
    
    // Send API request to clear on server
    fetch(`http://localhost:5000/api/sessions/${currentSessionId}/clear`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    .then(response => {
      if (!response.ok) {
        throw new Error('Failed to clear chat on server');
      }
      addLog({
        type: 'system',
        message: 'Chat cleared'
      });
    })
    .catch(error => {
      addLog({
        type: 'error',
        message: `Error clearing chat on server: ${error.message}`
      });
    });
  };

  // Handle exporting the chat
  const handleExportChat = () => {
    if (!currentSessionId || messageHistory.length === 0) {
      alert('No messages to export');
      return;
    }
    
    // Create export object
    const exportData = {
      session_id: currentSessionId,
      messages: messageHistory,
      exported_at: new Date().toISOString(),
      type: 'idea_development'
    };
    
    // Convert to JSON string
    const jsonStr = JSON.stringify(exportData, null, 2);
    
    // Create download link
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `kraft-chat-${currentSessionId.substring(0, 8)}-${new Date().toISOString().slice(0, 10)}.json`;
    
    // Trigger download
    document.body.appendChild(a);
    a.click();
    
    // Clean up
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 100);
    
    addLog({
      type: 'info',
      message: 'Chat exported to JSON'
    });
  };

  // Simple loading indicator component
  const LoadingIndicator = () => (
    <div className="flex gap-4 self-start">
      <div className="w-9 h-9 rounded-full bg-secondary text-white flex items-center justify-center">
        <i className="fas fa-robot"></i>
      </div>
      
      <div className="p-4 rounded-2xl rounded-bl-none bg-white shadow-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-gray-500">Processing...</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-center p-4 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <i className="fas fa-lightbulb text-xl text-primary"></i>
          <h2 className="text-lg font-medium text-gray-800">Idea Assistant</h2>
        </div>
        
        <div className="flex gap-2">
          <button
            onClick={handleExportChat}
            disabled={!currentSessionId || messageHistory.length === 0}
            className="p-2 rounded-full text-gray-600 hover:bg-gray-100 hover:text-gray-800 transition-colors"
            title="Export Conversation"
          >
            <i className="fas fa-download"></i>
          </button>
          
          <button
            onClick={handleClearChat}
            disabled={!currentSessionId || messageHistory.length === 0}
            className="p-2 rounded-full text-gray-600 hover:bg-gray-100 hover:text-gray-800 transition-colors"
            title="Clear Chat"
          >
            <i className="fas fa-refresh"></i>
          </button>
        </div>
      </div>
      
      <div 
        ref={chatContainerRef}
        className="flex-1 p-6 overflow-y-auto flex flex-col gap-4 bg-gray-50"
      >
        {/* Welcome message when no messages yet */}
        {messageHistory.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="message system"
          >
            <div className="p-4 rounded-md bg-gray-200 text-gray-800 text-center max-w-[80%] self-center">
              <p>Welcome to the Idea Development assistant. I can help you craft innovative concepts and solutions. What would you like to explore today?</p>
            </div>
          </motion.div>
        )}
        
        {/* Message history */}
        <AnimatePresence>
          {messageHistory.map((message, index) => (
            <Message 
              key={`${message.role}-${index}`}
              message={message}
              isLast={index === messageHistory.length - 1}
            />
          ))}
        </AnimatePresence>
        
        {/* Loading indicator */}
        {isTyping && <LoadingIndicator />}
        
        {/* Invisible element for scrolling */}
        <div ref={messagesEndRef} />
      </div>
      
      <ChatInput 
        onSendMessage={handleSendMessage}
        disabled={!currentSessionId || isTyping}
      />
    </div>
  );
}