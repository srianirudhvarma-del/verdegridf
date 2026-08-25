import React from 'react';
import LiveSimBadge from './LiveSimBadge';

// Common sub-header for modules
// Pass moduleName to show the correct LIVE/SIM badge (e.g. "CarbonClock", "IDLEhunter")
export default function ModuleHeader({ title, subtitle, moduleName }) {
  return (
    <div className="mb-10 animate-in slide-in-from-left duration-700">
      <h1 className="text-4xl font-sans font-light tracking-tighter text-textMain mb-2 uppercase flex items-center gap-4">
        <span className="text-accent-green font-black">//</span>
        {title}
        {moduleName && (
          <span className="flex-shrink-0">
            <LiveSimBadge moduleName={moduleName} />
          </span>
        )}
        <span className="ml-2 h-px flex-1 bg-gradient-to-r from-textMain/20 to-transparent hidden sm:block" />
      </h1>
      <p className="text-textMuted font-mono text-[11px] uppercase tracking-[0.3em] ml-11 opacity-70 italic">{subtitle}</p>
    </div>
  );
}
