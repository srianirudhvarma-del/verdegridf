import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Zap, CheckCircle2 } from 'lucide-react';
import ModuleHeader from '../../components/shared/ModuleHeader';
import MetricCard from '../../components/shared/MetricCard';
import { getCarbonIntensity, getJobQueue, deferJob, runJobNow } from '../../services/carbonclockApi';
import { useLiveResource } from '../../hooks/useLiveResource';

// ─── Number ticker ────────────────────────────────────────────────────────

function useTicker(value) {
  const [display, setDisplay] = useState(value);
  const ref = useRef(value);
  useEffect(() => {
    const diff = value - ref.current;
    if (diff === 0) return;
    const steps = 20;
    let i = 0;
    const start = ref.current;
    const iv = setInterval(() => {
      i++;
      setDisplay(start + (diff * i) / steps);
      if (i >= steps) { clearInterval(iv); ref.current = value; }
    }, 30);
    return () => clearInterval(iv);
  }, [value]);
  return display;
}

// ─── Auto-dismiss banner ──────────────────────────────────────────────────

function Banner({ message, color, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 5000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  const isOrange = color === 'orange';
  return (
    <div
      className="mb-4 px-5 py-3 rounded-xl flex items-center gap-3 text-sm font-medium"
      style={{ background: isOrange ? '#f97316' : '#10b981', color: '#000', animation: 'slideDown 0.4s ease' }}
    >
      {isOrange ? <Zap size={16} /> : <CheckCircle2 size={16} />}
      {message}
      <style>{`@keyframes slideDown { from { opacity:0; transform:translateY(-8px); } to { opacity:1; transform:translateY(0); } }`}</style>
    </div>
  );
}

// ─── Timeline chart (inline SVG area chart) ───────────────────────────────

function TimelineChart({ history }) {
  if (!history.length) return null;
  const W = 600, H = 120, PAD = 12;
  const vals = history.map(h => h.intensity);
  const min = Math.min(150, ...vals);
  const max = Math.max(500, ...vals);
  const xStep = (W - PAD * 2) / Math.max(history.length - 1, 1);

  const toX = i => PAD + i * xStep;
  const toY = v => PAD + ((max - v) / (max - min)) * (H - PAD * 2);
  const threshold = toY(300);

  const linePath = history.map((h, i) => `${i === 0 ? 'M' : 'L'} ${toX(i)} ${toY(h.intensity)}`).join(' ');
  const areaPath = `${linePath} L ${toX(history.length - 1)} ${H - PAD} L ${toX(0)} ${H - PAD} Z`;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H }} preserveAspectRatio="none">
        <line x1={PAD} y1={threshold} x2={W - PAD} y2={threshold} stroke="#f97316" strokeDasharray="4,3" strokeWidth={1} opacity={0.5} />
        <text x={W - PAD - 2} y={threshold - 3} fontSize="9" fill="#f97316" textAnchor="end" opacity={0.6}>300 g/kWh threshold</text>
        <defs>
          <clipPath id="clipGreen"><rect x={PAD} y={threshold} width={W - PAD * 2} height={H - threshold} /></clipPath>
          <clipPath id="clipRed"><rect x={PAD} y={PAD} width={W - PAD * 2} height={threshold - PAD} /></clipPath>
        </defs>
        <path d={areaPath} fill="#10b981" fillOpacity={0.2} clipPath="url(#clipGreen)" />
        <path d={areaPath} fill="#ef4444" fillOpacity={0.2} clipPath="url(#clipRed)" />
        <path d={linePath} fill="none" stroke="#f0b429" strokeWidth={1.5} />
      </svg>
    </div>
  );
}

// ─── Main CarbonClock component ───────────────────────────────────────────

