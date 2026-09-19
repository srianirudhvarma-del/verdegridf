"""
shared/real_agent.py -- real hardware telemetry: ingestion + hotspot
prediction for physical laptop nodes.

This is the "real client adapter" the Phase 0 decision in CLAUDE.md asked
for ("write real client adapters behind an interface so a future real
integration can swap in without touching algorithm code"). It does not
touch powerprune/threshold.py, powerprune/power.py, or any classification
logic -- it only produces the same shapes those modules already consume
(current resource values + history lists), sourced from a real
`datacenter-os/real-agent/agent.py` process running on real hardware
instead of shared/telemetry_sim.py.

Two real laptops (initially: an HP OMEN Transcend 16 and an HP Victus 15,
both Windows) push samples here over HTTP. Hosts are not pre-registered
the way the simulated topology in api/state.py is -- we don't know the
exact machine id in advance, so a host simply becomes "known" the first
time it posts a sample (see RealAgentRegistry.known_hosts).

Fail-safe-open: RealAgentRegistry.is_stale() is the single place that
answers "do we trust this host's data right now" -- api/real_nodes.py's
tick() skips any stale host entirely rather than classifying it from
missing/old data.
"""

from collections import deque
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel

# Maps the 4 MAD-relevant resources powerprune/threshold.py already knows
# about onto the real fields a Windows agent can actually report. cpu/mem
# are direct OS percentages; diskIO/network are throughput normalized to a
# 0-100 scale by the agent itself (see real-agent/agent.py) so the adaptive
# MAD threshold sees the same kind of bounded signal it does from the
# simulator -- the classifier never needs to know the values came from a
# laptop instead of a rack server.
RESOURCE_FIELDS: dict[str, str] = {
    "cpu": "cpuPercent",
    "mem": "memPercent",
    "diskIO": "diskIoPercent",
    "network": "networkPercent",
}

# Fields kept in rolling history for reasons other than MAD classification
# (currently just thermal prediction).
_EXTRA_HISTORY_FIELDS = ("cpuTempC",)


class RealAgentSample(BaseModel):
    hostId: str
    timestamp: str
    cpuPercent: float
    memPercent: float
    diskIoPercent: float
    networkPercent: float
    cpuFreqMhz: float
    cpuFreqMaxMhz: float
    cpuTempC: Optional[float] = None
    idleSeconds: float = 0.0
    batteryPercent: Optional[float] = None


class RealAgentRegistry:
    """Latest sample + rolling history per real host, keyed by hostId."""

    def __init__(self, *, history_len: int = 240) -> None:
        self._history_len = history_len
        self._latest: dict[str, RealAgentSample] = {}
        self._received_at: dict[str, datetime] = {}
        self._history: dict[str, dict[str, deque]] = {}

    def ingest(self, sample: RealAgentSample, *, received_at: Optional[datetime] = None) -> None:
        received_at = received_at or datetime.now(timezone.utc)
        self._latest[sample.hostId] = sample
        self._received_at[sample.hostId] = received_at
        host_history = self._history.setdefault(sample.hostId, {})
        for field_name in (*RESOURCE_FIELDS.values(), *_EXTRA_HISTORY_FIELDS):
            value = getattr(sample, field_name)
            if value is None:
                continue
            host_history.setdefault(field_name, deque(maxlen=self._history_len)).append(value)

    def known_hosts(self) -> list[str]:
        return list(self._latest.keys())

    def is_stale(self, host_id: str, now: datetime, *, max_age_seconds: float) -> bool:
        """No sample ever received, or the last one is older than
        max_age_seconds, both count as stale -- the fail-safe-open default
        is to trust nothing until proven fresh."""
        received = self._received_at.get(host_id)
        if received is None:
            return True
        return (now - received).total_seconds() > max_age_seconds

    def latest(self, host_id: str) -> Optional[RealAgentSample]:
        return self._latest.get(host_id)

    def current_resources(self, host_id: str) -> dict[str, float]:
        """The 4 MAD resources' current values, shaped exactly like
        powerprune/telemetry.py's PowerPruneTelemetry.current() output."""
        sample = self._latest[host_id]
        return {resource: getattr(sample, field_name) for resource, field_name in RESOURCE_FIELDS.items()}

    def history(self, host_id: str, resource: str, n: int) -> list[float]:
        return self.field_history(host_id, RESOURCE_FIELDS[resource], n)

    def field_history(self, host_id: str, field_name: str, n: int) -> list[float]:
        values = self._history.get(host_id, {}).get(field_name)
        if not values:
            return []
        return list(values)[-n:]


RiskLevel = Literal["ok", "watch", "critical"]

# Conservative default for gaming-laptop CPU packages, which typically
# start throttling in the mid-90s C -- comfortably below that, not at it.
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
    A genuine prediction, not a threshold on the current reading: fits a
    linear trend to recent CPU package temperatures and extrapolates it
    `horizon_seconds` into the future, using current clock speed relative
    to the chip's rated max to judge whether that trend reflects real
    sustained load (believable) or is likely sensor noise on a mostly
    idle chip (not believable enough to call it "critical" pre-emptively).

    critical: current temp already at/over the limit (always -- this
    never waits on clock speed, since an already-hot chip is real
    regardless of what it's doing right now), OR the projected temp
    crosses the limit within the horizon while running near max clock.
    watch: not yet critical, but within watch_margin_c of the limit right
    now, or projected to cross it (even if the clock isn't pinned yet --
    an earlier warning than "critical" requires).
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
