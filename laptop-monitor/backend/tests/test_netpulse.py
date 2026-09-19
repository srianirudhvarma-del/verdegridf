from app.netpulse import ElephantFlowTracker


def test_normal_below_threshold():
    tracker = ElephantFlowTracker(threshold_percent=70.0, sustained_samples=3)
    for _ in range(5):
        assert tracker.observe(40.0) == "normal"


def test_flips_to_elephant_flow_after_sustained_high_samples():
    tracker = ElephantFlowTracker(threshold_percent=70.0, sustained_samples=3)
    assert tracker.observe(80.0) == "normal"
    assert tracker.observe(80.0) == "normal"
    assert tracker.observe(80.0) == "elephant_flow"


def test_single_high_sample_is_not_enough():
    tracker = ElephantFlowTracker(threshold_percent=70.0, sustained_samples=3)
    assert tracker.observe(90.0) == "normal"
    assert tracker.observe(10.0) == "normal"
    assert tracker.observe(90.0) == "normal"


def test_dropping_below_threshold_resets_the_streak():
    tracker = ElephantFlowTracker(threshold_percent=70.0, sustained_samples=3)
    tracker.observe(80.0)
    tracker.observe(80.0)
    tracker.observe(10.0)  # resets
    assert tracker.observe(80.0) == "normal"
    assert tracker.observe(80.0) == "normal"
    assert tracker.observe(80.0) == "elephant_flow"
