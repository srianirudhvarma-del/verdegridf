from coolsense.anomaly import (
    MaintenanceModeRegistry,
    MaintenanceWindow,
    detect_flow_anomaly,
    evaluate_and_log,
    should_notify,
)

# ---------------------------------------------------------------------------
# MUST HAVE #12 -- anomaly decision
# ---------------------------------------------------------------------------


def test_unexplained_flow_drop_raises_an_anomaly():
    """A flow drop with no corresponding workload change DOES raise an anomaly."""
    is_anomaly = detect_flow_anomaly(flow_z=-3.0, flow_peer_z=2.5, utilization_delta_z=0.5)
    assert is_anomaly is True


def test_workload_explained_flow_drop_does_not_raise_an_anomaly():
    """A flow drop that coincides with a documented workload drop does NOT raise an anomaly."""
    is_anomaly = detect_flow_anomaly(flow_z=-3.0, flow_peer_z=2.5, utilization_delta_z=5.0)  # big util swing
    assert is_anomaly is False


def test_flow_drop_without_peer_divergence_does_not_raise():
    is_anomaly = detect_flow_anomaly(flow_z=-3.0, flow_peer_z=0.5, utilization_delta_z=0.1)
    assert is_anomaly is False


def test_peer_divergence_without_a_real_flow_drop_does_not_raise():
    is_anomaly = detect_flow_anomaly(flow_z=-1.0, flow_peer_z=3.0, utilization_delta_z=0.1)
    assert is_anomaly is False


# ---------------------------------------------------------------------------
# MUST HAVE #13 -- maintenance-mode suppression
# ---------------------------------------------------------------------------


def test_maintenance_window_suppresses_notification_but_still_logs_the_raw_anomaly():
    maintenance = MaintenanceModeRegistry()
    maintenance.declare(
        MaintenanceWindow(
            loopId="loop-1",
            start="2026-08-25T00:00:00",
            end="2026-08-25T02:00:00",
            operatorId="op-1",
        )
    )
    audit_log = []

    event = evaluate_and_log(
        "loop-1", "2026-08-25T01:00:00", flow_z=-3.0, flow_peer_z=2.5, utilization_delta_z=0.1,
        maintenance=maintenance, audit_log=audit_log,
    )

    assert event.isAnomaly is True
    assert event.suppressed is True
    assert should_notify(event) is False
    assert audit_log == [event]  # still logged for audit


def test_no_active_maintenance_window_does_not_suppress():
    maintenance = MaintenanceModeRegistry()
    audit_log = []

    event = evaluate_and_log(
        "loop-1", "2026-08-25T01:00:00", flow_z=-3.0, flow_peer_z=2.5, utilization_delta_z=0.1,
        maintenance=maintenance, audit_log=audit_log,
    )

    assert event.isAnomaly is True
    assert event.suppressed is False
    assert should_notify(event) is True


def test_maintenance_window_for_a_different_loop_does_not_suppress():
    maintenance = MaintenanceModeRegistry()
    maintenance.declare(
        MaintenanceWindow(loopId="loop-other", start="2026-08-25T00:00:00", end="2026-08-25T02:00:00", operatorId="op-1")
    )
    audit_log = []

    event = evaluate_and_log(
        "loop-1", "2026-08-25T01:00:00", flow_z=-3.0, flow_peer_z=2.5, utilization_delta_z=0.1,
        maintenance=maintenance, audit_log=audit_log,
    )

    assert event.suppressed is False


def test_maintenance_window_outside_its_time_range_does_not_suppress():
    maintenance = MaintenanceModeRegistry()
    maintenance.declare(
        MaintenanceWindow(loopId="loop-1", start="2026-08-25T00:00:00", end="2026-08-25T01:00:00", operatorId="op-1")
    )
    audit_log = []

    event = evaluate_and_log(
        "loop-1", "2026-08-25T05:00:00", flow_z=-3.0, flow_peer_z=2.5, utilization_delta_z=0.1,
        maintenance=maintenance, audit_log=audit_log,
    )

    assert event.suppressed is False


def test_no_anomaly_never_notifies_regardless_of_maintenance():
    maintenance = MaintenanceModeRegistry()
    audit_log = []

    event = evaluate_and_log(
        "loop-1", "2026-08-25T01:00:00", flow_z=0.1, flow_peer_z=0.1, utilization_delta_z=0.1,
        maintenance=maintenance, audit_log=audit_log,
    )

    assert event.isAnomaly is False
    assert should_notify(event) is False
