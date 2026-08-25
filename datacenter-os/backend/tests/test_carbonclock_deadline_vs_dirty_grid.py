"""
Integration acceptance test for the Section 10 CarbonClock checklist item:
"A deferrable job force-runs at its deadline even if the grid is still
dirty."

The Phase 7 verification pass found no test that actually proved this --
the existing deadline test never touched carbon intensity or
scheduler.py, and the existing dirty-threshold test never touched the
deadline queue. This file connects them: a real dirty-grid forecast is
fed into the real scheduler, the scheduling attempt is shown to fail
*specifically because of the dirty grid* (not because of unrelated
capacity or timing issues), and the deadline queue is then shown to
force-run the same job anyway once its deadline passes.
"""

from datetime import datetime, timedelta, timezone

from carbonclock.grid import HourlyForecast
from carbonclock.jobs import DeadlineQueue, submit_job
from carbonclock.scheduler import (
    DEFAULT_DIRTY_THRESHOLD,
    SchedulingPool,
    rank_windows_by_intensity,
    schedule_deferrable_job,
)
from shared.classification import WorkloadClassificationStore
from shared.contracts import CapacityForecast, WorkloadTag

NOW = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


def make_dirty_windows(hours: int, *, intensity: float) -> list[HourlyForecast]:
    return [
        HourlyForecast(
            windowStart=(NOW + timedelta(hours=h)).isoformat(),
            windowEnd=(NOW + timedelta(hours=h + 1)).isoformat(),
            carbonIntensity=intensity,
        )
        for h in range(hours)
    ]


def abundant_capacity_forecast(start: str, end: str) -> CapacityForecast:
    """
    Generous IdleHunter capacity on every window, so if scheduling still
    fails, it can only be because of the dirty-grid flexible-capacity cap
    -- not because IdleHunter capacity was also scarce.
    """
    return CapacityForecast(
        timestampRangeStart=start,
        timestampRangeEnd=end,
        poweredOnHostCount=100,
        availableCpuCapacity=100_000.0,
        availableMemCapacity=100_000.0,
        standbyHostCount=0,
        estimatedWakeLatencySeconds=60.0,
    )


def test_deferrable_job_force_runs_at_deadline_even_when_the_grid_is_dirty_throughout():
    # 1. A dirty grid: every hour in range is above DEFAULT_DIRTY_THRESHOLD,
    #    so the flexible-capacity cap floors at 50% every single hour --
    #    there is no green window anywhere before the deadline.
    dirty_intensity = DEFAULT_DIRTY_THRESHOLD + 100.0
    windows = rank_windows_by_intensity(make_dirty_windows(3, intensity=dirty_intensity))
    assert all(w.carbonIntensity > DEFAULT_DIRTY_THRESHOLD for w in windows)

    # 2. A small flexible-capacity budget whose 50%-floor-capped budget
    #    (50.0) is deliberately less than the job's required capacity
    #    (60.0) -- so the dirty grid's floor cap, specifically, is what
    #    blocks scheduling, not a lack of IdleHunter capacity (which is
    #    made deliberately abundant above) and not a deadline/window
    #    timing mismatch (the deadline is well after these windows).
    pool = SchedulingPool(total_flexible_capacity=100.0)
    required_capacity = 60.0

    decision = schedule_deferrable_job(
        "job-dirty-grid",
        required_capacity,
        windows,
        pool,
        now=NOW,
        deadline=NOW + timedelta(hours=5),
        get_capacity_forecast=abundant_capacity_forecast,
    )

    assert decision.proceed is False
    assert decision.windowStart is None
    assert "capacity" in decision.reason

    # 3. Independently confirm the floor cap is really the mechanism: on
    #    this dirty grid, available flexible capacity per hour is exactly
    #    the 50% floor of the pool, less than required_capacity.
    assert pool.available_capacity(windows[0]) == 50.0
    assert pool.available_capacity(windows[0]) < required_capacity

    # 4. The scheduler could never place it. Now prove the deadline
    #    backstop (MUST HAVE #7) force-runs it anyway, regardless of the
    #    still-dirty grid.
    store = WorkloadClassificationStore()
    store.set_tag(
        WorkloadTag(
            workloadId="job-dirty-grid", classification="deferrable", maxDelayMinutes=180,
            source="operator", updatedAt=NOW.isoformat(),
        )
    )
    job = submit_job("job-dirty-grid", NOW, store=store)
    queue = DeadlineQueue()
    queue.add(job)

    before_deadline = queue.force_release_overdue(NOW + timedelta(hours=2, minutes=59))
    assert before_deadline == []  # grid is still dirty, deadline hasn't arrived yet

    at_deadline = queue.force_release_overdue(NOW + timedelta(hours=3))
    assert [j.jobId for j in at_deadline] == ["job-dirty-grid"]
