'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Header from '@/components/ui/Header';
import BlockSidebar from '@/components/ui/BlockSidebar';
import BlockChatInterface from '@/components/ui/BlockChatInterface';
import InfoPanel from '@/components/ui/InfoPanel';
import { useChatStore } from '@/store/chatStore';
import { api } from '@/lib/api';
import { getWelcomeMessage, getBlockTypeInfo } from '@/lib/blockUtils';

export default function BlockPage({ blockType = 'general', blockId = null }) {
  const router = useRouter();
  const [isClient, setIsClient] = useState(false);
  
  const { 
    currentBlockId,
    setCurrentBlockId,
    setMessageHistory,
    setIsTyping,
    setBlockInfo,
    addLog,
    resetStore,
    createNewBlock,
    userId,
    initializeUser
  } = useChatStore();
  
  // Prevent hydration issues
  useEffect(() => {
    setIsClient(true);
    // Initialize user if needed
    initializeUser();
  }, [initializeUser]);

  // Initialize block based on blockId prop or create new block
  useEffect(() => {
    if (!userId) return;
    
    if (blockId) {
      // Load existing block
      loadBlock(blockId);
    } else {
      // Create new block
      createNewBlockHandler();
    }
    
    // Cleanup on unmount
    return () => {
      resetStore();
    };
  }, [blockId, userId, blockType]);
  
  // Get block info using utility function
  const blockInfo = getBlockTypeInfo(blockType);
  
  // Load a block
  const loadBlock = async (blockId) => {
    try {
      setIsTyping(true);
      
      const data = await api.getBlock({ blockId, userId });
      
      // Update block info
      setCurrentBlockId(blockId);
      setBlockInfo({
        created: data.block.created_at,
        messageCount: data.messages.length,
        type: data.block.type || blockType,
        blockId: data.block.block_id
      });
      
      // Load messages with proper formatting for display
      const formattedMessages = data.messages.map(msg => ({
        role: msg.role,
        content: msg.message,
        timestamp: msg.created_at || new Date().toISOString(),
        // Include fullResponse if it exists in the result field
        fullResponse: msg.result || null
      }));
      
      setMessageHistory(formattedMessages);
      
      // If no messages exist, add a welcome message
      if (formattedMessages.length === 0) {
        setMessageHistory([
          {
            role: 'system',
            content: getWelcomeMessage(data.block.type || blockType),
            timestamp: new Date().toISOString()
          }
        ]);
      }
      
      addLog({
        type: 'system',
        message: `Loaded block: ${blockId.substring(0, 8)}...`
      });
    } catch (error) {
      console.error('Error loading block:', error);
      addLog({
        type: 'error',
        message: `Error loading block: ${error.message}`
      });
      
      // Create new block if loading fails
      createNewBlockHandler();
    } finally {
      setIsTyping(false);
    }
  };
  
  // Create a new block
  const createNewBlockHandler = async () => {
    try {
      // Create new block on the server
      const data = await api.createBlock({ 
        userId, 
        blockType, 
        name: `New ${blockInfo.title}`
      });
      
      // Set as current block
      setCurrentBlockId(data.block_id);
      
      // Update block info
      setBlockInfo({
        created: data.created_at,
        type: blockType,
        blockId: data.block_id,
        messageCount: 1 // Starting with welcome message
      });
      
      // Update URL to use the dynamic route
      router.replace(`/blocks/${data.block_id}`);
      
      // Add welcome message
      setMessageHistory([
        {
          role: 'system',
          content: getWelcomeMessage(blockType),
          timestamp: new Date().toISOString()
        }
      ]);
      
      addLog({
        type: 'system',
        message: `Created new ${blockType} block: ${data.block_id.substring(0, 8)}...`
      });
    } catch (error) {
      console.error('Error creating block:', error);
      
      // Fallback to local creation if server fails
      const blockId = createNewBlock(blockType, `New ${blockInfo.title}`);
      
      // Update URL to use the dynamic route
      router.replace(`/blocks/${blockId}`);
      
      // Add welcome message
      setMessageHistory([
        {
          role: 'system',
          content: getWelcomeMessage(blockType),
          timestamp: new Date().toISOString()
        }
      ]);
      
      addLog({
        type: 'error',
        message: `Error creating block on server, using local fallback: ${error.message}`
      });
    }
  };
  
  // Handle block selection
  const handleBlockSelect = (blockId) => {
    if (blockId === currentBlockId) return;
    
    // Navigate to the selected block
    router.push(`/blocks/${blockId}`);
  };
  
  if (!isClient) {
    return null; // Prevent hydration errors
  }

  // Determine header properties based on block type
  const headerProps = {
    blockId: currentBlockId,
    handleNewChat: createNewBlockHandler,
    blockType: blockType
  };

  return (
    <main className="min-h-screen bg-gray-100 flex flex-col">
      <Header {...headerProps} />
      
      <div className="flex-1 grid grid-cols-[250px_1fr_300px] h-[calc(100vh-72px)]">
        <BlockSidebar onBlockSelect={handleBlockSelect} blockType={blockType} />
        <BlockChatInterface blockType={blockType} />
        <InfoPanel />
      </div>
    </main>
  );
}