from datetime import datetime, timedelta, timezone

import httpx

from app.gridsync import CarbonSignal, DeferrableJob, fetch_current_carbon_intensity


def make_signal(index="moderate") -> CarbonSignal:
    return CarbonSignal(intensityGCo2PerKwh=150.0, index=index, fetchedAt=datetime.now(timezone.utc).isoformat())


class TestDeferrableJobDecide:
    def test_waits_when_grid_is_dirty_and_not_overdue(self):
        now = datetime.now(timezone.utc)
        job = DeferrableJob(id="j1", name="Backup", max_wait=timedelta(minutes=30), submitted_at=now)
        status = job.decide(now + timedelta(minutes=5), make_signal("high"))
        assert status == "waiting_for_clean_grid"

    def test_runs_when_grid_turns_clean(self):
        now = datetime.now(timezone.utc)
        job = DeferrableJob(id="j1", name="Backup", max_wait=timedelta(minutes=30), submitted_at=now)
        status = job.decide(now + timedelta(minutes=5), make_signal("very low"))
        assert status == "running"
        assert job.decided_at is not None

    def test_force_runs_at_deadline_despite_dirty_grid(self):
        """Mirrors VerdeGrid's own GridSync acceptance test: a hard
        deadline overrides a still-dirty grid."""
        now = datetime.now(timezone.utc)
        job = DeferrableJob(id="j1", name="Backup", max_wait=timedelta(minutes=30), submitted_at=now)
        # Repeatedly attempted while dirty -- blocked every time.
        for minutes in (5, 10, 20, 29):
            assert job.decide(now + timedelta(minutes=minutes), make_signal("very high")) == "waiting_for_clean_grid"
        # At/after the deadline, force-runs regardless.
        status = job.decide(now + timedelta(minutes=30), make_signal("very high"))
        assert status == "force_run_deadline"

    def test_unknown_signal_never_triggers_a_run_but_deadline_still_does(self):
        now = datetime.now(timezone.utc)
        job = DeferrableJob(id="j1", name="Backup", max_wait=timedelta(minutes=10), submitted_at=now)
        assert job.decide(now + timedelta(minutes=5), make_signal("unknown")) == "waiting_for_clean_grid"
        assert job.decide(now + timedelta(minutes=10), make_signal("unknown")) == "force_run_deadline"

    def test_decision_is_sticky_once_running(self):
        now = datetime.now(timezone.utc)
        job = DeferrableJob(id="j1", name="Backup", max_wait=timedelta(minutes=30), submitted_at=now)
        job.decide(now + timedelta(minutes=1), make_signal("very low"))
        assert job.status == "running"
        # Grid turning dirty again afterward must not un-schedule it.
        status = job.decide(now + timedelta(minutes=2), make_signal("very high"))
        assert status == "running"


class TestFetchCarbonIntensity:
    def test_successful_response_is_parsed(self):
        def handler(request):
            return httpx.Response(200, json={"data": [{"intensity": {"forecast": 200, "actual": 180, "index": "moderate"}}]})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        signal = fetch_current_carbon_intensity(client)
        assert signal.index == "moderate"
        assert signal.intensityGCo2PerKwh == 180

    def test_failed_request_returns_unknown_not_a_crash(self):
        def handler(request):
            return httpx.Response(500)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        signal = fetch_current_carbon_intensity(client)
        assert signal.index == "unknown"
        assert signal.intensityGCo2PerKwh is None

    def test_network_error_returns_unknown_not_a_crash(self):
        def handler(request):
            raise httpx.ConnectError("no network", request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        signal = fetch_current_carbon_intensity(client)
        assert signal.index == "unknown"
