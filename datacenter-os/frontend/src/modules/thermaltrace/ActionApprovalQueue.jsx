import React, { useCallback } from 'react';
import { getPendingActions, approveAction, rejectAction } from '../../services/thermaltraceApi';
import { useLiveResource } from '../../hooks/useLiveResource';

// MUST HAVE #22: supervised (human-approved) closed-loop control. Every
// ActionRecommendation requires explicit approval here, every time --
// there's no auto-execute toggle in this UI on purpose (thermaltrace/control.py's
// trust ladder can only be enabled by an explicit backend call, never
// silently, and this pass doesn't add that control surface).
export default function ActionApprovalQueue() {
  const fetcher = useCallback(() => getPendingActions(), []);
  const [actions, refresh] = useLiveResource(fetcher, 8000);

  const decide = async (id, decision) => {
    try {
      if (decision === 'approve') await approveAction(id);
      else await rejectAction(id);
      refresh();
    } catch (err) {
      console.error(`${decision} action failed:`, err);
    }
  };

  if (!actions) return null;

  return (
    <div className="glass-panel p-8 rounded-2xl border-borderC mt-10">
      <div className="razor-border" />
      <h3 className="text-sm font-sans font-light text-textMain tracking-[0.2em] uppercase mb-8 border-b border-borderC pb-6">
        Action Approval Queue <span className="text-textMuted opacity-30 text-[10px] lowercase tracking-normal ml-3">supervised closed-loop control</span>
      </h3>

      {actions.length === 0 ? (
        <div className="text-[11px] font-mono text-textMuted opacity-50 uppercase tracking-widest">No pending recommendations</div>
      ) : (
        <div className="space-y-4">
          {actions.map((rec) => (
            <div key={rec.id} className="bg-card border border-borderC p-5 rounded-xl flex justify-between items-center">
              <div>
                <div className="text-xs font-bold text-textMain uppercase tracking-wider">{rec.type} — rack {rec.rackId}</div>
                <div className="text-[10px] text-textMuted font-mono opacity-60 mt-1">
                  magnitude {rec.magnitude} · {rec.predictedBenefit}
                </div>
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={() => decide(rec.id, 'approve')}
                  className="bg-card hover:bg-accent-green text-textMain hover:text-black border border-white/10 hover:border-accent-green text-[10px] px-3 py-1.5 rounded-lg transition-all font-bold uppercase tracking-widest"
                >
                  Approve
                </button>
                <button
                  onClick={() => decide(rec.id, 'reject')}
                  className="bg-card hover:bg-accent-red text-textMain hover:text-black border border-white/10 hover:border-accent-red text-[10px] px-3 py-1.5 rounded-lg transition-all font-bold uppercase tracking-widest"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
