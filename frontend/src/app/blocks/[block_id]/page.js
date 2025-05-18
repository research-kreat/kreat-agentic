'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useChatStore } from '@/store/chatStore';
import BlockPage from '@/components/pages/BlockPage';
import NotFoundPage from '@/app/not-found';
import { api } from '@/lib/api';

export default function BlockIdPage() {
  // Use the useParams hook to get route parameters in client components
  const params = useParams();
  const blockId = params?.block_id;
  
  const [blockType, setBlockType] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const userId = useChatStore(state => state.userId);
  const initializeUser = useChatStore(state => state.initializeUser);

  useEffect(() => {
    // Initialize user if needed
    const initializedUserId = initializeUser();

    if (!blockId) {
      setError(new Error("Block ID is required"));
      setLoading(false);
      return;
    }

    const fetchBlockType = async () => {
      try {
        setLoading(true);

        // Get block details to determine the type
        const data = await api.getBlock({ blockId, userId: initializedUserId });
        const type = data.block.type || 'general';
        
        setBlockType(type);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching block details:', error);
        setError(error);
        setLoading(false);
      }
    };

    // Only fetch if we have a userId
    if (initializedUserId) {
      fetchBlockType();
    }
  }, [blockId, initializeUser]);

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

  // Render the BlockPage with the determined block type and block ID
  return <BlockPage blockType={blockType} blockId={blockId} />;
}