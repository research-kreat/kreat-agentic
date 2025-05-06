'use client';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';

export default function AgentCard({ icon, title, description, active = false, link = null }) {
  const router = useRouter();
  
  const handleClick = () => {
    if (active && link) {
      router.push(link);
    }
  };
  
  return (
    <motion.div 
      className={`bg-white rounded-lg shadow p-6 flex flex-col gap-4 transition-all duration-300 ${
        active ? 'cursor-pointer hover:shadow-lg' : 'opacity-70 cursor-not-allowed'
      }`}
      onClick={handleClick}
      whileHover={active ? { y: -5 } : {}}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
        <i className={`fas ${icon} text-xl text-primary`}></i>
      </div>
      
      <div className="agent-info">
        <h2 className="text-lg font-medium text-gray-800 mb-1">{title}</h2>
        <p className="text-sm text-gray-600 mb-2">{description}</p>
        <span className={`text-xs py-1 px-2 rounded-full ${
          active ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'
        } inline-block`}>
          {active ? 'Active' : 'Coming Soon'}
        </span>
      </div>
    </motion.div>
  );
}