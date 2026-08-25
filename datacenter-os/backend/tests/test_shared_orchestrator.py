from datetime import datetime, timedelta, timezone

import pytest

from carbonclock.grid import HourlyForecast
from carbonclock.scheduler import SchedulingPool
from idlehunter.power import DwellStateMachine, HostState
from idlehunter.telemetry import IdleHunterTelemetry
from shared.eventbus import EventBus
from shared.orchestrator import (
    PrewakeSubscriber,
    bucket_rack_load,
    build_rack_feature_vector,
    compute_capacity_forecast,
    compute_thermal_headroom,
    filter_consolidation_targets_by_real_headroom,
    schedule_job_with_real_capacity,
)
from thermaltrace.sensors import ThermalTelemetry

NOW = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Dependency 1: IdleHunter -> ThermalTrace (load/power telemetry)
# ---------------------------------------------------------------------------


def test_build_rack_feature_vector_uses_real_idlehunter_telemetry():
    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)
    idlehunter_telemetry.register_host("host-2", seed=2)
    idlehunter_telemetry.poll("host-1")
    idlehunter_telemetry.poll("host-2")

    thermal_telemetry = ThermalTelemetry()
    thermal_telemetry.register_rack("rack-1", seed=1)
    thermal_telemetry.poll("rack-1")

    vector = build_rack_feature_vector(
        "rack-1", ["host-1", "host-2"], idlehunter_telemetry, thermal_telemetry, timestamp="2026-08-25T00:00:00+00:00"
    )

    # workloadUtil must come from the real average of the two hosts' actual
    # cpu readings, not a caller-supplied stub.
    expected_util = (idlehunter_telemetry.current("host-1")["cpu"] + idlehunter_telemetry.current("host-2")["cpu"]) / 2 / 100.0
    assert abs(vector.workloadUtil - expected_util) < 1e-6
    assert vector.powerDrawWatts is not None
    assert vector.humidity == thermal_telemetry.current("rack-1")["humidity"]


def test_build_rack_feature_vector_reflects_a_change_in_real_telemetry():
    """If the real IdleHunter reading changes, the feature vector must change too -- proving this is a live call, not a cached/fake value."""
    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)
    thermal_telemetry = ThermalTelemetry()
    thermal_telemetry.register_rack("rack-1", seed=1)
    thermal_telemetry.poll("rack-1")

    idlehunter_telemetry.poll("host-1")
    vector_before = build_rack_feature_vector("rack-1", ["host-1"], idlehunter_telemetry, thermal_telemetry)

    idlehunter_telemetry.inject_anomaly("host-1", "cpu", "spike", magnitude=90.0, duration_ticks=1)
    idlehunter_telemetry.poll("host-1")
    vector_after = build_rack_feature_vector("rack-1", ["host-1"], idlehunter_telemetry, thermal_telemetry)

    assert vector_after.workloadUtil != vector_before.workloadUtil


# ---------------------------------------------------------------------------
# Dependency 2: ThermalTrace -> IdleHunter (thermal headroom)
# ---------------------------------------------------------------------------


def test_compute_thermal_headroom_reflects_real_thermal_telemetry():
    thermal_telemetry = ThermalTelemetry()
    thermal_telemetry.register_rack("rack-hot", seed=1)
    thermal_telemetry.poll("rack-hot")

    headroom = compute_thermal_headroom("rack-hot", thermal_telemetry, ceiling_celsius=35.0)

    real_temp = thermal_telemetry.current("rack-hot")["temperature"]
    assert headroom.headroomCelsius == 35.0 - real_temp
    assert headroom.rackId == "rack-hot"


def test_headroom_status_is_constrained_near_the_ceiling():
    thermal_telemetry = ThermalTelemetry()
    thermal_telemetry.register_rack("rack-1", seed=1)
    thermal_telemetry.poll("rack-1")
    real_temp = thermal_telemetry.current("rack-1")["temperature"]

    headroom = compute_thermal_headroom("rack-1", thermal_telemetry, ceiling_celsius=real_temp + 2.0)
    assert headroom.status == "constrained"

    headroom_critical = compute_thermal_headroom("rack-1", thermal_telemetry, ceiling_celsius=real_temp - 1.0)
    assert headroom_critical.status == "critical"


