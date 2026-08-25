from datetime import datetime, timedelta, timezone

from lightspeed.congestion import CongestionTracker
from lightspeed.flow import classify_flow
from lightspeed.routing import (
    OptimizerWatchdog,
    PathPreferenceOverride,
    auto_reroute_allowed,
    resolve_latency_sensitivity,
    tag_latency_sensitivity,
)
from shared.classification import WorkloadClassificationStore
from shared.contracts import WorkloadTag

NOW = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


def make_elephant_flow():
    return classify_flow(
        src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=5000, dst_port=443, proto="tcp",
        bytes_last_interval=20 * 1024 * 1024, first_seen=NOW.isoformat(),
        last_seen=(NOW + timedelta(seconds=30)).isoformat(),
    )


def make_confirmed_congestion_tracker(link="link-1"):
    tracker = CongestionTracker(dwell_time_seconds=45.0)
    tracker.observe_utilization(link, 95.0, NOW)
    return tracker


# ---------------------------------------------------------------------------
# MUST HAVE #16 -- fail-safe-open watchdog
# ---------------------------------------------------------------------------


def test_healthy_optimizer_keeps_its_overrides_active():
    watchdog = OptimizerWatchdog(health_check_timeout_seconds=30.0)
    watchdog.heartbeat(NOW)
    watchdog.apply_override(PathPreferenceOverride(link="link-1", flowKey=("a",), altPath="path-2"))

    overrides = watchdog.active_overrides(NOW + timedelta(seconds=10))

    assert len(overrides) == 1


def test_traffic_still_flows_via_default_ecmp_when_optimizer_is_down():
    """Acceptance test: if the optimizer service is down, active overrides
    revert to nothing -- i.e. default ECMP/BGP, not a frozen stale override."""
    watchdog = OptimizerWatchdog(health_check_timeout_seconds=30.0)
    watchdog.heartbeat(NOW)
    watchdog.apply_override(PathPreferenceOverride(link="link-1", flowKey=("a",), altPath="path-2"))

    overrides = watchdog.active_overrides(NOW + timedelta(seconds=60))  # past the health-check timeout

    assert overrides == []


def test_optimizer_with_no_heartbeat_yet_is_unhealthy():
    watchdog = OptimizerWatchdog()
    assert watchdog.is_optimizer_healthy(NOW) is False
    assert watchdog.active_overrides(NOW) == []


def test_revert_all_clears_active_overrides():
    watchdog = OptimizerWatchdog()
    watchdog.heartbeat(NOW)
    watchdog.apply_override(PathPreferenceOverride(link="link-1", flowKey=("a",), altPath="path-2"))
    watchdog.revert_all()

    assert watchdog.active_overrides(NOW) == []


# ---------------------------------------------------------------------------
# MUST HAVE #17 -- scope auto-reroute to the narrow, pre-validated case
# ---------------------------------------------------------------------------


def test_latency_sensitive_flow_is_never_auto_rerouted():
    store = WorkloadClassificationStore()
    store.set_tag(
        WorkloadTag(workloadId="vm-db", classification="protected", source="operator", updatedAt=NOW.isoformat())
    )
    flow = tag_latency_sensitivity(make_elephant_flow(), "vm-db", store=store)
    tracker = make_confirmed_congestion_tracker()

    allowed = auto_reroute_allowed(
        flow, "link-1", tracker, alt_path_utilization_pct=10.0, at=NOW + timedelta(seconds=50)
    )

    assert flow.latencySensitive is True
    assert allowed is False


def test_untagged_flow_owner_is_never_auto_rerouted_fail_safe_open():
    store = WorkloadClassificationStore()  # vm-unknown has no tag at all
    flow = tag_latency_sensitivity(make_elephant_flow(), "vm-unknown", store=store)
    tracker = make_confirmed_congestion_tracker()

    allowed = auto_reroute_allowed(
        flow, "link-1", tracker, alt_path_utilization_pct=10.0, at=NOW + timedelta(seconds=50)
    )

    assert flow.latencySensitive is True  # untagged defaults to protected -> latency-sensitive
    assert allowed is False


