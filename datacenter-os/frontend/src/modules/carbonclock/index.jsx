import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Zap, CheckCircle2 } from 'lucide-react';
import ModuleHeader from '../../components/shared/ModuleHeader';
import MetricCard from '../../components/shared/MetricCard';

// ─── Time-of-day baseline (Indian Southern grid) ──────────────────────────

function getBaselineForHour(hour) {
  if (hour >= 22 || hour < 6) return 240;   // night — more wind
  if (hour < 9) return 290;                  // morning ramp
  if (hour < 19) return 335;                 // day peak
  return 385;                                // evening peak
}

// ─── Gaussian noise ───────────────────────────────────────────────────────

function gaussNoise(sigma = 15) {
  const u1 = Math.random(), u2 = Math.random();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2) * sigma;
}

// ─── useCarbonSimulation hook ─────────────────────────────────────────────

function useCarbonSimulation() {
  const [state, setState] = useState(() => {
    const hour = new Date().getHours();
    const base = getBaselineForHour(hour);
    return {
      intensity: base,
      trend: 0,
      isSpike: false,
      minutesUntilClean: null,
    };
  });

  const spikeRef = useRef({ active: false, remaining: 0, target: 0 });

  useEffect(() => {
    const tick = () => {
      const hour = new Date().getHours();
      const baseline = getBaselineForHour(hour);
      const spike = spikeRef.current;

      setState(prev => {
        let next;
        if (spike.active) {
          // Moving toward spike target
          next = prev.intensity + (spike.target - prev.intensity) * 0.4 + gaussNoise(5);
          spike.remaining--;
          if (spike.remaining <= 0) spike.active = false;
        } else {
          // Natural drift toward baseline
          next = prev.intensity + (baseline - prev.intensity) * 0.05 + gaussNoise(15);
        }
        next = Math.max(80, Math.min(500, next));
        const trend = next - prev.intensity;
        const minutesUntilClean = next > 300 ? Math.round((next - 300) / Math.abs(trend || 1) * 0.5) : null;
        return { intensity: Math.round(next), trend, isSpike: spike.active, minutesUntilClean };
      });
    };

    // Random spike events every 8–15 minutes
    let spikeTimer;
    const scheduleSpikeEvent = () => {
      const delayMs = (8 + Math.random() * 7) * 60 * 1000;
      spikeTimer = setTimeout(() => {
        spikeRef.current = { active: true, remaining: 3, target: 410 + Math.random() * 80 };
        scheduleSpikeEvent();
      }, delayMs);
    };
    scheduleSpikeEvent();

    const iv = setInterval(tick, 30000);
    return () => { clearInterval(iv); clearTimeout(spikeTimer); };
  }, []);

  const manualSpike = useCallback(() => {
    spikeRef.current = { active: true, remaining: 4, target: 460 };
    setState(p => ({ ...p, intensity: 420, isSpike: true }));
  }, []);

  return { ...state, manualSpike };
}

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
      style={{
        background: isOrange ? '#f97316' : '#10b981',
        color: '#000',
        animation: 'slideDown 0.4s ease',
      }}
    >
      {isOrange ? <Zap size={16} /> : <CheckCircle2 size={16} />}
      {message}
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

  // Split into clean/dirty segments for coloring
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H }} preserveAspectRatio="none">
        {/* Threshold line */}
        <line x1={PAD} y1={threshold} x2={W - PAD} y2={threshold} stroke="#f97316" strokeDasharray="4,3" strokeWidth={1} opacity={0.5} />
        <text x={W - PAD - 2} y={threshold - 3} fontSize="9" fill="#f97316" textAnchor="end" opacity={0.6}>300 g/kWh threshold</text>

        {/* Green fill (below threshold) */}
        <defs>
          <clipPath id="clipGreen">
            <rect x={PAD} y={threshold} width={W - PAD * 2} height={H - threshold} />
          </clipPath>
          <clipPath id="clipRed">
            <rect x={PAD} y={PAD} width={W - PAD * 2} height={threshold - PAD} />
          </clipPath>
        </defs>
        <path d={areaPath} fill="#10b981" fillOpacity={0.2} clipPath="url(#clipGreen)" />
        <path d={areaPath} fill="#ef4444" fillOpacity={0.2} clipPath="url(#clipRed)" />

        {/* Line */}
        <path d={linePath} fill="none" stroke="#f0b429" strokeWidth={1.5} />

        {/* Deferral markers */}
        {history.map((h, i) =>
          h.deferred ? (
            <circle key={i} cx={toX(i)} cy={toY(h.intensity)} r={3} fill="#f97316" />
          ) : h.released ? (
            <circle key={i} cx={toX(i)} cy={toY(h.intensity)} r={3} fill="#10b981" />
          ) : null
        )}
      </svg>
      <style>{`@keyframes slideDown { from { opacity:0; transform:translateY(-8px); } to { opacity:1; transform:translateY(0); } }`}</style>
    </div>
  );
}

