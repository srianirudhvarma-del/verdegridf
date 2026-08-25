"""
idlehunter/telemetry.py -- IdleHunter's telemetry source.

Wraps the shared synthetic simulator behind the shared TelemetryAdapter
interface, pre-registering the 4 MAD-relevant resources (cpu, mem, diskIO,
network) for each host. threshold.py/consolidation.py/power.py depend only
on this adapter's poll()/history() output, never on shared.telemetry_sim
directly -- so a real hypervisor/BMC poller can replace this file later
without any algorithm code changing.
"""

from shared.telemetry_sim import TelemetryAdapter, TelemetrySimulator

RESOURCE_DEFAULTS = {
    "cpu": dict(baseline=30.0, noise_std=4.0, reversion=0.15, min_value=0.0, max_value=100.0),
    "mem": dict(baseline=40.0, noise_std=3.0, reversion=0.1, min_value=0.0, max_value=100.0),
    "diskIO": dict(baseline=15.0, noise_std=5.0, reversion=0.2, min_value=0.0, max_value=100.0),
    "network": dict(baseline=20.0, noise_std=6.0, reversion=0.2, min_value=0.0, max_value=100.0),
}


class IdleHunterTelemetry(TelemetryAdapter):
    def __init__(self, simulator: TelemetrySimulator | None = None) -> None:
        self._simulator = simulator or TelemetrySimulator()

    def register_host(self, host_id: str, *, seed: int | None = None) -> None:
        for resource, params in RESOURCE_DEFAULTS.items():
            self._simulator.register_metric(host_id, resource, seed=seed, **params)

    def poll(self, host_id: str) -> dict[str, float]:
        """Advance and return the latest sample for every resource on host_id."""
        return self._simulator.sample(host_id)

    def current(self, host_id: str) -> dict[str, float]:
        """Latest values without advancing state."""
        return self._simulator.current(host_id)

    def history(self, host_id: str, resource: str, n: int) -> list[float]:
        return self._simulator.history(host_id, resource, n)

    def inject_anomaly(self, host_id: str, resource: str, kind: str, magnitude: float, duration_ticks: int) -> None:
        self._simulator.inject_anomaly(host_id, resource, kind, magnitude, duration_ticks)

    def host_ids(self) -> list[str]:
        return self._simulator.entity_ids()


class K8sTelemetryAdapter(TelemetryAdapter):
    """
    SHOULD HAVE #8 -- second telemetry adapter, normalizing Kubernetes
    metrics-server-shaped node metrics into the exact same resource keys
    (cpu, mem, diskIO, network) as IdleHunterTelemetry, so
    threshold.py/consolidation.py/power.py work unchanged regardless of
    which adapter is plugged in -- adapter-agnostic by construction. No
    real cluster access exists; this is simulator-backed like every other
    adapter in this codebase (Phase 0 Decision #1). A real implementation
    would poll /apis/metrics.k8s.io/v1beta1/nodes here instead.
    """

    def __init__(self, simulator: TelemetrySimulator | None = None) -> None:
        self._simulator = simulator or TelemetrySimulator()

    def register_node(self, node_id: str, *, seed: int | None = None) -> None:
        for resource, params in RESOURCE_DEFAULTS.items():
            self._simulator.register_metric(node_id, resource, seed=seed, **params)

    def poll(self, node_id: str) -> dict[str, float]:
        return self._simulator.sample(node_id)

    def current(self, node_id: str) -> dict[str, float]:
        return self._simulator.current(node_id)

    def history(self, node_id: str, resource: str, n: int) -> list[float]:
        return self._simulator.history(node_id, resource, n)

    def node_ids(self) -> list[str]:
        return self._simulator.entity_ids()
