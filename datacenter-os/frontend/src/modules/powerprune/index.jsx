import React, { useCallback, useEffect, useState } from 'react';
import { getServerCluster, consolidateIdleServers } from '../../services/powerpruneApi';
import { useLiveResource } from '../../hooks/useLiveResource';
import ModuleHeader from '../../components/shared/ModuleHeader';
import MetricCard from '../../components/shared/MetricCard';
import SavingsMeter from '../../components/shared/SavingsMeter';
import ClassificationOverride from './ClassificationOverride';

export default function PowerPrune() {
  const fetcher = useCallback(() => getServerCluster(), []);
  const [data] = useLiveResource(fetcher, 3000);
  const [autoConsolidate, setAutoConsolidate] = useState(false);

  useEffect(() => {
    // The real backend's consolidation pass is bulk (powerprune/power.py's
    // dwell state machine decides per-host, not per API call) -- auto-mode
    // just triggers that real pass on an interval instead of harvesting one
    // mock zombie at a time.
    let interval;
    if (autoConsolidate) {
      interval = setInterval(() => {
        consolidateIdleServers().catch((err) => console.error('auto-consolidate failed:', err));
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [autoConsolidate]);

  if (!data?.servers) return null;

  const { servers } = data;
  const zombies = servers.filter(s => s.state === 'zombie');
  const activeCount = servers.filter(s => s.state === 'active').length;
  const warnings = servers.filter(s => s.cpu_util >= 15 && s.cpu_util <= 30 && s.state === 'active');
  const avgCpu = servers.reduce((acc, curr) => acc + curr.cpu_util, 0) / servers.length;

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-start mb-10">
        <ModuleHeader 
          title="PowerPrune" 
          subtitle="Autonomous load-migration heuristic — utilization threshold: 15%" 
          moduleName="PowerPrune"
        />
        <div className="flex flex-col items-end space-y-2">
          <div className="flex items-center space-x-3 bg-card border border-white/5 px-4 py-2 rounded-xl">
             <div className="text-[9px] font-mono font-bold text-textMuted/50 uppercase tracking-[0.2em]">ECON-INDEX</div>
             <div className="text-xl font-sans font-light text-accent-green">{(100 - (zombies.length / servers.length) * 100).toFixed(1)}%</div>
          </div>
          <div className="text-[8px] font-mono text-textMuted uppercase tracking-widest opacity-30">PEAK THEORETICAL: 99.4%</div>
        </div>
      </div>

      <ClassificationOverride hostIds={servers.map((s) => s.id)} />

      {/* Top row metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <MetricCard
          title="ACTIVE ZOMBIE NODES"
          value={zombies.length}
          statusColor={zombies.length > 5 ? 'text-accent-red' : 'text-accent-green'}
        />

        <MetricCard 
          title="AVG CLUSTER CPU"
          value={avgCpu.toFixed(1)}
          unit="%"
        />

        <SavingsMeter 
          activeZombies={zombies.length} 
          wattsIdle={200}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left: Cluster Grid */}
        <div className="lg:col-span-2 glass-panel p-8 rounded-2xl animate-breath">
          <div className="razor-border" />
          <div className="flex justify-between items-center mb-8 border-b border-white/5 pb-6">
            <h3 className="text-lg font-sans font-light text-textMain tracking-widest uppercase flex items-center">
               Cluster Grid
               <span className="text-[10px] font-mono text-textMuted ml-4 opacity-50 tracking-[0.2em]">{servers.length} NODE POOL</span>
            </h3>
            
            {/* Extremely Obvious Legend */}
            <div className="flex space-x-6 text-[9px] font-bold uppercase tracking-[0.15em] border border-white/5 px-4 py-2 rounded-lg bg-black/40">
              <span className="flex items-center text-accent-green accent-glow"><div className="w-1.5 h-1.5 bg-accent-green rounded-full mr-2 shadow-[0_0_8px_currentColor]"/> Normal</span>
              <span className="flex items-center text-accent-amber accent-glow"><div className="w-1.5 h-1.5 bg-accent-amber rounded-full mr-2 shadow-[0_0_8px_currentColor]"/> Warning</span>
              <span className="flex items-center text-accent-red accent-glow animate-pulse"><div className="w-1.5 h-1.5 bg-accent-red rounded-full mr-2 shadow-[0_0_8px_currentColor]"/> Zombie</span>
            </div>
          </div>
          
          <div className="grid grid-cols-4 sm:grid-cols-5 gap-4">
            {servers.map(server => {
              let bgColor = 'bg-black border-white/10 text-textSecondary opacity-40';
              let iconColor = 'bg-white/20';
              
              if (server.state === 'active') {
                if (server.cpu_util >= 15 && server.cpu_util <= 30) {
                  bgColor = 'bg-accent-amber/20 border-accent-amber/80 text-accent-amber';
                  iconColor = 'bg-accent-amber shadow-[0_0_12px_currentColor]';
                } else {
                  bgColor = 'bg-accent-green/20 border-accent-green/80 text-accent-green';
                  iconColor = 'bg-accent-green shadow-[0_0_12px_currentColor]';
                }
              } else if (server.state === 'zombie') {
                bgColor = 'bg-accent-red/30 border-accent-red text-accent-red accent-glow animate-pulse';
                iconColor = 'bg-accent-red shadow-[0_0_20px_currentColor]';
              }

              const [rack, srv] = server.id.split('-');

              return (
                <div 
                  key={server.id} 
                  title={`${server.id} - CPU: ${server.cpu_util.toFixed(1)}% | RAM: ${server.ram_util.toFixed(1)}%`}
                  className={`aspect-square w-full rounded-xl border flex flex-col justify-center items-center p-2 transition-all duration-500 hover:scale-110 cursor-crosshair ${bgColor} group scanline-hover overflow-hidden relative shadow-lg`}
                >
                  <div className="flex flex-col items-center justify-center relative z-10 w-full space-y-1">
                    <span className="text-[11px] font-mono font-bold opacity-80 group-hover:opacity-100 transition-opacity tracking-wider">{rack}</span>
                    {srv && <span className="text-xs font-mono font-black opacity-100">{srv}</span>}
                  </div>
                  
                  <div className={`absolute top-2.5 right-2.5 w-2 h-2 rounded-full ${iconColor} transition-all duration-300 opacity-80 group-hover:opacity-100`}></div>
                  
                  <div className="absolute bottom-2 left-0 w-full px-3 relative z-10">
                     <div className="h-[3px] w-full bg-black/40 rounded-full overflow-hidden">
                        <div className="h-full bg-current transition-all duration-1000" style={{ width: `${server.cpu_util}%` }} />
                     </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Consolidation Queue */}
        <div className="glass-panel p-8 rounded-2xl flex flex-col h-[500px] border-borderC">
          <div className="razor-border" />
          <div className="flex justify-between items-center mb-8 border-b border-borderC pb-6">
            <h3 className="text-lg font-sans font-light text-textMain tracking-widest uppercase truncate mr-4">Harvest Queue</h3>
            <div className="relative flex-shrink-0">
              {autoConsolidate && <div className="absolute inset-0 bg-accent-green/20 rounded-lg animate-ping pointer-events-none" />}
              <button 
                onClick={() => setAutoConsolidate(!autoConsolidate)}
                className={`relative z-10 text-[10px] px-4 py-2.5 rounded-lg font-black tracking-[0.1em] whitespace-nowrap uppercase transition-all duration-500 border-2 ${
                  autoConsolidate 
                    ? 'bg-accent-green text-black border-accent-green shadow-[0_0_20px_#00FF41]' 
                    : 'bg-card border-white/20 text-textMuted hover:text-textMain hover:bg-white/10 hover:border-white/40'
                }`}
              >
                {autoConsolidate ? 'AUTO-HARVEST: ON' : 'AUTO-HARVEST: OFF'}
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto pr-2 space-y-4 custom-scrollbar">
            {zombies.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-textMuted text-xs space-y-4 opacity-50 uppercase tracking-widest font-mono">
                <div className="w-12 h-12 border border-dashed border-white/20 rounded-full animate-spin duration-[10s]" />
                <span>Scanning for zombie nodes...</span>
              </div>
            ) : (
              zombies.map(server => (
                <div key={server.id} className="relative group bg-card border border-white/5 rounded-xl p-5 transition-all hover:bg-white/[0.02] hover:border-white/10">
                  <div className="flex justify-between items-start">
                    <div className="space-y-1">
                      <div className="text-xs font-bold text-textMain uppercase tracking-wider">{server.id} <span className="text-textMuted/40 text-[10px] ml-2">[{server.rack}]</span></div>
                      <div className="text-[10px] text-textMuted font-mono opacity-60">CPU: {server.cpu_util.toFixed(1)}% · RAM: {server.ram_util.toFixed(1)}%</div>
                      <div className="text-[10px] text-accent-red font-mono font-bold tracking-tight bg-accent-red/5 px-2 py-0.5 rounded mt-2 inline-block">WASTE: {server.watts_idle} WATTS</div>
                    </div>
                    <button
                      onClick={() => consolidateIdleServers().catch((err) => console.error('consolidate failed:', err))}
                      className="bg-card hover:bg-accent-green text-textMain hover:text-black border border-white/10 hover:border-accent-green text-[10px] px-3 py-1.5 rounded-lg transition-all font-bold uppercase tracking-widest"
                    >
                      Harvest
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
        
      </div>
    </div>
  );
}
