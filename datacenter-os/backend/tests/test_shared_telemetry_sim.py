import pytest

from shared.telemetry_sim import (
    SimulatedTelemetryAdapter,
    SyntheticSeries,
    TelemetryAdapter,
    TelemetrySimulator,
    make_host_simulator,
)


def test_series_is_stateful_not_iid_noise():
    """
    A stateful mean-reverting walk should stay near its baseline across many
    ticks (bounded variance), unlike unrelated i.i.d. draws which could
    wander anywhere within [min, max]. We assert the simple, load-bearing
    property: consecutive samples are close to each other, not wildly
    different every tick.
    """
    series = SyntheticSeries(baseline=30.0, noise_std=2.0, reversion=0.1, seed=42)
    values = [series.tick() for _ in range(200)]

    max_step = max(abs(values[i] - values[i - 1]) for i in range(1, len(values)))
    assert max_step < 15.0  # no single tick should be a wild jump

    mean = sum(values) / len(values)
    assert 20.0 < mean < 40.0  # stays in the neighborhood of baseline=30


def test_series_is_deterministic_given_a_seed():
    a = SyntheticSeries(baseline=50.0, noise_std=5.0, seed=7)
    b = SyntheticSeries(baseline=50.0, noise_std=5.0, seed=7)

    a_values = [a.tick() for _ in range(20)]
    b_values = [b.tick() for _ in range(20)]

    assert a_values == b_values


def test_positive_trend_pulls_the_series_upward():
    flat = SyntheticSeries(baseline=30.0, trend_per_tick=0.0, noise_std=0.0, reversion=0.0, seed=1, max_value=1000.0)
    rising = SyntheticSeries(baseline=30.0, trend_per_tick=1.0, noise_std=0.0, reversion=0.0, seed=1, max_value=1000.0)

    for _ in range(20):
        flat.tick()
        rising.tick()

    assert rising.value > flat.value


def test_values_stay_within_configured_bounds():
    series = SyntheticSeries(baseline=90.0, trend_per_tick=5.0, noise_std=10.0, reversion=0.0, min_value=0.0, max_value=100.0, seed=3)
    for _ in range(500):
        v = series.tick()
        assert 0.0 <= v <= 100.0


def test_injected_anomaly_produces_a_clear_spike_then_expires():
    series = SyntheticSeries(baseline=20.0, noise_std=0.5, reversion=0.05, seed=9, max_value=1000.0)
    for _ in range(10):
        series.tick()
    pre_anomaly_value = series.value

    series.inject_anomaly("thermal_spike", magnitude=50.0, duration_ticks=3)
    assert series.active_anomaly == "thermal_spike"

    spiked_values = [series.tick() for _ in range(3)]
    assert all(v > pre_anomaly_value + 30 for v in spiked_values)
    assert series.active_anomaly is None  # anomaly must expire after duration_ticks

    post_values = [series.tick() for _ in range(20)]
    # after expiry, the series should settle back down toward baseline, not
    # stay pinned at the spike level
    assert post_values[-1] < spiked_values[-1]


def test_simulator_tracks_independent_metrics_per_entity():
    sim = TelemetrySimulator()
    sim.register_metric("host-1", "cpu", baseline=30.0, noise_std=1.0, seed=1)
    sim.register_metric("host-1", "mem", baseline=60.0, noise_std=1.0, seed=2)
    sim.register_metric("host-2", "cpu", baseline=80.0, noise_std=1.0, seed=3)

    sample_1 = sim.sample("host-1")
    sample_2 = sim.sample("host-2")

    assert set(sample_1.keys()) == {"cpu", "mem"}
    assert set(sample_2.keys()) == {"cpu"}
    assert sample_1["cpu"] != sample_2["cpu"]  # different baselines, not shared state


def test_simulator_history_accumulates_across_samples():
    sim = TelemetrySimulator()
    sim.register_metric("rack-1", "differential_pressure", baseline=5.0, noise_std=0.2, seed=1)

    for _ in range(10):
        sim.sample("rack-1")

    history = sim.history("rack-1", "differential_pressure", n=5)
    assert len(history) == 5


def test_simulator_unknown_entity_raises():
    sim = TelemetrySimulator()
    with pytest.raises(KeyError):
        sim.sample("does-not-exist")


def test_simulated_adapter_implements_the_adapter_interface():
    sim = TelemetrySimulator()
    sim.register_metric("link-1", "utilization", baseline=40.0, noise_std=2.0, seed=1)
    adapter = SimulatedTelemetryAdapter(sim)

    assert isinstance(adapter, TelemetryAdapter)

    polled = adapter.poll("link-1")
    assert "utilization" in polled

    hist = adapter.history("link-1", "utilization", n=1)
    assert len(hist) == 1


def test_make_host_simulator_registers_the_four_mad_resources():
    sim = make_host_simulator(["host-a", "host-b"], seed=123)

    assert set(sim.entity_ids()) == {"host-a", "host-b"}
    sample = sim.sample("host-a")
    assert set(sample.keys()) == {"cpu", "mem", "diskIO", "network"}


def test_make_host_simulator_hosts_have_independent_series():
    sim = make_host_simulator(["host-a", "host-b"], seed=123)
    for _ in range(30):
        sim.tick()

    a_history = sim.history("host-a", "cpu", n=30)
    b_history = sim.history("host-b", "cpu", n=30)
    assert a_history != b_history
