function fmt(value, digits = 1) {
  return typeof value === "number" ? value.toFixed(digits) : "—";
}

const COMMAND_LABELS = {
  sleep_prompt: "PowerPrune — sleep recommended",
  fan_max_on: "ThermOS — raise fan speed",
  fan_max_off: "ThermOS — fan speed reverted",
};

const RESULT_CLASS = {
  executed: "signal-ok",
  skipped: "signal-watch",
  declined: "signal-watch",
  failed: "signal-anomaly",
};

const COOLING_LABELS = {
  ok: { text: "CoolSense — normal", className: "signal-ok" },
  anomaly: { text: "CoolSense — cooling anomaly", className: "signal-anomaly" },
  insufficient_data: { text: "CoolSense — learning baseline", className: "signal-watch" },
};

const NETWORK_LABELS = {
  normal: { text: "NetPulse — normal", className: "signal-ok" },
  elephant_flow: { text: "NetPulse — elephant flow detected", className: "signal-anomaly" },
};

function SignalRow({ text, className }) {
  return (
    <div className="signal-row">
      <span className={`signal-dot ${className}`} />
      <span>{text}</span>
    </div>
  );
}

export default function HostCard({ host }) {
  const sample = host.lastSample;
  const badge = host.stale
    ? { className: "badge-stale", label: "STALE" }
    : host.isIdle
    ? { className: "badge-idle", label: "IDLE" }
    : { className: "badge-active", label: "ACTIVE" };

  const cooling = host.cooling ? COOLING_LABELS[host.cooling.status] : null;
  const network = NETWORK_LABELS[host.network] || null;
  const lastCommand = host.lastAck
    ? {
        text: `${COMMAND_LABELS[host.lastAck.type] || host.lastAck.type} → ${host.lastAck.result}`,
        className: RESULT_CLASS[host.lastAck.result] || "signal-watch",
      }
    : null;

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

      <div className="signal-section">
        {cooling && <SignalRow text={cooling.text} className={cooling.className} />}
        {network && <SignalRow text={network.text} className={network.className} />}
        {lastCommand && <SignalRow text={lastCommand.text} className={lastCommand.className} />}
      </div>
    </div>
  );
}
