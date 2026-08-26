from datetime import datetime, timedelta, timezone

from carbonclock.grid import (
    DEFAULT_SIGNAL_INFO,
    IMPLEMENTED_SIGNAL_TYPES,
    SUPPORTED_SIGNAL_TYPES,
    CarbonForecastSimulator,
)


def test_signal_info_reports_average_with_a_stated_rationale():
    assert DEFAULT_SIGNAL_INFO.type == "average"
    assert DEFAULT_SIGNAL_INFO.provider == "electricitymaps"
    assert DEFAULT_SIGNAL_INFO.rationale  # non-empty, documented justification


def test_marginal_is_a_known_but_unimplemented_signal_type():
    assert "marginal" in SUPPORTED_SIGNAL_TYPES
    assert "marginal" not in IMPLEMENTED_SIGNAL_TYPES
    assert "average" in IMPLEMENTED_SIGNAL_TYPES


def test_forecast_produces_48_hourly_buckets_spaced_one_hour_apart():
    sim = CarbonForecastSimulator()
    sim.register_zone("IN-SO", seed=1)
    start = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)

    forecast = sim.forecast_48h("IN-SO", start=start)

    assert len(forecast) == 48
    assert forecast[0].windowStart == start.isoformat()
    assert forecast[1].windowStart == (start + timedelta(hours=1)).isoformat()
    assert forecast[-1].windowEnd == (start + timedelta(hours=48)).isoformat()


def test_forecast_intensity_varies_across_hours_not_a_fixed_canned_value():
    sim = CarbonForecastSimulator()
    sim.register_zone("IN-SO", seed=1, noise_std=30.0)
    start = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)

    forecast = sim.forecast_48h("IN-SO", start=start)

    intensities = {bucket.carbonIntensity for bucket in forecast}
    assert len(intensities) > 1


def test_zones_have_independent_forecasts():
    sim = CarbonForecastSimulator()
    sim.register_zone("IN-SO", seed=1, baseline=250.0)
    sim.register_zone("US-CA", seed=2, baseline=400.0)
    start = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)

    in_so = sim.forecast_48h("IN-SO", start=start)
    us_ca = sim.forecast_48h("US-CA", start=start)

    assert in_so[0].carbonIntensity != us_ca[0].carbonIntensity


def test_sample_current_returns_a_live_reading_and_advances_history():
    sim = CarbonForecastSimulator()
    sim.register_zone("IN-SO", seed=1)

    first = sim.sample_current("IN-SO")
    second = sim.sample_current("IN-SO")

    assert isinstance(first, float)
    history = sim.history("IN-SO", 2)
    assert history == [first, second]
