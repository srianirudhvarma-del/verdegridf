"""
shared/scheduler_driver.py -- Phase 8c: periodic driver.

Investigation finding (see idlehunter/power.py): DwellStateMachine has no
internal clock. NORMAL->IDLE_CANDIDATE depends on the *count* of observe()
calls (consecutive samples), not elapsed wall-clock time, and
STANDBY->WAKING/WAKING->NORMAL are purely reactive to explicit
request_wake()/wake_confirmed() calls with no timeout built in. Nothing in
production code called wake_confirmed() before this phase -- once
shared.orchestrator.PrewakeSubscriber moved a host to WAKING, it stayed
there forever. "When did this host start waking" has to be tracked
externally, and tick() below is the sole place that does it -- recording
the wake start on the first tick that observes a host as WAKING, so the
whole driver is driven by one clock (the `now` passed into tick()), never
real wall-clock time read from inside a subscriber.

Separately: gridsync.jobs.DeadlineQueue.force_run_overdue() only does
the right thing when something calls it at the right moment -- nothing in
a running system called it on its own.

This file is that "something": SchedulerRegistry is the central place
every live DeadlineQueue and DwellStateMachine instance registers into
(rather than only the ones a test constructs locally), and tick(now) is a
pure periodic driver step -- no sleeping, no wall-clock access of its own
-- that a real interval loop (main.py) or a test (many simulated ticks)
can drive.
"""

from datetime import datetime
from typing import TypedDict

from gridsync.jobs import DeadlineQueue
from idlehunter.power import DwellStateMachine, HostState
from shared.eventbus import EventBus, event_bus

# Mirrors shared/orchestrator.py's DEFAULT_ESTIMATED_WAKE_LATENCY_SECONDS --
# not imported from there to avoid a needless cross-module coupling for a
# single constant; both represent the same "no real BMC wake-latency
# measurement exists" placeholder.
DEFAULT_WAKE_LATENCY_SECONDS = 180.0


class SchedulerRegistry:
    """
    Central registry so tick() can iterate every live DeadlineQueue and
    DwellStateMachine instance in a running system, instead of only the
    ones a test constructs locally.
    """

    def __init__(self) -> None:
        self.deadline_queues: dict[str, DeadlineQueue] = {}
        self.dwell_state_machines: dict[str, DwellStateMachine] = {}
        # DwellStateMachine has no internal clock (see module docstring);
        # this is where "when did this host start waking" actually lives.
        # tick() below is the sole writer -- it records the wake start on
        # the first tick that observes a host as WAKING, so the whole
        # driver stays driven by one clock (the caller's `now`), not real
        # wall-clock time read from inside a subscriber.
        self.wake_started_at: dict[str, datetime] = {}

    def register_deadline_queue(self, name: str, queue: DeadlineQueue) -> None:
        self.deadline_queues[name] = queue

    def unregister_deadline_queue(self, name: str) -> None:
        self.deadline_queues.pop(name, None)

    def register_dwell_state_machine(self, machine: DwellStateMachine) -> None:
        self.dwell_state_machines[machine.host_id] = machine

    def unregister_dwell_state_machine(self, host_id: str) -> None:
        self.dwell_state_machines.pop(host_id, None)
        self.wake_started_at.pop(host_id, None)


# Process-wide singleton, mirroring shared.eventbus.event_bus and
# shared.classification.classification_store.
scheduler_registry = SchedulerRegistry()


class TickResult(TypedDict):
    forceRun: dict[str, list[str]]
    wakeConfirmed: list[str]


def tick(
    now: datetime,
    *,
    registry: SchedulerRegistry = scheduler_registry,
    bus: EventBus = event_bus,
    wake_latency_seconds: float = DEFAULT_WAKE_LATENCY_SECONDS,
) -> TickResult:
    """
    Pure periodic driver step. Takes `now` as a parameter rather than
    reading the wall clock itself, so a test can simulate many ticks
    across simulated hours in milliseconds of real test time.

    1. GridSync deadlines: force_run_overdue(now) on every registered
       DeadlineQueue -- MUST HAVE #7's backstop, actually invoked over
       time instead of only when a caller happens to call it directly.
    2. IdleHunter wake completion: for every DwellStateMachine currently
       WAKING whose recorded wake start is at least wake_latency_seconds
       in the past relative to `now`, call wake_confirmed() -- the real
       production path for "BMC wake confirmed + host rejoins the pool,"
       which previously had no caller anywhere outside tests.
    """
    force_run: dict[str, list[str]] = {}
    for name, queue in registry.deadline_queues.items():
        released = queue.force_run_overdue(now, bus=bus)
        if released:
            force_run[name] = [job.jobId for job in released]

    wake_confirmed: list[str] = []
    for host_id, machine in list(registry.dwell_state_machines.items()):
        if machine.state != HostState.WAKING:
            # Not (or no longer) waking -- clear any stale record so a
            # future wake starts its clock fresh rather than reusing an
            # old timestamp.
            registry.wake_started_at.pop(host_id, None)
            continue

        started_at = registry.wake_started_at.get(host_id)
        if started_at is None:
            # First tick that observes this host as WAKING. tick() is the
            # sole timekeeper for the whole driver (DwellStateMachine has
            # no clock, and PrewakeSubscriber deliberately doesn't touch
            # time either -- see its docstring), so "now" is recorded from
            # here, not from whenever request_wake() happened to be called.
            registry.wake_started_at[host_id] = now
            continue

        if (now - started_at).total_seconds() >= wake_latency_seconds:
            machine.wake_confirmed()
            registry.wake_started_at.pop(host_id, None)
            wake_confirmed.append(host_id)

    return {"forceRun": force_run, "wakeConfirmed": wake_confirmed}
