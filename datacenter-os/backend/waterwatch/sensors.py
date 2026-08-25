"""
waterwatch/sensors.py

MUST HAVE #10 -- differential-pressure sensing. Imports PressureReading
from thermaltrace/sensors.py rather than redefining it -- per the
methodology, it's "one differential-pressure sensor type, two consumers,"
and ThermalTrace (Phase 2) built it first since it needed it before this
package existed.

MUST HAVE #11 -- facility/zone-level humidity sensing.

Also owns WaterWatch's own per-loop flow telemetry, ingested on the same
pipeline/cadence as pressure (1-5 min sampling), using the shared
synthetic simulator like every other module (Phase 0 Decision #1).
"""

from datetime import datetime, timezone

from pydantic import BaseModel

from shared.telemetry_sim import TelemetryAdapter, TelemetrySimulator
from thermaltrace.sensors import AMBIENT_ABSOLUTE_KPA, PressureReading

__all__ = ["PressureReading", "HumidityReading", "WaterWatchTelemetry"]


class HumidityReading(BaseModel):
    zoneId: str
    timestamp: str
    relativeHumidityPct: float


LOOP_METRIC_DEFAULTS = {
    "flow_rate": dict(baseline=80.0, noise_std=6.0, reversion=0.15, min_value=0.0, max_value=300.0),
    "differential_pressure": dict(baseline=15.0, noise_std=0.5, reversion=0.2, min_value=0.0, max_value=50.0),
}

ZONE_HUMIDITY_DEFAULTS = dict(baseline=45.0, noise_std=2.0, reversion=0.15, min_value=0.0, max_value=100.0)


class WaterWatchTelemetry(TelemetryAdapter):
    """Simulator-backed TelemetryAdapter for per-loop flow/pressure and per-zone humidity."""

    def __init__(self, simulator: TelemetrySimulator | None = None) -> None:
        self._simulator = simulator or TelemetrySimulator()

    def register_loop(self, loop_id: str, *, seed: int | None = None) -> None:
        for metric, params in LOOP_METRIC_DEFAULTS.items():
            self._simulator.register_metric(loop_id, metric, seed=seed, **params)

    def register_zone(self, zone_id: str, *, seed: int | None = None) -> None:
        self._simulator.register_metric(zone_id, "humidity", seed=seed, **ZONE_HUMIDITY_DEFAULTS)

    def poll(self, entity_id: str) -> dict[str, float]:
        return self._simulator.sample(entity_id)

    def current(self, entity_id: str) -> dict[str, float]:
        return self._simulator.current(entity_id)

    def history(self, entity_id: str, metric: str, n: int) -> list[float]:
        return self._simulator.history(entity_id, metric, n)

    def inject_anomaly(self, entity_id: str, metric: str, kind: str, magnitude: float, duration_ticks: int) -> None:
        self._simulator.inject_anomaly(entity_id, metric, kind, magnitude, duration_ticks)

    def pressure_reading(self, loop_id: str, *, timestamp: str | None = None) -> PressureReading:
        differential = self._simulator.current(loop_id)["differential_pressure"]
        return PressureReading(
            loopId=loop_id,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            differentialKPa=differential,
            absoluteKPa=AMBIENT_ABSOLUTE_KPA + differential,
        )

    def humidity_reading(self, zone_id: str, *, timestamp: str | None = None) -> HumidityReading:
        pct = self._simulator.current(zone_id)["humidity"]
        return HumidityReading(
            zoneId=zone_id,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            relativeHumidityPct=pct,
        )
