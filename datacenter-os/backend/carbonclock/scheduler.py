"""
carbonclock/scheduler.py

Core capacity-curve scheduling algorithm (methodology Section 4, "Core
scheduling algorithm") plus MUST HAVE #9 (cross-wire with IdleHunter's
capacity forecast before finalizing a scheduling window).

Only deferrable jobs (carbonclock/jobs.py's DeferrableJob, produced only
for jobs explicitly tagged deferrable) ever reach this scheduler --
protected/untagged jobs never do, so they are never subject to the
flexible-capacity cap below by construction, not by a check here.

If no window works before the job's deadline, this returns proceed=False;
carbonclock/jobs.py's DeadlineQueue.force_release_overdue() is the
fail-safe backstop that force-runs the job at its deadline regardless of
carbon state (MUST HAVE #7).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from shared.contracts import CapacityForecast
from shared.eventbus import EventBus, event_bus

from carbonclock.grid import HourlyForecast

# Methodology defaults for the capacity-curve cap. gCO2/kWh-scale
# thresholds, tunable per grid zone.
DEFAULT_GREEN_THRESHOLD = 150.0
DEFAULT_DIRTY_THRESHOLD = 400.0
DEFAULT_FLOOR_CAP_PERCENT = 50.0


def flexible_capacity_cap_percent(
    intensity: float,
    *,
    green_threshold: float = DEFAULT_GREEN_THRESHOLD,
    dirty_threshold: float = DEFAULT_DIRTY_THRESHOLD,
    floor_cap_percent: float = DEFAULT_FLOOR_CAP_PERCENT,
) -> float:
    """
    if intensity < greenThreshold: cap = 100%
    elif intensity > dirtyThreshold: cap = floorCapPercent
    else: linear interpolation between floorCapPercent and 100%
    """
    if intensity < green_threshold:
        return 100.0
    if intensity > dirty_threshold:
        return floor_cap_percent

    span = dirty_threshold - green_threshold
    fraction_toward_dirty = (intensity - green_threshold) / span
    return 100.0 - fraction_toward_dirty * (100.0 - floor_cap_percent)


def rank_windows_by_intensity(windows: list[HourlyForecast]) -> list[HourlyForecast]:
    return sorted(windows, key=lambda w: w.carbonIntensity)


class SchedulingPool:
    """Tracks how much of each hour's flexible-capacity budget is already consumed."""

    def __init__(self, total_flexible_capacity: float) -> None:
        self.total_flexible_capacity = total_flexible_capacity
        self._consumed: dict[str, float] = {}

    def available_capacity(self, window: HourlyForecast) -> float:
        cap_percent = flexible_capacity_cap_percent(window.carbonIntensity)
        budget = self.total_flexible_capacity * (cap_percent / 100.0)
        consumed = self._consumed.get(window.windowStart, 0.0)
        return max(0.0, budget - consumed)

    def reserve(self, window: HourlyForecast, amount: float) -> None:
        self._consumed[window.windowStart] = self._consumed.get(window.windowStart, 0.0) + amount


@dataclass
class SchedulingDecision:
    jobId: str
    windowStart: Optional[str]
    proceed: bool
    prewakeRequested: bool
    reason: str


# (windowStart, windowEnd) -> CapacityForecast, i.e. IdleHunter's
# GET /api/idlehunter/capacity-forecast?start=...&end=...
CapacityForecastProvider = Callable[[str, str], CapacityForecast]


def schedule_deferrable_job(
    job_id: str,
    required_capacity: float,
    ranked_windows: list[HourlyForecast],
    pool: SchedulingPool,
    *,
    now: datetime,
    deadline: datetime,
    get_capacity_forecast: CapacityForecastProvider,
    bus: EventBus = event_bus,
) -> SchedulingDecision:
    """
    Walk ranked_windows (ascending by carbon intensity) within [now,
    deadline). For the first window with flexible-pool room, cross-wire
    with IdleHunter's capacity forecast (MUST HAVE #9):
      - enough capacity -> proceed with this window.
      - not enough, but standby hosts exist and there's more lead time
        than the wake latency -> request a pre-wake and proceed anyway.
      - otherwise -> move on to the next-best window.
    """
    for window in ranked_windows:
        window_start = datetime.fromisoformat(window.windowStart)
        if window_start < now or window_start >= deadline:
            continue
        if pool.available_capacity(window) < required_capacity:
            continue

        forecast = get_capacity_forecast(window.windowStart, window.windowEnd)

        if forecast.availableCpuCapacity >= required_capacity:
            pool.reserve(window, required_capacity)
            return SchedulingDecision(
                jobId=job_id,
                windowStart=window.windowStart,
                proceed=True,
                prewakeRequested=False,
                reason="sufficient IdleHunter-reported capacity in ranked window",
            )

        lead_time_seconds = (window_start - now).total_seconds()
        if forecast.standbyHostCount > 0 and lead_time_seconds > forecast.estimatedWakeLatencySeconds:
            target_time = window_start - timedelta(seconds=forecast.estimatedWakeLatencySeconds)
            bus.publish(
                "carbonclock.prewake.requested",
                {"jobId": job_id, "targetTime": target_time.isoformat()},
            )
            pool.reserve(window, required_capacity)
            return SchedulingDecision(
                jobId=job_id,
                windowStart=window.windowStart,
                proceed=True,
                prewakeRequested=True,
                reason="insufficient capacity; pre-wake requested to cover the shortfall",
            )
        # Insufficient capacity and no viable pre-wake -- try the next-best window.

    return SchedulingDecision(
        jobId=job_id,
        windowStart=None,
        proceed=False,
        prewakeRequested=False,
        reason="no window before the deadline has sufficient capacity",
    )


# ---------------------------------------------------------------------------
# SHOULD HAVE #12 -- electricity-price signal alongside carbon
# ---------------------------------------------------------------------------

DEFAULT_CARBON_WEIGHT = 0.7
DEFAULT_PRICE_WEIGHT = 0.3


def rank_windows_by_carbon_and_price(
    windows: list[HourlyForecast],
    price_by_window_start: Optional[dict[str, float]],
    *,
    w_carbon: float = DEFAULT_CARBON_WEIGHT,
    w_price: float = DEFAULT_PRICE_WEIGHT,
) -> list[HourlyForecast]:
    """
    score(hour) = w_carbon * carbonRank(hour) + w_price * priceRank(hour)
    Falls back to carbon-only ranking if no price feed is available (the
    methodology's own fallback for an unreachable price API).
    """
    if not price_by_window_start:
        return rank_windows_by_intensity(windows)

    carbon_rank = {
        w.windowStart: rank for rank, w in enumerate(sorted(windows, key=lambda w: w.carbonIntensity))
    }
    # Windows with no price data rank last on the price axis, rather than
    # being dropped -- a missing single-hour price shouldn't disqualify a
    # window the way a fully unreachable price API falls back entirely.
    price_sorted = sorted(windows, key=lambda w: price_by_window_start.get(w.windowStart, float("inf")))
    price_rank = {w.windowStart: rank for rank, w in enumerate(price_sorted)}

    def score(window: HourlyForecast) -> float:
        return w_carbon * carbon_rank[window.windowStart] + w_price * price_rank[window.windowStart]

    return sorted(windows, key=score)
