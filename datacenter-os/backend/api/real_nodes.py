"""
api/real_nodes.py -- real hardware integration wiring: turns real laptop
telemetry (shared/real_agent.py) into the same actions the simulated
hosts already produce, by reusing the real algorithm modules unchanged --
powerprune/threshold.py's MAD classifier, powerprune/power.py's dwell
state machine, and thermos/control.py's supervised approval queue.

Real hosts are not part of api/state.py's fixed 5x4 simulated topology --
they self-register (RealAgentRegistry.known_hosts) the first time their
agent posts a sample, since the exact machine ids aren't known in advance
the way the simulated rack/host names are.

Two things a real laptop needs that a simulated rack host doesn't:

1. "Idle" doesn't mean "migrate workloads off and power down" -- there's
   nothing to migrate. It means asking the person in front of the laptop
   whether to sleep it. RealCommandQueue.enqueue(..., "sleep_prompt", ...)
   is that ask; the actual sleep only happens if the real-agent's local
   prompt is accepted (see datacenter-os/real-agent/agent.py).
2. "Adjust fan speed" (thermos/control.py's existing ActionType -- this
   codebase already had the type, just nothing that produced or executed
   it for a real host) still goes through the same supervised
   ActionRecommendationQueue as every other ThermOS action -- an operator
   must approve it in the dashboard before RealNodeManager.mark_fan_executed
   is even called. Reverting the fan speed once the hotspot clears is the
   one thing this module does *without* approval, since lowering fan
   speed back to auto is the safe direction (same fail-safe-open shape as
   everything else in this codebase: the escalation needs a human, the
   de-escalation doesn't).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from powerprune.power import DwellStateMachine, HostState
from powerprune.threshold import classify_host
from shared.real_agent import RealAgentRegistry, predict_hotspot
from shared.scheduler_driver import SchedulerRegistry
from thermos.control import ActionRecommendation, ActionRecommendationQueue

CommandType = Literal["sleep_prompt", "fan_max_on", "fan_max_off"]

DEFAULT_STALE_SECONDS = 20.0
DEFAULT_CRITICAL_TEMP_C = 92.0
DEFAULT_HOTSPOT_HORIZON_SECONDS = 60.0


@dataclass
class RealCommand:
    id: str
    hostId: str
    type: CommandType
    payload: dict
    issuedAt: str


class RealCommandQueue:
    """
    One pending command per host at a time. A laptop's agent polls for
    its own commands, so there's no benefit to queueing more than the
    latest actionable one -- and queueing would risk the agent executing
    a sleep prompt whose moment (and dwell state) has already moved on.
    """

    def __init__(self) -> None:
        self._pending: dict[str, RealCommand] = {}
        self._by_id: dict[str, RealCommand] = {}
        self._acks: dict[str, dict] = {}

    def enqueue(self, host_id: str, type_: CommandType, payload: dict) -> RealCommand:
        command = RealCommand(
            id=str(uuid4()),
            hostId=host_id,
            type=type_,
            payload=payload,
            issuedAt=datetime.now(timezone.utc).isoformat(),
        )
        self._pending[host_id] = command
        self._by_id[command.id] = command
        return command

    def poll(self, host_id: str) -> Optional[RealCommand]:
        """Pops the pending command for a host -- an agent that receives
        one is expected to act on it (or ack a decline), not see it again."""
        return self._pending.pop(host_id, None)

    def ack(self, command_id: str, result: str, detail: str = "") -> dict:
        command = self._by_id.get(command_id)
        if command is None:
            raise KeyError(f"unknown command: {command_id!r}")
        record = {
            "commandId": command_id,
            "hostId": command.hostId,
            "type": command.type,
            "result": result,
            "detail": detail,
        }
        self._acks[command_id] = record
        return record

    def last_ack_for_host(self, host_id: str) -> Optional[dict]:
        for record in reversed(list(self._acks.values())):
            if record["hostId"] == host_id:
                return record
        return None


class RealNodeManager:
    """
    Owns the per-real-host DwellStateMachines plus the edge-trigger state
    ("already prompted this idle episode", "fan currently maxed") that
    keeps tick() from re-firing the same command every 5s. Every
    DwellStateMachine it creates is registered into the same
    shared.scheduler_driver.SchedulerRegistry the simulated hosts use, so
    a real host's WAKING->NORMAL transition (irrelevant here, since a real
    laptop's own owner wakes it, not a BMC call) never gets stuck the way
    Phase 8c found the simulated ones could -- there's simply no code path
    that ever calls request_wake() for a real host.
    """

    def __init__(self, *, scheduler_registry: SchedulerRegistry) -> None:
        self._scheduler_registry = scheduler_registry
        self.dwell_machines: dict[str, DwellStateMachine] = {}
        self._sleep_prompted: set[str] = set()
        self._fan_maxed: set[str] = set()

    def _dwell_for(self, host_id: str) -> DwellStateMachine:
        machine = self.dwell_machines.get(host_id)
        if machine is None:
            machine = DwellStateMachine(host_id)
            self.dwell_machines[host_id] = machine
            self._scheduler_registry.register_dwell_state_machine(machine)
        return machine

    def mark_fan_executed(self, host_id: str) -> None:
        """Called once an approved adjust_fan_speed recommendation has
        actually been turned into a real fan_max_on command (see
        api/routes.py's approve_action) -- this is what lets a later tick
        know to send fan_max_off once the hotspot clears."""
        self._fan_maxed.add(host_id)

    def tick(
        self,
        now: datetime,
        *,
        registry: RealAgentRegistry,
        command_queue: RealCommandQueue,
        action_queue: ActionRecommendationQueue,
        stale_seconds: float = DEFAULT_STALE_SECONDS,
        critical_temp_c: float = DEFAULT_CRITICAL_TEMP_C,
        hotspot_horizon_seconds: float = DEFAULT_HOTSPOT_HORIZON_SECONDS,
    ) -> dict:
        prompted_sleep: list[str] = []
        fan_events: list[tuple[str, str]] = []

        for host_id in registry.known_hosts():
            if registry.is_stale(host_id, now, max_age_seconds=stale_seconds):
                # Fail-safe-open: no fresh data this tick -> no action at
                # all for this host, rather than acting on stale numbers.
                continue

            current = registry.current_resources(host_id)
            history = {resource: registry.history(host_id, resource, 120) for resource in current}
            status = classify_host(host_id, current, history, timestamp=now.isoformat()).status

            machine = self._dwell_for(host_id)
            new_state = machine.observe(status)

            if new_state == HostState.IDLE_CANDIDATE:
                if host_id not in self._sleep_prompted:
                    idle_minutes = round(machine.dwell_time_down_samples * stale_seconds / 60.0, 1)
                    command_queue.enqueue(host_id, "sleep_prompt", {"idleMinutes": idle_minutes})
                    self._sleep_prompted.add(host_id)
                    prompted_sleep.append(host_id)
            else:
                self._sleep_prompted.discard(host_id)

            latest = registry.latest(host_id)
            temp_history = registry.field_history(host_id, "cpuTempC", 30)
            if latest is None or latest.cpuTempC is None or not temp_history:
                continue

            prediction = predict_hotspot(
                host_id,
                temp_history,
                freq_current=latest.cpuFreqMhz,
                freq_max=latest.cpuFreqMaxMhz,
                critical_temp_c=critical_temp_c,
                horizon_seconds=hotspot_horizon_seconds,
                sample_interval_seconds=stale_seconds / 4.0,
            )

            if prediction.riskLevel == "critical" and host_id not in self._fan_maxed:
                already_pending = any(
                    rec.rackId == host_id and rec.type == "adjust_fan_speed" for rec in action_queue.pending()
                )
                if not already_pending:
                    action_queue.submit(
                        ActionRecommendation(
                            id=f"real-fan-{host_id}-{int(now.timestamp())}",
                            type="adjust_fan_speed",
                            rackId=host_id,
                            magnitude=100.0,
                            predictedBenefit=(
                                f"{host_id}: CPU {prediction.currentTempC:.1f}C now, projected "
                                f"{prediction.projectedTempC:.1f}C in {hotspot_horizon_seconds:.0f}s at "
                                f"{latest.cpuFreqMhz:.0f}/{latest.cpuFreqMaxMhz:.0f}MHz -- enable max fan mode"
                            ),
                        )
                    )
                    fan_events.append(("recommended", host_id))
            elif prediction.riskLevel == "ok" and host_id in self._fan_maxed:
                command_queue.enqueue(host_id, "fan_max_off", {"reason": "temperature back to normal"})
                self._fan_maxed.discard(host_id)
                fan_events.append(("reverted", host_id))

        return {"promptedSleep": prompted_sleep, "fanEvents": fan_events}
