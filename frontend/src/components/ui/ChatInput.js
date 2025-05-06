'use client';
import { useState, useRef, useEffect } from 'react';
import { useChatStore } from '@/store/chatStore';

export default function ChatInput({ onSendMessage, disabled = false }) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef(null);
  const addLog = useChatStore(state => state.addLog);
  
  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current) {
      // Reset height to auto to correctly calculate the new height
      textareaRef.current.style.height = 'auto';
      
      // Set the height based on scrollHeight, with a max height
      const newHeight = Math.min(textareaRef.current.scrollHeight, 120);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [message]);
  
  // Handle message submission
  const handleSend = () => {
    if (message.trim() && !disabled) {
      onSendMessage(message.trim());
      setMessage('');
      
      // Log the message sending
      addLog({
        type: 'info',
        message: `Sending message: "${message.substring(0, 30)}${message.length > 30 ? '...' : ''}"`
      });
      
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };
  
  // Handle Enter key press (Send on Enter, new line on Shift+Enter)
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
  
  return (
    <div className="flex items-center p-4 border-t border-gray-200 bg-white">
      <textarea
        ref={textareaRef}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? "Please select or create a session to start chatting..." : "Type your message here..."}
        disabled={disabled}
        className="flex-1 p-3 border border-gray-300 rounded-full resize-none max-h-30 transition-all focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        rows={1}
      />
      
      <button
        onClick={handleSend}
        disabled={!message.trim() || disabled}
        className={`ml-3 w-10 h-10 rounded-full flex items-center justify-center ${
          !message.trim() || disabled 
            ? 'bg-gray-300 cursor-not-allowed' 
            : 'bg-primary text-white hover:bg-primary-dark transition-colors'
        }`}
      >
        <i className="fas fa-paper-plane"></i>
      </button>
    </div>
  );
}