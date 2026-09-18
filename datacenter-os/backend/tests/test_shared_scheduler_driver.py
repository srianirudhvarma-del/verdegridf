from datetime import datetime, timedelta, timezone

from gridsync.jobs import DeadlineQueue, submit_job
from powerprune.power import DwellStateMachine, HostState
from shared.classification import WorkloadClassificationStore
from shared.contracts import WorkloadTag
from shared.eventbus import EventBus
from shared.orchestrator import JobExecutionTracker, PrewakeSubscriber
from shared.scheduler_driver import DEFAULT_WAKE_LATENCY_SECONDS, SchedulerRegistry, tick

NOW = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


def tag_job(store, job_id, max_delay):
    store.set_tag(
        WorkloadTag(
            workloadId=job_id, classification="deferrable", maxDelayMinutes=max_delay,
            source="operator", updatedAt=NOW.isoformat(),
        )
    )


# ---------------------------------------------------------------------------
# SchedulerRegistry
# ---------------------------------------------------------------------------


def test_registry_registers_and_unregisters_deadline_queues():
    registry = SchedulerRegistry()
    queue = DeadlineQueue()
    registry.register_deadline_queue("gridsync", queue)
    assert registry.deadline_queues["gridsync"] is queue

    registry.unregister_deadline_queue("gridsync")
    assert "gridsync" not in registry.deadline_queues


def test_registry_registers_dwell_state_machines_by_host_id():
    registry = SchedulerRegistry()
    machine = DwellStateMachine("host-1")
    registry.register_dwell_state_machine(machine)
    assert registry.dwell_state_machines["host-1"] is machine


def test_registry_unregister_also_clears_wake_started_at():
    registry = SchedulerRegistry()
    machine = DwellStateMachine("host-1")
    registry.register_dwell_state_machine(machine)
    registry.wake_started_at["host-1"] = NOW

    registry.unregister_dwell_state_machine("host-1")

    assert "host-1" not in registry.dwell_state_machines
    assert "host-1" not in registry.wake_started_at


# ---------------------------------------------------------------------------
# tick() -- GridSync deadline side, through ticking alone
# ---------------------------------------------------------------------------


def test_tick_force_runs_an_overdue_job_through_ticking_alone_no_manual_trigger():
    registry = SchedulerRegistry()
    store = WorkloadClassificationStore()
    tag_job(store, "job-1", max_delay=30)
    queue = DeadlineQueue()
    queue.add(submit_job("job-1", NOW, store=store))
    registry.register_deadline_queue("gridsync", queue)

    bus = EventBus()
    tracker = JobExecutionTracker(bus=bus)
    tracker.register()

    # Simulate several ticks across simulated time, well before the deadline.
    for minutes in (5, 10, 20, 29):
        result = tick(NOW + timedelta(minutes=minutes), registry=registry, bus=bus)
        assert result["forceRun"] == {}
        assert tracker.has_run("job-1") is False

    # Tick exactly at the deadline: no manual call to force_run_overdue
    # anywhere in this test -- only tick() was ever invoked.
    result_at_deadline = tick(NOW + timedelta(minutes=30), registry=registry, bus=bus)

    assert result_at_deadline["forceRun"] == {"gridsync": ["job-1"]}
    assert tracker.has_run("job-1") is True


def test_tick_drives_multiple_registered_queues_independently():
    registry = SchedulerRegistry()
    store = WorkloadClassificationStore()
    tag_job(store, "job-fast", max_delay=10)
    tag_job(store, "job-slow", max_delay=60)

    fast_queue = DeadlineQueue()
    fast_queue.add(submit_job("job-fast", NOW, store=store))
    slow_queue = DeadlineQueue()
    slow_queue.add(submit_job("job-slow", NOW, store=store))

    registry.register_deadline_queue("zone-a", fast_queue)
    registry.register_deadline_queue("zone-b", slow_queue)

    bus = EventBus()
    result = tick(NOW + timedelta(minutes=15), registry=registry, bus=bus)

    assert result["forceRun"] == {"zone-a": ["job-fast"]}  # only the fast queue's job is overdue yet


