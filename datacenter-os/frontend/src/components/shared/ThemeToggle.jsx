import React, { useState, useEffect } from 'react';
import { Moon, Sun, Monitor } from 'lucide-react';

const ThemeToggle = () => {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme');
    return (saved === 'noir' || saved === 'steel') ? saved : 'noir';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const themes = [
    { id: 'noir', icon: Moon, label: 'Noir' },
    { id: 'steel', icon: Monitor, label: 'Steel' }
  ];

  return (
    <div className="flex items-center bg-white/5 border border-white/5 p-1 rounded-xl w-full">
      {themes.map(t => {
        const Icon = t.icon;
        const isActive = theme === t.id;
        return (
          <button
            key={t.id}
            onClick={() => setTheme(t.id)}
            className={`flex-1 flex flex-col items-center justify-center py-2 rounded-lg transition-all duration-500 overflow-hidden relative group ${
              isActive 
                ? 'bg-white/10 text-white shadow-lg' 
                : 'text-textMuted hover:text-white hover:bg-white/5'
            }`}
          >
            <Icon size={14} className={`${isActive ? 'animate-pulse' : 'opacity-50'}`} />
            <span className={`text-[8px] font-bold uppercase mt-1 tracking-widest ${isActive ? 'opacity-100' : 'opacity-0 h-0'} transition-all`}>
              {t.label}
            </span>
          </button>
        );
      })}
    </div>
  );
};

export default ThemeToggle;
