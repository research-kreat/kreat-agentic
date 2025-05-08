'use client';
import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

export default function Message({ message, isLast }) {
  const { role, content, timestamp, fullResponse } = message;
  const messageRef = useRef(null);
  const [showDetails, setShowDetails] = useState(false);
  
  // Scroll into view if it's the last message
  useEffect(() => {
    if (isLast && messageRef.current) {
      messageRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [isLast]);
  
  // Format message content with links, code blocks, etc.
  const formatMessageContent = (content) => {
    if (!content) return '';
    
    // Handle line breaks
    let formattedContent = content.replace(/\n/g, '<br>');
    
    // Convert URLs to links
    formattedContent = formattedContent.replace(
      /(https?:\/\/[^\s]+)/g, 
      '<a href="$1" target="_blank" rel="noopener noreferrer" class="text-blue-500 hover:underline">$1</a>'
    );
    
    // Convert markdown-style code blocks to HTML
    formattedContent = formattedContent.replace(
      /```([^`]+)```/g,
      '<pre class="bg-gray-100 p-3 rounded my-2 overflow-auto"><code>$1</code></pre>'
    );
    
    // Convert markdown-style inline code to HTML
    formattedContent = formattedContent.replace(
      /`([^`]+)`/g,
      '<code class="bg-gray-100 px-1 rounded">$1</code>'
    );
    
    return formattedContent;
  };
  
  // Format timestamp
  const formattedTime = timestamp ? new Date(timestamp).toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit' 
  }) : '';
  
  // Animation variants
  const variants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  };
  
  // Toggle details view for assistants' responses when fullResponse exists
  const toggleDetails = () => {
    if (role === 'assistant' && fullResponse) {
      setShowDetails(!showDetails);
    }
  };
  
  // Render detailed response data if available
  const renderResponseDetails = () => {
    if (!fullResponse || typeof fullResponse !== 'object') return null;
  
    return (
      <div className="mt-3 border-t border-gray-200 pt-2 text-xs w-full max-w-full">
        <div className="font-medium mb-1 text-gray-700">Full Response Data:</div>
        <pre className="bg-gray-100 p-3 rounded-md overflow-auto max-h-60 text-left whitespace-pre-wrap break-words text-[11px]">
          {JSON.stringify(fullResponse, null, 2)}
        </pre>
      </div>
    );
  };
  
  
  return (
    <motion.div 
      ref={messageRef}
      className={`flex gap-4 max-w-[85%] ${
        role === 'user' 
          ? 'self-end flex-row-reverse' 
          : role === 'system' 
            ? 'self-center max-w-[80%]' 
            : 'self-start'
      }`}
      initial="hidden"
      animate="visible"
      variants={variants}
      transition={{ duration: 0.3 }}
    >
      {role !== 'system' && (
        <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${
          role === 'user' 
            ? 'bg-primary' 
            : 'bg-secondary'
        }`}>
          <i className={`fas ${role === 'user' ? 'fa-user' : 'fa-robot'}`}></i>
        </div>
      )}
      
      <div 
        className={`p-4 rounded-2xl shadow-sm ${
          role === 'user' 
            ? 'bg-primary rounded-br-none' 
            : role === 'system' 
              ? 'bg-gray-200 text-gray-800 text-center rounded-md' 
              : 'bg-white text-gray-800 rounded-bl-none'
        }`}
        onClick={role === 'assistant' && fullResponse ? toggleDetails : undefined}
      >
        <div 
          dangerouslySetInnerHTML={{ __html: formatMessageContent(content) }} 
          className="message-content"
        />
        
        {/* Show response details if toggled and available */}
        {showDetails && renderResponseDetails()}
        
        {role !== 'system' && (
          <div className="text-xs mt-1 text-right flex justify-between items-center">
            {role === 'assistant' && fullResponse && (
              <span className="cursor-pointer text-blue-500 hover:underline">
                {showDetails ? 'Hide details' : 'Show details'}
              </span>
            )}
            <span>{formattedTime}</span>
          </div>
        )}
      </div>
    </motion.div>
  );
}