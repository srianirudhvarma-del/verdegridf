"""
Acceptance tests for shared/real_agent.py -- the real-hardware telemetry
adapter and hotspot predictor.

Two documented behaviors under test, matching this codebase's "prove the
actual acceptance criterion" convention:
1. A host with no (or stale) sample is never treated as having real data
   -- RealAgentRegistry.is_stale() is the fail-safe-open gate.
2. predict_hotspot() is a real prediction (extrapolated trend), not a
   threshold on the current reading -- and it discounts a rising trend as
   "critical" specifically when the clock speed shows the chip isn't
   actually working hard, to avoid flagging sensor noise on an idle chip.
"""

from datetime import datetime, timedelta, timezone

import pytest

from shared.real_agent import RealAgentRegistry, RealAgentSample, predict_hotspot


def make_sample(host_id="laptop-1", **overrides) -> RealAgentSample:
    defaults = dict(
        hostId=host_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        cpuPercent=10.0,
        memPercent=20.0,
        diskIoPercent=5.0,
        networkPercent=5.0,
        cpuFreqMhz=2000.0,
        cpuFreqMaxMhz=4500.0,
        cpuTempC=50.0,
        idleSeconds=0.0,
    )
    defaults.update(overrides)
    return RealAgentSample(**defaults)


class TestRegistryStaleness:
    def test_unknown_host_is_stale(self):
        registry = RealAgentRegistry()
        assert registry.is_stale("nope", datetime.now(timezone.utc), max_age_seconds=20) is True

    def test_fresh_sample_is_not_stale(self):
        registry = RealAgentRegistry()
        now = datetime.now(timezone.utc)
        registry.ingest(make_sample(), received_at=now)
        assert registry.is_stale("laptop-1", now + timedelta(seconds=5), max_age_seconds=20) is False

    def test_old_sample_becomes_stale(self):
        registry = RealAgentRegistry()
        now = datetime.now(timezone.utc)
        registry.ingest(make_sample(), received_at=now)
        assert registry.is_stale("laptop-1", now + timedelta(seconds=30), max_age_seconds=20) is True

    def test_current_resources_maps_real_fields_to_mad_resources(self):
        registry = RealAgentRegistry()
        registry.ingest(make_sample(cpuPercent=42.0, memPercent=33.0, diskIoPercent=7.0, networkPercent=9.0))
        current = registry.current_resources("laptop-1")
        assert current == {"cpu": 42.0, "mem": 33.0, "diskIO": 7.0, "network": 9.0}

    def test_history_grows_and_is_capped(self):
        registry = RealAgentRegistry(history_len=5)
        for i in range(10):
            registry.ingest(make_sample(cpuPercent=float(i)))
        history = registry.history("laptop-1", "cpu", 100)
        assert history == [5.0, 6.0, 7.0, 8.0, 9.0]


class TestPredictHotspot:
    def test_flat_cool_temps_are_ok(self):
        prediction = predict_hotspot(
            "laptop-1", [45.0] * 10,
            freq_current=1800.0, freq_max=4500.0,
            horizon_seconds=60.0, sample_interval_seconds=5.0,
        )
        assert prediction.riskLevel == "ok"

    def test_already_over_critical_is_critical_even_at_low_clock(self):
        """Safety takes precedence over the noise-guard: an already-hot
        chip is real regardless of what it's doing right now."""
        prediction = predict_hotspot(
            "laptop-1", [80.0, 90.0, 95.0],
            freq_current=900.0, freq_max=4500.0,
            horizon_seconds=60.0, sample_interval_seconds=5.0,
        )
        assert prediction.riskLevel == "critical"

    def test_rising_trend_near_max_clock_projects_critical(self):
        # +2C every 5s (0.4C/s) from a 60C starting point, current=78C ->
        # projected 78 + 0.4*60 = 102C, well past the 92C default limit.
        temps = [60.0 + i * 2 for i in range(10)]
        prediction = predict_hotspot(
            "laptop-1", temps,
            freq_current=4300.0, freq_max=4500.0,
            horizon_seconds=60.0, sample_interval_seconds=5.0,
        )
        assert prediction.projectedTempC > 92.0
        assert prediction.riskLevel == "critical"

    def test_same_rising_trend_at_low_clock_is_only_watch_not_critical(self):
        """The exact same temperature trend, but the CPU isn't actually
        pinned -- the projection is discounted from "critical" to "watch"
        since a real sustained hotspot wouldn't come with a low clock."""
        temps = [60.0 + i * 2 for i in range(10)]
        prediction = predict_hotspot(
            "laptop-1", temps,
            freq_current=1200.0, freq_max=4500.0,
            horizon_seconds=60.0, sample_interval_seconds=5.0,
        )
        assert prediction.riskLevel == "watch"

    def test_close_to_critical_right_now_is_watch(self):
        prediction = predict_hotspot(
            "laptop-1", [89.0] * 5,
            freq_current=2000.0, freq_max=4500.0,
            horizon_seconds=60.0, sample_interval_seconds=5.0,
        )
        assert prediction.riskLevel == "watch"

    def test_empty_history_rejected(self):
        with pytest.raises(ValueError):
            predict_hotspot(
                "laptop-1", [],
                freq_current=2000.0, freq_max=4500.0,
                horizon_seconds=60.0, sample_interval_seconds=5.0,
            )
