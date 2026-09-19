import pytest

from powerprune.power import DwellStateMachine, HostState, InvalidTransition


def test_single_idle_sample_does_not_power_down_host():
    machine = DwellStateMachine("host-1", dwell_time_down_samples=20)
    state = machine.observe("idle-candidate")
    assert state == HostState.NORMAL


def test_sustained_idle_dwell_transitions_to_idle_candidate():
    machine = DwellStateMachine("host-1", dwell_time_down_samples=5)
    for _ in range(4):
        assert machine.observe("idle-candidate") == HostState.NORMAL
    assert machine.observe("idle-candidate") == HostState.IDLE_CANDIDATE


def test_activity_before_dwell_completes_resets_to_normal():
    machine = DwellStateMachine("host-1", dwell_time_down_samples=5)
    for _ in range(3):
        machine.observe("idle-candidate")
    machine.observe("normal")  # host became active again
    assert machine.state == HostState.NORMAL

    # dwell counter must have reset, not just paused
    for _ in range(4):
        assert machine.observe("idle-candidate") == HostState.NORMAL
    assert machine.observe("idle-candidate") == HostState.IDLE_CANDIDATE


def test_idle_candidate_reverts_to_normal_if_host_becomes_active_again():
    machine = DwellStateMachine("host-1", dwell_time_down_samples=2)
    machine.observe("idle-candidate")
    machine.observe("idle-candidate")
    assert machine.state == HostState.IDLE_CANDIDATE

    machine.observe("overloaded")
    assert machine.state == HostState.NORMAL


def test_consolidation_succeeded_moves_idle_candidate_to_standby():
    machine = DwellStateMachine("host-1", dwell_time_down_samples=1)
    machine.observe("idle-candidate")
    assert machine.state == HostState.IDLE_CANDIDATE

    machine.consolidation_succeeded()
    assert machine.state == HostState.STANDBY


def test_cannot_power_down_a_host_that_is_not_idle_candidate():
    machine = DwellStateMachine("host-1")
    with pytest.raises(InvalidTransition):
        machine.consolidation_succeeded()


def test_wake_fires_on_single_sample_no_dwell_required():
    """Asymmetric policy: wake requires only one triggering event, unlike
    the sustained dwell required to power down."""
    machine = DwellStateMachine("host-1", dwell_time_down_samples=1)
    machine.observe("idle-candidate")
    machine.consolidation_succeeded()
    assert machine.state == HostState.STANDBY

    state = machine.request_wake("high_water_mark_breach")
    assert state == HostState.WAKING
    assert machine.wake_reason == "high_water_mark_breach"


def test_wake_confirmed_returns_host_to_normal():
    machine = DwellStateMachine("host-1", dwell_time_down_samples=1)
    machine.observe("idle-candidate")
    machine.consolidation_succeeded()
    machine.request_wake("overload_elsewhere")

    state = machine.wake_confirmed()
    assert state == HostState.NORMAL
    assert machine.wake_reason is None


def test_cannot_wake_a_host_that_is_not_standby():
    machine = DwellStateMachine("host-1")
    with pytest.raises(InvalidTransition):
        machine.request_wake("some_reason")


def test_dwell_samples_default_is_within_methodology_range():
    from powerprune.power import DEFAULT_DWELL_TIME_DOWN_SAMPLES

    assert 20 <= DEFAULT_DWELL_TIME_DOWN_SAMPLES <= 40
