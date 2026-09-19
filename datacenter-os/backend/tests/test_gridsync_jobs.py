from datetime import datetime, timedelta, timezone

from gridsync.jobs import DeadlineQueue, submit_job
from shared.classification import WorkloadClassificationStore
from shared.contracts import WorkloadTag
from shared.eventbus import EventBus

NOW = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


def tag_job(store, job_id, classification, max_delay=None):
    store.set_tag(
        WorkloadTag(
            workloadId=job_id,
            classification=classification,
            maxDelayMinutes=max_delay,
            source="operator",
            updatedAt=NOW.isoformat(),
        )
    )


# ---------------------------------------------------------------------------
# MUST HAVE #6 -- classification with safe default
# ---------------------------------------------------------------------------


def test_untagged_job_defaults_to_protected_and_is_never_delayed():
    store = WorkloadClassificationStore()
    job = submit_job("job-untagged", NOW, store=store)
    assert job is None


def test_explicitly_protected_job_is_never_delayed():
    store = WorkloadClassificationStore()
    tag_job(store, "job-protected", "protected")
    job = submit_job("job-protected", NOW, store=store)
    assert job is None


def test_deferrable_job_gets_a_deadline_computed_from_max_delay():
    store = WorkloadClassificationStore()
    tag_job(store, "job-batch", "deferrable", max_delay=120)

    job = submit_job("job-batch", NOW, store=store)

    assert job is not None
    assert job.jobId == "job-batch"
    assert job.deadline == (NOW + timedelta(minutes=120)).isoformat()


# ---------------------------------------------------------------------------
# MUST HAVE #7 -- hard maximum-delay deadline
# ---------------------------------------------------------------------------


def test_deadline_queue_pops_in_deadline_order():
    store = WorkloadClassificationStore()
    tag_job(store, "job-a", "deferrable", max_delay=180)
    tag_job(store, "job-b", "deferrable", max_delay=30)

    queue = DeadlineQueue()
    queue.add(submit_job("job-a", NOW, store=store))
    queue.add(submit_job("job-b", NOW, store=store))

    assert queue.peek_next_deadline().jobId == "job-b"


def test_force_release_only_pops_jobs_past_their_deadline():
    store = WorkloadClassificationStore()
    tag_job(store, "job-soon", "deferrable", max_delay=10)
    tag_job(store, "job-later", "deferrable", max_delay=600)

    queue = DeadlineQueue()
    queue.add(submit_job("job-soon", NOW, store=store))
    queue.add(submit_job("job-later", NOW, store=store))

    released = queue.force_release_overdue(NOW + timedelta(minutes=15))

    assert [j.jobId for j in released] == ["job-soon"]
    assert len(queue) == 1


def test_deferrable_job_force_runs_at_deadline_even_if_never_scheduled_into_a_green_window():
    """Acceptance test: a deferrable job that the scheduler never managed to
    place into a green window must still force-run once its deadline
    passes, regardless of carbon state."""
    store = WorkloadClassificationStore()
    tag_job(store, "job-never-scheduled", "deferrable", max_delay=60)

    queue = DeadlineQueue()
    job = submit_job("job-never-scheduled", NOW, store=store)
    queue.add(job)  # scheduler.py never found room for this job -- still queued

    before_deadline = queue.force_release_overdue(NOW + timedelta(minutes=59))
    assert before_deadline == []

    at_deadline = queue.force_release_overdue(NOW + timedelta(minutes=60))
    assert [j.jobId for j in at_deadline] == ["job-never-scheduled"]


def test_force_run_overdue_publishes_gridsync_job_scheduled():
    store = WorkloadClassificationStore()
    tag_job(store, "job-1", "deferrable", max_delay=10)
    queue = DeadlineQueue()
    queue.add(submit_job("job-1", NOW, store=store))

    bus = EventBus()
    received = []
    bus.subscribe("gridsync.job.scheduled", received.append)

    released = queue.force_run_overdue(NOW + timedelta(minutes=10), bus=bus)

    assert [j.jobId for j in released] == ["job-1"]
    assert len(received) == 1
    assert received[0]["jobId"] == "job-1"
    assert received[0]["forceRun"] is True


def test_force_run_overdue_publishes_nothing_when_no_job_is_overdue():
    store = WorkloadClassificationStore()
    tag_job(store, "job-1", "deferrable", max_delay=60)
    queue = DeadlineQueue()
    queue.add(submit_job("job-1", NOW, store=store))

    bus = EventBus()
    received = []
    bus.subscribe("gridsync.job.scheduled", received.append)

    released = queue.force_run_overdue(NOW + timedelta(minutes=5), bus=bus)

    assert released == []
    assert received == []


def test_remove_pops_a_specific_job_before_its_deadline():
    store = WorkloadClassificationStore()
    tag_job(store, "job-1", "deferrable", max_delay=60)
    tag_job(store, "job-2", "deferrable", max_delay=90)
    queue = DeadlineQueue()
    queue.add(submit_job("job-1", NOW, store=store))
    queue.add(submit_job("job-2", NOW, store=store))

    removed = queue.remove("job-1")

    assert removed.jobId == "job-1"
    assert len(queue) == 1
    assert queue.peek_next_deadline().jobId == "job-2"


def test_remove_returns_none_for_an_unknown_job():
    queue = DeadlineQueue()
    assert queue.remove("does-not-exist") is None
