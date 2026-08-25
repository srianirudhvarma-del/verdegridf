from datetime import datetime, timedelta, timezone

from lightspeed.congestion import CongestionTracker
from lightspeed.flow import classify_flow

NOW = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


def make_flow():
    return classify_flow(
        src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=5000, dst_port=443, proto="tcp",
        bytes_last_interval=20 * 1024 * 1024, first_seen=NOW.isoformat(),
        last_seen=(NOW + timedelta(seconds=30)).isoformat(),
    )


def test_single_congested_sample_does_not_confirm_congestion():
    tracker = CongestionTracker(dwell_time_seconds=45.0)
    tracker.observe_utilization("link-1", 95.0, NOW)

    assert tracker.congestion_confirmed("link-1", NOW) is False


def test_sustained_congestion_past_dwell_time_confirms():
    tracker = CongestionTracker(dwell_time_seconds=45.0)
    tracker.observe_utilization("link-1", 95.0, NOW)

    assert tracker.congestion_confirmed("link-1", NOW + timedelta(seconds=50)) is True


def test_congestion_below_dwell_time_is_not_yet_confirmed():
    tracker = CongestionTracker(dwell_time_seconds=45.0)
    tracker.observe_utilization("link-1", 95.0, NOW)

    assert tracker.congestion_confirmed("link-1", NOW + timedelta(seconds=20)) is False


def test_utilization_dropping_below_threshold_resets_the_dwell_timer():
    tracker = CongestionTracker(dwell_time_seconds=45.0, congestion_threshold_pct=80.0)
    tracker.observe_utilization("link-1", 95.0, NOW)
    tracker.observe_utilization("link-1", 50.0, NOW + timedelta(seconds=30))  # dips below threshold
    tracker.observe_utilization("link-1", 95.0, NOW + timedelta(seconds=40))  # congested again, timer restarts

    assert tracker.congestion_confirmed("link-1", NOW + timedelta(seconds=60)) is False  # only 20s since restart
    assert tracker.congestion_confirmed("link-1", NOW + timedelta(seconds=90)) is True  # 50s since restart


def test_links_track_congestion_independently():
    tracker = CongestionTracker(dwell_time_seconds=45.0)
    tracker.observe_utilization("link-1", 95.0, NOW)

    assert tracker.congestion_confirmed("link-1", NOW + timedelta(seconds=50)) is True
    assert tracker.congestion_confirmed("link-2", NOW + timedelta(seconds=50)) is False


def test_reroute_starts_a_cooldown_blocking_the_same_flow_link_pair():
    tracker = CongestionTracker(cooldown_seconds=300.0)
    flow = make_flow()

    assert tracker.is_in_cooldown("link-1", flow, NOW) is False

    tracker.on_reroute_executed("link-1", flow, NOW)

    assert tracker.is_in_cooldown("link-1", flow, NOW + timedelta(seconds=100)) is True
    assert tracker.is_in_cooldown("link-1", flow, NOW + timedelta(seconds=301)) is False


def test_cooldown_is_scoped_to_the_specific_link_and_flow():
    tracker = CongestionTracker(cooldown_seconds=300.0)
    flow = make_flow()
    tracker.on_reroute_executed("link-1", flow, NOW)

    assert tracker.is_in_cooldown("link-2", flow, NOW + timedelta(seconds=10)) is False
