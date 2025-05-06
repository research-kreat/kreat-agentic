'use client';
import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Header from '@/components/ui/Header';
import SessionSidebar from '@/components/ui/SessionSidebar';
import ChatInterface from '@/components/ui/ChatInterface';
import InfoPanel from '@/components/ui/InfoPanel';
import { useChatStore } from '@/store/chatStore';

export default function IdeaPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isClient, setIsClient] = useState(false);
  
  const { 
    currentSessionId,
    setCurrentSessionId,
    setMessageHistory,
    setIsTyping,
    setSessionInfo,
    addLog,
    resetStore
  } = useChatStore();
  
  // Prevent hydration issues
  useEffect(() => {
    setIsClient(true);
  }, []);

  // Initialize session based on URL query params or create new session
  useEffect(() => {
    const sessionId = searchParams.get('session');
    
    if (sessionId) {
      // Load existing session
      loadSession(sessionId);
    } else {
      // Create new session
      createNewSession();
    }
    
    // Cleanup on unmount
    return () => {
      resetStore();
    };
  }, [searchParams]);
  
  // Load a session
  const loadSession = async (sessionId) => {
    try {
      setIsTyping(true);
      
      const response = await fetch(`http://localhost:5000/api/sessions/${sessionId}`);
      
      if (!response.ok) {
        throw new Error('Session not found');
      }
      
      const data = await response.json();
      
      // Update session info
      setCurrentSessionId(sessionId);
      setSessionInfo({
        created: data.session.created_at,
        messageCount: data.messages.length,
        type: data.session.type
      });
      
      // Load messages
      setMessageHistory(data.messages || []);
      
      // Update URL without reloading page
      updateURL(sessionId);
      
      addLog({
        type: 'system',
        message: `Loaded session: ${sessionId.substring(0, 8)}...`
      });
    } catch (error) {
      console.error('Error loading session:', error);
      addLog({
        type: 'error',
        message: `Error loading session: ${error.message}`
      });
      
      // Create new session if loading fails
      createNewSession();
    } finally {
      setIsTyping(false);
    }
  };
  
  // Create a new session
  const createNewSession = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/sessions/new', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          type: 'idea',
          name: 'New Idea Session'
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to create new session');
      }
      
      const data = await response.json();
      
      // Set current session ID
      setCurrentSessionId(data.session_id);
      
      // Clear chat and history
      setMessageHistory([]);
      
      // Update session info
      setSessionInfo({
        created: data.created_at,
        messageCount: 0,
        type: 'idea'
      });
      
      // Update URL without reloading page
      updateURL(data.session_id);
      
      addLog({
        type: 'system',
        message: `Created new session: ${data.session_id.substring(0, 8)}...`
      });
      
      // Add welcome message
      setMessageHistory([
        {
          role: 'system',
          content: 'Welcome to a new Idea Development session. How can I help you today?',
          timestamp: new Date().toISOString()
        }
      ]);
    } catch (error) {
      console.error('Error creating new session:', error);
      addLog({
        type: 'error',
        message: `Error creating new session: ${error.message}`
      });
    }
  };
  
  // Update URL with session ID
  const updateURL = (sessionId) => {
    if (!sessionId) return;
    
    // Create new URL with updated query params
    const params = new URLSearchParams(searchParams.toString());
    params.set('session', sessionId);
    
    // Update router
    router.push(`/idea?${params.toString()}`);
  };
  
  // Handle session selection
  const handleSessionSelect = (sessionId) => {
    if (sessionId === currentSessionId) return;
    loadSession(sessionId);
  };
  
  if (!isClient) {
    return null; // Prevent hydration errors
  }

  return (
    <main className="min-h-screen bg-gray-100 flex flex-col">
      <Header isIdeaPage={true} sessionId={currentSessionId} handleNewChat={createNewSession}/>
      
      <div className="flex-1 grid grid-cols-[250px_1fr_300px] h-[calc(100vh-72px)]">
        <SessionSidebar onSessionSelect={handleSessionSelect} />
        <ChatInterface />
        <InfoPanel />
      </div>
    </main>
  );
}