"""
api/state.py -- Phase 9: process-wide simulated datacenter state.

api/routes.py's endpoints (Phases 0-8c never touched this file -- it still
served canned/random mock data) now poll this module's singleton telemetry
adapters and run the real module algorithms against them, instead of
generating fresh random numbers on every request.

This is also where the Phase 8c scheduler driver actually gets something
real to tick: every DwellStateMachine and the CarbonClock DeadlineQueue
created here are registered into shared.scheduler_driver.scheduler_registry,
closing the gap confirmed at the end of Phase 8c ("the tick logic is real
and tested, but has nothing real to tick over until routes.py/main.py
actually create jobs and hosts").

A small, fixed topology -- 5 racks x 4 hosts, one WaterWatch loop and one
ThermalTrace sensor per rack, an 8-link LightSpeed fabric -- is registered
once at import time (module-level singletons, same pattern as
shared.eventbus.event_bus / shared.classification.classification_store).
"""

from datetime import datetime, timezone

from carbonclock.grid import CarbonForecastSimulator, DEFAULT_SIGNAL_INFO, HysteresisState
from carbonclock.jobs import DeadlineQueue, submit_job
from idlehunter.power import DwellStateMachine
from idlehunter.telemetry import IdleHunterTelemetry
from lightspeed.congestion import CongestionTracker
from lightspeed.telemetry import LightSpeedTelemetry
from shared.classification import classification_store
from shared.contracts import WorkloadTag
from shared.scheduler_driver import scheduler_registry
from thermaltrace.control import ActionRecommendationQueue
from thermaltrace.sensors import ThermalTelemetry
from waterwatch.anomaly import MaintenanceModeRegistry
from waterwatch.sensors import WaterWatchTelemetry

RACKS = [f"rack{i}" for i in range(1, 6)]
HOSTS_PER_RACK = 4
HOST_IDS_BY_RACK: dict[str, list[str]] = {
    rack: [f"{rack}-srv{n}" for n in range(1, HOSTS_PER_RACK + 1)] for rack in RACKS
}
ALL_HOST_IDS = [host_id for hosts in HOST_IDS_BY_RACK.values() for host_id in hosts]

LINKS: list[tuple[str, str]] = [
    ("A1", "A2"), ("A1", "B1"), ("A2", "B2"), ("B1", "B2"),
    ("C1", "A1"), ("C1", "A2"), ("C1", "B1"), ("C1", "B2"),
]
LINK_IDS = [f"{a}-{b}" for a, b in LINKS]

CARBON_ZONE = "IN-SO"
FACILITY_ZONE = "facility"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_for(name: str) -> int:
    return abs(hash(name)) % (2**31 - 1)


# ---------------------------------------------------------------------------
# IdleHunter
# ---------------------------------------------------------------------------

idlehunter_telemetry = IdleHunterTelemetry()
dwell_machines: dict[str, DwellStateMachine] = {}
host_to_rack: dict[str, str] = {}

for _rack, _hosts in HOST_IDS_BY_RACK.items():
    for _host_id in _hosts:
        idlehunter_telemetry.register_host(_host_id, seed=_seed_for(_host_id))
        host_to_rack[_host_id] = _rack
        machine = DwellStateMachine(_host_id)
        dwell_machines[_host_id] = machine
        scheduler_registry.register_dwell_state_machine(machine)

# ---------------------------------------------------------------------------
# ThermalTrace -- one real sensor per rack, spread across the 8x8 grid;
# thermaltrace/spatial.py's interpolate_grid() fills the rest.
# ---------------------------------------------------------------------------

thermal_telemetry = ThermalTelemetry()
RACK_GRID_POSITIONS: dict[str, tuple[int, int]] = {
    "rack1": (0, 0), "rack2": (2, 7), "rack3": (4, 3), "rack4": (6, 0), "rack5": (7, 7),
}
for _rack in RACKS:
    thermal_telemetry.register_rack(_rack, seed=_seed_for(_rack))

action_recommendation_queue = ActionRecommendationQueue()

