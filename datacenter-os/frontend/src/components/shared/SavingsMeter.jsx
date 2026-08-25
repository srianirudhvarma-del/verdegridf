import React, { useEffect, useState } from 'react';

export default function SavingsMeter({ activeZombies, wattsIdle }) {
  const [savingsKwh, setSavingsKwh] = useState(0);
  
  useEffect(() => {
    // Increment savings smoothly based on current zombie count
    // Realistically it would track historical, but for visual we animate
    const interval = setInterval(() => {
      // Very fast tick for demo visually
      setSavingsKwh(prev => prev + (activeZombies * wattsIdle * 0.0001));
    }, 100);
    return () => clearInterval(interval);
  }, [activeZombies, wattsIdle]);

  const moneySaved = (savingsKwh * 0.12).toFixed(4);

  return (
    <div className="bg-card rounded-xl p-6 border border-accent-green/30 shadow-[0_0_20px_rgba(16,185,129,0.1)] relative">
      <div className="text-xs font-semibold text-accent-green uppercase tracking-wider mb-2">Energy Offset Savings</div>
      <div className="flex flex-col space-y-1">
        <div className="flex items-baseline space-x-2">
          <span className="text-4xl font-bold font-mono text-accent-green">
            {savingsKwh.toFixed(2)}
          </span>
          <span className="text-sm font-medium text-textSecondary">kWh saved</span>
        </div>
        <div className="text-lg font-medium text-white font-mono flex items-center">
          <span className="text-textSecondary mr-2">avoided cost:</span> ${moneySaved}
        </div>
      </div>
    </div>
  );
}
