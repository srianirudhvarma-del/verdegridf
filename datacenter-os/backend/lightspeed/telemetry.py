"""
lightspeed/telemetry.py -- LightSpeed's per-link utilization telemetry
source, feeding MUST HAVE #15's congestion dwell timer. The streaming
gNMI/SNMP-fallback transport itself is SHOULD HAVE #20 (Phase 7); this
module only needs to produce plausible per-link utilization time series,
same pattern as every other module (shared/telemetry_sim.py, Phase 0
Decision #1).
"""

from shared.telemetry_sim import TelemetryAdapter, TelemetrySimulator

LINK_METRIC_DEFAULTS = dict(baseline=40.0, noise_std=8.0, reversion=0.2, min_value=0.0, max_value=100.0)


class LightSpeedTelemetry(TelemetryAdapter):
    def __init__(self, simulator: TelemetrySimulator | None = None) -> None:
        self._simulator = simulator or TelemetrySimulator()

    def register_link(self, link_id: str, *, seed: int | None = None) -> None:
        self._simulator.register_metric(link_id, "utilization_pct", seed=seed, **LINK_METRIC_DEFAULTS)

    def poll(self, link_id: str) -> dict[str, float]:
        return self._simulator.sample(link_id)

    def current(self, link_id: str) -> dict[str, float]:
        return self._simulator.current(link_id)

    def history(self, link_id: str, metric: str, n: int) -> list[float]:
        return self._simulator.history(link_id, metric, n)

    def inject_anomaly(self, link_id: str, metric: str, kind: str, magnitude: float, duration_ticks: int) -> None:
        self._simulator.inject_anomaly(link_id, metric, kind, magnitude, duration_ticks)

    def link_ids(self) -> list[str]:
        return self._simulator.entity_ids()
