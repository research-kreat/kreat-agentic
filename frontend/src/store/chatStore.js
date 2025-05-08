'use client';
import { create } from 'zustand';
import { v4 as uuidv4 } from 'uuid';
import { persist } from 'zustand/middleware';

export const useChatStore = create(
  persist(
    (set, get) => ({
      // User state
      userId: null,
      
      // Block state
      currentBlockId: null,
      blocks: [],
      messageHistory: [],
      isTyping: false,
      
      // Block info
      blockInfo: {
        created: null,
        messageCount: 0,
        type: 'general', // Default type is 'general'
        blockId: null,   // This will hold the backend blockId when created
      },
      
      // Console logs
      logs: [
        {
          type: 'system',
          message: 'Ready to assist with KRAFT framework',
          timestamp: new Date().toLocaleTimeString()
        }
      ],
      
      // Initialize user ID if not already set
      initializeUser: () => {
        const { userId } = get();
        if (!userId) {
          set({ userId: uuidv4() });
        }
        return get().userId;
      },
      
      // Actions
      setCurrentBlockId: (blockId) => set({ currentBlockId: blockId }),
      
      addMessage: (message) => {
        const { messageHistory } = get();
        // Create a new array instead of modifying the existing one
        const newHistory = [...messageHistory, message];
        
        set({ 
          messageHistory: newHistory,
          blockInfo: {
            ...get().blockInfo,
            messageCount: newHistory.length
          }
        });
      },
      
      setBlocks: (blocks) => set({ blocks }),
      
      addBlock: (block) => {
        const { blocks } = get();
        const existingIndex = blocks.findIndex(b => b.block_id === block.block_id);
        
        if (existingIndex >= 0) {
          // Update existing block
          const updatedBlocks = [...blocks];
          updatedBlocks[existingIndex] = block;
          set({ blocks: updatedBlocks });
        } else {
          // Add new block
          set({ blocks: [block, ...blocks] });
        }
      },
      
      removeBlock: (blockId) => {
        const { blocks, currentBlockId } = get();
        set({ 
          blocks: blocks.filter(b => b.block_id !== blockId),
          currentBlockId: blockId === currentBlockId ? null : currentBlockId,
          messageHistory: blockId === currentBlockId ? [] : get().messageHistory
        });
      },
      
      setMessageHistory: (messages) => {
        // Ensure each message has a timestamp
        const messagesWithTimestamps = messages.map(msg => ({
          ...msg,
          timestamp: msg.timestamp || new Date().toISOString()
        }));
        
        set({ 
          messageHistory: messagesWithTimestamps,
          blockInfo: {
            ...get().blockInfo,
            messageCount: messagesWithTimestamps.length
          } 
        });
      },
      
      clearMessages: () => set({ 
        messageHistory: [
          {
            role: 'system',
            content: 'Chat has been cleared. How can I help you today?',
            timestamp: new Date().toISOString()
          }
        ],
        blockInfo: {
          ...get().blockInfo,
          messageCount: 1
        }
      }),
      
      setBlockInfo: (info) => set({ 
        blockInfo: {
          ...get().blockInfo,
          ...info
        }
      }),
      
      setIsTyping: (status) => set({ isTyping: status }),
      
      addLog: (log) => {
        const { logs } = get();
        const newLog = {
          ...log,
          timestamp: new Date().toLocaleTimeString()
        };
        
        set({ logs: [...logs, newLog] });
      },
      
      resetStore: () => set({
        currentBlockId: null,
        messageHistory: [],
        isTyping: false,
        blockInfo: {
          created: null,
          messageCount: 0,
          type: 'general',
          blockId: null,
        },
        logs: [
          {
            type: 'system',
            message: 'Ready to assist with KRAFT framework',
            timestamp: new Date().toLocaleTimeString()
          }
        ]
      }),
      
      // Create a new block
      createNewBlock: (type = 'general', name = 'New Chat') => {
        const blockId = uuidv4();
        const newBlock = {
          block_id: blockId,
          type: type,
          name: name,
          created_at: new Date().toISOString()
        };
        
        const { addBlock, setCurrentBlockId, setBlockInfo, resetStore } = get();
        
        // Reset store to clear previous chat
        resetStore();
        
        // Add the new block to the list
        addBlock(newBlock);
        
        // Set as current block
        setCurrentBlockId(blockId);
        
        // Update block info
        setBlockInfo({
          created: newBlock.created_at,
          type: type,
          blockId: blockId,
          messageCount: 0
        });
        
        return blockId;
      }
    }),
    {
      name: 'kraft-chat-storage',
      partialize: (state) => ({
        userId: state.userId,
        blocks: state.blocks,
        // Don't persist these volatile states
        // messageHistory, isTyping, blockInfo, logs
      }),
    }
  )
);

export default useChatStore;