'use client';
import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Header from '@/components/ui/Header';
import BlockSidebar from '@/components/ui/BlockSidebar';
import BlockChatInterface from '@/components/ui/BlockChatInterface';
import InfoPanel from '@/components/ui/InfoPanel';
import { useChatStore } from '@/store/chatStore';
import { api } from '@/lib/api';

export default function GeneralChatPage() {
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
      // Redirect to the dynamic route
      router.replace(`/blocks/${blockId}`);
    } else {
      // Create new block
      createNewGeneralBlock();
    }
    
    // Cleanup on unmount
    return () => {
      resetStore();
    };
  }, [searchParams, userId, router]);
  
  // Create a new general block
  const createNewGeneralBlock = async () => {
    try {
      // Create block on the server
      const data = await api.createBlock({
        userId,
        blockType: 'general',
        name: 'New Chat'
      });
      
      // Set as current block
      setCurrentBlockId(data.block_id);
      
      // Update block info
      setBlockInfo({
        created: data.created_at,
        type: 'general',
        blockId: data.block_id,
        messageCount: 1 // Starting with welcome message
      });
      
      // Navigate to the dynamic route
      router.replace(`/blocks/${data.block_id}`);
      
      // Add welcome message
      setMessageHistory([
        {
          role: 'system',
          content: 'Welcome to KRAFT. I can assist with creative problem-solving and innovation. How can I help you today?',
          timestamp: new Date().toISOString()
        }
      ]);
      
      addLog({
        type: 'system',
        message: `Created new general block: ${data.block_id.substring(0, 8)}...`
      });
    } catch (error) {
      console.error('Error creating block:', error);
      
      // Fallback to local creation
      const blockId = createNewBlock('general', 'New Chat');
      
      // Navigate to the dynamic route
      router.replace(`/blocks/${blockId}`);
      
      // Add welcome message
      setMessageHistory([
        {
          role: 'system',
          content: 'Welcome to KRAFT. I can assist with creative problem-solving and innovation. How can I help you today?',
          timestamp: new Date().toISOString()
        }
      ]);
      
      addLog({
        type: 'error',
        message: `Error creating block on server, using local fallback: ${error.message}`
      });
    }
  };
  
  if (!isClient) {
    return null; // Prevent hydration errors
  }

  return (
    <main className="min-h-screen bg-gray-100 flex flex-col">
      <Header 
        isGeneralChat={true}
        blockId={currentBlockId} 
        handleNewChat={createNewGeneralBlock} 
      />
      
      <div className="flex-1 grid grid-cols-[250px_1fr_300px] h-[calc(100vh-72px)]">
        <BlockSidebar onBlockSelect={(blockId) => router.push(`/blocks/${blockId}`)} blockType="general" />
        <BlockChatInterface blockType="general" />
        <InfoPanel />
      </div>
    </main>
  );
}