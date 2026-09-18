"""
shared/orchestrator.py -- Phase 8b: real cross-module orchestration.

The verification pass after Phase 7 found that every cross-module
dependency in the change list's dependency map was a correctly-typed
interface (a Callable parameter or a shared Pydantic schema) that nothing
in the codebase actually called with real data -- each module's logic was
independently correct and independently tested, but never wired to any
other module's real output.

This file is the wiring: one function per dependency in the map, each
taking real adapter/telemetry instances and calling the downstream
module's real function with real upstream data, not a caller-supplied
stub. It does not replace api/routes.py (still frontend-facing mock data,
untouched per the Phase 9 sequencing decision) -- it's the integration
layer the individual module packages were always meant to be called
through.
"""

from datetime import datetime, timezone
from typing import Optional

from carbonclock.grid import HourlyForecast
from carbonclock.scheduler import SchedulingDecision, SchedulingPool, schedule_deferrable_job
from idlehunter.consolidation import filter_targets_by_thermal_headroom
from idlehunter.power import DwellStateMachine, HostState
from idlehunter.telemetry import IdleHunterTelemetry
from netpulse.flow import Flow
from netpulse.routing import IpToVmLookup, auto_tag_latency_sensitivity
from shared.classification import WorkloadClassificationStore, classification_store
from shared.contracts import CapacityForecast, ThermalHeadroom, WorkloadTag
from shared.eventbus import EventBus, event_bus
from thermaltrace.model import IdleHunterRackReading, ThermalFeatureVector, build_feature_vector
from thermaltrace.sensors import ThermalTelemetry
from coolsense.baseline import LoadBucket, bucket_utilization
from coolsense.cooling import cooling_performance
from coolsense.sensors import CoolSenseTelemetry

# Same idle/active watt figures api/routes.py's mock ServerData already uses,
# reused here to derive a power estimate from a host's real cpu utilization.
HOST_IDLE_WATTS = 120.0
HOST_ACTIVE_WATTS = 280.0

# ThermalTrace doesn't (yet) expose a documented ASHRAE-envelope ceiling
# per rack; this is a facility-wide placeholder default, tunable per site.
DEFAULT_THERMAL_CEILING_CELSIUS = 35.0
DEFAULT_CONSTRAINED_HEADROOM_CELSIUS = 5.0

# No real BMC wake-latency measurement exists; a documented placeholder,
# same spirit as every other simulated constant in this codebase.
DEFAULT_ESTIMATED_WAKE_LATENCY_SECONDS = 180.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Dependency 1: IdleHunter -> ThermalTrace (load/power telemetry)
# ---------------------------------------------------------------------------


def build_rack_feature_vector(
    rack_id: str,
    host_ids: list[str],
    idlehunter_telemetry: IdleHunterTelemetry,
    thermal_telemetry: ThermalTelemetry,
    *,
    timestamp: Optional[str] = None,
) -> ThermalFeatureVector:
    """
    Aggregates this rack's hosts' *real* current IdleHunter telemetry (mean
    cpu utilization, total power draw estimated from it) into a single
    rack-level IdleHunterRackReading, then calls
    thermaltrace.model.build_feature_vector -- the actual MUST HAVE #19
    join, fed by real upstream data instead of a caller-supplied list.
    """
    if not host_ids:
        raise ValueError(f"no hosts given for rack {rack_id!r}")

    ts = timestamp or _now_iso()
    cpu_readings = [idlehunter_telemetry.current(host_id)["cpu"] for host_id in host_ids]
    mean_cpu_pct = sum(cpu_readings) / len(cpu_readings)
    total_power_watts = sum(
        HOST_IDLE_WATTS + (HOST_ACTIVE_WATTS - HOST_IDLE_WATTS) * (cpu_pct / 100.0) for cpu_pct in cpu_readings
    )
    readings = [
        IdleHunterRackReading(rackId=rack_id, timestamp=ts, workloadUtil=mean_cpu_pct / 100.0, powerDrawWatts=total_power_watts)
    ]

    thermal_current = thermal_telemetry.current(rack_id)
    return build_feature_vector(
        rack_id,
        ts,
        temp_grid=[[thermal_current["temperature"]]],
        humidity=thermal_current["humidity"],
        idlehunter_readings=readings,
    )


