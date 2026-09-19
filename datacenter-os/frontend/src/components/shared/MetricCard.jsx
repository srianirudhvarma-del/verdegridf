import React from 'react';

export default function MetricCard({ title, value, unit, statusColor = 'text-textMain' }) {
  return (
    <div className="glass-panel animate-breath rounded-[14px] p-6 group">
      <div className="razor-border" />
      <div className="text-[10px] font-bold text-textMuted uppercase tracking-[0.2em] mb-3 opacity-80">{title}</div>
      <div className="flex items-baseline space-x-2">
        <span className={`text-4xl metric-text ${statusColor} accent-glow`}>{value}</span>
        {unit && <span className="text-sm font-mono text-textMuted opacity-80">{unit}</span>}
      </div>
    </div>
  );
}
