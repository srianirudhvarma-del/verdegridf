import { useEffect, useState, useCallback } from "react";
import { api } from "./api.js";
import HostCard from "./HostCard.jsx";

const POLL_INTERVAL_MS = 4000;

export default function App() {
  const [hosts, setHosts] = useState([]);
  const [actions, setActions] = useState([]);
  const [error, setError] = useState(null);
  const [pendingDecision, setPendingDecision] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [hostsData, actionsData] = await Promise.all([api.getHosts(), api.getPendingActions()]);
      setHosts(hostsData);
      setActions(actionsData);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  const decide = async (id, decision) => {
    setPendingDecision(id);
    try {
      if (decision === "approve") {
        await api.approveAction(id);
      } else {
        await api.rejectAction(id);
      }
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setPendingDecision(null);
    }
  };

  return (
    <>
      <h1>Laptop Monitor</h1>
      <p className="subtitle">Real telemetry from physical laptops — idle → sleep prompts, temperature + clock speed → fan-speed recommendations.</p>

      {error && <div className="error-banner">Couldn't reach the backend: {error}</div>}

      <div className="section-title">Hosts ({hosts.length})</div>
      {hosts.length === 0 ? (
        <div className="empty-state">No laptops have reported in yet. Start an agent pointed at this backend to see it here.</div>
      ) : (
        <div className="host-grid">
          {hosts.map((host) => (
            <HostCard key={host.hostId} host={host} />
          ))}
        </div>
      )}

      <div className="section-title">Pending fan-speed approvals ({actions.length})</div>
      {actions.length === 0 ? (
        <div className="empty-state">Nothing waiting on approval right now.</div>
      ) : (
        actions.map((action) => (
          <div className="card action-card" key={action.id} style={{ marginBottom: 12 }}>
            <span className="action-benefit">{action.predictedBenefit}</span>
            <div className="action-buttons">
              <button className="btn-reject" disabled={pendingDecision === action.id} onClick={() => decide(action.id, "reject")}>
                Reject
              </button>
              <button className="btn-approve" disabled={pendingDecision === action.id} onClick={() => decide(action.id, "approve")}>
                Approve
              </button>
            </div>
          </div>
        ))
      )}
    </>
  );
}
