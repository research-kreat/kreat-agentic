'use client';
import { useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import BlockPage from '@/components/pages/BlockPage';
import { useChatStore } from '@/store/chatStore';

export default function BlocksPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { initializeUser, createNewBlock } = useChatStore();
  
  // Get block type from query params or default to 'general'
  const blockType = searchParams.get('type') || 'general';
  
  useEffect(() => {
    // Initialize user if needed
    initializeUser();
    
    // Check if there's a block ID in the query params
    const blockId = searchParams.get('block');
    
    if (blockId) {
      // If there's a block ID, update the URL to the dynamic route
      router.push(`/blocks/${blockId}`);
    }
  }, [searchParams, router, initializeUser]);

  return <BlockPage blockType={blockType} />;
}