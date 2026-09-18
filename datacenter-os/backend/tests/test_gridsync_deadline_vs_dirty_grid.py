"""
Integration acceptance test for the Section 10 GridSync checklist item:
"A deferrable job force-runs at its deadline even if the grid is still
dirty."

A first version of this test proved the two halves separately: a dirty
grid blocks schedule_deferrable_job in one assertion, and
force_release_overdue pops overdue jobs in a second, unconnected
assertion -- force_release_overdue doesn't take carbon intensity as
input, so that version could never actually distinguish "deadline
overrides a real block" from "the deadline queue just doesn't know about
carbon at all." It also surfaced a real gap: force_release_overdue's
return value was never consumed by anything in production code --
gridsync.job.scheduled has been a defined topic since Phase 0 with no
publisher and no subscriber, the same "publish to nobody" pattern the
Phase 8b audit found for gridsync.prewake.requested.

This version is one continuous scenario against the same job, the same
pool, and the same dirty windows throughout: the real scheduler is
attempted repeatedly across the job's lifetime and shown blocked every
time by the dirty grid specifically, then at the exact deadline instant
the real production force-run path (DeadlineQueue.force_run_overdue(),
added alongside this test) is shown to both release the job AND produce
a real, externally-observable effect -- a JobExecutionTracker, subscribed
on the same event bus, actually recording that the job ran, with no
prior activity for that job on the tracker before the deadline.
"""

from datetime import datetime, timedelta, timezone

from gridsync.grid import HourlyForecast
from gridsync.jobs import DeadlineQueue, submit_job
from gridsync.scheduler import (
    DEFAULT_DIRTY_THRESHOLD,
    SchedulingPool,
    rank_windows_by_intensity,
    schedule_deferrable_job,
)
from shared.classification import WorkloadClassificationStore
from shared.contracts import CapacityForecast, WorkloadTag
from shared.eventbus import EventBus
from shared.orchestrator import JobExecutionTracker

NOW = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)
JOB_ID = "job-dirty-grid"
MAX_DELAY_MINUTES = 180
DEADLINE = NOW + timedelta(minutes=MAX_DELAY_MINUTES)

DIRTY_INTENSITY = DEFAULT_DIRTY_THRESHOLD + 100.0
REQUIRED_CAPACITY = 60.0  # deliberately more than the dirty grid's 50%-floor-capped budget below


def make_dirty_windows() -> list[HourlyForecast]:
    """Every hour across the job's full lifetime is above DEFAULT_DIRTY_THRESHOLD -- no green window ever appears."""
    return rank_windows_by_intensity(
        [
            HourlyForecast(
                windowStart=(NOW + timedelta(hours=h)).isoformat(),
                windowEnd=(NOW + timedelta(hours=h + 1)).isoformat(),
                carbonIntensity=DIRTY_INTENSITY,
            )
            for h in range(3)
        ]
    )


def abundant_capacity_forecast(start: str, end: str) -> CapacityForecast:
    """
    Generous PowerPrune capacity on every window, so that if scheduling
    still fails, it can only be because of the dirty-grid flexible-capacity
    cap -- never because PowerPrune capacity was also scarce.
    """
    return CapacityForecast(
        timestampRangeStart=start, timestampRangeEnd=end,
        poweredOnHostCount=100, availableCpuCapacity=100_000.0, availableMemCapacity=100_000.0,
        standbyHostCount=0, estimatedWakeLatencySeconds=60.0,
    )


def test_deferrable_job_force_runs_at_deadline_even_when_the_grid_is_dirty_throughout():
    windows = make_dirty_windows()
    assert all(w.carbonIntensity > DEFAULT_DIRTY_THRESHOLD for w in windows)
    pool = SchedulingPool(total_flexible_capacity=100.0)  # dirty-grid floor cap -> 50.0 budget/hour, always < REQUIRED_CAPACITY

    store = WorkloadClassificationStore()
    store.set_tag(
        WorkloadTag(
            workloadId=JOB_ID, classification="deferrable", maxDelayMinutes=MAX_DELAY_MINUTES,
            source="operator", updatedAt=NOW.isoformat(),
        )
    )
    job = submit_job(JOB_ID, NOW, store=store)
    assert job.deadline == DEADLINE.isoformat()

    queue = DeadlineQueue()
    queue.add(job)

    bus = EventBus()
    tracker = JobExecutionTracker(bus=bus)
    tracker.register()

    # 1. Attempt real scheduling repeatedly across the job's lifetime, on
    #    the *same* job/pool/windows -- confirm the dirty grid blocks it
    #    every single time, and that nothing has run yet according to the
    #    real subscriber.
    for attempt_offset_minutes in (0, 60, 119):
        now = NOW + timedelta(minutes=attempt_offset_minutes)
        decision = schedule_deferrable_job(
            JOB_ID, REQUIRED_CAPACITY, windows, pool,
            now=now, deadline=DEADLINE, get_capacity_forecast=abundant_capacity_forecast,
        )
        assert decision.proceed is False, f"expected the dirty grid to block scheduling at {now}"
        assert "capacity" in decision.reason

    assert tracker.has_run(JOB_ID) is False  # confirmed unrun at every point before the deadline

    # Independently confirm *why* it was blocked: the dirty grid's floor
    # cap, not PowerPrune capacity (made abundant above) or a deadline
    # already having passed (all attempts were well before DEADLINE).
    assert pool.available_capacity(windows[0]) == 50.0
    assert pool.available_capacity(windows[0]) < REQUIRED_CAPACITY

    # 2. Advance to exactly the deadline. The real scheduler, tried one
    #    more time against the same still-dirty grid, is still blocked.
    decision_at_deadline = schedule_deferrable_job(
        JOB_ID, REQUIRED_CAPACITY, windows, pool,
        now=DEADLINE, deadline=DEADLINE, get_capacity_forecast=abundant_capacity_forecast,
    )
    assert decision_at_deadline.proceed is False
    assert tracker.has_run(JOB_ID) is False  # scheduling attempts alone never mark it as run

    # 3. The real production force-run path: DeadlineQueue.force_run_overdue()
    #    releases the same job and publishes gridsync.job.scheduled on
    #    the same bus the tracker is listening on.
    released = queue.force_run_overdue(DEADLINE, bus=bus)

    assert [j.jobId for j in released] == [JOB_ID]
    assert tracker.has_run(JOB_ID) is True  # the real end effect: an external subscriber now knows it ran
    assert tracker.executions[-1]["forceRun"] is True
