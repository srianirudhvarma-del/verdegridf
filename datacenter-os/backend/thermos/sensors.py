"""
thermos/sensors.py -- MUST HAVE #21: basic airflow sensing.

Per the methodology (Section 7, MUST HAVE #21): "Shares the exact
PressureReading schema and ingestion pipeline built for CoolSense (Section
5, MUST HAVE #10) -- one differential-pressure sensor type, two consumers."

Build sequencing (Phase 2 before Phase 4) means ThermOS needs this
schema before CoolSense's own package exists. `PressureReading` is defined
here, once, as the real shared primitive the methodology describes -- when
CoolSense's MUST HAVE #10 is implemented (Phase 4), it should import
`PressureReading` from this module rather than redefining it, so there is
still exactly one sensor type serving two consumers.

Also owns ThermOS's per-rack temperature/humidity/pressure telemetry,
built on the same shared synthetic simulator every other module uses
(shared/telemetry_sim.py, Phase 0 Decision #1).
"""

import math
from datetime import datetime, timezone

from pydantic import BaseModel

from shared.telemetry_sim import TelemetryAdapter, TelemetrySimulator


class PressureReading(BaseModel):
    loopId: str
    timestamp: str
    differentialKPa: float
    absoluteKPa: float


# Standard atmospheric pressure, used as the ambient baseline the simulated
# differential reading is added to for absoluteKPa. A real sensor reports
# absoluteKPa directly; this is a documented simplification for the
# synthetic simulator, not a physical derivation.
AMBIENT_ABSOLUTE_KPA = 101.325

# Fan-law derived: airflow = calibrationConstant * sqrt(differentialKPa).
# Facility/fan-model specific in reality; a reasonable placeholder default.
DEFAULT_AIRFLOW_CALIBRATION_CONSTANT = 12.0

RACK_METRIC_DEFAULTS = {
    "temperature": dict(baseline=28.0, noise_std=1.5, reversion=0.2, min_value=15.0, max_value=45.0),
    "differential_pressure": dict(baseline=15.0, noise_std=0.5, reversion=0.2, min_value=0.0, max_value=50.0),
    "humidity": dict(baseline=45.0, noise_std=2.0, reversion=0.15, min_value=0.0, max_value=100.0),
}


def estimate_airflow(differential_kpa: float, *, calibration_constant: float = DEFAULT_AIRFLOW_CALIBRATION_CONSTANT) -> float:
    """airflowEstimate = calibrationConstant * sqrt(differentialKPa)."""
    if differential_kpa < 0:
        raise ValueError("differential_kpa cannot be negative")
    return calibration_constant * math.sqrt(differential_kpa)


class ThermalTelemetry(TelemetryAdapter):
    """
    Simulator-backed TelemetryAdapter for ThermOS's per-rack
    temperature, differential pressure, and humidity signals.
    """

    def __init__(self, simulator: TelemetrySimulator | None = None) -> None:
        self._simulator = simulator or TelemetrySimulator()

    def register_rack(self, rack_id: str, *, seed: int | None = None) -> None:
        for metric, params in RACK_METRIC_DEFAULTS.items():
            self._simulator.register_metric(rack_id, metric, seed=seed, **params)

    def poll(self, rack_id: str) -> dict[str, float]:
        return self._simulator.sample(rack_id)

    def current(self, rack_id: str) -> dict[str, float]:
        return self._simulator.current(rack_id)

    def history(self, rack_id: str, metric: str, n: int) -> list[float]:
        return self._simulator.history(rack_id, metric, n)

    def inject_anomaly(self, rack_id: str, metric: str, kind: str, magnitude: float, duration_ticks: int) -> None:
        self._simulator.inject_anomaly(rack_id, metric, kind, magnitude, duration_ticks)

    def rack_ids(self) -> list[str]:
        return self._simulator.entity_ids()

    def pressure_reading(self, rack_id: str, *, timestamp: str | None = None) -> PressureReading:
        differential = self._simulator.current(rack_id)["differential_pressure"]
        return PressureReading(
            loopId=rack_id,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            differentialKPa=differential,
            absoluteKPa=AMBIENT_ABSOLUTE_KPA + differential,
        )
