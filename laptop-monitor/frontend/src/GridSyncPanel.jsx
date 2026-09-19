const JOB_STATUS_LABELS = {
  waiting_for_clean_grid: { text: "Waiting for clean grid", className: "signal-watch" },
  running: { text: "Running now (grid is clean)", className: "signal-ok" },
  force_run_deadline: { text: "Force-run at deadline", className: "signal-anomaly" },
};

const INDEX_CLASS = {
  "very low": "signal-ok",
  low: "signal-ok",
  moderate: "signal-watch",
  high: "signal-anomaly",
  "very high": "signal-anomaly",
  unknown: "signal-watch",
};

export default function GridSyncPanel({ gridsync }) {
  if (!gridsync) return null;
  const { signal, jobs } = gridsync;

  return (
    <div className="card">
      {signal ? (
        <div className="metric-row">
          <span>Grid carbon intensity</span>
          <span>
            <span className={`signal-dot ${INDEX_CLASS[signal.index] || "signal-watch"}`} />
            {signal.index}
            {signal.intensityGCo2PerKwh != null ? ` (${Math.round(signal.intensityGCo2PerKwh)} gCO2/kWh)` : ""}
          </span>
        </div>
      ) : (
        <div className="metric-row"><span>Grid carbon intensity</span><span>fetching…</span></div>
      )}
      {signal && <div className="metric-row"><span>Source</span><span style={{ fontSize: 12 }}>{signal.source}</span></div>}

      <div className="signal-section">
        {jobs.map((job) => {
          const label = JOB_STATUS_LABELS[job.status];
          return (
            <div className="metric-row" key={job.id}>
              <span>{job.name}</span>
              <span>
                <span className={`signal-dot ${label.className}`} />
                {label.text}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
