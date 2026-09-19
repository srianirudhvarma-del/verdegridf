import pytest

from coolsense.baseline import Baseline, bucket_utilization, compute_baseline, peer_z_score, z_score


def test_bucket_utilization_falls_back_to_medium_with_insufficient_history():
    assert bucket_utilization(50.0, [10.0, 20.0]) == "medium"


def test_bucket_utilization_assigns_low_medium_high_by_tertile():
    history = list(range(0, 30))  # 0..29, tertile cuts at index 10 and 20 -> values 10, 20

    assert bucket_utilization(2.0, history) == "low"
    assert bucket_utilization(15.0, history) == "medium"
    assert bucket_utilization(28.0, history) == "high"


def test_compute_baseline_mean_and_std():
    baseline = compute_baseline([10.0, 20.0, 30.0])
    assert baseline.mean == 20.0
    assert baseline.std == pytest.approx(8.16496580927726)


def test_compute_baseline_requires_at_least_two_samples():
    with pytest.raises(ValueError):
        compute_baseline([10.0])


def test_z_score_positive_above_mean_negative_below():
    baseline = Baseline(mean=100.0, std=10.0)
    assert z_score(120.0, baseline) == pytest.approx(2.0)
    assert z_score(80.0, baseline) == pytest.approx(-2.0)
    assert z_score(100.0, baseline) == pytest.approx(0.0)


def test_z_score_zero_std_with_matching_value_is_zero():
    baseline = Baseline(mean=50.0, std=0.0)
    assert z_score(50.0, baseline) == 0.0


def test_peer_z_score_subtracts_peer_average():
    # rack's own z is 3.0; peers average to 1.0 -> peerZ = 2.0
    assert peer_z_score(3.0, [0.5, 1.5]) == pytest.approx(2.0)


def test_peer_z_score_with_no_peers_is_zero():
    assert peer_z_score(5.0, []) == 0.0
