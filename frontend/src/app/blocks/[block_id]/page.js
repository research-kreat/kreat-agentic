'use client';
import { useEffect, useState } from 'react';
import { notFound } from 'next/navigation';
import { useChatStore } from '@/store/chatStore';
import BlockPage from '@/components/pages/BlockPage';
import NotFoundPage from '@/app/not-found';

export default function BlockIdPage({ params }) {
  const { block_id } = params;
  const [blockType, setBlockType] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const userId = useChatStore(state => state.userId);
  const initializeUser = useChatStore(state => state.initializeUser);

  useEffect(() => {
    // Initialize user if needed
    initializeUser();

    if (!userId || !block_id) return;

    const fetchBlockType = async () => {
      try {
        setLoading(true);
        // Import api from lib
        const { api } = await import('@/lib/api');

        // Get block details to determine the type
        const data = await api.getBlock({ blockId: block_id, userId });
        const type = data.block.type || 'general';
        
        setBlockType(type);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching block details:', error);
        setError(error);
        setLoading(false);
      }
    };

    fetchBlockType();
  }, [block_id, userId, initializeUser]);

  // Show loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-gray-600">
          <div className="flex items-center">
            <i className="fas fa-spinner fa-spin text-xl mr-2"></i>
            <span>Loading block...</span>
          </div>
        </div>
      </div>
    );
  }

  // Show error or not found
  if (error || !blockType) {
    return <NotFoundPage message="Block not found or inaccessible" />;
  }

  // Render the BlockPage with the determined block type
  return <BlockPage blockType={blockType} />;
}