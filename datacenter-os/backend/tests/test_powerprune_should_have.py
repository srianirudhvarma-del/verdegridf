from powerprune.consolidation import filter_targets_by_thermal_headroom
from powerprune.resilience import ConsolidationFailureHandler
from powerprune.telemetry import PowerPruneTelemetry, K8sTelemetryAdapter
from powerprune.threshold import RESOURCES, classify_host
from shared.contracts import ThermalHeadroom


# ---------------------------------------------------------------------------
# SHOULD HAVE #6 -- failure-during-consolidation handling
# ---------------------------------------------------------------------------


def test_host_failure_excludes_it_from_future_candidate_lists():
    handler = ConsolidationFailureHandler()
    handler.on_host_failure("host-1", ["vm-a", "vm-b"], timestamp="2026-08-25T00:00:00Z")

    remaining = handler.filter_candidate_hosts(["host-1", "host-2", "host-3"])

    assert remaining == ["host-2", "host-3"]


def test_vms_from_failed_host_become_top_priority():
    handler = ConsolidationFailureHandler()
    handler.on_host_failure("host-1", ["vm-a", "vm-b"], timestamp="2026-08-25T00:00:00Z")

    assert handler.is_top_priority("vm-a") is True
    assert handler.is_top_priority("vm-c") is False


def test_failure_is_logged_as_an_incident():
    handler = ConsolidationFailureHandler()
    handler.on_host_failure("host-1", ["vm-a"], timestamp="2026-08-25T00:00:00Z", reason="BMC unreachable")

    incidents = handler.incidents()
    assert len(incidents) == 1
    assert incidents[0].hostId == "host-1"
    assert incidents[0].reason == "BMC unreachable"


def test_clear_priority_removes_top_priority_status_after_replacement():
    handler = ConsolidationFailureHandler()
    handler.on_host_failure("host-1", ["vm-a"], timestamp="2026-08-25T00:00:00Z")
    handler.clear_priority("vm-a")

    assert handler.is_top_priority("vm-a") is False


# ---------------------------------------------------------------------------
# SHOULD HAVE #7 -- thermal-headroom cross-wiring
# ---------------------------------------------------------------------------


def test_constrained_rack_hosts_are_excluded_from_targets():
    host_to_rack = {"host-1": "rack-a", "host-2": "rack-b"}

    def get_headroom(rack_id):
        if rack_id == "rack-a":
            return ThermalHeadroom(rackId="rack-a", timestamp="2026-08-25T00:00:00Z", headroomCelsius=0.5, status="constrained")
        return ThermalHeadroom(rackId="rack-b", timestamp="2026-08-25T00:00:00Z", headroomCelsius=5.0, status="ok")

    allowed = filter_targets_by_thermal_headroom(host_to_rack, ["host-1", "host-2"], get_headroom)

    assert allowed == ["host-2"]


def test_hosts_with_no_known_rack_mapping_are_not_excluded():
    allowed = filter_targets_by_thermal_headroom({}, ["host-1"], lambda rack_id: None)
    assert allowed == ["host-1"]


# ---------------------------------------------------------------------------
# SHOULD HAVE #8 -- Kubernetes telemetry adapter, adapter-agnostic
# ---------------------------------------------------------------------------


def test_k8s_adapter_produces_the_same_resource_keys_as_the_hypervisor_adapter():
    hypervisor = PowerPruneTelemetry()
    hypervisor.register_host("host-1", seed=1)
    k8s = K8sTelemetryAdapter()
    k8s.register_node("node-1", seed=1)

    assert set(hypervisor.poll("host-1").keys()) == set(k8s.poll("node-1").keys()) == set(RESOURCES)


def test_threshold_engine_works_unchanged_against_the_k8s_adapter():
    """Adapter-agnostic: the same classify_host() call works whether the
    telemetry came from the hypervisor adapter or the k8s adapter."""
    k8s = K8sTelemetryAdapter()
    k8s.register_node("node-1", seed=42)
    for _ in range(65):
        k8s.poll("node-1")

    history = {r: k8s.history("node-1", r, 60) for r in RESOURCES}
    current = k8s.current("node-1")

    state = classify_host("node-1", current, history)
    assert state.status in {"normal", "idle-candidate", "overloaded"}
