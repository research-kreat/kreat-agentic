'use client';
import { create } from 'zustand';

export const useChatStore = create((set, get) => ({
  // Session state
  currentSessionId: null,
  sessions: [],
  messageHistory: [],
  isTyping: false,
  
  // Session info
  sessionInfo: {
    created: null,
    messageCount: 0,
    type: 'idea'
  },
  
  // Console logs
  logs: [
    {
      type: 'system',
      message: 'Ready to assist with idea development',
      timestamp: new Date().toLocaleTimeString()
    }
  ],
  
  // Actions
  setCurrentSessionId: (sessionId) => set({ currentSessionId: sessionId }),
  
  addMessage: (message) => {
    const { messageHistory } = get();
    set({ 
      messageHistory: [...messageHistory, message],
      sessionInfo: {
        ...get().sessionInfo,
        messageCount: get().sessionInfo.messageCount + 1
      }
    });
  },
  
  setSessions: (sessions) => set({ sessions }),
  
  addSession: (session) => {
    const { sessions } = get();
    const existingIndex = sessions.findIndex(s => s.session_id === session.session_id);
    
    if (existingIndex >= 0) {
      // Update existing session
      const updatedSessions = [...sessions];
      updatedSessions[existingIndex] = session;
      set({ sessions: updatedSessions });
    } else {
      // Add new session
      set({ sessions: [session, ...sessions] });
    }
  },
  
  removeSession: (sessionId) => {
    const { sessions, currentSessionId } = get();
    set({ 
      sessions: sessions.filter(s => s.session_id !== sessionId),
      currentSessionId: sessionId === currentSessionId ? null : currentSessionId,
      messageHistory: sessionId === currentSessionId ? [] : get().messageHistory
    });
  },
  
  setMessageHistory: (messages) => set({ messageHistory: messages }),
  
  clearMessages: () => set({ 
    messageHistory: [
      {
        role: 'system',
        content: 'Chat has been cleared. How can I help you today?',
        timestamp: new Date().toISOString()
      }
    ],
    sessionInfo: {
      ...get().sessionInfo,
      messageCount: 1
    }
  }),
  
  setSessionInfo: (info) => set({ 
    sessionInfo: {
      ...get().sessionInfo,
      ...info
    }
  }),
  
  setIsTyping: (status) => set({ isTyping: status }),
  
  addLog: (log) => {
    const { logs } = get();
    const newLog = {
      ...log,
      timestamp: new Date().toLocaleTimeString()
    };
    
    set({ logs: [...logs, newLog] });
  },
  
  resetStore: () => set({
    currentSessionId: null,
    messageHistory: [],
    isTyping: false,
    sessionInfo: {
      created: null,
      messageCount: 0,
      type: 'idea'
    },
    logs: [
      {
        type: 'system',
        message: 'Ready to assist with idea development',
        timestamp: new Date().toLocaleTimeString()
      }
    ]
  })
}));