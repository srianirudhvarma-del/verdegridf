from idlehunter.telemetry import IdleHunterTelemetry
from shared.orchestrator import (
    build_rack_feature_vector,
    compute_thermal_headroom,
    filter_consolidation_targets_by_real_headroom,
)
from thermaltrace.sensors import ThermalTelemetry


# ---------------------------------------------------------------------------
# Dependency 1: IdleHunter -> ThermalTrace (load/power telemetry)
# ---------------------------------------------------------------------------


def test_build_rack_feature_vector_uses_real_idlehunter_telemetry():
    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)
    idlehunter_telemetry.register_host("host-2", seed=2)
    idlehunter_telemetry.poll("host-1")
    idlehunter_telemetry.poll("host-2")

    thermal_telemetry = ThermalTelemetry()
    thermal_telemetry.register_rack("rack-1", seed=1)
    thermal_telemetry.poll("rack-1")

    vector = build_rack_feature_vector(
        "rack-1", ["host-1", "host-2"], idlehunter_telemetry, thermal_telemetry, timestamp="2026-08-25T00:00:00+00:00"
    )

    # workloadUtil must come from the real average of the two hosts' actual
    # cpu readings, not a caller-supplied stub.
    expected_util = (idlehunter_telemetry.current("host-1")["cpu"] + idlehunter_telemetry.current("host-2")["cpu"]) / 2 / 100.0
    assert abs(vector.workloadUtil - expected_util) < 1e-6
    assert vector.powerDrawWatts is not None
    assert vector.humidity == thermal_telemetry.current("rack-1")["humidity"]


def test_build_rack_feature_vector_reflects_a_change_in_real_telemetry():
    """If the real IdleHunter reading changes, the feature vector must change too -- proving this is a live call, not a cached/fake value."""
    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)
    thermal_telemetry = ThermalTelemetry()
    thermal_telemetry.register_rack("rack-1", seed=1)
    thermal_telemetry.poll("rack-1")

    idlehunter_telemetry.poll("host-1")
    vector_before = build_rack_feature_vector("rack-1", ["host-1"], idlehunter_telemetry, thermal_telemetry)

    idlehunter_telemetry.inject_anomaly("host-1", "cpu", "spike", magnitude=90.0, duration_ticks=1)
    idlehunter_telemetry.poll("host-1")
    vector_after = build_rack_feature_vector("rack-1", ["host-1"], idlehunter_telemetry, thermal_telemetry)

    assert vector_after.workloadUtil != vector_before.workloadUtil


# ---------------------------------------------------------------------------
# Dependency 2: ThermalTrace -> IdleHunter (thermal headroom)
# ---------------------------------------------------------------------------


def test_compute_thermal_headroom_reflects_real_thermal_telemetry():
    thermal_telemetry = ThermalTelemetry()
    thermal_telemetry.register_rack("rack-hot", seed=1)
    thermal_telemetry.poll("rack-hot")

    headroom = compute_thermal_headroom("rack-hot", thermal_telemetry, ceiling_celsius=35.0)

    real_temp = thermal_telemetry.current("rack-hot")["temperature"]
    assert headroom.headroomCelsius == 35.0 - real_temp
    assert headroom.rackId == "rack-hot"


def test_headroom_status_is_constrained_near_the_ceiling():
    thermal_telemetry = ThermalTelemetry()
    thermal_telemetry.register_rack("rack-1", seed=1)
    thermal_telemetry.poll("rack-1")
    real_temp = thermal_telemetry.current("rack-1")["temperature"]

    headroom = compute_thermal_headroom("rack-1", thermal_telemetry, ceiling_celsius=real_temp + 2.0)
    assert headroom.status == "constrained"

    headroom_critical = compute_thermal_headroom("rack-1", thermal_telemetry, ceiling_celsius=real_temp - 1.0)
    assert headroom_critical.status == "critical"


def test_filter_targets_excludes_hosts_on_a_real_constrained_rack():
    """Real end-to-end call: idlehunter.consolidation.filter_targets_by_thermal_headroom
    is invoked with a get_headroom backed by real ThermalTrace telemetry, and
    a genuinely hot rack's host is actually excluded."""
    thermal_telemetry = ThermalTelemetry()
    thermal_telemetry.register_rack("rack-hot", seed=1)
    thermal_telemetry.register_rack("rack-cool", seed=2)
    thermal_telemetry.poll("rack-hot")
    thermal_telemetry.poll("rack-cool")

    # Force both racks' real temperatures deterministically apart via the
    # real telemetry engine's anomaly injection, so this test doesn't
    # depend on random baseline noise landing on the right side of the
    # ceiling.
    thermal_telemetry.inject_anomaly("rack-hot", "temperature", "thermal_spike", magnitude=50.0, duration_ticks=1)
    thermal_telemetry.poll("rack-hot")
    thermal_telemetry.inject_anomaly("rack-cool", "temperature", "cooling_event", magnitude=-15.0, duration_ticks=1)
    thermal_telemetry.poll("rack-cool")

    host_to_rack = {"host-1": "rack-hot", "host-2": "rack-cool"}
    allowed = filter_consolidation_targets_by_real_headroom(host_to_rack, ["host-1", "host-2"], thermal_telemetry)

    assert "host-1" not in allowed
    assert "host-2" in allowed
