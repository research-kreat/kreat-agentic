'use client';
import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

export default function Message({ message, isLast }) {
  const { role, content, timestamp, fullResponse } = message;
  const messageRef = useRef(null);
  const [showDetails, setShowDetails] = useState(false);
  
  // Card styles for different content types
  const cardStyles = {
    title: "bg-blue-50 border-blue-200",
    abstract: "bg-indigo-50 border-indigo-200",
    stakeholders: "bg-purple-50 border-purple-200",
    tags: "bg-pink-50 border-pink-200",
    assumptions: "bg-red-50 border-red-200",
    constraints: "bg-orange-50 border-orange-200",
    risks: "bg-yellow-50 border-yellow-200",
    areas: "bg-green-50 border-green-200",
    impact: "bg-teal-50 border-teal-200",
    connections: "bg-cyan-50 border-cyan-200",
    classifications: "bg-sky-50 border-sky-200", 
    think_models: "bg-emerald-50 border-emerald-200",
    suggestion: "bg-gray-50 border-gray-200"
  };

  // Icons for different content types
  const cardIcons = {
    title: "fa-heading",
    abstract: "fa-align-left",
    stakeholders: "fa-users",
    tags: "fa-tags",
    assumptions: "fa-lightbulb",
    constraints: "fa-ban",
    risks: "fa-exclamation-triangle",
    areas: "fa-layer-group",
    impact: "fa-chart-line",
    connections: "fa-network-wired",
    classifications: "fa-sitemap",
    think_models: "fa-brain",
    suggestion: "fa-comment"
  };
  
  // Nice human-readable labels for each key
  const keyLabels = {
    title: "Title",
    abstract: "Abstract",
    stakeholders: "Stakeholders",
    tags: "Tags & Categories",
    assumptions: "Assumptions",
    constraints: "Constraints",
    risks: "Risks",
    areas: "Related Areas",
    impact: "Impact",
    connections: "Connections",
    classifications: "Classifications",
    think_models: "Thinking Models",
    suggestion: "Suggestion"
  };
  
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
  
  // Format list items for display
  const formatListItems = (items) => {
    if (!Array.isArray(items)) return formatMessageContent(items);
    
    return (
      <ul className="list-disc ml-5 mt-2 space-y-1">
        {items.map((item, index) => (
          <li key={index} className="text-gray-700">
            {typeof item === 'object' 
              ? JSON.stringify(item) 
              : item}
          </li>
        ))}
      </ul>
    );
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
  
  // Render response cards for assistant messages
  const renderResponseCards = () => {
    if (role !== 'assistant' || !fullResponse || typeof fullResponse !== 'object') {
      return null;
    }
    
    // Get the keys we want to display as cards (excluding some meta fields)
    const cardKeys = Object.keys(fullResponse).filter(key => 
      key !== 'updated_flow_status' && 
      key !== 'classification_message' &&
      key !== 'identified_as' &&
      key in cardStyles
    );
    
    if (cardKeys.length === 0) return null;
    
    return (
      <div className="mt-4 space-y-3 w-full">
        {cardKeys.map(key => (
          <div 
            key={key}
            className={`p-4 rounded-lg border ${cardStyles[key] || 'bg-gray-50 border-gray-200'} shadow-sm`}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${cardStyles[key].replace('bg-', 'bg-').replace('border-', 'text-')}`}>
                <i className={`fas ${cardIcons[key] || 'fa-file-alt'}`}></i>
              </div>
              <h4 className="font-medium text-gray-800">{keyLabels[key] || key}</h4>
            </div>
            
            <div className="pl-10">
              {key === 'title' || key === 'abstract' || key === 'suggestion' ? (
                <div dangerouslySetInnerHTML={{ __html: formatMessageContent(fullResponse[key]) }} />
              ) : Array.isArray(fullResponse[key]) ? (
                formatListItems(fullResponse[key])
              ) : typeof fullResponse[key] === 'object' ? (
                <pre className="text-sm bg-white p-2 rounded overflow-auto">
                  {JSON.stringify(fullResponse[key], null, 2)}
                </pre>
              ) : (
                <div dangerouslySetInnerHTML={{ __html: formatMessageContent(fullResponse[key]) }} />
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };
  
  // Render detailed response data if requested
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
  
  // Special rendering for system messages
  if (role === 'system') {
    return (
      <motion.div 
        ref={messageRef}
        className="self-center max-w-[80%]"
        initial="hidden"
        animate="visible"
        variants={variants}
        transition={{ duration: 0.3 }}
      >
        <div className="p-4 rounded-md bg-gray-200 text-gray-800 text-center">
          <p>{content}</p>
        </div>
      </motion.div>
    );
  }
  
  return (
    <motion.div 
      ref={messageRef}
      className={`flex gap-4 max-w-[85%] ${
        role === 'user' 
          ? 'self-end flex-row-reverse' 
          : 'self-start'
      }`}
      initial="hidden"
      animate="visible"
      variants={variants}
      transition={{ duration: 0.3 }}
    >
      <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${
        role === 'user' 
          ? 'bg-primary text-black' 
          : 'bg-secondary text-black'
      }`}>
        <i className={`fas ${role === 'user' ? 'fa-user' : 'fa-robot'}`}></i>
      </div>
      
      <div className="flex flex-col items-start max-w-full">
        <div 
          className={`p-4 rounded-2xl shadow-sm ${
            role === 'user' 
              ? 'bg-primary text-black rounded-br-none' 
              : 'bg-white text-gray-800 rounded-bl-none'
          }`}
          onClick={role === 'assistant' && fullResponse ? toggleDetails : undefined}
        >
          {(!fullResponse || Object.keys(fullResponse).every(key => 
            key === 'updated_flow_status' || 
            key === 'classification_message' ||
            key === 'identified_as'
          )) ? (
            <div 
              dangerouslySetInnerHTML={{ __html: formatMessageContent(content) }} 
              className="message-content"
            />
          ) : (
            <div className="message-content">
              {/* For assistant messages with fullResponse, only show suggestion in the bubble */}
              {role === 'assistant' && fullResponse.suggestion && (
                <div dangerouslySetInnerHTML={{ __html: formatMessageContent(fullResponse.suggestion) }} />
              )}
              
              {/* For assistant messages without suggestion, show the regular content */}
              {role === 'assistant' && !fullResponse.suggestion && (
                <div dangerouslySetInnerHTML={{ __html: formatMessageContent(content) }} />
              )}
              
              {/* Always show user content */}
              {role === 'user' && (
                <div dangerouslySetInnerHTML={{ __html: formatMessageContent(content) }} />
              )}
            </div>
          )}
          
          {/* Show response details if toggled and available */}
          {showDetails && renderResponseDetails()}
          
          <div className="text-xs mt-1 text-right flex justify-between items-center">
            {role === 'assistant' && fullResponse && Object.keys(fullResponse).length > 0 && (
              <span className="cursor-pointer text-blue-500 hover:underline">
                {showDetails ? 'Hide details' : 'Show details'}
              </span>
            )}
            <span className={role === 'user' ? 'text-black' : 'text-gray-500'}>{formattedTime}</span>
          </div>
        </div>
        
        {/* Render cards for response data */}
        {role === 'assistant' && renderResponseCards()}
      </div>
    </motion.div>
  );
}