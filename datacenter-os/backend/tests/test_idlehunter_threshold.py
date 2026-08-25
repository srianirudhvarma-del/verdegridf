from idlehunter.threshold import (
    COLD_START_LOWER,
    RESOURCES,
    classify_host,
    compute_resource_threshold,
)


def flat_history(value, n=60):
    return [value] * n


def test_cold_start_uses_static_defaults_below_window_size():
    threshold = compute_resource_threshold("cpu", flat_history(30.0, n=10))
    assert threshold.lower == COLD_START_LOWER["cpu"]


def test_threshold_widens_as_variance_rises_not_fixed_at_15_percent():
    """Adaptive threshold acceptance test: rising variance must widen the
    idle-candidate floor's distance from the median, not stay pinned at a
    fixed 15%."""
    low_variance_history = [30.0 + (i % 2) * 0.5 for i in range(60)]  # tight spread around 30
    high_variance_history = [30.0 + (-1) ** i * (i % 20) for i in range(60)]  # wide spread around 30

    low_var_threshold = compute_resource_threshold("cpu", low_variance_history)
    high_var_threshold = compute_resource_threshold("cpu", high_variance_history)

    low_var_width = low_var_threshold.upper - low_var_threshold.lower
    high_var_width = high_var_threshold.upper - high_var_threshold.lower

    assert high_var_width > low_var_width
    # and neither is just the hardcoded legacy 15% cutoff
    assert low_var_threshold.lower != 15.0 or high_var_threshold.lower != 15.0


def test_memory_bound_host_is_never_idle_candidate_even_if_cpu_idle():
    """Multi-resource check: a host idle on cpu/diskIO/network but pegged on
    mem must never be classified idle-candidate."""
    history = {resource: flat_history(30.0) for resource in RESOURCES}
    current = {"cpu": 2.0, "mem": 95.0, "diskIO": 2.0, "network": 2.0}

    state = classify_host("host-1", current, history)

    assert state.status != "idle-candidate"


def test_host_idle_on_all_resources_is_idle_candidate():
    history = {resource: flat_history(30.0) for resource in RESOURCES}
    current = {"cpu": 1.0, "mem": 1.0, "diskIO": 1.0, "network": 1.0}

    state = classify_host("host-2", current, history)

    assert state.status == "idle-candidate"


def test_host_over_upper_on_any_resource_is_overloaded():
    history = {resource: flat_history(30.0) for resource in RESOURCES}
    current = {"cpu": 99.0, "mem": 30.0, "diskIO": 30.0, "network": 30.0}

    state = classify_host("host-3", current, history)

    assert state.status == "overloaded"


def test_normal_host_is_neither_idle_nor_overloaded():
    history = {resource: flat_history(30.0) for resource in RESOURCES}
    current = {"cpu": 30.0, "mem": 30.0, "diskIO": 30.0, "network": 30.0}

    state = classify_host("host-4", current, history)

    assert state.status == "normal"
