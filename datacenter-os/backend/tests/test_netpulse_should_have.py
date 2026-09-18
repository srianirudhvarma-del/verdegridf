from datetime import datetime, timedelta, timezone

from netpulse.congestion import CongestionTracker
from netpulse.flow import classify_flow
from netpulse.routing import IpToVmLookup, auto_tag_latency_sensitivity
from netpulse.telemetry import UnsupportedStreamingTelemetryError, connect_telemetry
from netpulse.topology import LldpNeighbor, LldpTopologyDiscovery, TopologyGraph
from shared.classification import WorkloadClassificationStore
from shared.contracts import WorkloadTag

NOW = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# SHOULD HAVE #18 -- packet-loss / queue-depth as OR conditions
# ---------------------------------------------------------------------------


def test_high_queue_depth_alone_confirms_congestion_even_with_low_utilization():
    tracker = CongestionTracker(dwell_time_seconds=30.0)
    tracker.observe_utilization("link-1", 20.0, NOW, queue_depth=500.0)
    assert tracker.congestion_confirmed("link-1", NOW + timedelta(seconds=40)) is True


def test_high_packet_loss_alone_confirms_congestion():
    tracker = CongestionTracker(dwell_time_seconds=30.0)
    tracker.observe_utilization("link-1", 20.0, NOW, packet_loss_pct=5.0)
    assert tracker.congestion_confirmed("link-1", NOW + timedelta(seconds=40)) is True


def test_low_everything_does_not_confirm_congestion():
    tracker = CongestionTracker(dwell_time_seconds=30.0)
    tracker.observe_utilization("link-1", 20.0, NOW, queue_depth=5.0, packet_loss_pct=0.01)
    assert tracker.congestion_confirmed("link-1", NOW + timedelta(seconds=40)) is False


def test_existing_utilization_only_signature_still_works():
    """Backward compatibility with Phase 5 callers."""
    tracker = CongestionTracker(dwell_time_seconds=30.0)
    tracker.observe_utilization("link-1", 95.0, NOW)
    assert tracker.congestion_confirmed("link-1", NOW + timedelta(seconds=40)) is True


# ---------------------------------------------------------------------------
# SHOULD HAVE #19 -- automatic LLDP topology discovery
# ---------------------------------------------------------------------------


def test_topology_graph_builds_edges_from_neighbors():
    graph = TopologyGraph()
    graph.ingest_neighbors([LldpNeighbor(localSwitch="sw-1", localPort="p1", remoteSwitch="sw-2", remotePort="p2")])

    assert graph.neighbors_of("sw-1") == {"sw-2"}
    assert graph.neighbors_of("sw-2") == {"sw-1"}


def test_discovery_respects_the_slow_poll_interval():
    calls = []

    def get_neighbors():
        calls.append(1)
        return [LldpNeighbor(localSwitch="sw-1", localPort="p1", remoteSwitch="sw-2", remotePort="p2")]

    discovery = LldpTopologyDiscovery(get_neighbors, poll_interval_seconds=300.0)

    assert discovery.poll(NOW) is True
    assert discovery.poll(NOW + timedelta(seconds=60)) is False  # too soon
    assert discovery.poll(NOW + timedelta(seconds=301)) is True
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# SHOULD HAVE #20 -- SNMP fallback telemetry path
# ---------------------------------------------------------------------------


def test_connect_uses_streaming_when_supported():
    connection = connect_telemetry("switch-1", streaming_subscribe=lambda switch: None)
    assert connection.mode == "streaming"
    assert connection.pollIntervalSeconds is None


def test_connect_falls_back_to_snmp_when_streaming_unsupported():
    def unsupported(switch):
        raise UnsupportedStreamingTelemetryError()

    connection = connect_telemetry("switch-2", streaming_subscribe=unsupported)
    assert connection.mode == "snmp_fallback"
    assert connection.pollIntervalSeconds == 15.0


# ---------------------------------------------------------------------------
# SHOULD HAVE #21 -- IP->VM auto-lookup cross-wire
# ---------------------------------------------------------------------------


def make_elephant_flow(src_ip="10.0.0.5"):
    return classify_flow(
        src_ip=src_ip, dst_ip="10.0.0.9", src_port=5000, dst_port=443, proto="tcp",
        bytes_last_interval=20 * 1024 * 1024, first_seen=NOW.isoformat(),
        last_seen=(NOW + timedelta(seconds=30)).isoformat(),
    )


def test_auto_tag_resolves_via_synced_ip_to_vm_mapping():
    store = WorkloadClassificationStore()
    store.set_tag(
        WorkloadTag(
            workloadId="vm-batch", classification="deferrable", maxDelayMinutes=60,
            source="operator", updatedAt=NOW.isoformat(),
        )
    )
    lookup = IpToVmLookup()
    lookup.sync({"10.0.0.5": "vm-batch"})

    flow = auto_tag_latency_sensitivity(make_elephant_flow(), lookup, store=store)

    assert flow.latencySensitive is False


def test_auto_tag_leaves_flow_unresolved_when_ip_not_synced():
    store = WorkloadClassificationStore()
    lookup = IpToVmLookup()  # no mapping synced

    flow = auto_tag_latency_sensitivity(make_elephant_flow(), lookup, store=store)

    assert flow.latencySensitive is None  # fail-safe: never assumed safe
