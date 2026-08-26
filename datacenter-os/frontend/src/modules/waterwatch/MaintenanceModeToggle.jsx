import React, { useCallback, useState } from 'react';
import { declareMaintenanceWindow, getMaintenanceStatus } from '../../services/waterwatchApi';
import { useLiveResource } from '../../hooks/useLiveResource';

// SHOULD HAVE #13/#15: operator-facing maintenance-mode declaration UI.
// Declaring a window here suppresses WaterWatch's anomaly *escalation*
// for that loop -- the raw anomaly is still logged for audit, it just
// doesn't alert (waterwatch/anomaly.py's evaluate_and_log/should_notify).
export default function MaintenanceModeToggle({ loopIds }) {
  const [selectedLoop, setSelectedLoop] = useState(loopIds[0] || '');
  const [durationHours, setDurationHours] = useState(2);
  const [busy, setBusy] = useState(false);

  const fetcher = useCallback(
    () => (selectedLoop ? getMaintenanceStatus(selectedLoop) : Promise.resolve(null)),
    [selectedLoop]
  );
  const [status, refresh] = useLiveResource(fetcher, 10000);

  const declare = async () => {
    if (!selectedLoop) return;
    setBusy(true);
    try {
      const start = new Date();
      const end = new Date(start.getTime() + durationHours * 3600 * 1000);
      await declareMaintenanceWindow(selectedLoop, start.toISOString(), end.toISOString());
      refresh();
    } catch (err) {
      console.error('declare maintenance window failed:', err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-panel p-6 rounded-2xl border-borderC flex flex-wrap items-center gap-4 mb-10">
      <div className="text-[10px] font-mono font-bold text-textMuted uppercase tracking-[0.2em]">Maintenance Mode</div>
      <select
        value={selectedLoop}
        onChange={(e) => setSelectedLoop(e.target.value)}
        className="bg-card border border-borderC text-textMain text-[11px] font-mono px-3 py-2 rounded-lg"
      >
        {loopIds.map((id) => (
          <option key={id} value={id}>{id}</option>
        ))}
      </select>
      <select
        value={durationHours}
        onChange={(e) => setDurationHours(Number(e.target.value))}
        className="bg-card border border-borderC text-textMain text-[11px] font-mono px-3 py-2 rounded-lg"
      >
        {[1, 2, 4, 8, 24].map((h) => (
          <option key={h} value={h}>{h}h</option>
        ))}
      </select>
      <button
        onClick={declare}
        disabled={busy || !selectedLoop}
        className="bg-card hover:bg-accent-amber text-textMain hover:text-black border border-white/10 hover:border-accent-amber text-[10px] px-4 py-2 rounded-lg transition-all font-bold uppercase tracking-widest disabled:opacity-40"
      >
        Declare Window
      </button>
      {status && (
        <span className={`text-[10px] font-mono uppercase tracking-widest ${status.active ? 'text-accent-amber' : 'text-textMuted opacity-50'}`}>
          {selectedLoop}: {status.active ? 'Suppressing alerts' : 'No active window'}
        </span>
      )}
    </div>
  );
}