# ---------------------------------------------------------------------------
# Dependency 2: ThermalTrace -> IdleHunter (thermal headroom)
# ---------------------------------------------------------------------------


def compute_thermal_headroom(
    rack_id: str,
    thermal_telemetry: ThermalTelemetry,
    *,
    ceiling_celsius: float = DEFAULT_THERMAL_CEILING_CELSIUS,
    constrained_headroom_celsius: float = DEFAULT_CONSTRAINED_HEADROOM_CELSIUS,
    timestamp: Optional[str] = None,
) -> ThermalHeadroom:
    """Derives a real ThermalHeadroom from this rack's actual current ThermalTrace temperature reading."""
    current_temp = thermal_telemetry.current(rack_id)["temperature"]
    headroom_celsius = ceiling_celsius - current_temp

    if headroom_celsius <= 0:
        status = "critical"
    elif headroom_celsius < constrained_headroom_celsius:
        status = "constrained"
    else:
        status = "ok"

    return ThermalHeadroom(
        rackId=rack_id, timestamp=timestamp or _now_iso(), headroomCelsius=headroom_celsius, status=status
    )


def filter_consolidation_targets_by_real_headroom(
    host_to_rack: dict[str, str],
    candidate_target_hosts: list[str],
    thermal_telemetry: ThermalTelemetry,
    *,
    ceiling_celsius: float = DEFAULT_THERMAL_CEILING_CELSIUS,
) -> list[str]:
    """
    Calls idlehunter.consolidation.filter_targets_by_thermal_headroom with
    a get_headroom callback backed by real ThermalTrace telemetry --
    compute_thermal_headroom() above -- instead of a caller-supplied stub.
    """
    return filter_targets_by_thermal_headroom(
        host_to_rack,
        candidate_target_hosts,
        lambda rack_id: compute_thermal_headroom(rack_id, thermal_telemetry, ceiling_celsius=ceiling_celsius),
    )


# ---------------------------------------------------------------------------
# Dependency 3: IdleHunter -> CarbonClock (capacity state)
# ---------------------------------------------------------------------------


def compute_capacity_forecast(
    idlehunter_telemetry: IdleHunterTelemetry,
    dwell_state_machines: dict[str, DwellStateMachine],
    window_start: str,
    window_end: str,
    *,
    estimated_wake_latency_seconds: float = DEFAULT_ESTIMATED_WAKE_LATENCY_SECONDS,
) -> CapacityForecast:
    """
    Aggregates real IdleHunter telemetry + real dwell-state-machine state
    across every registered host into a genuine CapacityForecast: hosts
    currently STANDBY count toward standbyHostCount, everything else
    contributes its real (100 - current_utilization) headroom to the
    available capacity totals.
    """
    powered_on = 0
    standby = 0
    available_cpu = 0.0
    available_mem = 0.0

    for host_id in idlehunter_telemetry.host_ids():
        machine = dwell_state_machines.get(host_id)
        if machine is not None and machine.state == HostState.STANDBY:
            standby += 1
            continue
        powered_on += 1
        current = idlehunter_telemetry.current(host_id)
        available_cpu += max(0.0, 100.0 - current["cpu"])
        available_mem += max(0.0, 100.0 - current["mem"])

    return CapacityForecast(
        timestampRangeStart=window_start,
        timestampRangeEnd=window_end,
        poweredOnHostCount=powered_on,
        availableCpuCapacity=available_cpu,
        availableMemCapacity=available_mem,
        standbyHostCount=standby,
        estimatedWakeLatencySeconds=estimated_wake_latency_seconds,
    )


