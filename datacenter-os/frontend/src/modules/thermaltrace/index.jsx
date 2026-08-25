import React, { useEffect, useState } from 'react';
import { getSnapshot, subscribe } from '../../data/mock/thermalSensors';
import ModuleHeader from '../../components/shared/ModuleHeader';
import MetricCard from '../../components/shared/MetricCard';
import AlertBadge from '../../components/shared/AlertBadge';
import { Activity } from 'lucide-react';

export default function ThermalTrace() {
  const [data, setData] = useState(() => getSnapshot());
  const [showML, setShowML] = useState(false);
  const [hoveredCell, setHoveredCell] = useState(null);

  useEffect(() => {
    const unsub = subscribe((newData) => {
      setData({ ...newData });
    }, 5000);
    return unsub;
  }, []);

  if (!data?.grid) return null;

  // Compute metrics
  let maxTemp = 0;
  let totalTemp = 0;
  let hotspots = [];
  let alertCells = [];

  data.grid.forEach(row => {
    row.forEach(cell => {
      if (cell.inlet_temp > maxTemp) maxTemp = cell.inlet_temp;
      totalTemp += cell.inlet_temp;
      if (cell.inlet_temp > 32) hotspots.push(cell);
      
      if (cell.inlet_temp > 32 || (cell.outlet_temp - cell.inlet_temp) > 15) {
        alertCells.push(cell);
      }
    });
  });
  const avgTemp = totalTemp / 64;

  const getCellColor = (temp, isPredicted = false) => {
    // Add fake temp if ML predicted (slightly worse temp if > 28)
    const t = isPredicted ? temp + (temp > 28 ? 1.5 : 0.5) : temp;
    if (t < 20) return '#3b82f6';
    if (t < 24) return '#06b6d4';
    if (t < 28) return '#eab308';
    if (t < 32) return '#f97316';
    return '#ef4444';
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-start mb-10">
        <ModuleHeader 
          title="ThermalTrace" 
          subtitle="Real-time thermal topology — marginal heat-mitigation vector"
          moduleName="ThermalTrace"
        />
        <div className="flex items-center space-x-6">
          <div className="text-right hidden sm:block">
            <div className="text-[10px] font-mono text-textMuted/40 uppercase tracking-[0.2em] mb-1">PROGNOSTIC ENGINE</div>
            <div className="text-[11px] font-mono text-accent-violet font-bold uppercase tracking-widest">LSTM-v4 Active</div>
          </div>
          <button 
             onClick={() => setShowML(!showML)}
             className={`relative h-10 w-24 rounded-full border transition-all duration-500 p-1 flex items-center ${showML ? 'bg-accent-violet/20 border-accent-violet shadow-[0_0_15px_#6200EE]' : 'bg-card border-white/10'}`}
          >
            <div className={`h-full aspect-square rounded-full transition-all duration-500 flex items-center justify-center ${showML ? 'translate-x-14 bg-accent-violet text-textMain shadow-[0_0_10px_#6200EE]' : 'translate-x-0 bg-white/20 text-white/40'}`}>
              <Activity size={14} className={showML ? 'animate-pulse' : ''} />
            </div>
            <span className={`absolute ${showML ? 'left-4' : 'right-4'} text-[9px] font-bold uppercase tracking-widest text-textMain/40 pointer-events-none`}>
              {showML ? 'ON' : 'OFF'}
            </span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <MetricCard 
          title="MAX INLET TEMP" 
          value={maxTemp.toFixed(1)} unit="°C" 
          statusColor={maxTemp > 32 ? 'text-accent-red' : 'text-textMain'} 
        />
        <MetricCard title="AVG INLET TEMP" value={avgTemp.toFixed(1)} unit="°C" />
        <MetricCard 
          title="HOTSPOT CELLS" 
          value={hotspots.length} 
          statusColor={hotspots.length > 0 ? 'text-accent-red' : 'text-textMain'}
        />
      </div>

      {alertCells.length > 0 && (
        <div className="mb-6 space-y-2 max-h-32 overflow-y-auto custom-scrollbar">
          {alertCells.map((c, i) => (
            <AlertBadge 
              key={i} 
              type="warning" 
              message={`Excessive temperature delta in cell-${c.row}-${c.col}: ${(c.outlet_temp - c.inlet_temp).toFixed(1)}°C (inlet: ${c.inlet_temp.toFixed(1)}°C, outlet: ${c.outlet_temp.toFixed(1)}°C)`} 
            />
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
        {/* Left: Isometric Heatmap */}
        <div className="lg:col-span-2 glass-panel p-12 rounded-2xl flex flex-col items-center min-h-[600px] overflow-hidden">
          <div className="razor-border" />
          <h3 className="text-sm font-sans font-light text-textMain tracking-[0.2em] uppercase mb-16 border-b border-borderC pb-6 w-full">
            Topographic Heat Vector <span className="text-textMuted opacity-30 text-[10px] lowercase tracking-normal ml-3">8x8 Cluster Perspective</span>
          </h3>
          
          <div className="perspective-[1000px] mt-10">
            <div 
              className="grid grid-cols-8 gap-2 w-[480px] aspect-square rotate-x-[55deg] rotate-z-[45deg] transition-all duration-1000 transform-gpu bg-card p-4 rounded-xl border border-borderC shadow-[0_50px_100px_rgba(0,0,0,0.8)]"
              style={{ transformStyle: 'preserve-3d' }}
            >
              {data.grid.flat().map((c, i) => {
                 const t = showML ? c.inlet_temp + (c.inlet_temp > 28 ? 1.5 : 0.5) : c.inlet_temp;
                 const color = t < 20 ? 'var(--accent-cyan)' : t < 24 ? 'var(--accent-green)' : t < 28 ? 'var(--accent-gold)' : t < 32 ? '#f97316' : 'var(--accent-red)';
                 const isPredictedAlert = showML && t > 32;

                 return (
                   <div 
                     key={i}
                     onMouseEnter={() => setHoveredCell({ ...c, predicted: t })}
                     onMouseLeave={() => setHoveredCell(null)}
                     className={`w-full aspect-square rounded-[2px] transition-all duration-1000 ease-in-out cursor-crosshair relative transform-gpu hover:translate-z-8 hover:shadow-[0_0_20px_white]
                       ${isPredictedAlert ? 'animate-pulse shadow-[0_0_15px_#ff3333]' : ''}
                     `}
                     style={{ 
                        backgroundColor: color,
                        boxShadow: `0 0 10px ${color}33`,
                        transform: `translateZ(${t * 0.8}px)`,
                        transformStyle: 'preserve-3d'
                     }}
                   >
                      {/* Vertical side of the 3D pillar (fake) */}
                      <div className="absolute top-0 right-0 h-full w-[2px] bg-background/60 origin-right rotate-y-90 pointer-events-none" style={{ height: `${t * 0.8}px` }} />
                   </div>
                 )
              })}
            </div>
          </div>

          {/* Holographic Tooltip */}
          {hoveredCell && (
            <div className="absolute bottom-10 right-10 glass-panel p-6 rounded-xl border-accent-green/30 animate-in fade-in zoom-in duration-300 z-50">
              <div className="razor-border" />
              <div className="text-[10px] font-mono font-bold text-accent-green mb-3 uppercase tracking-widest flex items-center">
                 <div className="w-1.5 h-1.5 bg-accent-green rounded-full mr-2 animate-ping" />
                 SENS-POINT {hoveredCell.row}:{hoveredCell.col}
              </div>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <div className="text-[9px] text-textMuted opacity-50 uppercase tracking-tighter mb-1">REAL-TIME</div>
                  <div className="text-2xl font-sans font-light text-textMain">{hoveredCell.inlet_temp.toFixed(1)}°C</div>
                </div>
                {showML && (
                  <div>
                    <div className="text-[9px] text-accent-violet opacity-50 uppercase tracking-tighter mb-1">PROGNOSIS</div>
                    <div className="text-2xl font-sans font-light text-accent-violet">{hoveredCell.predicted.toFixed(1)}°C</div>
                  </div>
                )}
              </div>
              <div className="mt-4 pt-4 border-t border-borderC flex justify-between items-center text-[10px] font-mono">
                 <span className="text-textMuted opacity-40 uppercase">∆ GRADIENT</span>
                 <span className="text-textMain">{(hoveredCell.outlet_temp - hoveredCell.inlet_temp).toFixed(1)}°C</span>
              </div>
            </div>
          )}
        </div>

        {/* Right: Legend and ML */}
        {/* Right: Legend and ML */}
        <div className="flex flex-col space-y-6">
          <div className="glass-panel p-8 rounded-2xl border-borderC">
             <div className="razor-border" />
             <h3 className="text-[10px] font-mono font-bold text-textMuted/50 uppercase tracking-[0.2em] mb-6">Thermal Palette</h3>
             <div className="space-y-4 text-[11px] font-mono text-textMuted/70 uppercase tracking-widest">
               <div className="flex items-center group transition-all hover:translate-x-1"><div className="w-2.5 h-2.5 bg-accent-cyan rounded-full mr-4 shadow-[0_0_10px_var(--accent-cyan)]" /> &lt; 20°C [CRYO]</div>
               <div className="flex items-center group transition-all hover:translate-x-1"><div className="w-2.5 h-2.5 bg-accent-green rounded-full mr-4 shadow-[0_0_10px_var(--accent-green)]" /> 20 - 24°C [NOM]</div>
               <div className="flex items-center group transition-all hover:translate-x-1"><div className="w-2.5 h-2.5 bg-accent-gold rounded-full mr-4 shadow-[0_0_10px_var(--accent-gold)]" /> 24 - 28°C [MOD]</div>
               <div className="flex items-center group transition-all hover:translate-x-1"><div className="w-2.5 h-2.5 bg-orange-500 rounded-full mr-4 shadow-[0_0_10px_#f97316]" /> 28 - 32°C [HOT]</div>
               <div className="flex items-center group transition-all hover:translate-x-1"><div className="w-2.5 h-2.5 bg-accent-red rounded-full mr-4 shadow-[0_0_10px_var(--accent-red)] animate-pulse" /> &gt; 32°C [ALRT]</div>
             </div>
          </div>

          <div className="glass-panel p-8 rounded-2xl border-white/5 relative overflow-hidden group">
            <div className="razor-border" />
            <div className="absolute top-0 left-0 w-full h-1 bg-accent-violet/30" />
            <span className="inline-block bg-accent-violet/10 text-accent-violet border border-accent-violet/20 text-[9px] uppercase font-bold px-3 py-1 rounded-full mb-4 tracking-[0.2em]">
              Prediction Engine
            </span>
            <p className="text-[11px] text-textMuted uppercase leading-relaxed font-mono tracking-tight opacity-60">
              LSTM-V4 Prognostic Engine analyzes historical thermal drift to predict hotspot formation 15m in advance. <br/><br/>
              Status: <span className="text-accent-green">Active</span><br/>
              Confidence: <span className="text-textMain">98.2%</span>
            </p>
          </div>
          
          <div className="mt-auto bg-background/40 p-6 rounded-2xl text-[9px] font-mono text-textMuted border border-borderC uppercase tracking-tighter leading-relaxed">
            {`// SYSTEM ADVISORY:
// COOLING FAN SPEED @ 85%
// CHILLER DELTA: 12.4°C
// RACK HUMIDITY: 42% [NOMINAL]`}
          </div>
        </div>
      </div>
    </div>
  );
}
