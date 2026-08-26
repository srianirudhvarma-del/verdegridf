"""
carbonclock/jobs.py

MUST HAVE #6 -- workload classification, reusing the shared WorkloadTag
contract exactly as IdleHunter does (shared/classification.py), keyed by
jobId instead of vmId. Same fail-safe-open default: an untagged or
unclassified job is "protected" and is never delayed.

MUST HAVE #7 -- hard maximum-delay deadline per deferrable job. The
scheduler (scheduler.py) is free to try to place a job into a green
window, but this queue is the backstop: whatever scheduler.py decides,
any job past its deadline must force-run regardless of current carbon
state.
"""

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel

from shared.classification import WorkloadClassificationStore, classification_store
from shared.eventbus import EventBus, event_bus


class DeferrableJob(BaseModel):
    jobId: str
    submittedAt: str
    maxDelayMinutes: int
    deadline: str


def submit_job(
    job_id: str,
    submitted_at: datetime,
    *,
    store: WorkloadClassificationStore = classification_store,
) -> Optional[DeferrableJob]:
    """
    Returns a DeferrableJob only if job_id is explicitly tagged
    "deferrable" in the shared classification store. An untagged,
    unclassified, or explicitly protected job returns None -- meaning
    "run now, never delayed," the fail-safe-open default.
    """
    if not store.is_deferrable(job_id):
        return None

    tag = store.get_tag(job_id)
    # store.is_deferrable() only returns True for a tag whose classification
    # is "deferrable", and WorkloadTag's own validator requires
    # maxDelayMinutes whenever classification is "deferrable" -- so this is
    # always present here, not an optional lookup.
    deadline = submitted_at + timedelta(minutes=tag.maxDelayMinutes)
    return DeferrableJob(
        jobId=job_id,
        submittedAt=submitted_at.isoformat(),
        maxDelayMinutes=tag.maxDelayMinutes,
        deadline=deadline.isoformat(),
    )


@dataclass(order=True)
class _QueueEntry:
    deadline: datetime
    job: DeferrableJob = field(compare=False)


class DeadlineQueue:
    """Priority queue of DeferrableJobs, sorted by deadline ascending."""

    def __init__(self) -> None:
        self._heap: list[_QueueEntry] = []

    def add(self, job: DeferrableJob) -> None:
        heapq.heappush(self._heap, _QueueEntry(datetime.fromisoformat(job.deadline), job))

    def peek_next_deadline(self) -> Optional[DeferrableJob]:
        return self._heap[0].job if self._heap else None

    def force_release_overdue(self, now: datetime) -> list[DeferrableJob]:
        """
        Rule: force-run any job where now >= deadline, regardless of
        current carbon state. Pops and returns every job whose deadline
        has passed; a scheduled cron/interval check (every 1-5 min per the
        methodology) is expected to call this repeatedly.

        This is a pure queue operation -- it does not, by itself, cause
        anything else in the system to know the job ran. Production code
        should call force_run_overdue() below instead, which is the same
        release plus the real production side-effect.
        """
        released = []
        while self._heap and self._heap[0].deadline <= now:
            released.append(heapq.heappop(self._heap).job)
        return released

    def force_run_overdue(self, now: datetime, *, bus: EventBus = event_bus) -> list[DeferrableJob]:
        """
        The real production path for MUST HAVE #7: force-releases every
        job past its deadline (force_release_overdue above) and publishes
        carbonclock.job.scheduled for each one, tagged forceRun=True.

        carbonclock.job.scheduled has been a defined topic since Phase 0
        but nothing ever published to it -- the same "publish to nobody"
        gap the Phase 8b verification found for carbonclock.prewake.requested.
        shared.orchestrator.JobExecutionTracker is the real subscriber.
        """
        released = self.force_release_overdue(now)
        for job in released:
            bus.publish(
                "carbonclock.job.scheduled",
                {"jobId": job.jobId, "windowStart": now.isoformat(), "forceRun": True},
            )
        return released

    def __len__(self) -> int:
        return len(self._heap)
