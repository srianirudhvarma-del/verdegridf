from idlehunter.consolidation import (
    HostPowerDownCandidate,
    enforce_min_redundancy,
    estimate_migration_decision,
    filter_consolidation_candidates,
    suggest_deferrable,
    violates_anti_affinity,
)
from shared.classification import WorkloadClassificationStore
from shared.contracts import WorkloadTag


COMMON_POWER = dict(
    p_source_elevated_watts=280.0,
    p_source_idle_watts=120.0,
    p_dest_elevated_watts=280.0,
    p_dest_idle_watts=120.0,
    p_host_baseline_draw_watts=150.0,
)


# ---------------------------------------------------------------------------
# MUST HAVE #2 -- migration-cost check
# ---------------------------------------------------------------------------


def test_large_memory_low_dwell_vm_is_blocked():
    decision = estimate_migration_decision(
        "vm-large",
        "host-a",
        "host-b",
        vm_mem_mb=64000.0,
        bandwidth_mbps=100.0,
        expected_dwell_hours=0.25,  # 15 minutes
        **COMMON_POWER,
    )
    assert decision.proceed is False


def test_small_memory_overnight_dwell_vm_is_allowed():
    decision = estimate_migration_decision(
        "vm-small",
        "host-a",
        "host-b",
        vm_mem_mb=512.0,
        bandwidth_mbps=1000.0,
        expected_dwell_hours=10.0,  # overnight
        **COMMON_POWER,
    )
    assert decision.proceed is True


def test_migration_decision_reports_costs_and_savings():
    decision = estimate_migration_decision(
        "vm-1",
        "host-a",
        "host-b",
        vm_mem_mb=1000.0,
        bandwidth_mbps=1000.0,
        expected_dwell_hours=5.0,
        **COMMON_POWER,
    )
    assert decision.estimatedCostJoules > 0
    assert decision.estimatedSavingsJoules > 0
    assert decision.reason  # non-empty explanation


# ---------------------------------------------------------------------------
# MUST HAVE #3 -- workload classification hard filter
# ---------------------------------------------------------------------------


def test_untagged_vm_never_in_candidate_list_even_if_idle():
    store = WorkloadClassificationStore()
    # vm-cpu-idle is never tagged at all -- defaults to protected.
    store.set_tag(
        WorkloadTag(
            workloadId="vm-tagged-deferrable",
            classification="deferrable",
            maxDelayMinutes=60,
            source="operator",
            updatedAt="2026-08-25T00:00:00Z",
        )
    )
    candidates = filter_consolidation_candidates(["vm-cpu-idle", "vm-tagged-deferrable"], store)

    assert "vm-cpu-idle" not in candidates
    assert "vm-tagged-deferrable" in candidates


def test_explicitly_protected_vm_never_in_candidate_list():
    store = WorkloadClassificationStore()
    store.set_tag(
        WorkloadTag(
            workloadId="vm-protected",
            classification="protected",
            source="operator",
            updatedAt="2026-08-25T00:00:00Z",
        )
    )
    candidates = filter_consolidation_candidates(["vm-protected"], store)
    assert candidates == []


def test_suggest_deferrable_matches_common_batch_workload_names_but_does_not_apply_it():
    store = WorkloadClassificationStore()

    assert suggest_deferrable("nightly-backup-job") is True
    assert suggest_deferrable("prod-webserver-01") is False

    # Suggesting must never itself write to the store.
    assert store.classification_for("nightly-backup-job") == "protected"


# ---------------------------------------------------------------------------
# MUST HAVE #4 -- redundancy-aware placement
# ---------------------------------------------------------------------------


def test_refuses_to_power_down_hosts_that_would_breach_min_redundancy():
    """With minRedundancy=1 and only exactly N+1 hosts running, powering
    down any host must be refused."""
    # N=1 host needed for running workload; +1 redundancy => need 2 hosts'
    # worth of capacity powered on. Exactly 2 hosts (N+1) are running.
    candidates = [
        HostPowerDownCandidate(host_id="host-2", capacity=100.0, savings=50.0),
    ]

    remaining = enforce_min_redundancy(
        candidates,
        total_capacity=200.0,  # 2 hosts x 100 capacity
        running_vm_requirement=100.0,  # N=1 host's worth of running workload
        min_redundancy=1,
        avg_host_capacity=100.0,
    )

    assert remaining == []


def test_trims_lowest_savings_hosts_first_to_satisfy_redundancy():
    candidates = [
        HostPowerDownCandidate(host_id="host-low-savings", capacity=100.0, savings=10.0),
        HostPowerDownCandidate(host_id="host-high-savings", capacity=100.0, savings=90.0),
    ]

    # total=400 (4 hosts), required = 100 (running) + 1*100 (redundancy) = 200
    # powering down both leaves 200 (OK) so both should stay -- tighten it:
    remaining = enforce_min_redundancy(
        candidates,
        total_capacity=300.0,  # 3 hosts of 100
        running_vm_requirement=100.0,
        min_redundancy=1,
        avg_host_capacity=100.0,
    )

    # Powering down both would leave 100 < required 200 -> must trim.
    # Powering down only the high-savings one leaves 200 == required -> OK.
    assert [c.host_id for c in remaining] == ["host-high-savings"]


def test_plan_within_redundancy_budget_is_left_untouched():
    candidates = [
        HostPowerDownCandidate(host_id="host-1", capacity=50.0, savings=20.0),
    ]
    remaining = enforce_min_redundancy(
        candidates,
        total_capacity=1000.0,
        running_vm_requirement=100.0,
        min_redundancy=1,
        avg_host_capacity=100.0,
    )
    assert [c.host_id for c in remaining] == ["host-1"]


def test_anti_affinity_rejects_colocating_replica_group_members():
    groups = {"web-replicas": {"vm-web-1", "vm-web-2"}}
    current_placements = {"vm-web-1": "host-a"}

    assert violates_anti_affinity("host-a", "vm-web-2", groups, current_placements) is True
    assert violates_anti_affinity("host-b", "vm-web-2", groups, current_placements) is False


def test_anti_affinity_ignores_vms_outside_any_group():
    groups = {"web-replicas": {"vm-web-1", "vm-web-2"}}
    current_placements = {"vm-web-1": "host-a"}

    assert violates_anti_affinity("host-a", "vm-standalone", groups, current_placements) is False
