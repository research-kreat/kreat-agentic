'use client';
import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Header from '@/components/ui/Header';
import BlockSidebar from '@/components/ui/BlockSidebar';
import BlockChatInterface from '@/components/ui/BlockChatInterface';
import InfoPanel from '@/components/ui/InfoPanel';
import { useChatStore } from '@/store/chatStore';

export default function ProblemPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
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

  // Initialize block based on URL query params or create new block
  useEffect(() => {
    if (!userId) return;
    
    const blockId = searchParams.get('block');
    
    if (blockId) {
      // Load existing block
      loadBlock(blockId);
    } else {
      // Create new block
      createNewProblemBlock();
    }
    
    // Cleanup on unmount
    return () => {
      resetStore();
    };
  }, [searchParams, userId]);
  
  // Load a block
  const loadBlock = async (blockId) => {
    try {
      setIsTyping(true);
      
      const response = await fetch(`http://localhost:5000/api/blocks/${blockId}?user_id=${userId}`);
      
      if (!response.ok) {
        throw new Error('Block not found');
      }
      
      const data = await response.json();
      
      // Update block info
      setCurrentBlockId(blockId);
      setBlockInfo({
        created: data.block.created_at,
        messageCount: data.messages.length,
        type: data.block.type,
        blockId: data.block.block_id
      });
      
      // Load messages
      setMessageHistory(data.messages || []);
      
      // Update URL without reloading page
      updateURL(blockId);
      
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
      createNewProblemBlock();
    } finally {
      setIsTyping(false);
    }
  };
  
  // Create a new problem block
  const createNewProblemBlock = () => {
    // Use the createNewBlock function from the store
    const blockId = createNewBlock('problem', 'New Problem Definition');
    
    // Update URL without reloading page
    updateURL(blockId);
    
    // Add welcome message
    setMessageHistory([
      {
        role: 'system',
        content: 'Welcome to Problem Definition. I can help you articulate and analyze challenges. What problem would you like to address?',
        timestamp: new Date().toISOString()
      }
    ]);
  };
  
  // Update URL with block ID
  const updateURL = (blockId) => {
    if (!blockId) return;
    
    // Create new URL with updated query params
    const params = new URLSearchParams(searchParams.toString());
    params.set('block', blockId);
    
    // Update router
    router.push(`/problem?${params.toString()}`);
  };
  
  // Handle block selection
  const handleBlockSelect = (blockId) => {
    if (blockId === currentBlockId) return;
    loadBlock(blockId);
  };
  
  if (!isClient) {
    return null; // Prevent hydration errors
  }

  return (
    <main className="min-h-screen bg-gray-100 flex flex-col">
      <Header 
        isIdeaPage={false} 
        isProblemPage={true} 
        blockId={currentBlockId} 
        handleNewChat={createNewProblemBlock} 
      />
      
      <div className="flex-1 grid grid-cols-[250px_1fr_300px] h-[calc(100vh-72px)]">
        <BlockSidebar onBlockSelect={handleBlockSelect} blockType="problem" />
        <BlockChatInterface blockType="problem" />
        <InfoPanel />
      </div>
    </main>
  );
}