def test_filter_targets_excludes_hosts_on_a_real_constrained_rack():
    """Real end-to-end call: idlehunter.consolidation.filter_targets_by_thermal_headroom
    is invoked with a get_headroom backed by real ThermalTrace telemetry, and
    a genuinely hot rack's host is actually excluded."""
    thermal_telemetry = ThermalTelemetry()
    thermal_telemetry.register_rack("rack-hot", seed=1)
    thermal_telemetry.register_rack("rack-cool", seed=2)
    thermal_telemetry.poll("rack-hot")
    thermal_telemetry.poll("rack-cool")

    # Force both racks' real temperatures deterministically apart via the
    # real telemetry engine's anomaly injection, so this test doesn't
    # depend on random baseline noise landing on the right side of the
    # ceiling.
    thermal_telemetry.inject_anomaly("rack-hot", "temperature", "thermal_spike", magnitude=50.0, duration_ticks=1)
    thermal_telemetry.poll("rack-hot")
    thermal_telemetry.inject_anomaly("rack-cool", "temperature", "cooling_event", magnitude=-15.0, duration_ticks=1)
    thermal_telemetry.poll("rack-cool")

    host_to_rack = {"host-1": "rack-hot", "host-2": "rack-cool"}
    allowed = filter_consolidation_targets_by_real_headroom(host_to_rack, ["host-1", "host-2"], thermal_telemetry)

    assert "host-1" not in allowed
    assert "host-2" in allowed


# ---------------------------------------------------------------------------
# Dependency 3: IdleHunter -> CarbonClock (capacity state)
# ---------------------------------------------------------------------------


def test_compute_capacity_forecast_uses_real_idlehunter_utilization():
    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)
    idlehunter_telemetry.poll("host-1")

    forecast = compute_capacity_forecast(idlehunter_telemetry, {}, NOW.isoformat(), (NOW + timedelta(hours=1)).isoformat())

    real_cpu = idlehunter_telemetry.current("host-1")["cpu"]
    assert forecast.poweredOnHostCount == 1
    assert forecast.standbyHostCount == 0
    assert forecast.availableCpuCapacity == max(0.0, 100.0 - real_cpu)


def test_compute_capacity_forecast_excludes_real_standby_hosts():
    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)
    idlehunter_telemetry.register_host("host-2", seed=2)
    idlehunter_telemetry.poll("host-1")
    idlehunter_telemetry.poll("host-2")

    machine = DwellStateMachine("host-2", dwell_time_down_samples=1)
    machine.observe("idle-candidate")
    machine.consolidation_succeeded()
    assert machine.state == HostState.STANDBY

    forecast = compute_capacity_forecast(
        idlehunter_telemetry, {"host-2": machine}, NOW.isoformat(), (NOW + timedelta(hours=1)).isoformat()
    )

    assert forecast.poweredOnHostCount == 1
    assert forecast.standbyHostCount == 1


def test_schedule_job_with_real_capacity_proceeds_when_real_telemetry_has_room():
    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)
    idlehunter_telemetry.poll("host-1")  # low baseline cpu -- plenty of real headroom

    windows = [
        HourlyForecast(
            windowStart=NOW.isoformat(), windowEnd=(NOW + timedelta(hours=1)).isoformat(), carbonIntensity=50.0
        )
    ]
    pool = SchedulingPool(total_flexible_capacity=1000.0)

    decision = schedule_job_with_real_capacity(
        "job-1", 5.0, windows, pool, idlehunter_telemetry, {}, now=NOW, deadline=NOW + timedelta(hours=5)
    )

    assert decision.proceed is True


