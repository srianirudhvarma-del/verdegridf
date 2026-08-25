import pytest

from thermaltrace.sensors import PressureReading as ThermalTracePressureReading
from waterwatch.sensors import AMBIENT_ABSOLUTE_KPA, HumidityReading, PressureReading, WaterWatchTelemetry


def test_waterwatch_reuses_the_thermaltrace_pressure_reading_class():
    """One differential-pressure sensor type, two consumers -- not a
    parallel redefinition."""
    assert PressureReading is ThermalTracePressureReading


def test_registered_loop_polls_flow_rate_and_differential_pressure():
    telemetry = WaterWatchTelemetry()
    telemetry.register_loop("loop-1", seed=1)

    sample = telemetry.poll("loop-1")

    assert set(sample.keys()) == {"flow_rate", "differential_pressure"}


def test_pressure_reading_matches_the_shared_schema():
    telemetry = WaterWatchTelemetry()
    telemetry.register_loop("loop-1", seed=1)
    telemetry.poll("loop-1")

    reading = telemetry.pressure_reading("loop-1", timestamp="2026-08-25T00:00:00Z")

    assert isinstance(reading, PressureReading)
    assert reading.loopId == "loop-1"
    assert reading.absoluteKPa == pytest.approx(AMBIENT_ABSOLUTE_KPA + reading.differentialKPa)


def test_humidity_reading_is_zone_scoped_not_per_rack():
    telemetry = WaterWatchTelemetry()
    telemetry.register_zone("zone-a", seed=1)
    telemetry.poll("zone-a")

    reading = telemetry.humidity_reading("zone-a", timestamp="2026-08-25T00:00:00Z")

    assert isinstance(reading, HumidityReading)
    assert reading.zoneId == "zone-a"


def test_loops_and_zones_have_independent_telemetry():
    telemetry = WaterWatchTelemetry()
    telemetry.register_loop("loop-a", seed=1)
    telemetry.register_loop("loop-b", seed=2)

    for _ in range(10):
        telemetry.poll("loop-a")
        telemetry.poll("loop-b")

    assert telemetry.history("loop-a", "flow_rate", 10) != telemetry.history("loop-b", "flow_rate", 10)
