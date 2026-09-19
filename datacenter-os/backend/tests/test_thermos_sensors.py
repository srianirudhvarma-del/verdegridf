import math

import pytest

from thermos.sensors import (
    AMBIENT_ABSOLUTE_KPA,
    DEFAULT_AIRFLOW_CALIBRATION_CONSTANT,
    PressureReading,
    ThermalTelemetry,
    estimate_airflow,
)


def test_estimate_airflow_follows_fan_law_relationship():
    airflow = estimate_airflow(4.0, calibration_constant=10.0)
    assert airflow == pytest.approx(10.0 * math.sqrt(4.0))


def test_estimate_airflow_uses_default_calibration_constant():
    airflow = estimate_airflow(9.0)
    assert airflow == pytest.approx(DEFAULT_AIRFLOW_CALIBRATION_CONSTANT * 3.0)


def test_estimate_airflow_rejects_negative_pressure():
    with pytest.raises(ValueError):
        estimate_airflow(-1.0)


def test_registered_rack_polls_temperature_pressure_and_humidity():
    telemetry = ThermalTelemetry()
    telemetry.register_rack("rack-1", seed=1)

    sample = telemetry.poll("rack-1")

    assert set(sample.keys()) == {"temperature", "differential_pressure", "humidity"}


def test_pressure_reading_matches_the_shared_schema():
    telemetry = ThermalTelemetry()
    telemetry.register_rack("rack-1", seed=1)
    telemetry.poll("rack-1")

    reading = telemetry.pressure_reading("rack-1", timestamp="2026-08-25T00:00:00Z")

    assert isinstance(reading, PressureReading)
    assert reading.loopId == "rack-1"
    assert reading.absoluteKPa == pytest.approx(AMBIENT_ABSOLUTE_KPA + reading.differentialKPa)


def test_racks_have_independent_telemetry():
    telemetry = ThermalTelemetry()
    telemetry.register_rack("rack-a", seed=1)
    telemetry.register_rack("rack-b", seed=2)

    for _ in range(10):
        telemetry.poll("rack-a")
        telemetry.poll("rack-b")

    a_history = telemetry.history("rack-a", "temperature", 10)
    b_history = telemetry.history("rack-b", "temperature", 10)
    assert a_history != b_history