# ---------------------------------------------------------------------------
# tick() -- PowerPrune wake side, through ticking alone
# ---------------------------------------------------------------------------


def test_tick_confirms_a_waking_host_through_ticking_alone_no_manual_trigger():
    registry = SchedulerRegistry()
    machine = DwellStateMachine("host-1", dwell_time_down_samples=1)
    machine.observe("idle-candidate")
    machine.consolidation_succeeded()
    assert machine.state == HostState.STANDBY
    registry.register_dwell_state_machine(machine)

    bus = EventBus()
    subscriber = PrewakeSubscriber(registry.dwell_state_machines, bus=bus)
    subscriber.register()

    bus.publish("gridsync.prewake.requested", {"jobId": "job-1", "targetTime": NOW.isoformat()})
    assert machine.state == HostState.WAKING
    assert "host-1" not in registry.wake_started_at  # not recorded until tick() first observes it

    # tick() is the sole timekeeper: its first call after the wake begins
    # records the wake-start timestamp (from its own `now`, not real wall
    # time) and doesn't confirm yet.
    tick(NOW, registry=registry, bus=bus)
    assert registry.wake_started_at["host-1"] == NOW
    assert machine.state == HostState.WAKING

    # Ticks before the wake latency has elapsed since that recorded start: still WAKING.
    result_early = tick(NOW + timedelta(seconds=DEFAULT_WAKE_LATENCY_SECONDS - 1), registry=registry, bus=bus)
    assert result_early["wakeConfirmed"] == []
    assert machine.state == HostState.WAKING

    # A tick once the wake latency has elapsed since the recorded start:
    # the state machine reaches NORMAL (its "active" state) through
    # ticking alone -- no manual call to wake_confirmed() anywhere in this
    # test.
    result_confirmed = tick(NOW + timedelta(seconds=DEFAULT_WAKE_LATENCY_SECONDS), registry=registry, bus=bus)

    assert result_confirmed["wakeConfirmed"] == ["host-1"]
    assert machine.state == HostState.NORMAL
    assert "host-1" not in registry.wake_started_at


def test_tick_ignores_hosts_not_currently_waking():
    registry = SchedulerRegistry()
    machine = DwellStateMachine("host-1")  # NORMAL, never touched
    registry.register_dwell_state_machine(machine)

    bus = EventBus()
    result = tick(NOW + timedelta(days=1), registry=registry, bus=bus)

    assert result["wakeConfirmed"] == []
    assert machine.state == HostState.NORMAL


def test_tick_across_many_simulated_hours_settles_both_a_deadline_and_a_wake():
    """One registry, one tick loop simulating a full day in a handful of
    calls -- proving both mechanisms work through repeated ticking with no
    real sleeping."""
    registry = SchedulerRegistry()

    store = WorkloadClassificationStore()
    tag_job(store, "job-1", max_delay=120)
    queue = DeadlineQueue()
    queue.add(submit_job("job-1", NOW, store=store))
    registry.register_deadline_queue("gridsync", queue)

    machine = DwellStateMachine("host-1", dwell_time_down_samples=1)
    machine.observe("idle-candidate")
    machine.consolidation_succeeded()
    registry.register_dwell_state_machine(machine)

    bus = EventBus()
    job_tracker = JobExecutionTracker(bus=bus)
    job_tracker.register()
    prewake_subscriber = PrewakeSubscriber(registry.dwell_state_machines, bus=bus)
    prewake_subscriber.register()
    bus.publish("gridsync.prewake.requested", {"jobId": "job-1", "targetTime": NOW.isoformat()})
    assert machine.state == HostState.WAKING

    # Simulate a full day of 30-minute ticks in a normal test-speed loop.
    # tick() records the wake start on its first pass and confirms it on a
    # later one, purely from repeated ticking.
    for step in range(1, 49):  # 48 * 30min = 24h
        simulated_now = NOW + timedelta(minutes=30 * step)
        tick(simulated_now, registry=registry, bus=bus)

    assert job_tracker.has_run("job-1") is True  # 120min deadline, long since passed
    assert machine.state == HostState.NORMAL  # wake latency long since elapsed
