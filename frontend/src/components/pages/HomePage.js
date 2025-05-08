'use client';
import { motion } from 'framer-motion';
import Header from '@/components/ui/Header';
import AgentCard from '@/components/ui/AgentCard';

export default function Home() {
  // Animation variants for staggered children
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  return (
    <main className="min-h-screen bg-gray-100 flex flex-col">
      <Header />
      
      <div className="flex-1 py-8 px-6 md:px-12 max-w-6xl mx-auto w-full">
        <motion.section 
          className="text-center mb-8"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Welcome to KRAFT</h2>
          <p className="text-gray-600">
            Your AI-powered creative framework for innovation and problem-solving
          </p>
        </motion.section>
        
        <motion.section
          className="mb-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <h3 className="text-lg font-medium text-gray-700 mb-4 pb-2 border-b border-gray-300">
            GENERAL CHAT
          </h3>
          
          <motion.div 
            className="grid grid-cols-1 sm:grid-cols-1 lg:grid-cols-1 gap-6"
            variants={container}
            initial="hidden"
            animate="show"
          >
            <AgentCard 
              icon="fa-comment" 
              title="General Assistant" 
              description="AI-powered creative guidance" 
              active={true} 
              link="/chat" 
            />
          </motion.div>
        </motion.section>
        
        <motion.section
          className="mb-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <h3 className="text-lg font-medium text-gray-700 mb-4 pb-2 border-b border-gray-300">
            SPARK BLOCKS
          </h3>
          
          <motion.div 
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6"
            variants={container}
            initial="hidden"
            animate="show"
          >
            <AgentCard 
              icon="fa-question-circle" 
              title="Problem" 
              description="Define and explore challenges" 
              active={true} 
              link="/problem" 
            />
            
            <AgentCard 
              icon="fa-route" 
              title="Possibility" 
              description="Explore potential solutions" 
              active={false} 
            />
            
            <AgentCard 
              icon="fa-lightbulb" 
              title="Idea" 
              description="Craft innovative concepts" 
              active={true} 
              link="/idea" 
            />
            
            <AgentCard 
              icon="fa-rocket" 
              title="Moonshot (IFR)" 
              description="Ideal Final Result thinking" 
              active={false} 
            />
          </motion.div>
        </motion.section>
        
        <motion.section
          className="mb-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.4 }}
        >
          <h3 className="text-lg font-medium text-gray-700 mb-4 pb-2 border-b border-gray-300">
            BUILD BLOCKS
          </h3>
          
          <motion.div 
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6"
            variants={container}
            initial="hidden"
            animate="show"
          >
            <AgentCard 
              icon="fa-clipboard-list" 
              title="Needs" 
              description="Identify requirements and goals" 
              active={false} 
            />
            
            <AgentCard 
              icon="fa-door-open" 
              title="Opportunity" 
              description="Discover potential markets" 
              active={false} 
            />
            
            <AgentCard 
              icon="fa-puzzle-piece" 
              title="Concept" 
              description="Develop structured solutions" 
              active={false} 
            />
            
            <AgentCard 
              icon="fa-flag-checkered" 
              title="Outcome" 
              description="Measure and analyze results" 
              active={false} 
            />
          </motion.div>
        </motion.section>
        
        <motion.section
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.6 }}
        >
          <h3 className="text-lg font-medium text-gray-700 mb-4 pb-2 border-b border-gray-300">
            DEV TOOLS
          </h3>
          
          <motion.div 
            className="grid grid-cols-1 sm:grid-cols-2 gap-6"
            variants={container}
            initial="hidden"
            animate="show"
          >
            <AgentCard 
              icon="fa-history" 
              title="Block History" 
              description="View previous conversations" 
              active={false} 
            />
            
            <AgentCard 
              icon="fa-comment-dots" 
              title="Feedback" 
              description="Review and provide feedback" 
              active={false} 
            />
          </motion.div>
        </motion.section>
      </div>
    </main>
  );
}