import React, { useEffect, useState, useRef } from 'react';
import * as d3 from 'd3';
import { getSnapshot, subscribe, injectSpike } from '../../data/mock/networkTraffic';
import ModuleHeader from '../../components/shared/ModuleHeader';
import MetricCard from '../../components/shared/MetricCard';
import AlertBadge from '../../components/shared/AlertBadge';
import { Activity, Zap, Clock } from 'lucide-react';

export default function LightSpeed({ isDeferralActive }) {
  const [data, setData] = useState(() => getSnapshot());
  const svgRef = useRef(null);

  useEffect(() => {
    const unsub = subscribe((newData) => {
      setData({ ...newData });
    }, 4000);
    return unsub;
  }, []);

  useEffect(() => {
    if (!svgRef.current || !data?.nodes) return;
    
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    
    // Inject flow animation keyframes
    svg.append('defs')
      .append('style')
      .text(`
        @keyframes flowAnimation {
          from { stroke-dashoffset: 100; }
          to   { stroke-dashoffset: 0; }
        }
      `);

    const width = 500;
    const height = 400;

    const nodes = data.nodes.map(d => ({ id: d }));
    const links = data.links.map(d => ({ ...d }));

    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2));

    const link = svg.append('g')
      .selectAll('line')
      .data(links)
      .enter().append('line')
      .attr('stroke', d => {
        if (isDeferralActive) return 'rgba(255,165,0,0.8)';
        if (d.utilization_pct > 80) return '#ef4444';
        if (d.utilization_pct > 60) return '#f97316';
        return '#10b981';
      })
      .attr('stroke-width', d => Math.max(1.5, (d.utilization_pct / 100) * 3.5))
      .attr('stroke-dasharray', d => d.utilization_pct > 80 ? '4,2' : '6,4')
      .attr('opacity', 0.75)
      .style('animation', d => {
        if (isDeferralActive) return 'flowAnimation 2s linear infinite';
        if (d.utilization_pct > 80) return 'flowAnimation 0.8s linear infinite';
        if (d.utilization_pct > 60) return 'flowAnimation 1.5s linear infinite';
        return 'flowAnimation 3s linear infinite';
      });

    const node = svg.append('g')
      .selectAll('circle')
      .data(nodes)
      .enter().append('circle')
      .attr('r', 12)
      .attr('fill', 'var(--sidebar-bg)')
      .attr('stroke', isDeferralActive ? 'rgba(255, 165, 0, 1)' : 'var(--accent-violet)')
      .attr('stroke-width', 2)
      .attr('class', 'animate-pulse');

    const labels = svg.append('g')
      .selectAll('text')
      .data(nodes)
      .enter().append('text')
      .text(d => d.id)
      .attr('font-size', '8px')
      .attr('font-family', 'IBM Plex Mono')
      .attr('fill', 'var(--text-main)')
      .attr('opacity', 0.6)
      .attr('text-anchor', 'middle')
      .attr('dy', 22);

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);

      labels
        .attr('x', d => d.x)
        .attr('y', d => d.y);
    });

    return () => simulation.stop();
  }, [data, isDeferralActive]); // Re-render svg on data or target deferral change

  if (!data?.links) return null;

  const maxUtil = Math.max(...data.links.map(l => l.utilization_pct));
  const bottlenecks = data.links.filter(l => l.utilization_pct > 80);

  return (
    <div className="animate-in fade-in duration-500 pb-10">
      <div className="flex justify-between items-start mb-10">
        <ModuleHeader 
          title="LightSpeed" 
          subtitle="Network map and traffic management"
          moduleName="LightSpeed"
        />
        <button 
          onClick={injectSpike}
          className="relative z-10 bg-card border border-borderC text-textMuted hover:text-textMain hover:bg-white/5 hover:border-borderC px-6 py-2.5 rounded-lg text-[10px] font-bold transition-all uppercase tracking-[0.2em] flex items-center group"
        >
          <Zap className="w-3 h-3 mr-2 text-accent-gold group-hover:animate-pulse" />
          More Traffic
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <MetricCard 
          title="HIGHEST TRAFFIC" 
          value={maxUtil.toFixed(1)} 
          unit="%" 
          statusColor={maxUtil > 80 ? 'text-accent-red' : 'text-accent-green'} 
        />
        <MetricCard 
          title="SLOW CONNECTIONS" 
          value={bottlenecks.length} 
          statusColor={bottlenecks.length > 0 ? 'text-accent-red' : 'text-textMuted'} 
        />
        <MetricCard 
          title="ACTIVE MACHINES" 
          value={data.nodes.length} 
          unit="connected"
        />
      </div>

      {bottlenecks.length > 0 && (
        <AlertBadge 
          type="warning" 
          message={`${bottlenecks.length} connections are slow right now.`} 
        />
      )}

      {isDeferralActive && (
         <AlertBadge 
           type="info" 
           message="Carbon Deferral is active. Traffic has been shifted to Amber links to save power." 
         />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-10 mb-10 mt-4">
        <div className="lg:col-span-2 glass-panel p-10 rounded-2xl flex flex-col items-center min-h-[500px] border-borderC relative overflow-hidden">
          <div className="razor-border" />
          <h3 className="text-[10px] font-mono font-bold text-textMuted/50 uppercase tracking-[0.2em] mb-10 w-full text-left ml-4">Internet Usage Map</h3>
          
          <div className="flex-1 flex items-center justify-center w-full relative z-10 scale-110">
             <svg ref={svgRef} width="500" height="400" className="max-w-full overflow-visible drop-shadow-[0_0_30px_rgba(98,0,238,0.2)]" />
          </div>
          
          <div className="absolute bottom-6 right-8 text-[9px] font-mono text-textMuted/30 tracking-widest uppercase">
             // LIVE NETWORK MAP
          </div>
        </div>

        <div className="glass-panel p-8 rounded-2xl flex flex-col min-h-[500px] border-borderC">
          <div className="razor-border" />
          <h3 className="text-sm font-sans font-light text-textMain tracking-[0.2em] uppercase mb-10 border-b border-borderC pb-6">
             Alternative Paths
          </h3>
          
          <div className="flex-1 overflow-y-auto space-y-4 custom-scrollbar pr-2">
            {bottlenecks.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-textMuted text-[10px] space-y-4 opacity-50 uppercase tracking-widest font-mono">
                <div className="w-10 h-10 border border-dashed border-borderC rounded-full animate-ping duration-[4s]" />
                <span>No slow paths detected</span>
              </div>
            ) : bottlenecks.map((l, i) => (
              <div key={i} className="bg-card border border-borderC p-5 rounded-xl transition-all hover:bg-white/[0.05] group">
                <div className="flex justify-between items-start mb-3">
                  <div className="font-mono text-xs text-textMain group-hover:text-accent-violet transition-colors tracking-tighter uppercase">{l.source} → {l.target}</div>
                  <div className="text-accent-red font-mono text-[10px] font-bold">{l.utilization_pct.toFixed(1)}%</div>
                </div>
                <div className="h-[2px] w-full bg-borderC rounded-full overflow-hidden mb-4">
                   <div className="h-full bg-accent-red shadow-[0_0_10px_var(--accent-red)]" style={{ width: `${l.utilization_pct}%` }} />
                </div>
                <div className="text-[9px] text-accent-gold font-bold uppercase tracking-widest bg-accent-gold/10 px-2 py-1 rounded inline-block text-center w-full">
                  Suggestion: Try a different connection
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 pt-6 border-t border-borderC text-[10px] font-mono text-textMuted/40 uppercase tracking-widest leading-relaxed">
             Wait Time: 0.12ms <br/>
             Lost Data: Zero <br/>
             Connection Quality: Perfect
          </div>
        </div>
      </div>

      <div className="glass-panel p-10 rounded-2xl border-borderC">
        <div className="razor-border" />
        <h3 className="text-sm font-sans font-light text-textMain tracking-[0.2em] uppercase mb-10 border-b border-borderC pb-6">Traffic Breakdown</h3>
        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-left text-[11px] text-textMuted font-mono uppercase tracking-wider">
            <thead className="bg-card text-textMain opacity-40">
              <tr>
                <th className="p-6 font-bold tracking-[0.2em]">Start</th>
                <th className="p-6 font-bold tracking-[0.2em]">End</th>
                <th className="p-6 font-bold tracking-[0.2em] text-right">Max Speed</th>
                <th className="p-6 font-bold tracking-[0.2em]">Current Traffic</th>
                <th className="p-6 font-bold tracking-[0.2em] text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borderC">
              {data.links.map((l, i) => {
                let badgeClass = 'bg-accent-green text-black';
                let sText = 'Good';
                
                if (l.utilization_pct > 80) { badgeClass = 'bg-accent-red text-textMain'; sText = 'Too Busy'; }
                else if (l.utilization_pct > 60) { badgeClass = 'bg-accent-gold text-black'; sText = 'Heavy Traffic'; }

                return (
                  <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                    <td className="p-6 font-bold text-textMain uppercase tracking-normal">{l.source}</td>
                    <td className="p-6 font-bold text-textMain uppercase tracking-normal">{l.target}</td>
                    <td className="p-6 text-right opacity-60">{l.capacity_gbps} GBPS</td>
                    <td className="p-6 min-w-[240px]">
                      <div className="flex items-center space-x-4 w-full">
                        <div className="h-[2px] flex-1 bg-borderC rounded-full overflow-hidden">
                          <div className={`h-full transition-all duration-1000 ${badgeClass.split(' ')[0]}`} style={{ width: `${l.utilization_pct}%` }} />
                        </div>
                        <span className="font-mono w-[40px] text-right text-[10px] opacity-40">{l.utilization_pct.toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="p-6 text-right">
                      <span className={`px-4 py-2 rounded-lg font-bold text-[9px] tracking-[0.1em] ${badgeClass}`}>
                        {sText}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