# Two demo recommendations so the approval queue (MUST HAVE #22) isn't
# empty on first load. In a full system these would come from
# thermaltrace/zoning.py's build_setpoint_recommendation() reacting to a
# real zoning/cooling-performance signal; seeded directly here since that
# full zoning pipeline isn't wired into a live trigger yet.
from thermaltrace.control import ActionRecommendation as _ActionRecommendation

action_recommendation_queue.submit(
    _ActionRecommendation(
        id="rec-1", type="adjust_setpoint", rackId="rack2", magnitude=-1.5,
        predictedBenefit="rack2 setpoint 22C -> 20.5C, ~40W cooling reduction",
    )
)
action_recommendation_queue.submit(
    _ActionRecommendation(
        id="rec-2", type="adjust_fan_speed", rackId="rack4", magnitude=10.0,
        predictedBenefit="rack4 fan speed +10%, headroom improves ~0.8C",
    )
)

# ---------------------------------------------------------------------------
# WaterWatch -- one loop per rack (same id, so the ThermalTrace
# cooling-performance cross-wire can key off it directly), plus one
# facility-level humidity zone.
# ---------------------------------------------------------------------------

waterwatch_telemetry = WaterWatchTelemetry()
for _rack in RACKS:
    waterwatch_telemetry.register_loop(_rack, seed=_seed_for(f"water-{_rack}"))
waterwatch_telemetry.register_zone(FACILITY_ZONE, seed=_seed_for(FACILITY_ZONE))

maintenance_registry = MaintenanceModeRegistry()

# ---------------------------------------------------------------------------
# LightSpeed
# ---------------------------------------------------------------------------

lightspeed_telemetry = LightSpeedTelemetry()
for _link_id in LINK_IDS:
    lightspeed_telemetry.register_link(_link_id, seed=_seed_for(_link_id))
congestion_tracker = CongestionTracker()

# ---------------------------------------------------------------------------
# CarbonClock
# ---------------------------------------------------------------------------

carbon_forecast_sim = CarbonForecastSimulator()
carbon_forecast_sim.register_zone(CARBON_ZONE, seed=_seed_for(CARBON_ZONE))
carbon_hysteresis = HysteresisState()

carbon_job_queue = DeadlineQueue()
scheduler_registry.register_deadline_queue("carbonclock", carbon_job_queue)

signal_info = DEFAULT_SIGNAL_INFO

# carbon_job_records is the API layer's display state (id, name, type,
# duration_mins, est_kwh, deferrable, status) -- carbon_job_queue remains
# the sole source of truth for deadline tracking (MUST HAVE #7); this dict
# is kept in sync with it by the /carbonclock/* route handlers, not an
# independent copy of the scheduling logic.
INITIAL_JOBS = [
    {"id": "job-402", "name": "AI Training Job #402", "type": "training", "duration_mins": 240, "est_kwh": 40.0, "deferrable": True, "max_delay_minutes": 180},
    {"id": "job-156", "name": "Data Processing #156", "type": "batch", "duration_mins": 120, "est_kwh": 15.0, "deferrable": True, "max_delay_minutes": 120},
    {"id": "job-89", "name": "Backup Sync #89", "type": "backup", "duration_mins": 360, "est_kwh": 25.0, "deferrable": False, "max_delay_minutes": None},
]

carbon_job_records: dict[str, dict] = {}


def _seed_carbon_jobs() -> None:
    for job in INITIAL_JOBS:
        classification = "deferrable" if job["deferrable"] else "protected"
        classification_store.set_tag(
            WorkloadTag(
                workloadId=job["id"], classification=classification,
                maxDelayMinutes=job["max_delay_minutes"], source="operator", updatedAt=_now_iso(),
            )
        )
        deferrable_job = submit_job(job["id"], datetime.now(timezone.utc), store=classification_store)
        if deferrable_job is not None:
            carbon_job_queue.add(deferrable_job)
            status = "pending"
            deadline = deferrable_job.deadline
        else:
            status = "scheduled"
            deadline = None
        carbon_job_records[job["id"]] = {**job, "status": status, "deadline": deadline}


_seed_carbon_jobs()