def test_confirmed_elephant_flow_on_non_latency_sensitive_traffic_can_auto_reroute():
    store = WorkloadClassificationStore()
    store.set_tag(
        WorkloadTag(
            workloadId="vm-batch", classification="deferrable", maxDelayMinutes=60,
            source="operator", updatedAt=NOW.isoformat(),
        )
    )
    flow = tag_latency_sensitivity(make_elephant_flow(), "vm-batch", store=store)
    tracker = make_confirmed_congestion_tracker()

    allowed = auto_reroute_allowed(
        flow, "link-1", tracker, alt_path_utilization_pct=10.0, at=NOW + timedelta(seconds=50)
    )

    assert flow.latencySensitive is False
    assert allowed is True


def test_single_congested_sample_does_not_permit_auto_reroute():
    store = WorkloadClassificationStore()
    store.set_tag(
        WorkloadTag(
            workloadId="vm-batch", classification="deferrable", maxDelayMinutes=60,
            source="operator", updatedAt=NOW.isoformat(),
        )
    )
    flow = tag_latency_sensitivity(make_elephant_flow(), "vm-batch", store=store)
    tracker = CongestionTracker(dwell_time_seconds=45.0)
    tracker.observe_utilization("link-1", 95.0, NOW)  # only one sample, no dwell yet

    allowed = auto_reroute_allowed(
        flow, "link-1", tracker, alt_path_utilization_pct=10.0, at=NOW + timedelta(seconds=5)
    )

    assert allowed is False


def test_no_viable_alt_path_blocks_auto_reroute():
    store = WorkloadClassificationStore()
    store.set_tag(
        WorkloadTag(
            workloadId="vm-batch", classification="deferrable", maxDelayMinutes=60,
            source="operator", updatedAt=NOW.isoformat(),
        )
    )
    flow = tag_latency_sensitivity(make_elephant_flow(), "vm-batch", store=store)
    tracker = make_confirmed_congestion_tracker()

    allowed = auto_reroute_allowed(
        flow, "link-1", tracker, alt_path_utilization_pct=75.0, at=NOW + timedelta(seconds=50)
    )
    assert allowed is False

    allowed_no_alt = auto_reroute_allowed(
        flow, "link-1", tracker, alt_path_utilization_pct=None, at=NOW + timedelta(seconds=50)
    )
    assert allowed_no_alt is False


def test_non_elephant_flow_never_auto_reroutes_even_if_everything_else_is_ready():
    store = WorkloadClassificationStore()
    store.set_tag(
        WorkloadTag(
            workloadId="vm-batch", classification="deferrable", maxDelayMinutes=60,
            source="operator", updatedAt=NOW.isoformat(),
        )
    )
    small_flow = classify_flow(
        src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=5000, dst_port=443, proto="tcp",
        bytes_last_interval=1024, first_seen=NOW.isoformat(),
        last_seen=(NOW + timedelta(seconds=30)).isoformat(),
    )
    flow = tag_latency_sensitivity(small_flow, "vm-batch", store=store)
    tracker = make_confirmed_congestion_tracker()

    allowed = auto_reroute_allowed(
        flow, "link-1", tracker, alt_path_utilization_pct=10.0, at=NOW + timedelta(seconds=50)
    )
    assert allowed is False


def test_resolve_latency_sensitivity_matches_the_deferrable_negation():
    store = WorkloadClassificationStore()
    store.set_tag(
        WorkloadTag(
            workloadId="vm-batch", classification="deferrable", maxDelayMinutes=60,
            source="operator", updatedAt=NOW.isoformat(),
        )
    )
    assert resolve_latency_sensitivity("vm-batch", store=store) is False
    assert resolve_latency_sensitivity("vm-unknown", store=store) is True
