import pytest

from thermos.model import (
    MIN_RESIDUAL_TRAINING_SAMPLES,
    PowerPruneRackReading,
    RCThermalModel,
    ResidualCorrector,
    build_feature_vector,
    join_workload_telemetry,
    predict_with_uncertainty,
)


# ---------------------------------------------------------------------------
# MUST HAVE #20 -- physics-lite RC core + ML residual correction
# ---------------------------------------------------------------------------


def test_physics_core_alone_produces_a_plausible_prediction_with_zero_training_data():
    """Acceptance test: the physics-only core needs no training data."""
    model = RCThermalModel(thermal_resistance=60.0, thermal_capacitance=60.0, cooling_capacity=40.0)
    prediction = model.predict(current_temp_c=30.0, power_draw_watts=500.0, supply_temp_c=18.0, dt_seconds=60.0)

    assert isinstance(prediction, float)
    assert 0.0 < prediction < 100.0  # plausible datacenter temperature range


def test_higher_power_draw_raises_the_predicted_temperature():
    model = RCThermalModel(thermal_resistance=60.0, thermal_capacitance=60.0, cooling_capacity=40.0)
    low_power = model.predict(current_temp_c=30.0, power_draw_watts=100.0, supply_temp_c=18.0, dt_seconds=60.0)
    high_power = model.predict(current_temp_c=30.0, power_draw_watts=1000.0, supply_temp_c=18.0, dt_seconds=60.0)

    assert high_power > low_power


def test_rc_model_rejects_nonpositive_constants():
    with pytest.raises(ValueError):
        RCThermalModel(thermal_resistance=0.0, thermal_capacitance=5.0, cooling_capacity=50.0)


def test_residual_corrector_falls_back_to_zero_before_enough_data():
    corrector = ResidualCorrector()
    for _ in range(MIN_RESIDUAL_TRAINING_SAMPLES - 1):
        corrector.record_residual(2.0)

    assert corrector.has_enough_data is False
    assert corrector.predict_residual() == 0.0


def test_residual_corrector_learns_an_upward_trend_once_enough_data_exists():
    corrector = ResidualCorrector()
    for i in range(MIN_RESIDUAL_TRAINING_SAMPLES):
        corrector.record_residual(float(i))  # clearly increasing residual

    assert corrector.has_enough_data is True
    assert corrector.predict_residual() > corrector._residuals[-1] - 1  # continues the upward trend


# ---------------------------------------------------------------------------
# MUST HAVE #18 -- uncertainty bands
# ---------------------------------------------------------------------------


def test_every_prediction_ships_with_a_confidence_band_not_a_bare_point_estimate():
    model = RCThermalModel(thermal_resistance=60.0, thermal_capacitance=60.0, cooling_capacity=40.0)
    corrector = ResidualCorrector()

    prediction = predict_with_uncertainty(
        model,
        corrector,
        rack_id="rack-1",
        current_temp_c=30.0,
        power_draw_watts=500.0,
        supply_temp_c=18.0,
        dt_seconds=60.0,
        seed=1,
    )

    assert prediction.lower <= prediction.mean <= prediction.upper
    assert prediction.lower < prediction.upper  # a real band, not a collapsed point


def test_prediction_is_physics_only_when_corrector_has_no_training_data():
    model = RCThermalModel(thermal_resistance=60.0, thermal_capacitance=60.0, cooling_capacity=40.0)
    corrector = ResidualCorrector()

    prediction = predict_with_uncertainty(
        model, corrector, rack_id="rack-1", current_temp_c=30.0, power_draw_watts=500.0,
        supply_temp_c=18.0, dt_seconds=60.0, seed=1,
    )

    assert prediction.physicsOnly is True


