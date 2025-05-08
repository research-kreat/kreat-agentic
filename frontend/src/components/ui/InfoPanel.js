'use client';
import { useChatStore } from '@/store/chatStore';
import ConsoleLogs from './ConsoleLogs';

export default function InfoPanel() {
  const { blockInfo } = useChatStore();
  
  // Get the block type label
  const getBlockTypeLabel = () => {
    const typeLabels = {
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
    
    return typeLabels[blockInfo.type] || 'KRAFT Assistant';
  };
  
  return (
    <div className="bg-white border-l border-gray-200 h-full flex flex-col">
      <div className="p-6 border-b border-gray-200">
        <h3 className="text-base font-medium text-gray-700 mb-4">Block Information</h3>
        <div className="space-y-2">
          <p className="text-sm text-gray-700">
            <strong>Type:</strong>{' '}
            <span className="px-2 py-1 bg-gray-100 rounded-full text-xs">
              {getBlockTypeLabel()}
            </span>
          </p>
          <p className="text-sm text-gray-700">
            <strong>Created:</strong>{' '}
            <span id="block-created">
              {blockInfo.created 
                ? new Date(blockInfo.created).toLocaleString() 
                : '-'}
            </span>
          </p>
          <p className="text-sm text-gray-700">
            <strong>Messages:</strong>{' '}
            <span id="message-count">{blockInfo.messageCount}</span>
          </p>
          {blockInfo.blockId && (
            <p className="text-sm text-gray-700">
              <strong>Backend ID:</strong>{' '}
              <span className="text-xs font-mono bg-gray-100 px-2 py-1 rounded">
                {blockInfo.blockId.substring(0, 8)}...
              </span>
            </p>
          )}
        </div>
      </div>
      
      <div className="p-6 flex-1 overflow-hidden">
        <h3 className="text-base font-medium text-gray-700 mb-4">Activity Log</h3>
        <ConsoleLogs />
      </div>
    </div>
  );
}