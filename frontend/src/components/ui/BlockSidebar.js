'use client';
import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useChatStore } from '@/store/chatStore';
import { api } from '@/lib/api';

export default function BlockSidebar({ onBlockSelect, blockType = 'general' }) {
  const { 
    blocks, 
    currentBlockId, 
    setBlocks,
    removeBlock,
    addLog,
    userId
  } = useChatStore();
  
  // Load blocks from API on component mount
  useEffect(() => {
    if (!userId) return;
    
    const fetchBlocks = async () => {
      try {
        const data = await api.getBlocks({ userId, blockType, limit: 10 });
        setBlocks(data.blocks || []);
        addLog({
          type: 'info',
          message: 'Loaded previous blocks'
        });
      } catch (error) {
        addLog({
          type: 'error',
          message: `Error loading blocks: ${error.message}`
        });
      }
    };
    
    fetchBlocks();
  }, [userId, blockType, setBlocks, addLog]);
  
  const handleDeleteBlock = async (e, blockId) => {
    e.stopPropagation(); // Prevent block selection
    
    if (!confirm('Are you sure you want to delete this block? This action cannot be undone.')) {
      return;
    }
    
    try {
      await api.deleteBlock({ blockId, userId });
      removeBlock(blockId);
      addLog({
        type: 'info',
        message: `Deleted block: ${blockId.substring(0, 8)}`
      });
    } catch (error) {
      addLog({
        type: 'error',
        message: `Error deleting block: ${error.message}`
      });
    }
  };

  // Get block title based on type
  const getBlockTitle = (type) => {
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
    
    return titles[type] || 'KRAFT Assistant';
  };
  
  return (
    <div className="h-full bg-white border-r border-gray-200 flex flex-col">
      <div className="p-6 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-800 mb-2">{getBlockTitle(blockType)}</h3>
        <p className="text-sm text-gray-600">
          {blockType === 'idea' && 'Craft innovative concepts'}
          {blockType === 'problem' && 'Define and explore challenges'}
          {blockType === 'general' && 'AI-powered creative assistance'}
          {!['idea', 'problem', 'general'].includes(blockType) && 'Creative problem-solving'}
        </p>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4">
        <h4 className="text-xs uppercase text-gray-600 mb-4 pb-2 border-b border-gray-200">
          Recent Blocks
        </h4>
        
        {blocks.length === 0 ? (
          <p className="text-gray-600 italic text-center py-4">No previous blocks found</p>
        ) : (
          <AnimatePresence>
            <ul>
              {blocks.map(block => {
                const formattedDate = new Date(block.created_at).toLocaleString();
                const displayName = block.name || `${blockType.charAt(0).toUpperCase() + blockType.slice(1)} ${block.block_id.substring(0, 8)}`;
                
                return (
                  <motion.li
                    key={block.block_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{ duration: 0.3 }}
                    className={`py-3 px-4 mb-2 rounded-lg cursor-pointer transition-all duration-300 ${
                      currentBlockId === block.block_id 
                        ? 'bg-blue-50 border-l-4 border-primary' 
                        : 'bg-gray-100 hover:bg-gray-200'
                    }`}
                    onClick={() => onBlockSelect(block.block_id)}
                  >
                    <div className="block-content">
                      <div className="text-gray-800 font-medium mb-1 truncate">
                        {displayName}
                      </div>
                      <div className="flex justify-between items-center">
                        <div className="text-xs text-gray-600">{formattedDate}</div>
                        <button
                          className="text-red-500 hover:text-red-700 transition-colors duration-300"
                          title="Delete Block"
                          onClick={(e) => handleDeleteBlock(e, block.block_id)}
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