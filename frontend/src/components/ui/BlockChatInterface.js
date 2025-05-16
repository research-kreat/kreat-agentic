'use client';
import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import Message from '@/components/ui/Message';
import ChatInput from '@/components/ui/ChatInput';
import TypingIndicator from '@/components/ui/TypingIndicator';
import { useChatStore } from '@/store/chatStore';
import { api } from '@/lib/api';
import { getWelcomeMessage } from '@/lib/blockUtils';

export default function BlockChatInterface({ blockType = 'general' }) {
  const router = useRouter();
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
  const setMessageHistory = useChatStore(state => state.setMessageHistory);

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

  useEffect(() => {
    if (currentBlockId && userId) {
      // Set loading state
      setIsTyping(true);
      
      // Fetch messages for the current block
      const fetchMessages = async () => {
        try {
          const data = await api.getBlock({ blockId: currentBlockId, userId });
          
          // Check if we received valid messages
          if (data.messages && Array.isArray(data.messages)) {
            // If there are no messages, add a welcome message
            if (data.messages.length === 0) {
              setMessageHistory([
                {
                  role: 'system',
                  content: getWelcomeMessage(blockType),
                  timestamp: new Date().toISOString()
                }
              ]);
            } else {
              // Format messages to match expected structure
              const formattedMessages = data.messages.map(msg => ({
                role: msg.role,
                content: msg.message,
                timestamp: msg.created_at || new Date().toISOString(),
                // Include fullResponse if it exists in the result
                fullResponse: msg.result || null
              }));
              
              setMessageHistory(formattedMessages);
            }
            
            // Update block info
            setBlockInfo({
              ...blockInfo,
              messageCount: data.messages.length,
              type: data.block.type || blockType,
              blockId: data.block.block_id,
              created: data.block.created_at
            });
            
            addLog({
              type: 'info',
              message: 'Loaded conversation history'
            });
          }
        } catch (error) {
          console.error('Error loading messages:', error);
          addLog({
            type: 'error',
            message: `Error loading messages: ${error.message}`
          });
          
          // Add a welcome message as fallback
          setMessageHistory([
            {
              role: 'system',
              content: getWelcomeMessage(blockType),
              timestamp: new Date().toISOString()
            }
          ]);
        } finally {
          setIsTyping(false);
        }
      };
      
      fetchMessages();
    }
  }, [currentBlockId, userId, blockType]);

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
      // Use the centralized API
      const data = await api.analyzeBlock({
        message: content,
        userId: currentUserId,
        blockId: blockInfo.blockId
      });
      
      // Extract the response content based on API response structure
      let responseContent = '';
      let fullResponseData = {};
      
      if (data.response && typeof data.response === 'object') {
        // Store the full response data
        fullResponseData = data.response;
        
        // For structured block responses
        if (data.response.suggestion) {
          responseContent = data.response.suggestion;
          
          // Check if there's a classification message to display first
          if (data.response.classification_message) {
            // Add classification message as a separate system message
            addMessage({
              role: 'system',
              content: data.response.classification_message,
              timestamp: new Date().toISOString()
            });
          }
        } else if (data.response.analysis) {
          // Initial block analysis
          responseContent = `${data.response.analysis}\n\n${data.response.suggestion}`;
        } else {
          // Fallback to serializing the response
          responseContent = JSON.stringify(data.response, null, 2);
        }
        
        // Format step data for better readability
        Object.keys(data.response).forEach(key => {
          if (key !== 'suggestion' && key !== 'updated_flow_status' && key !== 'classification_message') {
            const stepData = data.response[key];
            if (Array.isArray(stepData)) {
              // Format arrays for better display
              fullResponseData[key] = stepData;
            }
          }
        });
        
        // If this is a new block with a backend ID, update the block info
        if (data.block_id && (!blockInfo.blockId || blockInfo.blockId !== data.block_id)) {
          setBlockInfo({
            blockId: data.block_id,
            type: data.block_type || blockType
          });
          
          // Update the URL to use the dynamic route
          router.replace(`/blocks/${data.block_id}`);
          
          addLog({
            type: 'info',
            message: `Identified as ${data.block_type || blockType} block (ID: ${data.block_id.substring(0, 8)}...)`
          });
        }
      } else if (data.response && typeof data.response === 'string') {
        // For simple string responses
        responseContent = data.response;
        fullResponseData = { suggestion: data.response };
      } else {
        // Fallback
        responseContent = "I've processed your request, but I'm not sure how to respond. Can you provide more details?";
        fullResponseData = { suggestion: responseContent };
      }
      
      // Add assistant's response to chat with full data
      addMessage({
        role: 'assistant',
        content: responseContent,
        timestamp: new Date().toISOString(),
        fullResponse: fullResponseData // Store the full response data
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
  const handleClearChat = async () => {
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
      try {
        await api.clearBlock({ blockId: blockInfo.blockId, userId });
        addLog({
          type: 'system',
          message: 'Chat cleared'
        });
      } catch (error) {
        addLog({
          type: 'error',
          message: `Error clearing chat on server: ${error.message}`
        });
      }
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
              <p>{getWelcomeMessage(blockType)}</p>
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