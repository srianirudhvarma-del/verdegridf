from app.coolsense import assess_cooling


def test_insufficient_data_before_min_samples():
    pairs = [(20.0, 40.0)] * 5  # well under COLD_START_MIN_SAMPLES (20)
    result = assess_cooling("laptop-1", pairs, current_cpu=20.0, current_temp=40.0)
    assert result.status == "insufficient_data"
    assert result.expectedTempC is None


def test_normal_reading_matching_baseline_is_ok():
    # temp = 30 + 0.5*cpu, with tiny alternating jitter so MAD isn't
    # degenerately zero -- a realistic, well-behaved baseline.
    pairs = [(cpu, 30.0 + 0.5 * cpu + (0.2 if i % 2 == 0 else -0.2)) for i, cpu in enumerate(range(10, 40))]
    # Current reading fits the same relationship: cpu=25 -> expected ~42.5
    result = assess_cooling("laptop-1", pairs, current_cpu=25.0, current_temp=42.6)
    assert result.status == "ok"


def test_reading_far_above_baseline_is_anomaly():
    pairs = [(cpu, 30.0 + 0.5 * cpu + (0.2 if i % 2 == 0 else -0.2)) for i, cpu in enumerate(range(10, 40))]
    # Same cpu=25 (expected ~42.5), but a wildly hot actual reading --
    # simulates a clogged fan / degraded cooling at the same workload.
    result = assess_cooling("laptop-1", pairs, current_cpu=25.0, current_temp=70.0)
    assert result.status == "anomaly"
    assert result.residualC > 20  # actual far exceeds expected
