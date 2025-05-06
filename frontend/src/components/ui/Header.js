'use client';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';

export default function Header({ sessionId = null, isIdeaPage = false, handleNewChat = () => {} }) {
  const router = useRouter();
  
  return (
    <header className="bg-white shadow-md py-4 px-6 flex justify-between items-center">
      <div className="flex items-center gap-3">
        <motion.i 
          className="fas fa-lightbulb text-2xl text-primary"
          initial={{ rotate: -30 }}
          animate={{ rotate: 0 }}
          transition={{ duration: 0.5 }}
        />
        <h1 className="text-xl font-semibold text-gray-800">KRAFT</h1>
      </div>
      
      {isIdeaPage ? (
        <nav className="flex items-center">
          <button 
            onClick={() => router.push('/')}
            className="flex items-center gap-2 px-3 py-2 bg-transparent border border-gray-300 rounded-md text-gray-700 hover:bg-gray-200 transition duration-300"
          >
            <i className="fas fa-arrow-left"></i> Back to Dashboard
          </button>
          
          {sessionId && (
            <div className="ml-4 flex items-center">
              <span id="session-id" className="text-gray-600 text-sm mr-3">
                Session: {sessionId.substring(0, 8)}...
              </span>
              <button
                id="new-session-btn"
                onClick={handleNewChat}
                className="px-3 py-2 bg-gray-200 text-gray-700 rounded-md text-sm flex items-center gap-1 hover:bg-gray-300 transition duration-300"
              >
                <i className="fas fa-plus"></i> New Session
              </button>
            </div>
          )}
        </nav>
      ) : (
        <p className="text-gray-600 text-sm">Version 1.0/MAY-05-2025</p>
      )}
    </header>
  );
}