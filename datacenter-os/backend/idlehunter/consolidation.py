"""
idlehunter/consolidation.py

MUST HAVE #2 -- migration-cost check before triggering a move.
MUST HAVE #3 -- workload classification hard filter on the candidate list.
MUST HAVE #4 -- redundancy-aware placement (minRedundancy + anti-affinity).
"""

import re
from dataclasses import dataclass

from pydantic import BaseModel

from shared.classification import WorkloadClassificationStore

# ---------------------------------------------------------------------------
# MUST HAVE #2 -- migration-cost check
# ---------------------------------------------------------------------------

# Methodology default: if a real cost/benefit is uncertain, require savings
# to exceed cost by this multiple before proceeding.
DEFAULT_SAFETY_MARGIN = 3.0

# Simplification (flagged per methodology MUST HAVE #2): rather than the
# closed-form iterative-precopy downtime formula, use the simpler bound
# migrationDurationSeconds ~= vmMemMB / effectiveBandwidthMBps, and treat
# downtime as a fixed conservative fraction of that duration.
DOWNTIME_FRACTION_OF_DURATION = 0.05


class MigrationDecision(BaseModel):
    vmId: str
    sourceHost: str
    targetHost: str
    estimatedCostJoules: float
    estimatedSavingsJoules: float
    proceed: bool
    reason: str


def estimate_migration_decision(
    vm_id: str,
    source_host: str,
    target_host: str,
    *,
    vm_mem_mb: float,
    bandwidth_mbps: float,
    expected_dwell_hours: float,
    p_source_elevated_watts: float,
    p_source_idle_watts: float,
    p_dest_elevated_watts: float,
    p_dest_idle_watts: float,
    p_host_baseline_draw_watts: float,
    safety_margin: float = DEFAULT_SAFETY_MARGIN,
) -> MigrationDecision:
    """
    migrationEnergyCost = (P_source_elevated - P_source_idle) * durationSeconds
                         + (P_dest_elevated  - P_dest_idle)   * durationSeconds
    projectedSavings    = P_host_baseline_draw * expectedDwellHours * 3600
    proceed = projectedSavings > migrationEnergyCost * SAFETY_MARGIN
    """
    effective_bandwidth_mbps = bandwidth_mbps / 8.0  # Mbps -> MBps
    migration_duration_seconds = vm_mem_mb / effective_bandwidth_mbps

    migration_energy_cost_joules = (
        (p_source_elevated_watts - p_source_idle_watts) * migration_duration_seconds
        + (p_dest_elevated_watts - p_dest_idle_watts) * migration_duration_seconds
    )
    projected_savings_joules = p_host_baseline_draw_watts * expected_dwell_hours * 3600.0

    proceed = projected_savings_joules > migration_energy_cost_joules * safety_margin

    if proceed:
        reason = (
            f"projected savings {projected_savings_joules:.0f}J exceed "
            f"{safety_margin}x migration cost {migration_energy_cost_joules:.0f}J"
        )
    else:
        reason = (
            f"projected savings {projected_savings_joules:.0f}J do not exceed "
            f"{safety_margin}x migration cost {migration_energy_cost_joules:.0f}J"
        )

    return MigrationDecision(
        vmId=vm_id,
        sourceHost=source_host,
        targetHost=target_host,
        estimatedCostJoules=migration_energy_cost_joules,
        estimatedSavingsJoules=projected_savings_joules,
        proceed=proceed,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# MUST HAVE #3 -- workload classification hard filter
# ---------------------------------------------------------------------------

# Optional inference helper (methodology step 3): suggest deferrable for VM
# names matching this pattern. Never auto-applied -- callers must surface
# this as a one-click operator confirmation, not set the tag themselves.
DEFERRABLE_NAME_PATTERN = re.compile(r"batch|backup|etl|report|training", re.IGNORECASE)


def suggest_deferrable(vm_name: str) -> bool:
    """Suggestion only. Never write this straight into the classification store."""
    return bool(DEFERRABLE_NAME_PATTERN.search(vm_name))


def filter_consolidation_candidates(
    vm_ids: list[str],
    store: WorkloadClassificationStore,
) -> list[str]:
    """
    Hard filter: any VM without classification == "deferrable" (including
    untagged/unclassified VMs, which default to "protected") is excluded
    from the migration candidate list entirely -- regardless of how idle
    it looks.
    """
    return [vm_id for vm_id in vm_ids if store.is_deferrable(vm_id)]


# ---------------------------------------------------------------------------
# MUST HAVE #4 -- redundancy-aware placement
# ---------------------------------------------------------------------------


@dataclass
class HostPowerDownCandidate:
    host_id: str
    capacity: float
    savings: float


def enforce_min_redundancy(
    hosts_to_power_down: list[HostPowerDownCandidate],
    *,
    total_capacity: float,
    running_vm_requirement: float,
    min_redundancy: int,
    avg_host_capacity: float,
) -> list[HostPowerDownCandidate]:
    """
    requiredCapacity = runningVmResourceRequirements + minRedundancy * avgHostCapacity
    Trim the power-down plan (removing lowest-savings hosts first) until
    poweredOnCapacityAfterPlan >= requiredCapacity.
    """
    required_capacity = running_vm_requirement + min_redundancy * avg_host_capacity

    # Keep highest-savings hosts preferentially; the last element is always
    # the next one to trim when the constraint isn't met.
    remaining = sorted(hosts_to_power_down, key=lambda h: h.savings, reverse=True)

    while remaining:
        powered_down_capacity = sum(h.capacity for h in remaining)
        powered_on_capacity_after_plan = total_capacity - powered_down_capacity
        if powered_on_capacity_after_plan >= required_capacity:
            break
        remaining.pop()

    return remaining


def violates_anti_affinity(
    target_host: str,
    vm_id: str,
    anti_affinity_groups: dict[str, set[str]],
    current_placements: dict[str, str],
) -> bool:
    """
    True if placing vm_id on target_host would co-locate it with another
    member of one of its anti-affinity (replica) groups.
    """
    for group in anti_affinity_groups.values():
        if vm_id not in group:
            continue
        for other_vm_id in group:
            if other_vm_id == vm_id:
                continue
            if current_placements.get(other_vm_id) == target_host:
                return True
    return False
