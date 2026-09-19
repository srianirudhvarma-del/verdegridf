"""
app/coolsense.py -- cooling-performance anomaly detection, analogous to
VerdeGrid's CoolSense (z-score leak detection against a water loop's own
baseline flow rate) but applied to a laptop's real CPU-temp-vs-load
relationship instead of water flow.

This asks a different question than hotspot.py's predictive warning.
hotspot.py asks "is temperature trending toward a critical limit" using
only the recent trend. This module asks "is temperature abnormally high
for the CPU load this machine is actually under, relative to this
machine's own established baseline" -- which is what surfaces a real
degraded-cooling problem (a clogged fan, dried thermal paste, blocked
vents) rather than momentary heat from real work. Two different failure
modes, both worth knowing about.

Pure algorithm module: operates on plain (cpu, temp) history pairs, no
dependency on telemetry.py, independently testable.
"""

import statistics
from typing import Literal, Optional

from pydantic import BaseModel

# Need a real baseline before judging anything -- fewer points than this
# and individual-sample noise would dominate any regression fit.
COLD_START_MIN_SAMPLES = 20
DEFAULT_SENSITIVITY = 2.5

CoolingStatus = Literal["ok", "anomaly", "insufficient_data"]


class CoolingAssessment(BaseModel):
    hostId: str
    expectedTempC: Optional[float]
    actualTempC: float
    residualC: Optional[float]
    status: CoolingStatus


def _ols_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """OLS fit of ys = intercept + slope*xs. Returns (intercept, slope)."""
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    slope = numerator / denominator if denominator else 0.0
    intercept = mean_y - slope * mean_x
    return intercept, slope


def assess_cooling(
    host_id: str,
    cpu_temp_pairs: list[tuple[float, float]],
    *,
    current_cpu: float,
    current_temp: float,
    sensitivity: float = DEFAULT_SENSITIVITY,
    min_samples: int = COLD_START_MIN_SAMPLES,
) -> CoolingAssessment:
    """
    Fits temp = intercept + slope*cpu over this host's own history, then
    checks whether the CURRENT reading's residual (actual - expected) is
    a robust outlier (MAD-based, same pattern as threshold.py's adaptive
    threshold) relative to the spread of past residuals. status="anomaly"
    means this host is running hotter than its own established
    temp-vs-load relationship predicts -- not just "it's hot right now."
    """
    if len(cpu_temp_pairs) < min_samples:
        return CoolingAssessment(
            hostId=host_id, expectedTempC=None, actualTempC=current_temp, residualC=None, status="insufficient_data"
        )

    xs = [cpu for cpu, _ in cpu_temp_pairs]
    ys = [temp for _, temp in cpu_temp_pairs]
    intercept, slope = _ols_fit(xs, ys)
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]

    median_r = statistics.median(residuals)
    mad_r = statistics.median([abs(r - median_r) for r in residuals])
    # A perfectly flat history (mad_r == 0) would make any deviation look
    # infinitely anomalous; floor it instead of dividing by zero.
    spread = mad_r if mad_r > 1e-6 else 1e-6

    expected_temp = intercept + slope * current_cpu
    current_residual = current_temp - expected_temp
    z = abs(current_residual - median_r) / spread

    status: CoolingStatus = "anomaly" if z > sensitivity else "ok"
    return CoolingAssessment(
        hostId=host_id, expectedTempC=expected_temp, actualTempC=current_temp, residualC=current_residual, status=status
    )
