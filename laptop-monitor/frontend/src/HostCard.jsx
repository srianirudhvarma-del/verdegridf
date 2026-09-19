function fmt(value, digits = 1) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

export default function HostCard({ host }) {
  const sample = host.lastSample;
  const badge = host.stale
    ? { className: "badge-stale", label: "STALE" }
    : host.isIdle
    ? { className: "badge-idle", label: "IDLE" }
    : { className: "badge-active", label: "ACTIVE" };

  return (
    <div className="card">
      <div className="host-card-header">
        <span className="host-id">{host.hostId}</span>
        <span className={`badge ${badge.className}`}>{badge.label}</span>
      </div>
      {sample ? (
        <>
          <div className="metric-row"><span>CPU</span><span>{fmt(sample.cpuPercent)}%</span></div>
          <div className="metric-row"><span>Memory</span><span>{fmt(sample.memPercent)}%</span></div>
          <div className="metric-row"><span>Disk I/O</span><span>{fmt(sample.diskIoPercent)}%</span></div>
          <div className="metric-row"><span>Network</span><span>{fmt(sample.networkPercent)}%</span></div>
          <div className="metric-row"><span>Clock speed</span><span>{fmt(sample.cpuFreqMhz, 0)} / {fmt(sample.cpuFreqMaxMhz, 0)} MHz</span></div>
          <div className="metric-row">
            <span>CPU temp</span>
            <span>{sample.cpuTempC != null ? `${fmt(sample.cpuTempC)}°C` : "unavailable"}</span>
          </div>
          <div className="metric-row"><span>Idle for</span><span>{fmt(sample.idleSeconds / 60, 1)} min</span></div>
          {sample.batteryPercent != null && (
            <div className="metric-row"><span>Battery</span><span>{fmt(sample.batteryPercent, 0)}%</span></div>
          )}
        </>
      ) : (
        <div className="metric-row"><span>No data yet</span></div>
      )}
      {host.lastAck && (
        <div className="metric-row">
          <span>Last command</span>
          <span>{host.lastAck.type} → {host.lastAck.result}</span>
        </div>
      )}
    </div>
  );
}
