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

from idlehunter.consolidation import filter_targets_by_thermal_headroom
from idlehunter.telemetry import IdleHunterTelemetry
from shared.contracts import ThermalHeadroom
from thermaltrace.model import IdleHunterRackReading, ThermalFeatureVector, build_feature_vector
from thermaltrace.sensors import ThermalTelemetry

# Same idle/active watt figures api/routes.py's mock ServerData already uses,
# reused here to derive a power estimate from a host's real cpu utilization.
HOST_IDLE_WATTS = 120.0
HOST_ACTIVE_WATTS = 280.0

# ThermalTrace doesn't (yet) expose a documented ASHRAE-envelope ceiling
# per rack; this is a facility-wide placeholder default, tunable per site.
DEFAULT_THERMAL_CEILING_CELSIUS = 35.0
DEFAULT_CONSTRAINED_HEADROOM_CELSIUS = 5.0


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
