import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, X, Bot, Send } from 'lucide-react';
import { cn } from '../../lib/utils';

export default function HardwareConcierge() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { sender: 'ai', text: 'Hello! I am your Hardware Concierge. I can see your overall setup. How can I help you today?' }
  ]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    setMessages(prev => [...prev, { sender: 'user', text: input }]);
    setInput('');

    setTimeout(() => {
      setMessages(prev => [...prev, { 
        sender: 'ai', 
        text: 'I operate as an omnipresent guide across all screens. Check the setup guide for detailed steps on your hardware!' 
      }]);
    }, 1000);
  };

  return (
    <>
      <div className="fixed bottom-8 right-8 z-50 flex flex-col items-end">
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.9 }}
              className="bg-obsidian/95 backdrop-blur-xl border border-white/10 w-80 h-96 rounded-2xl shadow-2xl mb-4 flex flex-col overflow-hidden"
            >
              <div className="p-3 bg-white/5 border-b border-white/10 flex justify-between items-center">
                <div className="flex items-center space-x-2">
                  <Bot className="w-5 h-5 text-accent-green" />
                  <span className="text-white font-medium text-sm">Hardware Concierge</span>
                </div>
                <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
              
              <div className="flex-1 p-4 overflow-y-auto space-y-3">
                {messages.map((m, i) => (
                  <div key={i} className={cn(
                    "text-sm max-w-[85%] p-2 rounded-xl",
                    m.sender === 'ai' ? "bg-white/10 text-gray-200 self-start rounded-tl-none mr-auto" : "bg-accent-green text-black self-end rounded-tr-none ml-auto"
                  )}>
                    {m.text}
                  </div>
                ))}
              </div>

              <form onSubmit={handleSend} className="p-3 border-t border-white/10 flex space-x-2">
                 <input
                   type="text"
                   value={input}
                   onChange={e => setInput(e.target.value)}
                   placeholder="Ask me anything..."
                   className="flex-1 bg-black/40 border border-white/10 rounded-md px-3 py-1.5 text-sm text-white focus:outline-none focus:border-accent-green"
                 />
                 <button type="submit" className="bg-accent-green text-black px-3 rounded-md hover:bg-accent-green/90">
                   <Send className="w-4 h-4" />
                 </button>
              </form>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.button
          onClick={() => setIsOpen(!isOpen)}
          className="bg-accent-green text-black w-14 h-14 rounded-full flex items-center justify-center shadow-[0_0_20px_rgba(0,255,128,0.3)] hover:scale-105 transition-transform"
          whileTap={{ scale: 0.95 }}
        >
          {isOpen ? <X className="w-6 h-6" /> : <MessageSquare className="w-6 h-6 outline-none" />}
        </motion.button>
      </div>
    </>
  );
}
