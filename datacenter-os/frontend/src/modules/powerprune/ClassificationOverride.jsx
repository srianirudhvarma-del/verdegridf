import React, { useState } from 'react';
import { setWorkloadClassification } from '../../services/powerpruneApi';

// MUST HAVE #3 step 2: the operator-facing classification override --
// PATCH /powerprune/workloads/:id/classification, the one production path
// that writes into the shared classification store every module (this
// one's own consolidation filter, GridSync's job scheduler,
// NetPulse's reroute-safety check) reads through.
export default function ClassificationOverride({ hostIds }) {
  const [hostId, setHostId] = useState(hostIds[0] || '');
  const [classification, setClassification] = useState('deferrable');
  const [maxDelayMinutes, setMaxDelayMinutes] = useState(60);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const apply = async () => {
    if (!hostId) return;
    setBusy(true);
    setResult(null);
    try {
      const tag = await setWorkloadClassification(
        hostId, classification, classification === 'deferrable' ? maxDelayMinutes : null
      );
      setResult(tag);
    } catch (err) {
      console.error('classification override failed:', err);
      setResult({ error: err.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-panel p-6 rounded-2xl border-borderC flex flex-wrap items-center gap-4 mb-10">
      <div className="text-[10px] font-mono font-bold text-textMuted uppercase tracking-[0.2em]">Classification Override</div>
      <select
        value={hostId}
        onChange={(e) => setHostId(e.target.value)}
        className="bg-card border border-borderC text-textMain text-[11px] font-mono px-3 py-2 rounded-lg"
      >
        {hostIds.map((id) => (
          <option key={id} value={id}>{id}</option>
        ))}
      </select>
      <select
        value={classification}
        onChange={(e) => setClassification(e.target.value)}
        className="bg-card border border-borderC text-textMain text-[11px] font-mono px-3 py-2 rounded-lg"
      >
        <option value="protected">protected</option>
        <option value="deferrable">deferrable</option>
      </select>
      {classification === 'deferrable' && (
        <input
          type="number"
          min={1}
          value={maxDelayMinutes}
          onChange={(e) => setMaxDelayMinutes(Number(e.target.value))}
          className="bg-card border border-borderC text-textMain text-[11px] font-mono px-3 py-2 rounded-lg w-24"
          title="max delay minutes"
        />
      )}
      <button
        onClick={apply}
        disabled={busy || !hostId}
        className="bg-card hover:bg-accent-violet text-textMain hover:text-black border border-white/10 hover:border-accent-violet text-[10px] px-4 py-2 rounded-lg transition-all font-bold uppercase tracking-widest disabled:opacity-40"
      >
        Apply
      </button>
      {result && !result.error && (
        <span className="text-[10px] font-mono uppercase tracking-widest text-accent-green">
          {result.workloadId} -&gt; {result.classification}
        </span>
      )}
      {result?.error && <span className="text-[10px] font-mono uppercase tracking-widest text-accent-red">{result.error}</span>}
    </div>
  );
}
