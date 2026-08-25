from idlehunter.telemetry import IdleHunterTelemetry
from idlehunter.threshold import RESOURCES, classify_host
from shared.telemetry_sim import TelemetryAdapter


def test_adapter_implements_the_shared_telemetry_interface():
    telemetry = IdleHunterTelemetry()
    assert isinstance(telemetry, TelemetryAdapter)


def test_registered_host_polls_all_four_resources():
    telemetry = IdleHunterTelemetry()
    telemetry.register_host("host-1", seed=1)

    sample = telemetry.poll("host-1")

    assert set(sample.keys()) == set(RESOURCES)


def test_end_to_end_history_feeds_the_threshold_engine():
    """Real integration proof: the simulator's output is directly usable by
    the MAD threshold engine without any adaptation."""
    telemetry = IdleHunterTelemetry()
    telemetry.register_host("host-1", seed=42)

    for _ in range(65):
        telemetry.poll("host-1")

    history = {resource: telemetry.history("host-1", resource, 60) for resource in RESOURCES}
    current = telemetry.current("host-1")

    state = classify_host("host-1", current, history)

    assert state.status in {"normal", "idle-candidate", "overloaded"}
    # with 65 samples collected we're past cold start (N=60)
    assert all(len(history[r]) == 60 for r in RESOURCES)


def test_injected_anomaly_pushes_a_host_into_overloaded():
    telemetry = IdleHunterTelemetry()
    telemetry.register_host("host-1", seed=7)

    for _ in range(65):
        telemetry.poll("host-1")

    telemetry.inject_anomaly("host-1", "cpu", "cpu_spike", magnitude=80.0, duration_ticks=1)
    current = telemetry.poll("host-1")
    history = {resource: telemetry.history("host-1", resource, 60) for resource in RESOURCES}

    state = classify_host("host-1", current, history)

    assert state.status == "overloaded"
    assert current["cpu"] > 90.0
