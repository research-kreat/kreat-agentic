'use client';
import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Message from '@/components/ui/Message';
import ChatInput from '@/components/ui/ChatInput';
import TypingIndicator from '@/components/ui/TypingIndicator';
import { useChatStore } from '@/store/chatStore';

export default function BlockChatInterface({ blockType = 'general' }) {
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  
  // Extract all state from the store
  const userId = useChatStore(state => state.userId);
  const currentBlockId = useChatStore(state => state.currentBlockId);
  const messageHistory = useChatStore(state => state.messageHistory);
  const isTyping = useChatStore(state => state.isTyping);
  const blockInfo = useChatStore(state => state.blockInfo);
  const addMessage = useChatStore(state => state.addMessage);
  const addLog = useChatStore(state => state.addLog);
  const setIsTyping = useChatStore(state => state.setIsTyping);
  const clearMessages = useChatStore(state => state.clearMessages);
  const initializeUser = useChatStore(state => state.initializeUser);
  const setBlockInfo = useChatStore(state => state.setBlockInfo);

  // Initialize user if not already set
  useEffect(() => {
    initializeUser();
  }, [initializeUser]);

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messageHistory, isTyping]);

  // Handle sending a message
  const handleSendMessage = async (content) => {
    if (!currentBlockId || !content.trim()) return;

    // Get userId from store
    const currentUserId = useChatStore.getState().userId;
    if (!currentUserId) {
      addLog({
        type: 'error',
        message: 'User ID not initialized'
      });
      return;
    }

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
      // Determine the endpoint based on whether this is a new block or existing one
      const endpoint = blockInfo.blockId 
        ? '/api/analysis_of_block' 
        : '/api/blocks/analyze';
      
      // Prepare request body
      const requestBody = blockInfo.blockId 
        ? {
            message: content,
            user_id: currentUserId,
            block_id: blockInfo.blockId
          }
        : {
            message: content,
            user_id: currentUserId,
            block_type: blockType
          };
            
      // Send message to API
      const response = await fetch(`http://localhost:5000${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const data = await response.json();
      
      // Extract the response content based on API response structure
      let responseContent = '';
      
      if (data.response && typeof data.response === 'object') {
        // For structured block responses
        if (data.response.suggestion) {
          responseContent = data.response.suggestion;
        } else if (data.response.analysis) {
          // Initial block analysis
          responseContent = `${data.response.analysis}\n\n${data.response.suggestion}`;
        } else {
          // Fallback to serializing the response
          responseContent = JSON.stringify(data.response, null, 2);
        }
        
        // If this is a new block with a backend ID, update the block info
        if (data.block_id && !blockInfo.blockId) {
          setBlockInfo({
            blockId: data.block_id,
            type: data.block_type || blockType
          });
          
          addLog({
            type: 'info',
            message: `Identified as ${data.block_type || blockType} block (ID: ${data.block_id.substring(0, 8)}...)`
          });
        }
      } else if (data.response && typeof data.response === 'string') {
        // For simple string responses
        responseContent = data.response;
      } else {
        // Fallback
        responseContent = "I've processed your request, but I'm not sure how to respond. Can you provide more details?";
      }
      
      // Add assistant's response to chat
      addMessage({
        role: 'assistant',
        content: responseContent,
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
    if (!currentBlockId) return;
    
    if (messageHistory.length > 1) {
      if (!confirm('Are you sure you want to clear this chat? This cannot be undone.')) {
        return;
      }
    }

    // Clear messages locally
    clearMessages();
    
    // Send API request to clear on server if we have a backend block ID
    if (blockInfo.blockId) {
      fetch(`http://localhost:5000/api/blocks/${blockInfo.blockId}/clear`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ user_id: userId })
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
    } else {
      addLog({
        type: 'system',
        message: 'Chat cleared locally'
      });
    }
  };

  // Handle exporting the chat
  const handleExportChat = () => {
    if (!currentBlockId || messageHistory.length === 0) {
      alert('No messages to export');
      return;
    }
    
    // Create export object
    const exportData = {
      block_id: currentBlockId,
      backend_block_id: blockInfo.blockId,
      block_type: blockInfo.type || blockType,
      messages: messageHistory,
      exported_at: new Date().toISOString(),
    };
    
    // Convert to JSON string
    const jsonStr = JSON.stringify(exportData, null, 2);
    
    // Create download link
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `kraft-chat-${currentBlockId.substring(0, 8)}-${new Date().toISOString().slice(0, 10)}.json`;
    
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

  // Get block icon based on type
  const getBlockIcon = () => {
    const icons = {
      idea: 'fa-lightbulb',
      problem: 'fa-question-circle',
      possibility: 'fa-route',
      moonshot: 'fa-rocket',
      needs: 'fa-clipboard-list',
      opportunity: 'fa-door-open',
      concept: 'fa-puzzle-piece',
      outcome: 'fa-flag-checkered',
      general: 'fa-comment'
    };
    
    return icons[blockType] || 'fa-comment';
  };
  
  // Get block title based on type
  const getBlockTitle = () => {
    const titles = {
      idea: 'Idea Development',
      problem: 'Problem Definition',
      possibility: 'Possibility Explorer',
      moonshot: 'Moonshot Ideation',
      needs: 'Needs Analysis',
      opportunity: 'Opportunity Assessment',
      concept: 'Concept Development',
      outcome: 'Outcome Evaluation',
      general: 'General Assistant'
    };
    
    return titles[blockType] || 'KRAFT Assistant';
  };

  // Get welcome message based on block type
  const getWelcomeMessage = () => {
    const messages = {
      idea: "Welcome to the Idea Development assistant. I can help you craft innovative concepts and solutions. What would you like to explore today?",
      problem: "Welcome to the Problem Definition assistant. I can help you articulate and analyze challenges. What problem would you like to address?",
      possibility: "Welcome to the Possibility Explorer. I can help you discover potential solutions and approaches. What possibilities would you like to explore?",
      moonshot: "Welcome to Moonshot Ideation. I can help you develop ambitious, transformative ideas. What big challenge would you like to tackle?",
      needs: "Welcome to Needs Analysis. I can help you identify and understand requirements and goals. What needs would you like to analyze?",
      opportunity: "Welcome to Opportunity Assessment. I can help you discover and evaluate potential markets or directions. What opportunity interests you?",
      concept: "Welcome to Concept Development. I can help you structure and refine solutions. What concept would you like to develop?",
      outcome: "Welcome to Outcome Evaluation. I can help you measure and analyze results. What outcomes would you like to evaluate?",
      general: "Welcome to the KRAFT framework. I can help guide you through creative problem-solving and innovation. How can I assist you today?"
    };
    
    return messages[blockType] || "Welcome to the KRAFT framework. How can I assist you today?";
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-center p-4 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <i className={`fas ${getBlockIcon()} text-xl text-primary`}></i>
          <h2 className="text-lg font-medium text-gray-800">{getBlockTitle()}</h2>
          {blockInfo.blockId && (
            <span className="text-xs bg-gray-100 px-2 py-1 rounded-full text-gray-600">
              {blockInfo.blockId.substring(0, 8)}...
            </span>
          )}
        </div>
        
        <div className="flex gap-2">
          <button
            onClick={handleExportChat}
            disabled={!currentBlockId || messageHistory.length === 0}
            className="p-2 rounded-full text-gray-600 hover:bg-gray-100 hover:text-gray-800 transition-colors"
            title="Export Conversation"
          >
            <i className="fas fa-download"></i>
          </button>
          
          <button
            onClick={handleClearChat}
            disabled={!currentBlockId || messageHistory.length === 0}
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
              <p>{getWelcomeMessage()}</p>
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
        
        {/* Typing indicator */}
        {isTyping && <TypingIndicator />}
        
        {/* Invisible element for scrolling */}
        <div ref={messagesEndRef} />
      </div>
      
      <ChatInput 
        onSendMessage={handleSendMessage}
        disabled={!currentBlockId || isTyping}
      />
    </div>
  );
}