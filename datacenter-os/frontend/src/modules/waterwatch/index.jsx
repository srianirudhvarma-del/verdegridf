import React, { useEffect, useState } from 'react';
import { getSnapshot, subscribe } from '../../data/mock/waterFlow';
import ModuleHeader from '../../components/shared/ModuleHeader';
import MetricCard from '../../components/shared/MetricCard';
import AlertBadge from '../../components/shared/AlertBadge';

export default function WaterWatch() {
  const [data, setData] = useState(() => getSnapshot());
  const [reportOpen, setReportOpen] = useState(false);

  useEffect(() => {
    const unsub = subscribe((newData) => {
      setData({ ...newData });
    }, 5000);
    return unsub;
  }, []);

  if (!data?.units) return null;

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-start mb-10">
        <ModuleHeader 
          title="WaterWatch" 
          subtitle="Statistical processing — Z-Score Anomaly Detection (σ > 2.5)" 
          moduleName="WaterWatch"
        />
        <button 
          onClick={() => setReportOpen(!reportOpen)}
          className="relative z-10 bg-card border border-borderC text-textMuted hover:text-textMain hover:bg-white/10 hover:border-borderC px-6 py-2.5 rounded-lg text-[10px] font-bold transition-all uppercase tracking-[0.2em]"
        >
          {reportOpen ? 'Close System Analysis' : 'Generate Fluid Report'}
        </button>
      </div>

      {reportOpen && (
        <div className="glass-panel p-8 rounded-2xl mb-10 animate-in zoom-in-95 duration-300">
          <div className="razor-border" />
          <h3 className="text-sm font-bold text-textMain uppercase tracking-widest mb-4 flex items-center">
             <div className="w-2 h-2 rounded-full bg-accent-green mr-3 animate-pulse" />
             Sub-surface Leakage Diagnosis
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-[11px] text-textMuted font-mono uppercase tracking-wider leading-loose">
            <div className="space-y-2 opacity-80">
              <p>Current WUE Vector: <span className="text-textMain">{data.wue.toFixed(2)} L/kWh</span></p>
              <p>Theoretical Baseline: <span className="text-accent-green">1.80 L/kWh</span></p>
              <p>Variance Detected: <span className={data.wue > 1.8 ? 'text-accent-red font-bold' : 'text-accent-green'}>{(data.wue - 1.8).toFixed(2)} ΔL/kWh</span></p>
            </div>
            <div className="bg-card p-4 rounded-lg border border-borderC space-y-4">
              <div className="text-textMain font-bold">Recommended Mitigation:</div>
              <ul className="space-y-2 opacity-60">
                 <li>· PRESSURE-CHECK CHILLER LOOPS ON RACKS [A1, B4]</li>
                 <li>· EXECUTE PUMP FREQUENCY RE-ALIGNMENT</li>
                 <li>· RESET SECONDARY VALVE THRESHOLDS</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Top row metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
        <MetricCard 
          title="CURRENT GLOBAL WUE" 
          value={data.wue.toFixed(2)} 
          unit="L/kWh" 
          statusColor={data.wue > 2.0 ? 'text-accent-red' : 'text-textMain'} 
        />
        <MetricCard 
          title="ACTIVE CHILLERS" 
          value={data.units.length} 
        />
        <MetricCard 
          title="TOTAL FLOW RATE" 
          value={Math.round(data.totalFlow)} 
          unit="L/hr" 
        />
        <MetricCard 
          title="LEAK SUSPICIONS" 
          value={data.anomalies.length} 
          statusColor={data.anomalies.length > 0 ? 'text-accent-red' : 'text-textMain'} 
        />
      </div>

      {data.anomalies.map((a, i) => (
        <AlertBadge 
          key={i} 
          type="warning" 
          message={`Anomaly detected in ${a.rack}. Abnormal flow rate: ${Math.round(a.val)} L/hr. Potential loop leak.`} 
        />
      ))}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-10 mt-10">
        {/* Left: Flow Heatmap */}
        <div className="glass-panel p-8 rounded-2xl flex flex-col min-h-[500px]">
          <div className="razor-border" />
          <h3 className="text-sm font-sans font-light text-textMain tracking-[0.2em] uppercase mb-10 border-b border-borderC pb-6">
            Cooling Matrix <span className="text-textMuted opacity-30 text-[10px] lowercase tracking-normal ml-3">Fluid Loop Dynamic Vectors</span>
          </h3>
          
          <div className="flex-1 grid grid-cols-2 lg:grid-cols-5 gap-8">
            {data.units.map(u => {
              let waterColor = '#00FF41'; // Phosphor Green
              let statusClass = 'text-accent-green';
              if (u.flow_rate_lph > 2500) { waterColor = '#ff3333'; statusClass = 'text-accent-red animate-pulse'; }
              else if (u.flow_rate_lph > 1500) { waterColor = '#FFB800'; statusClass = 'text-accent-amber'; }

              const pct = Math.min(100, Math.max(8, (u.flow_rate_lph / 3500) * 100));

              return (
                <div key={u.id} className="flex flex-col items-center group scanline-hover cursor-crosshair">
                  {/* Glass Cylinder */}
                  <div className="relative w-full aspect-[1/3] border border-borderC rounded-full overflow-hidden flex items-end shadow-inner bg-background p-0.5">
                    <div className="absolute inset-0 bg-gradient-to-b from-white/5 via-transparent to-transparent pointer-events-none z-20" />
                    
                    {/* Interior Scale Marks */}
                    <div className="absolute left-1/2 -translate-x-1/2 top-0 h-full w-[1px] bg-white/[0.03] z-10 flex flex-col justify-between py-6">
                       {[...Array(6)].map((_, idx) => <div key={idx} className="w-2 h-px bg-white/20 -translate-x-[50%]" />)}
                    </div>

                    {/* Fluid Level */}
                    <div 
                      className="w-full transition-all duration-1000 ease-in-out relative origin-bottom rounded-full"
                      style={{ height: `${pct}%`, backgroundColor: waterColor, opacity: 0.3 }}
                    >
                      {/* Fluid Surface Surface */}
                      <div className="absolute top-0 left-0 w-full h-[6px] bg-white/40 blur-sm"></div>
                      {/* Fluid Gradient Glow */}
                      <div className="absolute inset-0 bg-gradient-to-t from-transparent via-white/5 to-white/10" />
                    </div>
                  </div>

                  <div className="mt-4 text-center">
                    <div className="text-[10px] font-mono text-textMuted uppercase tracking-widest opacity-40 mb-1">{u.id}</div>
                    <div className={`text-xl metric-text font-bold ${statusClass}`}>
                      {Math.round(u.flow_rate_lph)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Industry Benchmarks */}
        <div className="glass-panel p-8 rounded-2xl flex flex-col border-borderC">
          <div className="razor-border" />
          <h3 className="text-sm font-sans font-light text-textMain tracking-[0.2em] uppercase mb-10 border-b border-borderC pb-6">
            WUE Benchmark Index
          </h3>
          
          <div className="space-y-10">
            <div className="w-full group">
              <div className="flex justify-between text-[10px] text-textMuted mb-3 font-mono uppercase tracking-widest opacity-50 group-hover:opacity-100 transition-opacity">
                <span>Big Tech Avg [Baseline]</span>
                <span className="text-textMain">1.1 L/kWh</span>
              </div>
              <div className="h-1 w-full bg-borderC rounded-full overflow-hidden">
                <div className="h-full bg-accent-green opacity-40" style={{ width: '25%' }} />
              </div>
            </div>

            <div className="w-full group">
              <div className="flex justify-between text-[10px] text-textMuted mb-3 font-mono uppercase tracking-widest opacity-50 group-hover:opacity-100 transition-opacity">
                <span>Physical Site Vector</span>
                <span className="text-accent-violet font-bold accent-glow">{data.wue.toFixed(2)} L/kWh</span>
              </div>
              <div className="h-1 w-full bg-borderC rounded-full overflow-hidden">
                <div className="h-full bg-accent-violet shadow-[0_0_10px_#6200EE] transition-all duration-[1.5s]" style={{ width: `${Math.min(100, (data.wue/4)*100)}%` }} />
              </div>
            </div>

            <div className="w-full group">
              <div className="flex justify-between text-[10px] text-textMuted mb-3 font-mono uppercase tracking-widest opacity-50 group-hover:opacity-100 transition-opacity">
                <span>Standard Datacenter</span>
                <span className="text-textMain">1.8 L/kWh</span>
              </div>
              <div className="h-1 w-full bg-borderC rounded-full overflow-hidden">
                <div className="h-full bg-accent-amber opacity-40" style={{ width: '45%' }} />
              </div>
            </div>

            <div className="w-full group">
              <div className="flex justify-between text-[10px] text-textMuted mb-3 font-mono uppercase tracking-widest opacity-50 group-hover:opacity-100 transition-opacity">
                <span>Critical Threshold</span>
                <span className="text-textMain">3.0+ L/kWh</span>
              </div>
              <div className="h-1 w-full bg-borderC rounded-full overflow-hidden">
                <div className="h-full bg-accent-red opacity-40" style={{ width: '75%' }} />
              </div>
            </div>
          </div>
          
          <div className="mt-auto pt-10 text-[10px] font-mono text-textMuted/30 leading-relaxed uppercase tracking-tighter">
             PUE / WUE CORRELATION: POSITIVE <br/>
             THERMAL EXHAUST RECOVERY: ACTIVE <br/>
             LOOP PRESSURE: 42 PSI [NOMINAL]
          </div>
        </div>
      </div>
    </div>
  );
}
