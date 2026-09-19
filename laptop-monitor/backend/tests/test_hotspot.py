import pytest

from app.hotspot import predict_hotspot


def test_flat_cool_temps_are_ok():
    prediction = predict_hotspot(
        "laptop-1", [45.0] * 10, freq_current=1800.0, freq_max=4500.0,
        horizon_seconds=60.0, sample_interval_seconds=5.0,
    )
    assert prediction.riskLevel == "ok"


def test_already_over_critical_is_critical_even_at_low_clock():
    """Safety takes precedence over the noise-guard: an already-hot chip
    is real regardless of what it's doing right now."""
    prediction = predict_hotspot(
        "laptop-1", [80.0, 90.0, 95.0], freq_current=900.0, freq_max=4500.0,
        horizon_seconds=60.0, sample_interval_seconds=5.0,
    )
    assert prediction.riskLevel == "critical"


def test_rising_trend_near_max_clock_projects_critical():
    # +2C every 5s (0.4C/s) from a 60C start -> current 78C, projected
    # 78 + 0.4*60 = 102C, well past the 92C default limit.
    temps = [60.0 + i * 2 for i in range(10)]
    prediction = predict_hotspot(
        "laptop-1", temps, freq_current=4300.0, freq_max=4500.0,
        horizon_seconds=60.0, sample_interval_seconds=5.0,
    )
    assert prediction.projectedTempC > 92.0
    assert prediction.riskLevel == "critical"


def test_same_rising_trend_at_low_clock_is_only_watch_not_critical():
    """Same temperature trend, but the CPU isn't actually pinned -- the
    projection is discounted from "critical" to "watch"."""
    temps = [60.0 + i * 2 for i in range(10)]
    prediction = predict_hotspot(
        "laptop-1", temps, freq_current=1200.0, freq_max=4500.0,
        horizon_seconds=60.0, sample_interval_seconds=5.0,
    )
    assert prediction.riskLevel == "watch"


def test_close_to_critical_right_now_is_watch():
    prediction = predict_hotspot(
        "laptop-1", [89.0] * 5, freq_current=2000.0, freq_max=4500.0,
        horizon_seconds=60.0, sample_interval_seconds=5.0,
    )
    assert prediction.riskLevel == "watch"


def test_empty_history_rejected():
    with pytest.raises(ValueError):
        predict_hotspot(
            "laptop-1", [], freq_current=2000.0, freq_max=4500.0,
            horizon_seconds=60.0, sample_interval_seconds=5.0,
        )
