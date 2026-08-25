import React from 'react';
import { AlertCircle } from 'lucide-react';

export default function AlertBadge({ message, type = 'warning' }) {
  const colors = {
    warning: 'bg-accent-orange/10 border-accent-orange/30 text-accent-orange',
    critical: 'bg-accent-red/10 border-accent-red/30 text-accent-red',
    info: 'bg-blue-500/10 border-blue-500/30 text-blue-400'
  };

  return (
    <div className={`flex items-center space-x-3 p-4 rounded-lg border ${colors[type]} mb-4`}>
      <AlertCircle className="w-5 h-5 flex-shrink-0" />
      <span className="text-sm font-medium leading-relaxed">{message}</span>
    </div>
  );
}