def schedule_job_with_real_capacity(
    job_id: str,
    required_capacity: float,
    ranked_windows: list[HourlyForecast],
    pool: SchedulingPool,
    idlehunter_telemetry: IdleHunterTelemetry,
    dwell_state_machines: dict[str, DwellStateMachine],
    *,
    now,
    deadline,
    bus: EventBus = event_bus,
) -> SchedulingDecision:
    """
    Calls carbonclock.scheduler.schedule_deferrable_job with a
    get_capacity_forecast backed by compute_capacity_forecast() above --
    real IdleHunter telemetry and real dwell state, not a caller-supplied
    CapacityForecast.
    """
    return schedule_deferrable_job(
        job_id,
        required_capacity,
        ranked_windows,
        pool,
        now=now,
        deadline=deadline,
        get_capacity_forecast=lambda start, end: compute_capacity_forecast(
            idlehunter_telemetry, dwell_state_machines, start, end
        ),
        bus=bus,
    )


# ---------------------------------------------------------------------------
# Dependency 4: CarbonClock -> IdleHunter (prewake subscription / wake scheduling)
# ---------------------------------------------------------------------------


class PrewakeSubscriber:
    """
    Subscribes to carbonclock.prewake.requested on the event bus and
    actually calls a STANDBY host's real DwellStateMachine.request_wake()
    -- not just logging the event. carbonclock/scheduler.py's
    schedule_deferrable_job() is the publisher (MUST HAVE #9); this is
    the subscriber the methodology's cross-wire assumed would exist.
    register() must be called once to wire the subscription up.
    """

    def __init__(self, dwell_state_machines: dict[str, DwellStateMachine], *, bus: EventBus = event_bus) -> None:
        self.dwell_state_machines = dwell_state_machines
        self.bus = bus
        self.actions: list[tuple[str, dict]] = []

    def register(self) -> None:
        self.bus.subscribe("carbonclock.prewake.requested", self._on_prewake_requested)

    def _on_prewake_requested(self, payload: dict) -> None:
        # Deliberately does not record a wake-start timestamp here:
        # DwellStateMachine has no clock of its own, and this subscriber
        # only ever sees real wall-clock time when it's actually invoked,
        # which would conflict with shared.scheduler_driver.tick()'s
        # simulated `now`. tick() itself is the sole timekeeper -- it
        # records the wake start on the first tick that observes a host as
        # WAKING, so the whole driver stays driven by one clock.
        for host_id, machine in self.dwell_state_machines.items():
            if machine.state == HostState.STANDBY:
                machine.request_wake(reason=f"carbonclock prewake for job {payload.get('jobId')}")
                self.actions.append((host_id, payload))
                return


# ---------------------------------------------------------------------------
# Dependency 5: IdleHunter -> CoolSense (per-rack workload signal)
# ---------------------------------------------------------------------------


def bucket_rack_load(
    rack_id: str,
    host_ids: list[str],
    idlehunter_telemetry: IdleHunterTelemetry,
    *,
    history_window: int = 60,
) -> LoadBucket:
    """
    Aggregates this rack's hosts' real current + historical IdleHunter cpu
    utilization and calls coolsense.baseline.bucket_utilization() with
    it -- MUST HAVE #12's "bucket time into load buckets using IdleHunter's
    per-rack utilization signal" step, fed by real telemetry instead of a
    caller-supplied list of floats.
    """
    if not host_ids:
        raise ValueError(f"no hosts registered for rack {rack_id!r}")

    current_values = [idlehunter_telemetry.current(host_id)["cpu"] for host_id in host_ids]
    current_avg = sum(current_values) / len(current_values)

    historical: list[float] = []
    for host_id in host_ids:
        historical.extend(idlehunter_telemetry.history(host_id, "cpu", history_window))

    return bucket_utilization(current_avg, historical)


# ---------------------------------------------------------------------------
# Dependency 6: ThermalTrace -> CoolSense (cooling-performance estimate)
# ---------------------------------------------------------------------------

