"""
coolsense/sensor_health.py -- SHOULD HAVE #15: sensor-failure/drift
plausibility checks.

flag sensor_fault if:
    reading is flatlined (variance == 0) for > 2 hours, OR
    reading outside physically valid bounds (e.g. flow < 0, flow > ratedMaxFlow), OR
    reading missing for > 3 consecutive expected samples

A sensor_fault flag suppresses that signal from the anomaly engine (does
NOT count as "no anomaly") -- callers should check check_sensor_fault()
before feeding a reading into coolsense/anomaly.py's detect_flow_anomaly,
and surface the fault as its own "sensor needs attention" alert instead.
"""

import statistics
from dataclasses import dataclass
from typing import Optional

FLATLINE_DURATION_SECONDS = 2 * 3600.0  # 2 hours
MAX_CONSECUTIVE_MISSING_SAMPLES = 3


@dataclass
class SensorFaultEvent:
    loopId: str
    timestamp: str
    reason: str


def is_flatlined(readings: list[float], *, sample_interval_seconds: float, duration_threshold_seconds: float = FLATLINE_DURATION_SECONDS) -> bool:
    """variance == 0 across a window spanning > duration_threshold_seconds."""
    min_samples = int(duration_threshold_seconds // sample_interval_seconds) + 1
    if len(readings) < min_samples:
        return False
    return statistics.pvariance(readings[-min_samples:]) == 0.0


def is_out_of_bounds(value: float, *, min_value: float = 0.0, max_value: float) -> bool:
    return value < min_value or value > max_value


def missing_samples_exceeded(consecutive_missing: int, *, max_missing: int = MAX_CONSECUTIVE_MISSING_SAMPLES) -> bool:
    return consecutive_missing > max_missing


def check_sensor_fault(
    loop_id: str,
    timestamp: str,
    readings: list[float],
    *,
    sample_interval_seconds: float,
    rated_max_flow: float,
    consecutive_missing: int = 0,
) -> Optional[SensorFaultEvent]:
    if readings and is_out_of_bounds(readings[-1], max_value=rated_max_flow):
        return SensorFaultEvent(
            loopId=loop_id, timestamp=timestamp,
            reason=f"reading {readings[-1]} outside physically valid bounds [0, {rated_max_flow}]",
        )
    if is_flatlined(readings, sample_interval_seconds=sample_interval_seconds):
        return SensorFaultEvent(loopId=loop_id, timestamp=timestamp, reason="flatlined (zero variance) for > 2 hours")
    if missing_samples_exceeded(consecutive_missing):
        return SensorFaultEvent(
            loopId=loop_id, timestamp=timestamp,
            reason=f"missing for {consecutive_missing} consecutive expected samples",
        )
    return None
