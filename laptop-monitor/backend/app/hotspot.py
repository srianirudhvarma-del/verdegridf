"""
Hotspot prediction: a real linear extrapolation of a laptop's CPU package
temperature, `horizon_seconds` into the future, cross-checked against
whether the CPU is actually running near its rated max clock speed.

This is a prediction, not a threshold on the current reading -- the point
is to catch a hotspot *before* it happens (while there's still time to
spin up fans) rather than only reacting once the chip is already hot.
"""

from typing import Literal

from pydantic import BaseModel

RiskLevel = Literal["ok", "watch", "critical"]

# Conservative default for a gaming-laptop CPU package, which typically
# starts throttling in the mid-90s C -- comfortably below that, not at it.
DEFAULT_CRITICAL_TEMP_C = 92.0
DEFAULT_WATCH_MARGIN_C = 5.0
# "Near max clock" -- the chip is actually working hard enough that a
# rising temperature trend is real load, not sensor noise on an idle chip.
DEFAULT_HIGH_CLOCK_FRACTION = 0.9


class HotspotPrediction(BaseModel):
    hostId: str
    currentTempC: float
    projectedTempC: float
    slopeCPerSecond: float
    cpuFreqMhz: float
    cpuFreqMaxMhz: float
    riskLevel: RiskLevel


def _linear_trend_slope(values: list[float], sample_interval_seconds: float) -> float:
    """OLS slope (value change per second) over evenly-spaced samples."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = [i * sample_interval_seconds for i in range(n)]
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def predict_hotspot(
    host_id: str,
    temp_history: list[float],
    *,
    freq_current: float,
    freq_max: float,
    critical_temp_c: float = DEFAULT_CRITICAL_TEMP_C,
    horizon_seconds: float,
    sample_interval_seconds: float,
    watch_margin_c: float = DEFAULT_WATCH_MARGIN_C,
    high_clock_fraction: float = DEFAULT_HIGH_CLOCK_FRACTION,
) -> HotspotPrediction:
    """
    critical: current temp already at/over the limit (always -- an
    already-hot chip is real regardless of what it's doing right now), OR
    the projected temp crosses the limit within the horizon while running
    near max clock (the noise guard: a low clock speed means a rising
    trend is more likely sensor jitter on a mostly idle chip than a real
    sustained hotspot).
    watch: not yet critical, but close to the limit right now or
    projected to cross it (even without a pinned clock -- an earlier
    warning than "critical" requires).
    ok: otherwise.
    """
    if not temp_history:
        raise ValueError("temp_history must contain at least one sample")

    current_temp = temp_history[-1]
    slope = _linear_trend_slope(temp_history, sample_interval_seconds)
    projected_temp = current_temp + slope * horizon_seconds

    near_max_clock = freq_max > 0 and (freq_current / freq_max) >= high_clock_fraction

    risk: RiskLevel
    if current_temp >= critical_temp_c or (projected_temp >= critical_temp_c and near_max_clock):
        risk = "critical"
    elif current_temp >= critical_temp_c - watch_margin_c or projected_temp >= critical_temp_c:
        risk = "watch"
    else:
        risk = "ok"

    return HotspotPrediction(
        hostId=host_id,
        currentTempC=current_temp,
        projectedTempC=projected_temp,
        slopeCPerSecond=slope,
        cpuFreqMhz=freq_current,
        cpuFreqMaxMhz=freq_max,
        riskLevel=risk,
    )
