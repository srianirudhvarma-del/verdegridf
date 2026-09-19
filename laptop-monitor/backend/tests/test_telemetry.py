from datetime import datetime, timedelta, timezone

from app.telemetry import TelemetryRegistry, TelemetrySample


def make_sample(host_id="laptop-1", **overrides) -> TelemetrySample:
    defaults = dict(
        hostId=host_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        cpuPercent=10.0, memPercent=20.0, diskIoPercent=5.0, networkPercent=5.0,
        cpuFreqMhz=2000.0, cpuFreqMaxMhz=4500.0, cpuTempC=50.0, idleSeconds=0.0,
    )
    defaults.update(overrides)
    return TelemetrySample(**defaults)


def test_unknown_host_is_stale():
    registry = TelemetryRegistry()
    assert registry.is_stale("nope", datetime.now(timezone.utc), max_age_seconds=20) is True


def test_fresh_sample_is_not_stale():
    registry = TelemetryRegistry()
    now = datetime.now(timezone.utc)
    registry.ingest(make_sample(), received_at=now)
    assert registry.is_stale("laptop-1", now + timedelta(seconds=5), max_age_seconds=20) is False


def test_old_sample_becomes_stale():
    registry = TelemetryRegistry()
    now = datetime.now(timezone.utc)
    registry.ingest(make_sample(), received_at=now)
    assert registry.is_stale("laptop-1", now + timedelta(seconds=30), max_age_seconds=20) is True


def test_current_resources_maps_real_fields():
    registry = TelemetryRegistry()
    registry.ingest(make_sample(cpuPercent=42.0, memPercent=33.0, diskIoPercent=7.0, networkPercent=9.0))
    assert registry.current_resources("laptop-1") == {"cpu": 42.0, "mem": 33.0, "diskIO": 7.0, "network": 9.0}


def test_history_grows_and_is_capped():
    registry = TelemetryRegistry(history_len=5)
    for i in range(10):
        registry.ingest(make_sample(cpuPercent=float(i)))
    assert registry.history("laptop-1", "cpu", 100) == [5.0, 6.0, 7.0, 8.0, 9.0]
