"""
netpulse/telemetry.py -- NetPulse's per-link utilization telemetry
source, feeding MUST HAVE #15's congestion dwell timer, same pattern as
every other module (shared/telemetry_sim.py, Phase 0 Decision #1).

SHOULD HAVE #20 -- explicit SNMP-fallback telemetry path: connect_telemetry
tries the real streaming transport (gNMI/gRPC) first, falling back to SNMP
polling instead of failing telemetry collection entirely when a switch
doesn't support streaming.
"""

from dataclasses import dataclass
from typing import Callable, Literal, Optional

from shared.telemetry_sim import TelemetryAdapter, TelemetrySimulator

LINK_METRIC_DEFAULTS = dict(baseline=40.0, noise_std=8.0, reversion=0.2, min_value=0.0, max_value=100.0)


class NetPulseTelemetry(TelemetryAdapter):
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


# ---------------------------------------------------------------------------
# SHOULD HAVE #20 -- explicit SNMP-fallback telemetry path
# ---------------------------------------------------------------------------

DEFAULT_SNMP_POLL_INTERVAL_SECONDS = 15.0


class UnsupportedStreamingTelemetryError(Exception):
    """Raised by a streaming_subscribe callback when a switch doesn't support gNMI/gRPC streaming."""


@dataclass
class TelemetryConnection:
    switch: str
    mode: Literal["streaming", "snmp_fallback"]
    pollIntervalSeconds: Optional[float] = None


def connect_telemetry(
    switch: str,
    *,
    streaming_subscribe: Callable[[str], None],
    snmp_poll_interval_seconds: float = DEFAULT_SNMP_POLL_INTERVAL_SECONDS,
) -> TelemetryConnection:
    """
    telemetryClient.connect(switch):
        try streamingTelemetry.subscribe(switch)
        catch (unsupported): fallback to snmpPoller.poll(switch, intervalSeconds=15)
    """
    try:
        streaming_subscribe(switch)
        return TelemetryConnection(switch=switch, mode="streaming")
    except UnsupportedStreamingTelemetryError:
        return TelemetryConnection(switch=switch, mode="snmp_fallback", pollIntervalSeconds=snmp_poll_interval_seconds)
