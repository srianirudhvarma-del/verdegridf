from datetime import datetime, timedelta, timezone

import pytest

from gridsync.grid import HourlyForecast
from gridsync.scheduler import (
    DEFAULT_DIRTY_THRESHOLD,
    DEFAULT_FLOOR_CAP_PERCENT,
    DEFAULT_GREEN_THRESHOLD,
    SchedulingPool,
    flexible_capacity_cap_percent,
    rank_windows_by_intensity,
    schedule_deferrable_job,
)
from shared.contracts import CapacityForecast
from shared.eventbus import EventBus

NOW = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


def make_window(hour_offset, intensity):
    start = NOW + timedelta(hours=hour_offset)
    return HourlyForecast(
        windowStart=start.isoformat(),
        windowEnd=(start + timedelta(hours=1)).isoformat(),
        carbonIntensity=intensity,
    )


def make_capacity_forecast(*, available_cpu, standby_hosts=0, wake_latency=300.0):
    return CapacityForecast(
        timestampRangeStart=NOW.isoformat(),
        timestampRangeEnd=(NOW + timedelta(hours=1)).isoformat(),
        poweredOnHostCount=10,
        availableCpuCapacity=available_cpu,
        availableMemCapacity=1000.0,
        standbyHostCount=standby_hosts,
        estimatedWakeLatencySeconds=wake_latency,
    )


# ---------------------------------------------------------------------------
# Core capacity-curve algorithm
# ---------------------------------------------------------------------------


def test_cap_is_full_below_green_threshold():
    assert flexible_capacity_cap_percent(DEFAULT_GREEN_THRESHOLD - 1) == 100.0


def test_cap_is_floor_above_dirty_threshold():
    assert flexible_capacity_cap_percent(DEFAULT_DIRTY_THRESHOLD + 1) == DEFAULT_FLOOR_CAP_PERCENT


def test_cap_interpolates_strictly_between_floor_and_full_in_the_middle_band():
    midpoint = (DEFAULT_GREEN_THRESHOLD + DEFAULT_DIRTY_THRESHOLD) / 2
    cap = flexible_capacity_cap_percent(midpoint)
    assert DEFAULT_FLOOR_CAP_PERCENT < cap < 100.0


def test_rank_windows_orders_ascending_by_intensity():
    windows = [make_window(0, 300.0), make_window(1, 100.0), make_window(2, 500.0)]
    ranked = rank_windows_by_intensity(windows)
    assert [w.carbonIntensity for w in ranked] == [100.0, 300.0, 500.0]


# ---------------------------------------------------------------------------
# MUST HAVE #9 -- cross-wire with PowerPrune capacity
# ---------------------------------------------------------------------------


def test_schedules_into_greenest_window_with_sufficient_capacity():
    windows = rank_windows_by_intensity([make_window(0, 100.0), make_window(1, 300.0)])
    pool = SchedulingPool(total_flexible_capacity=1000.0)

    decision = schedule_deferrable_job(
        "job-1",
        required_capacity=100.0,
        ranked_windows=windows,
        pool=pool,
        now=NOW,
        deadline=NOW + timedelta(hours=5),
        get_capacity_forecast=lambda start, end: make_capacity_forecast(available_cpu=500.0),
    )

    assert decision.proceed is True
    assert decision.windowStart == windows[0].windowStart
    assert decision.prewakeRequested is False


def test_requests_prewake_when_capacity_short_but_standby_and_lead_time_available():
    windows = rank_windows_by_intensity([make_window(2, 100.0)])  # 2h lead time
    pool = SchedulingPool(total_flexible_capacity=1000.0)
    bus = EventBus()
    received = []
    bus.subscribe("gridsync.prewake.requested", received.append)

    decision = schedule_deferrable_job(
        "job-1",
        required_capacity=200.0,
        ranked_windows=windows,
        pool=pool,
        now=NOW,
        deadline=NOW + timedelta(hours=5),
        get_capacity_forecast=lambda start, end: make_capacity_forecast(
            available_cpu=50.0, standby_hosts=2, wake_latency=300.0  # 5 min << 2h lead time
        ),
        bus=bus,
    )

    assert decision.proceed is True
    assert decision.prewakeRequested is True
    assert len(received) == 1
    assert received[0]["jobId"] == "job-1"


def test_moves_to_next_window_when_no_prewake_is_viable():
    windows = rank_windows_by_intensity([make_window(0, 100.0), make_window(1, 300.0)])
    pool = SchedulingPool(total_flexible_capacity=1000.0)

    def forecast(start, end):
        if start == windows[0].windowStart:
            # no standby hosts available -- prewake impossible, must skip
            return make_capacity_forecast(available_cpu=10.0, standby_hosts=0)
        return make_capacity_forecast(available_cpu=500.0)

    decision = schedule_deferrable_job(
        "job-1",
        required_capacity=100.0,
        ranked_windows=windows,
        pool=pool,
        now=NOW,
        deadline=NOW + timedelta(hours=5),
        get_capacity_forecast=forecast,
    )

    assert decision.proceed is True
    assert decision.windowStart == windows[1].windowStart


def test_proceed_false_when_no_window_before_deadline_has_capacity():
    """This is the case gridsync/jobs.py's DeadlineQueue backstops --
    the job stays queued and force-runs at its deadline instead."""
    windows = rank_windows_by_intensity([make_window(0, 100.0)])
    pool = SchedulingPool(total_flexible_capacity=1000.0)

    decision = schedule_deferrable_job(
        "job-1",
        required_capacity=100.0,
        ranked_windows=windows,
        pool=pool,
        now=NOW,
        deadline=NOW + timedelta(hours=5),
        get_capacity_forecast=lambda start, end: make_capacity_forecast(available_cpu=10.0, standby_hosts=0),
    )

    assert decision.proceed is False
    assert decision.windowStart is None


def test_windows_at_or_after_the_deadline_are_never_considered():
    windows = rank_windows_by_intensity([make_window(5, 50.0)])  # 5h out
    pool = SchedulingPool(total_flexible_capacity=1000.0)

    decision = schedule_deferrable_job(
        "job-1",
        required_capacity=100.0,
        ranked_windows=windows,
        pool=pool,
        now=NOW,
        deadline=NOW + timedelta(hours=2),  # deadline before the only window
        get_capacity_forecast=lambda start, end: make_capacity_forecast(available_cpu=500.0),
    )

    assert decision.proceed is False


def test_pool_reservation_is_exhausted_by_repeated_scheduling():
    windows = rank_windows_by_intensity([make_window(0, 100.0)])
    pool = SchedulingPool(total_flexible_capacity=150.0)  # cap=100% at intensity=100 -> budget 150

    first = schedule_deferrable_job(
        "job-1", required_capacity=100.0, ranked_windows=windows, pool=pool,
        now=NOW, deadline=NOW + timedelta(hours=5),
        get_capacity_forecast=lambda start, end: make_capacity_forecast(available_cpu=500.0),
    )
    second = schedule_deferrable_job(
        "job-2", required_capacity=100.0, ranked_windows=windows, pool=pool,
        now=NOW, deadline=NOW + timedelta(hours=5),
        get_capacity_forecast=lambda start, end: make_capacity_forecast(available_cpu=500.0),
    )

    assert first.proceed is True
    assert second.proceed is False  # only 50 of the 150 budget remains, job-2 needs 100
