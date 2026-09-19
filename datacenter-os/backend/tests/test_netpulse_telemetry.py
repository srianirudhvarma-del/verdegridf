from netpulse.telemetry import NetPulseTelemetry
from shared.telemetry_sim import TelemetryAdapter


def test_adapter_implements_the_shared_telemetry_interface():
    assert isinstance(NetPulseTelemetry(), TelemetryAdapter)


def test_registered_link_polls_utilization():
    telemetry = NetPulseTelemetry()
    telemetry.register_link("link-1", seed=1)

    sample = telemetry.poll("link-1")

    assert "utilization_pct" in sample
    assert 0.0 <= sample["utilization_pct"] <= 100.0


def test_links_have_independent_telemetry():
    telemetry = NetPulseTelemetry()
    telemetry.register_link("link-1", seed=1)
    telemetry.register_link("link-2", seed=2)

    for _ in range(10):
        telemetry.poll("link-1")
        telemetry.poll("link-2")

    assert telemetry.history("link-1", "utilization_pct", 10) != telemetry.history("link-2", "utilization_pct", 10)