def test_prediction_is_not_physics_only_once_corrector_is_trained():
    model = RCThermalModel(thermal_resistance=60.0, thermal_capacitance=60.0, cooling_capacity=40.0)
    corrector = ResidualCorrector()
    for _ in range(MIN_RESIDUAL_TRAINING_SAMPLES):
        corrector.record_residual(0.5)

    prediction = predict_with_uncertainty(
        model, corrector, rack_id="rack-1", current_temp_c=30.0, power_draw_watts=500.0,
        supply_temp_c=18.0, dt_seconds=60.0, seed=1,
    )

    assert prediction.physicsOnly is False


def test_single_pass_ensemble_has_zero_width_band():
    model = RCThermalModel(thermal_resistance=60.0, thermal_capacitance=60.0, cooling_capacity=40.0)
    corrector = ResidualCorrector()

    prediction = predict_with_uncertainty(
        model, corrector, rack_id="rack-1", current_temp_c=30.0, power_draw_watts=500.0,
        supply_temp_c=18.0, dt_seconds=60.0, n_passes=1, seed=1,
    )
    assert prediction.lower == prediction.upper == prediction.mean


def test_prediction_is_deterministic_given_a_seed():
    model = RCThermalModel(thermal_resistance=60.0, thermal_capacitance=60.0, cooling_capacity=40.0)

    p1 = predict_with_uncertainty(
        model, ResidualCorrector(), rack_id="rack-1", current_temp_c=30.0, power_draw_watts=500.0,
        supply_temp_c=18.0, dt_seconds=60.0, seed=99,
    )
    p2 = predict_with_uncertainty(
        model, ResidualCorrector(), rack_id="rack-1", current_temp_c=30.0, power_draw_watts=500.0,
        supply_temp_c=18.0, dt_seconds=60.0, seed=99,
    )
    assert p1.mean == p2.mean
    assert p1.lower == p2.lower
    assert p1.upper == p2.upper


# ---------------------------------------------------------------------------
# MUST HAVE #19 -- PowerPrune telemetry join
# ---------------------------------------------------------------------------


def test_join_finds_the_most_recent_reading_within_tolerance():
    readings = [
        PowerPruneRackReading(rackId="rack-1", timestamp="2026-08-25T00:00:00+00:00", workloadUtil=0.4, powerDrawWatts=800.0),
        PowerPruneRackReading(rackId="rack-1", timestamp="2026-08-25T00:00:30+00:00", workloadUtil=0.6, powerDrawWatts=900.0),
    ]

    util, power = join_workload_telemetry("rack-1", "2026-08-25T00:00:45+00:00", readings)

    assert util == 0.6
    assert power == 900.0


def test_join_ignores_readings_from_a_different_rack():
    readings = [
        PowerPruneRackReading(rackId="rack-2", timestamp="2026-08-25T00:00:00+00:00", workloadUtil=0.9, powerDrawWatts=1200.0),
    ]

    util, power = join_workload_telemetry("rack-1", "2026-08-25T00:00:05+00:00", readings)

    assert util is None
    assert power is None


def test_join_falls_back_to_none_when_reading_is_too_stale():
    readings = [
        PowerPruneRackReading(rackId="rack-1", timestamp="2026-08-25T00:00:00+00:00", workloadUtil=0.4, powerDrawWatts=800.0),
    ]

    util, power = join_workload_telemetry(
        "rack-1", "2026-08-25T00:05:00+00:00", readings, max_staleness_seconds=60.0
    )

    assert util is None
    assert power is None


def test_build_feature_vector_matches_the_shared_schema_shape():
    readings = [
        PowerPruneRackReading(rackId="rack-1", timestamp="2026-08-25T00:00:00+00:00", workloadUtil=0.3, powerDrawWatts=700.0),
    ]
    vector = build_feature_vector(
        "rack-1",
        "2026-08-25T00:00:10+00:00",
        temp_grid=[[25.0, 26.0], [27.0, 28.0]],
        humidity=45.0,
        powerprune_readings=readings,
    )

    assert vector.workloadUtil == 0.3
    assert vector.powerDrawWatts == 700.0
    assert vector.tempGrid == [[25.0, 26.0], [27.0, 28.0]]
