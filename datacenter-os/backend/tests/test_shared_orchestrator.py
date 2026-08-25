from idlehunter.telemetry import IdleHunterTelemetry
from shared.orchestrator import build_rack_feature_vector
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
