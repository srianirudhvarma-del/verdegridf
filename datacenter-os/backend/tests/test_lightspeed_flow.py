from lightspeed.flow import classify_flow


def make_flow(bytes_last_interval, duration_seconds, **overrides):
    first_seen = "2026-08-25T00:00:00+00:00"
    last_seen_offset = duration_seconds
    from datetime import datetime, timedelta

    last_seen = (datetime.fromisoformat(first_seen) + timedelta(seconds=last_seen_offset)).isoformat()
    kwargs = dict(
        src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=5000, dst_port=443, proto="tcp",
        bytes_last_interval=bytes_last_interval, first_seen=first_seen, last_seen=last_seen,
    )
    kwargs.update(overrides)
    return classify_flow(**kwargs)


def test_large_sustained_flow_is_an_elephant():
    flow = make_flow(bytes_last_interval=20 * 1024 * 1024, duration_seconds=30)
    assert flow.isElephant is True


def test_large_but_brand_new_flow_is_not_yet_an_elephant():
    """Below min_duration_seconds, even a huge flow doesn't count yet."""
    flow = make_flow(bytes_last_interval=20 * 1024 * 1024, duration_seconds=2)
    assert flow.isElephant is False


def test_small_sustained_flow_is_not_an_elephant():
    flow = make_flow(bytes_last_interval=1024, duration_seconds=60)
    assert flow.isElephant is False


def test_elephant_threshold_is_configurable():
    flow = make_flow(
        bytes_last_interval=500_000, duration_seconds=30,
        elephant_threshold_bytes=100_000, min_duration_seconds=5,
    )
    assert flow.isElephant is True


def test_new_flow_has_no_latency_sensitivity_classification_yet():
    flow = make_flow(bytes_last_interval=20 * 1024 * 1024, duration_seconds=30)
    assert flow.latencySensitive is None