def test_schedule_job_with_real_capacity_reflects_real_scarcity():
    """If every real host is pegged near 100% cpu, the real capacity
    forecast should have too little room, and scheduling must fail --
    proving the scheduler actually consumed the real telemetry rather
    than a fixed stub."""
    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)
    idlehunter_telemetry.poll("host-1")
    idlehunter_telemetry.inject_anomaly("host-1", "cpu", "spike", magnitude=95.0, duration_ticks=1)
    idlehunter_telemetry.poll("host-1")

    windows = [
        HourlyForecast(
            windowStart=NOW.isoformat(), windowEnd=(NOW + timedelta(hours=1)).isoformat(), carbonIntensity=50.0
        )
    ]
    pool = SchedulingPool(total_flexible_capacity=1000.0)

    decision = schedule_job_with_real_capacity(
        "job-1", 50.0, windows, pool, idlehunter_telemetry, {}, now=NOW, deadline=NOW + timedelta(hours=5)
    )

    assert decision.proceed is False


# ---------------------------------------------------------------------------
# Dependency 4: CarbonClock -> IdleHunter (prewake subscription)
# ---------------------------------------------------------------------------


def test_prewake_subscriber_wakes_a_real_standby_host_when_the_real_scheduler_publishes():
    """Full round trip: the real scheduler publishes
    carbonclock.prewake.requested; the real PrewakeSubscriber, registered
    on the same bus, actually calls the standby host's real
    DwellStateMachine.request_wake() -- not a logged no-op."""
    bus = EventBus()

    machine = DwellStateMachine("host-1", dwell_time_down_samples=1)
    machine.observe("idle-candidate")
    machine.consolidation_succeeded()
    assert machine.state == HostState.STANDBY

    subscriber = PrewakeSubscriber({"host-1": machine}, bus=bus)
    subscriber.register()

    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)  # the standby host -- excluded from capacity by its dwell state, not its telemetry
    idlehunter_telemetry.register_host("host-2", seed=2)  # a second, powered-on host
    idlehunter_telemetry.poll("host-1")
    idlehunter_telemetry.poll("host-2")

    # Window starts an hour out, so there's real lead time for a prewake
    # (estimatedWakeLatencySeconds default is 180s).
    window_start = NOW + timedelta(hours=1)
    windows = [
        HourlyForecast(
            windowStart=window_start.isoformat(), windowEnd=(window_start + timedelta(hours=1)).isoformat(),
            carbonIntensity=50.0,
        )
    ]
    pool = SchedulingPool(total_flexible_capacity=1000.0)

    # host-2 alone can't cover this job's required capacity (max 100
    # headroom), but host-1 is standby with wake latency well within the
    # lead time -- the real scheduler should request a prewake, which the
    # real subscriber acts on.
    decision = schedule_job_with_real_capacity(
        "job-1", 150.0, windows, pool, idlehunter_telemetry, {"host-1": machine},
        now=NOW, deadline=NOW + timedelta(hours=5), bus=bus,
    )

    assert decision.prewakeRequested is True
    assert machine.state == HostState.WAKING  # the real state machine actually transitioned
    assert len(subscriber.actions) == 1
    assert subscriber.actions[0][0] == "host-1"


# ---------------------------------------------------------------------------
# Dependency 5: IdleHunter -> WaterWatch (per-rack workload signal)
# ---------------------------------------------------------------------------


def test_bucket_rack_load_uses_real_idlehunter_history():
    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)
    for _ in range(65):
        idlehunter_telemetry.poll("host-1")

    bucket = bucket_rack_load("rack-1", ["host-1"], idlehunter_telemetry)
    assert bucket in {"low", "medium", "high"}


def test_bucket_rack_load_reflects_a_real_idle_spike():
    """Forcing the real telemetry idle (very low cpu) should genuinely
    bucket the rack as low, not a stubbed answer."""
    idlehunter_telemetry = IdleHunterTelemetry()
    idlehunter_telemetry.register_host("host-1", seed=1)
    for _ in range(65):
        idlehunter_telemetry.poll("host-1")

    idlehunter_telemetry.inject_anomaly("host-1", "cpu", "idle_drop", magnitude=-30.0, duration_ticks=1)
    idlehunter_telemetry.poll("host-1")

    bucket = bucket_rack_load("rack-1", ["host-1"], idlehunter_telemetry)
    assert bucket == "low"


def test_bucket_rack_load_raises_for_a_rack_with_no_registered_hosts():
    idlehunter_telemetry = IdleHunterTelemetry()
    with pytest.raises(ValueError):
        bucket_rack_load("rack-empty", [], idlehunter_telemetry)
