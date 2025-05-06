'use client';
import { useChatStore } from '@/store/chatStore';
import ConsoleLogs from './ConsoleLogs';

export default function InfoPanel() {
  const { sessionInfo } = useChatStore();
  
  return (
    <div className="bg-white border-l border-gray-200 h-full flex flex-col">
      <div className="p-6 border-b border-gray-200">
        <h3 className="text-base font-medium text-gray-700 mb-4">Session Information</h3>
        <div className="space-y-2">
          <p className="text-sm text-gray-700">
            <strong>Created:</strong>{' '}
            <span id="session-created">
              {sessionInfo.created 
                ? new Date(sessionInfo.created).toLocaleString() 
                : '-'}
            </span>
          </p>
          <p className="text-sm text-gray-700">
            <strong>Messages:</strong>{' '}
            <span id="message-count">{sessionInfo.messageCount}</span>
          </p>
        </div>
      </div>
      
      <div className="p-6 flex-1 overflow-hidden">
        <h3 className="text-base font-medium text-gray-700 mb-4">Activity Log</h3>
        <ConsoleLogs />
      </div>
    </div>
  );
}