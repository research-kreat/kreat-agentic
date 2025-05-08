'use client';
import { useRouter, useEffect } from 'next/navigation';
import { useChatStore } from '@/store/chatStore';
import NotFoundPage from '@/app/not-found';

// Map of block types to their routes
const blockTypeRoutes = {
    idea: '/idea',
    problem: '/problem',
    general: '/chat',
};

// This dynamic [block_id] route will redirect to the appropriate page with query param
export default function BlockRedirect({ params }) {
    const router = useRouter();
    const { blockId } = params;
    const userId = useChatStore(state => state.userId);
    const initializeUser = useChatStore(state => state.initializeUser);

    useEffect(() => {
        // Initialize user if needed
        initializeUser();

        if (!userId) return;

        const fetchBlock = async () => {
            try {
                // Import api from lib
                const { api } = await import('@/lib/api');

                // Get block details to determine the proper route
                const data = await api.getBlock({ blockId, userId });
                const blockType = data.block.type || 'general';

                // Get the appropriate route for this block type
                const route = blockTypeRoutes[blockType] || '/chat';

                // Redirect to the correct page with the block ID as a query param
                router.replace(`${route}?block=${blockId}`);
            } catch (error) {
                console.error('Error fetching block details:', error);
                router.replace('/');
            }
        };

        fetchBlock();
    }, [blockId, router, userId, initializeUser]);

    return (
        <div className="min-h-screen flex items-center justify-center">
            <div className="animate-pulse text-gray-600">
                <div className="flex items-center">
                    <i className="fas fa-spinner fa-spin text-xl mr-2"></i>
                    <span>Redirecting to the appropriate block...</span>
                </div>
            </div>
        </div>
    );
}