export default function CarbonClock() {
  const intensityFetcher = useCallback(() => getCarbonIntensity(), []);
  const [intensitySnapshot] = useLiveResource(intensityFetcher, 15000);

  const jobsFetcher = useCallback(() => getJobQueue(), []);
  const [jobs, refreshJobs] = useLiveResource(jobsFetcher, 15000);

  const [history, setHistory] = useState([]);
  const [banner, setBanner] = useState(null);
  const prevSpike = useRef(false);

  const ci = intensitySnapshot?.intensity ?? 0;
  const trend = intensitySnapshot ? (intensitySnapshot.trend === 'rising' ? 1 : intensitySnapshot.trend === 'falling' ? -1 : 0) : 0;
  const isSpike = intensitySnapshot?.isSpike ?? false;
  const minutesUntilClean = intensitySnapshot?.minutesUntilClean ?? 0;
  const displayCi = useTicker(ci);

  // Real-intensity history for the timeline chart.
  useEffect(() => {
    if (!intensitySnapshot) return;
    setHistory((prev) => [...prev.slice(-119), { time: Date.now(), intensity: intensitySnapshot.intensity }]);
  }, [intensitySnapshot]);

  // Banner on real spike transitions (the real dirty-grid signal, not a client-side threshold guess).
  useEffect(() => {
    if (isSpike && !prevSpike.current) {
      setBanner({ message: `⚡ Grid intensity spike detected — deferrable jobs should be held back`, color: 'orange' });
    } else if (!isSpike && prevSpike.current) {
      setBanner({ message: `✓ Grid intensity normalized`, color: 'green' });
    }
    prevSpike.current = isSpike;
  }, [isSpike]);

  let statusColor = 'text-green-400';
  let statusText = 'CLEAN — ideal execution';
  if (ci > 200 && ci <= 300) { statusColor = 'text-yellow-400'; statusText = 'MODERATE — ready to run'; }
  else if (ci > 300 && ci <= 400) { statusColor = 'text-orange-400'; statusText = 'HIGH — defer if possible'; }
  else if (ci > 400) { statusColor = 'text-red-400'; statusText = 'CRITICAL — deferring all'; }

  const jobList = jobs || [];
  const deferredJobs = jobList.filter((j) => j.status === 'deferred');
  // Illustrative CO2-avoided figure computed on real fetched data (real
  // intensity above the green threshold, real deferred jobs' kwh) -- not
  // a fabricated running counter.
  const co2Avoided = isSpike
    ? deferredJobs.reduce((acc, j) => acc + (j.est_kwh || 0) * Math.max(0, ci - 300) / 1_000_000, 0)
    : 0;
  const displayCo2 = useTicker(co2Avoided);

  const handleDefer = async (jobId) => {
    try {
      await deferJob(jobId, 2);
      refreshJobs();
    } catch (err) {
      console.error('defer failed:', err);
    }
  };

  const handleRun = async (jobId) => {
    try {
      await runJobNow(jobId);
      refreshJobs();
    } catch (err) {
      console.error('run now failed:', err);
    }
  };

  if (!intensitySnapshot || !jobs) return null;

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-start mb-10">
        <ModuleHeader
          title="CarbonClock"
          subtitle="Adaptive Workload Scheduling & Grid Intensity Synchronization"
          moduleName="CarbonClock"
        />
      </div>

      {banner && (
        <Banner message={banner.message} color={banner.color} onDismiss={() => setBanner(null)} />
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        <MetricCard
          title={() => (
            <div className="flex justify-between items-center w-full">
              <span>GRID INTENSITY</span>
              <span className={`text-[8px] animate-pulse font-mono tracking-widest border px-1 rounded ${isSpike ? 'text-red-400 border-red-400/30' : 'text-green-400 border-green-400/30'}`}>
                {isSpike ? 'SPIKE' : 'LIVE'}
              </span>
            </div>
          )}
          value={Math.round(displayCi)}
          unit="gCO₂ / kWh"
          statusColor={statusColor}
        />
        <MetricCard title="DEFERRED WORKLOADS" value={deferredJobs.length} unit="jobs" statusColor={deferredJobs.length > 0 ? 'text-orange-400' : 'text-textMuted'} />
        <div className="glass-panel p-6 rounded-2xl border-borderC">
          <div className="razor-border" />
          <div className="text-[10px] font-mono font-bold text-textMuted uppercase tracking-[0.2em] mb-4 opacity-50">CO₂ AVOIDED (EST.)</div>
          <div className="text-4xl metric-text text-green-400 accent-glow">
            {displayCo2.toFixed(4)} <span className="text-xs font-mono text-green-400/40 ml-1">kg CO₂</span>
          </div>
          {minutesUntilClean > 0 && (
            <div className="text-[10px] font-mono text-orange-400 mt-2 opacity-70">
              ~{minutesUntilClean}m until clean window
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 mb-12">
        <div className="lg:col-span-1 space-y-6">
          <div className="glass-panel p-10 rounded-2xl flex flex-col items-center justify-center text-center relative overflow-hidden animate-breath border-borderC">
            <div className="razor-border" />
            <h3 className="text-[10px] font-mono font-bold text-textMuted/50 uppercase tracking-[0.3em] mb-10 w-full text-left">Carbon Intensity Gauge</h3>
            <div className="relative mb-8">
              <div className={`text-9xl font-sans font-thin tracking-tighter drop-shadow-2xl relative z-10 transition-all duration-1000 ${statusColor}`}>{Math.round(displayCi)}</div>
              <div className="text-[11px] font-mono text-textMuted/40 tracking-[0.4em] uppercase mt-2">
                gCO₂/kWh · IN-SO · {trend > 0 ? '↑ rising' : trend < 0 ? '↓ falling' : '→ stable'}
              </div>
            </div>
            <div className={`mt-8 text-[11px] font-mono font-bold px-8 py-3 rounded-full border border-borderC ${statusColor} bg-white/[0.02] uppercase tracking-[0.2em] transition-all`}>
              <span className="opacity-40 font-normal mr-2">// STATUS //</span> {statusText}
            </div>
          </div>

          <div className="glass-panel p-6 rounded-2xl border-borderC">
            <div className="razor-border" />
            <h3 className="text-[10px] font-mono font-bold text-textMuted/50 uppercase tracking-[0.2em] mb-4">Intensity Timeline (live)</h3>
            <TimelineChart history={history} />
          </div>
        </div>

        <div className="glass-panel p-8 rounded-2xl flex flex-col h-full border-borderC">
          <div className="razor-border" />
          <h3 className="text-sm font-sans font-light text-textMain tracking-[0.2em] uppercase mb-10 border-b border-borderC pb-6 flex justify-between items-center">
            <span>Adaptive Schedule Queue</span>
            <span className="text-[10px] font-mono text-textMuted opacity-50 lowercase tracking-normal italic">{jobList.length} jobs</span>
          </h3>

          <div className="flex-1 overflow-y-auto space-y-4 custom-scrollbar pr-2">
            {jobList.map((j) => (
              <div key={j.id} className="bg-card border border-borderC p-5 rounded-xl transition-all hover:bg-white/[0.05]">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-mono text-textMain font-bold uppercase tracking-tighter">{j.name}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                    j.status === 'running' ? 'bg-purple-600 text-white' :
                    j.status === 'deferred' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40 animate-pulse' :
                    j.status === 'scheduled' ? 'bg-green-500 text-black' :
                    'bg-card text-textMuted opacity-50'
                  }`}>
                    {j.status}
                  </span>
                </div>
                {j.deferrable && j.status !== 'running' && (
                  <div className="flex justify-end gap-2 mt-2">
                    <button onClick={() => handleDefer(j.id)} className="text-[9px] font-mono px-2 py-1 rounded border border-orange-500/40 text-orange-400 hover:bg-orange-500/10">Defer</button>
                    <button onClick={() => handleRun(j.id)} className="text-[9px] font-mono px-2 py-1 rounded border border-green-500/40 text-green-400 hover:bg-green-500/10">Run Now</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="glass-panel p-10 rounded-2xl border-borderC">
        <div className="razor-border" />
        <h3 className="text-sm font-sans font-light text-textMain tracking-[0.2em] uppercase mb-10 border-b border-borderC pb-6">Workload Allocation Map</h3>
        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-left text-[11px] text-textMuted font-mono uppercase tracking-wider">
            <thead className="bg-card text-textMain opacity-40">
              <tr>
                <th className="p-6 font-bold tracking-[0.2em]">Asset</th>
                <th className="p-6 font-bold tracking-[0.2em]">Category</th>
                <th className="p-6 font-bold tracking-[0.2em] text-right">Duration</th>
                <th className="p-6 font-bold tracking-[0.2em] text-right">Energy</th>
                <th className="p-6 font-bold tracking-[0.2em] text-center">Deferrable</th>
                <th className="p-6 font-bold tracking-[0.2em] text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {jobList.map((j) => (
                <tr key={j.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-6 font-bold text-textMain">{j.name}</td>
                  <td className="p-6 opacity-60 italic">{j.type}</td>
                  <td className="p-6 text-right opacity-60">{j.duration_mins || '∞'} MIN</td>
                  <td className="p-6 text-right opacity-60 text-green-400/80 font-bold">{j.est_kwh} KWH</td>
                  <td className="p-6 text-center">{j.deferrable ? <span className="text-green-400">TRUE</span> : <span className="opacity-20">—</span>}</td>
                  <td className="p-6 text-right">
                    <span className={`px-4 py-2 rounded-lg font-bold text-[9px] tracking-[0.1em]
                      ${j.status === 'running' ? 'bg-purple-600 text-white' : ''}
                      ${j.status === 'deferred' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40 animate-pulse' : ''}
                      ${j.status === 'scheduled' || j.status === 'pending' ? 'bg-card text-textMuted opacity-50' : ''}
                    `}>
                      {j.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
