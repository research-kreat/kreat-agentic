'use client';
import { motion } from 'framer-motion';

export default function TypingIndicator() {
  return (
    <div className="flex gap-4 self-start">
      <div className="w-9 h-9 rounded-full bg-secondary text-white flex items-center justify-center">
        <i className="fas fa-robot"></i>
      </div>
      
      <div className="p-4 rounded-2xl rounded-bl-none bg-white shadow-sm">
        <div className="flex gap-1 py-2">
          {[0, 1, 2].map((dot) => (
            <motion.div
              key={dot}
              className="w-2 h-2 bg-gray-400 rounded-full"
              initial={{ y: 0 }}
              animate={{ y: [0, -5, 0] }}
              transition={{
                duration: 1,
                ease: "easeInOut",
                repeat: Infinity,
                delay: dot * 0.2
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}