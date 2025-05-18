'use client';
import { useRef, useEffect } from 'react';
import { useChatStore } from '@/store/chatStore';

export default function ConsoleLogs() {
  const logs = useChatStore(state => state.logs);
  const logsEndRef = useRef(null);
  
  // Auto-scroll to the bottom when new logs are added
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);
  
  // Get appropriate color class based on log type
  const getLogClass = (type) => {
    switch(type) {
      case 'system':
        return 'text-teal-300';
      case 'info':
        return 'text-blue-300';
      case 'warning':
        return 'text-amber-300';
      case 'error':
        return 'text-red-300';
      default:
        return 'text-gray-300';
    }
  };
  
  return (
    <div className="h-96 overflow-y-auto bg-gray-900 rounded-lg p-3 font-mono text-sm">
      {logs.map((log, index) => (
        <div key={index} className={`mb-2 ${getLogClass(log.type)}`}>
          <span className="text-gray-500 mr-2">{log.timestamp}</span>
          {log.message}
        </div>
      ))}
      <div ref={logsEndRef} />
    </div>
  );
}