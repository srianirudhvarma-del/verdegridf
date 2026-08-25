from waterwatch.anomaly import PointSensorReading, evaluate_point_sensor
from waterwatch.cooling import cooling_performance
from waterwatch.sensor_health import check_sensor_fault, is_flatlined, is_out_of_bounds, missing_samples_exceeded


# ---------------------------------------------------------------------------
# SHOULD HAVE #14 -- physical point sensor backstop
# ---------------------------------------------------------------------------


def test_dry_point_sensor_reading_produces_no_event():
    reading = PointSensorReading(sensorId="sensor-1", loopId="loop-1", timestamp="2026-08-25T00:00:00", wet=False)
    assert evaluate_point_sensor(reading) is None


def test_wet_point_sensor_reading_is_critical_and_never_suppressed():
    reading = PointSensorReading(sensorId="sensor-1", loopId="loop-1", timestamp="2026-08-25T00:00:00", wet=True)
    event = evaluate_point_sensor(reading)

    assert event is not None
    assert event.isAnomaly is True
    assert event.suppressed is False  # hard trip-wire -- bypasses even maintenance suppression


# ---------------------------------------------------------------------------
# SHOULD HAVE #15 -- sensor-failure/drift plausibility checks
# ---------------------------------------------------------------------------


def test_is_flatlined_true_when_variance_is_zero_across_the_window():
    readings = [50.0] * 10  # constant reading
    assert is_flatlined(readings, sample_interval_seconds=900.0) is True  # 10 samples * 15min = 2.5h


def test_is_flatlined_false_with_insufficient_history():
    readings = [50.0] * 3
    assert is_flatlined(readings, sample_interval_seconds=900.0) is False


def test_is_flatlined_false_when_reading_actually_varies():
    readings = [50.0, 52.0, 48.0, 51.0, 49.0, 50.5, 49.5, 51.5, 48.5, 50.0]
    assert is_flatlined(readings, sample_interval_seconds=900.0) is False


def test_is_out_of_bounds_flags_negative_and_above_rated_max():
    assert is_out_of_bounds(-1.0, max_value=100.0) is True
    assert is_out_of_bounds(150.0, max_value=100.0) is True
    assert is_out_of_bounds(50.0, max_value=100.0) is False


def test_missing_samples_exceeded():
    assert missing_samples_exceeded(4) is True
    assert missing_samples_exceeded(3) is False


def test_check_sensor_fault_flags_out_of_bounds_reading():
    fault = check_sensor_fault(
        "loop-1", "2026-08-25T00:00:00", [150.0], sample_interval_seconds=900.0, rated_max_flow=100.0
    )
    assert fault is not None
    assert "bounds" in fault.reason


def test_check_sensor_fault_flags_flatline():
    fault = check_sensor_fault(
        "loop-1", "2026-08-25T00:00:00", [50.0] * 10, sample_interval_seconds=900.0, rated_max_flow=200.0
    )
    assert fault is not None
    assert "flatlined" in fault.reason


def test_check_sensor_fault_flags_too_many_missing_samples():
    fault = check_sensor_fault(
        "loop-1", "2026-08-25T00:00:00", [50.0], sample_interval_seconds=900.0, rated_max_flow=200.0,
        consecutive_missing=5,
    )
    assert fault is not None
    assert "missing" in fault.reason


def test_check_sensor_fault_returns_none_for_a_healthy_sensor():
    readings = [50.0, 52.0, 48.0, 51.0, 49.0]
    fault = check_sensor_fault(
        "loop-1", "2026-08-25T00:00:00", readings, sample_interval_seconds=900.0, rated_max_flow=200.0
    )
    assert fault is None


# ---------------------------------------------------------------------------
# SHOULD HAVE #16 -- ThermalTrace cross-wire for cooling performance
# ---------------------------------------------------------------------------


def test_cooling_performance_positive_when_return_warmer_than_supply():
    performance = cooling_performance(flow_l_per_s=2.0, t_return_c=30.0, t_supply_c=18.0)
    assert performance == 2.0 * 4.186 * 12.0


def test_cooling_performance_zero_with_no_temperature_delta():
    assert cooling_performance(flow_l_per_s=2.0, t_return_c=20.0, t_supply_c=20.0) == 0.0