// ─── INITIAL JOBS (unchanged from previous version) ───────────────────────

const INITIAL_JOBS = [
  { id: 1, name: 'Database Backup', type: 'backup', duration_mins: 120, est_kwh: 50, deferrable: true },
  { id: 2, name: 'Batch ETL Job', type: 'batch_etl', duration_mins: 240, est_kwh: 200, deferrable: true },
  { id: 3, name: 'Model Training', type: 'model_training', duration_mins: 360, est_kwh: 500, deferrable: true },
  { id: 4, name: 'Log Archival', type: 'log_archival', duration_mins: 60, est_kwh: 20, deferrable: true },
  { id: 5, name: 'User Auth Service', type: 'critical', duration_mins: 0, est_kwh: 5, deferrable: false },
  { id: 6, name: 'API Gateway', type: 'critical', duration_mins: 0, est_kwh: 8, deferrable: false },
  { id: 7, name: 'Health Monitor', type: 'critical', duration_mins: 0, est_kwh: 3, deferrable: false },
  { id: 8, name: 'DNS Resolution', type: 'critical', duration_mins: 0, est_kwh: 2, deferrable: false },
].map(j => ({ ...j, status: 'PENDING' }));

// ─── Main CarbonClock component ───────────────────────────────────────────

export default function CarbonClock() {
  const { intensity: ci, trend, isSpike, minutesUntilClean, manualSpike } = useCarbonSimulation();
  const [jobs, setJobs] = useState(INITIAL_JOBS);
  const [co2Avoided, setCo2Avoided] = useState(0);
  const [history, setHistory] = useState(() =>
    Array.from({ length: 24 }, (_, i) => ({ time: i, intensity: 250 + Math.random() * 100 }))
  );
  const [banner, setBanner] = useState(null);
  const prevDeferred = useRef(false);
  const displayCi = useTicker(ci);

  // Auto-deferral logic
  useEffect(() => {
    const shouldDefer = ci > 300;
    const newJobs = jobs.map(j => ({
      ...j,
      status: !j.deferrable ? 'RUNNING' : shouldDefer ? 'DEFERRED' : 'READY',
    }));
    const deferredCount = newJobs.filter(j => j.status === 'DEFERRED').length;

    if (shouldDefer && !prevDeferred.current) {
      setBanner({ message: `⚡ Grid intensity spike detected — deferring ${deferredCount} jobs to protect carbon budget`, color: 'orange' });
    } else if (!shouldDefer && prevDeferred.current) {
      setBanner({ message: `✓ Grid intensity normalized — ${deferredCount > 0 ? 0 : INITIAL_JOBS.filter(j => j.deferrable).length} jobs ready to execute`, color: 'green' });
    }
    prevDeferred.current = shouldDefer;
    setJobs(newJobs);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ci]);

  // Append to history every 30sec (debounce with timestamp)
  useEffect(() => {
    setHistory(prev => {
      const last = prev[prev.length - 1];
      const isDeferEvent = ci > 300 && (prev[prev.length - 1]?.intensity || 0) <= 300;
      const isReleaseEvent = ci <= 250 && (prev[prev.length - 1]?.intensity || 0) > 300;
      const entry = { time: Date.now(), intensity: ci, deferred: isDeferEvent, released: isReleaseEvent };
      const next = [...prev.slice(-239), entry];
      return next;
    });
  }, [ci]);

  // CO2 counter: increment while deferred
  useEffect(() => {
    if (ci <= 300) return;
    const deferredJobs = jobs.filter(j => j.status === 'DEFERRED');
    const totalKwh = deferredJobs.reduce((a, b) => a + b.est_kwh, 0);
    const iv = setInterval(() => {
      setCo2Avoided(prev => prev + (totalKwh * (ci - 300) / 1_000_000));
    }, 1000);
    return () => clearInterval(iv);
  }, [ci, jobs]);

  // Status colours
  let statusColor = 'text-green-400';
  let gaugeColor = 'bg-green-500';
  let statusText = 'CLEAN — ideal execution';
  if (ci > 200 && ci <= 300) { statusColor = 'text-yellow-400'; gaugeColor = 'bg-yellow-500'; statusText = 'MODERATE — ready to run'; }
  else if (ci > 300 && ci <= 400) { statusColor = 'text-orange-400'; gaugeColor = 'bg-orange-500'; statusText = 'HIGH — defer if possible'; }
  else if (ci > 400) { statusColor = 'text-red-400'; gaugeColor = 'bg-red-500'; statusText = 'CRITICAL — deferring all'; }

  const deferredJobs = jobs.filter(j => j.status === 'DEFERRED');
  const displayCo2 = useTicker(co2Avoided);

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-start mb-10">
        <ModuleHeader
          title="CarbonClock"
          subtitle="Adaptive Workload Scheduling & Grid Intensity Synchronization"
          moduleName="CarbonClock"
        />
        <button
          onClick={manualSpike}
          className="relative z-10 bg-card border border-borderC text-textMuted hover:text-textMain hover:bg-white/5 hover:border-borderC px-6 py-2.5 rounded-lg text-[10px] font-bold transition-all uppercase tracking-[0.2em] flex items-center group"
        >
          <Zap className="w-3 h-3 mr-2 text-accent-amber group-hover:animate-pulse" />
          Simulate Grid Spike
        </button>
      </div>

      {/* Auto-dismiss banner */}
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
          <div className="text-[10px] font-mono font-bold text-textMuted uppercase tracking-[0.2em] mb-4 opacity-50">CO₂ AVOIDED THIS SESSION</div>
          <div className="text-4xl metric-text text-green-400 accent-glow">
            {displayCo2.toFixed(4)} <span className="text-xs font-mono text-green-400/40 ml-1">kg CO₂</span>
          </div>
          {minutesUntilClean && (
            <div className="text-[10px] font-mono text-orange-400 mt-2 opacity-70">
              ~{minutesUntilClean}m until clean window
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 mb-12">
        {/* Big intensity gauge */}
        <div className="lg:col-span-1 space-y-6">
          <div className="glass-panel p-10 rounded-2xl flex flex-col items-center justify-center text-center relative overflow-hidden animate-breath border-borderC">
            <div className="razor-border" />
            <h3 className="text-[10px] font-mono font-bold text-textMuted/50 uppercase tracking-[0.3em] mb-10 w-full text-left">Carbon Intensity Gauge</h3>

            <div className="relative mb-8">
              <div className={`absolute inset-0 blur-3xl opacity-10 rounded-full`} />
              <div className={`text-9xl font-sans font-thin tracking-tighter drop-shadow-2xl relative z-10 transition-all duration-1000 ${statusColor}`}>{Math.round(displayCi)}</div>
              <div className="text-[11px] font-mono text-textMuted/40 tracking-[0.4em] uppercase mt-2">
                gCO₂/kWh · IN-SO · {trend > 0 ? `↑ +${Math.abs(trend).toFixed(1)}` : `↓ ${Math.abs(trend).toFixed(1)}`}
              </div>
            </div>

            <div className={`mt-8 text-[11px] font-mono font-bold px-8 py-3 rounded-full border border-borderC ${statusColor} bg-white/[0.02] uppercase tracking-[0.2em] transition-all`}>
              <span className="opacity-40 font-normal mr-2">// STATUS //</span> {statusText}
            </div>
          </div>

          {/* 2h Timeline Chart */}
          <div className="glass-panel p-6 rounded-2xl border-borderC">
            <div className="razor-border" />
            <h3 className="text-[10px] font-mono font-bold text-textMuted/50 uppercase tracking-[0.2em] mb-4">2h Intensity Timeline</h3>
            <TimelineChart history={history.slice(-120)} />
            <div className="flex gap-6 mt-3 text-[9px] font-mono text-textMuted/50 uppercase">
              <span className="flex items-center gap-1"><span style={{ width: 8, height: 8, background: '#10b981', borderRadius: 2, display: 'inline-block' }} /> Clean window</span>
              <span className="flex items-center gap-1"><span style={{ width: 8, height: 8, background: '#ef4444', borderRadius: 2, display: 'inline-block' }} /> Defer window</span>
              <span className="flex items-center gap-1"><span style={{ width: 6, height: 6, background: '#f97316', borderRadius: '50%', display: 'inline-block' }} /> Deferred</span>
            </div>
          </div>
        </div>

        {/* Job queue */}
        <div className="glass-panel p-8 rounded-2xl flex flex-col h-full border-borderC">
          <div className="razor-border" />
          <h3 className="text-sm font-sans font-light text-textMain tracking-[0.2em] uppercase mb-10 border-b border-borderC pb-6 flex justify-between items-center">
            <span>Adaptive Schedule Queue</span>
            <span className="text-[10px] font-mono text-textMuted opacity-50 lowercase tracking-normal italic">{jobs.length} jobs</span>
          </h3>

          <div className="flex-1 overflow-y-auto space-y-4 custom-scrollbar pr-2">
            {jobs.map(j => (
              <div key={j.id} className="bg-card border border-borderC p-5 rounded-xl transition-all hover:bg-white/[0.05]">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs font-mono text-textMain font-bold uppercase tracking-tighter">{j.name}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                    j.status === 'READY' ? 'bg-green-500 text-black' :
                    j.status === 'RUNNING' ? 'bg-purple-600 text-white' :
                    j.status === 'DEFERRED' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40 animate-pulse' :
                    'bg-card text-textMuted opacity-50'
                  }`}>
                    {j.status}
                  </span>
                </div>
                {j.status === 'DEFERRED' && (
                  <div className="text-right">
                    <span className="text-[9px] font-mono text-green-400/80 bg-green-500/5 px-2 py-0.5 rounded border border-green-500/10">
                      Saves {(j.est_kwh * (ci - 300) / 1000).toFixed(2)} kg CO₂
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Workload table */}
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
              {jobs.map(j => (
                <tr key={j.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-6 font-bold text-textMain">{j.name}</td>
                  <td className="p-6 opacity-60 italic">{j.type}</td>
                  <td className="p-6 text-right opacity-60">{j.duration_mins || '∞'} MIN</td>
                  <td className="p-6 text-right opacity-60 text-green-400/80 font-bold">{j.est_kwh} KWH</td>
                  <td className="p-6 text-center">{j.deferrable ? <span className="text-green-400">TRUE</span> : <span className="opacity-20">—</span>}</td>
                  <td className="p-6 text-right">
                    <span className={`px-4 py-2 rounded-lg font-bold text-[9px] tracking-[0.1em]
                      ${j.status === 'READY' ? 'bg-green-500 text-black' : ''}
                      ${j.status === 'RUNNING' ? 'bg-purple-600 text-white' : ''}
                      ${j.status === 'DEFERRED' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40 animate-pulse' : ''}
                      ${j.status === 'PENDING' ? 'bg-card text-textMuted opacity-50' : ''}
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
