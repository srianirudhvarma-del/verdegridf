from datetime import datetime, timedelta, timezone

from carbonclock.grid import (
    CarbonForecastSimulator,
    DEFAULT_GREEN_THRESHOLD,
    DEFAULT_DIRTY_THRESHOLD,
    ForecastCache,
    HysteresisState,
)
from carbonclock.scheduler import rank_windows_by_carbon_and_price
from carbonclock.grid import HourlyForecast

NOW = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


def make_window(hour_offset, intensity):
    start = NOW + timedelta(hours=hour_offset)
    return HourlyForecast(windowStart=start.isoformat(), windowEnd=(start + timedelta(hours=1)).isoformat(), carbonIntensity=intensity)


# ---------------------------------------------------------------------------
# SHOULD HAVE #10 -- forecast refresh cadence
# ---------------------------------------------------------------------------


def test_forecast_is_not_regenerated_within_the_refresh_interval():
    sim = CarbonForecastSimulator()
    sim.register_zone("IN-SO", seed=1)
    cache = ForecastCache(sim, refresh_interval_seconds=3600.0)

    first = cache.get_forecast("IN-SO", now=NOW)
    second = cache.get_forecast("IN-SO", now=NOW + timedelta(minutes=30))

    assert first == second
    assert cache.last_refreshed("IN-SO") == NOW


def test_forecast_refreshes_after_the_interval_elapses():
    sim = CarbonForecastSimulator()
    sim.register_zone("IN-SO", seed=1)
    cache = ForecastCache(sim, refresh_interval_seconds=3600.0)

    first = cache.get_forecast("IN-SO", now=NOW)
    second = cache.get_forecast("IN-SO", now=NOW + timedelta(hours=2))

    assert first != second
    assert cache.last_refreshed("IN-SO") == NOW + timedelta(hours=2)


# ---------------------------------------------------------------------------
# SHOULD HAVE #11 -- hysteresis/smoothing
# ---------------------------------------------------------------------------


def test_single_sample_crossing_the_band_does_not_flip_classification():
    state = HysteresisState(confirm_samples=2)
    result = state.observe(DEFAULT_GREEN_THRESHOLD - 100.0)  # well below green threshold
    assert result == "normal"  # starts normal, one sample isn't enough


def test_sustained_crossing_for_confirm_samples_flips_classification():
    state = HysteresisState(confirm_samples=2, window=1)
    state.observe(DEFAULT_GREEN_THRESHOLD - 100.0)
    result = state.observe(DEFAULT_GREEN_THRESHOLD - 100.0)
    assert result == "green"


def test_dirty_crossing_flips_to_dirty_after_confirm_samples():
    state = HysteresisState(confirm_samples=2, window=1)
    state.observe(DEFAULT_DIRTY_THRESHOLD + 100.0)
    result = state.observe(DEFAULT_DIRTY_THRESHOLD + 100.0)
    assert result == "dirty"


def test_reverting_to_normal_before_confirm_samples_does_not_flip():
    state = HysteresisState(confirm_samples=3, window=1)
    state.observe(DEFAULT_GREEN_THRESHOLD - 100.0)
    state.observe(DEFAULT_GREEN_THRESHOLD - 100.0)
    result = state.observe((DEFAULT_GREEN_THRESHOLD + DEFAULT_DIRTY_THRESHOLD) / 2)  # back to normal zone
    assert result == "normal"  # never accumulated 3 consecutive green samples


# ---------------------------------------------------------------------------
# SHOULD HAVE #12 -- electricity-price signal
# ---------------------------------------------------------------------------


def test_falls_back_to_carbon_only_ranking_when_no_price_feed():
    windows = [make_window(0, 300.0), make_window(1, 100.0)]
    ranked = rank_windows_by_carbon_and_price(windows, None)
    assert [w.carbonIntensity for w in ranked] == [100.0, 300.0]


def test_price_signal_can_reorder_ranking_when_carbon_is_close():
    w1 = make_window(0, 100.0)
    w2 = make_window(1, 105.0)  # nearly identical carbon
    prices = {w1.windowStart: 0.50, w2.windowStart: 0.05}  # w2 is much cheaper

    ranked = rank_windows_by_carbon_and_price([w1, w2], prices, w_carbon=0.3, w_price=0.7)

    assert ranked[0].windowStart == w2.windowStart


def test_missing_price_for_one_window_ranks_it_last_on_price_not_dropped():
    w1 = make_window(0, 200.0)
    w2 = make_window(1, 210.0)
    prices = {w1.windowStart: 0.20}  # w2 has no price data

    ranked = rank_windows_by_carbon_and_price([w1, w2], prices)

    assert {w.windowStart for w in ranked} == {w1.windowStart, w2.windowStart}