# coolsense/sensors.py's flow_rate metric, like api/routes.py's original
# WaterFlowData mock, is in L/hr; cooling_performance() wants L/s.
_LITERS_PER_HOUR_TO_LITERS_PER_SECOND = 1.0 / 3600.0


def compute_rack_cooling_performance(
    rack_id: str,
    coolsense_telemetry: CoolSenseTelemetry,
    thermal_telemetry: ThermalTelemetry,
    *,
    supply_temp_celsius: float,
) -> float:
    """
    Pulls real flow from CoolSense's own telemetry and real T_return from
    ThermalTrace's telemetry (rack_id must be a loop registered in both),
    then calls coolsense.cooling.cooling_performance() with both real
    readings -- SHOULD HAVE #16's cross-wire, not two caller-supplied
    floats.
    """
    flow_l_per_s = coolsense_telemetry.current(rack_id)["flow_rate"] * _LITERS_PER_HOUR_TO_LITERS_PER_SECOND
    t_return_c = thermal_telemetry.current(rack_id)["temperature"]
    return cooling_performance(flow_l_per_s, t_return_c, supply_temp_celsius)


# ---------------------------------------------------------------------------
# Dependency 7: IdleHunter -> NetPulse (workload classification for
# reroute safety)
# ---------------------------------------------------------------------------


def apply_operator_classification(
    vm_id: str,
    classification: str,
    *,
    max_delay_minutes: Optional[int] = None,
    source: str = "operator",
    store: WorkloadClassificationStore = classification_store,
    timestamp: Optional[str] = None,
) -> WorkloadTag:
    """
    IdleHunter's operator-facing classification write path (methodology
    MUST HAVE #3 step 2: "PATCH /api/idlehunter/workloads/:vmId/classification
    (operator-only)"). This is the one production code path that actually
    calls classification_store.set_tag() -- every consumer
    (idlehunter.consolidation.filter_consolidation_candidates,
    carbonclock.jobs.submit_job, netpulse.routing's
    resolve_latency_sensitivity/tag_latency_sensitivity) reads through the
    exact same store this writes to.
    """
    tag = WorkloadTag(
        workloadId=vm_id,
        classification=classification,
        maxDelayMinutes=max_delay_minutes,
        source=source,
        updatedAt=timestamp or _now_iso(),
    )
    store.set_tag(tag)
    return tag


def tag_flow_with_real_classification(
    flow: Flow,
    lookup: IpToVmLookup,
    *,
    store: WorkloadClassificationStore = classification_store,
) -> Flow:
    """
    Calls netpulse.routing.auto_tag_latency_sensitivity(), reading
    through the same classification store apply_operator_classification()
    above writes to -- the real IdleHunter -> NetPulse link, not just
    two functions that happen to accept the same store type.
    """
    return auto_tag_latency_sensitivity(flow, lookup, store=store)


# ---------------------------------------------------------------------------
# JobExecutionTracker: the real subscriber for carbonclock.job.scheduled --
# a topic defined since Phase 0 that had no publisher until
# carbonclock/jobs.py's force_run_overdue() and no subscriber until this.
# ---------------------------------------------------------------------------


class JobExecutionTracker:
    """
    Subscribes to carbonclock.job.scheduled and records the real effect of
    a job actually starting to run. Right now the only publisher is
    carbonclock/jobs.py's DeadlineQueue.force_run_overdue() (a job forced
    through past its deadline); this is deliberately generic so a future
    publisher on the scheduler's own successful-placement path could reuse
    the same topic and subscriber without new wiring.
    """

    def __init__(self, *, bus: EventBus = event_bus) -> None:
        self.bus = bus
        self.executions: list[dict] = []

    def register(self) -> None:
        self.bus.subscribe("carbonclock.job.scheduled", self._on_job_scheduled)

    def _on_job_scheduled(self, payload: dict) -> None:
        self.executions.append(payload)

    def has_run(self, job_id: str) -> bool:
        return any(execution.get("jobId") == job_id for execution in self.executions)
