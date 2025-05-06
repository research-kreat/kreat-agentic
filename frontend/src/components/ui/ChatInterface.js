'use client';
import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Message from './Message';
import TypingIndicator from './TypingIndicator';
import ChatInput from './ChatInput';
import { useChatStore } from '../../store/chatStore';

export default function ChatInterface() {
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const evtSourceRef = useRef(null);
  
  const { 
    currentSessionId,
    messageHistory,
    isTyping,
    streamingMessage,
    addMessage,
    addLog,
    startStreaming,
    appendToStream,
    endStreaming,
    clearMessages,
  } = useChatStore();

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messageHistory, isTyping, streamingMessage]);

  // Cleanup event source on unmount
  useEffect(() => {
    return () => {
      if (evtSourceRef.current) {
        evtSourceRef.current.close();
      }
    };
  }, []);

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

    // Start streaming indicator
    startStreaming();

    try {
      // Close any existing event source
      if (evtSourceRef.current) {
        evtSourceRef.current.close();
      }

      // Create a new event source for streaming
      const url = `http://localhost:5000/api/chat?message=${encodeURIComponent(content)}&session_id=${currentSessionId}`;
      evtSourceRef.current = new EventSource(url);

      evtSourceRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.chunk === '[DONE]') {
            // Streaming complete
            endStreaming();
            evtSourceRef.current.close();
            evtSourceRef.current = null;
            
            addLog({
              type: 'info',
              message: 'Received complete response from assistant'
            });
          } else {
            // Append chunk to streaming message
            appendToStream(data.chunk);
          }
        } catch (error) {
          console.error('Error parsing chunk:', error);
        }
      };

      evtSourceRef.current.onerror = (error) => {
        console.error('EventSource error:', error);
        endStreaming();
        
        if (evtSourceRef.current) {
          evtSourceRef.current.close();
          evtSourceRef.current = null;
        }
        
        // Add error message
        addMessage({
          role: 'system',
          content: `Error: Connection to server lost. Please try again.`,
          timestamp: new Date().toISOString(),
          error: true
        });
        
        addLog({
          type: 'error',
          message: `Error streaming response: Connection failed`
        });
      };
    } catch (error) {
      console.error('Error sending message:', error);
      endStreaming();
      
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
        
        {/* Streaming message */}
        {streamingMessage && (
          <Message 
            message={{
              role: 'assistant',
              content: streamingMessage,
              timestamp: new Date().toISOString()
            }}
            isLast={true}
          />
        )}
        
        {/* Typing indicator */}
        {isTyping && !streamingMessage && <TypingIndicator />}
        
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