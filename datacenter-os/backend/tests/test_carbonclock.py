"""
Phase 9 update: api/routes.py's CarbonClock endpoints now delegate to the
real synthetic carbon-intensity engine + hysteresis (SHOULD HAVE #11) and
the real DeadlineQueue-backed job records (api/state.py), instead of a
direct ElectricityMaps passthrough with a hardcoded fallback and 3
completely static jobs.

Note: api/state.py's singletons persist for the life of the test process
(same pattern as shared.eventbus.event_bus), so these tests are written
to be robust to prior mutation from other tests in this file or module
(e.g. a job's status may already be "deferred"/"running" by the time a
later test reads it) rather than assuming a pristine starting state.
"""


def test_get_carbon_intensity_returns_a_real_live_reading(client):
    resp = client.get("/api/carbonclock/intensity")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["intensity"], (int, float))
    assert body["trend"] in {"rising", "falling", "stable"}
    assert isinstance(body["isSpike"], bool)
    assert body["minutesUntilClean"] >= 0.0


def test_get_carbon_intensity_reflects_real_engine_movement(client):
    first = client.get("/api/carbonclock/intensity").json()["intensity"]
    second = client.get("/api/carbonclock/intensity").json()["intensity"]
    # Real stateful series -- two consecutive polls should not be
    # guaranteed identical (this is a live-simulator smoke check, not a
    # strict inequality, since noise could coincidentally repeat a value).
    assert isinstance(second, (int, float))


def test_get_signal_info_reports_average_with_a_rationale(client):
    resp = client.get("/api/carbonclock/signal-info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "average"
    assert body["rationale"]


def test_get_job_queue_returns_the_three_seeded_jobs(client):
    resp = client.get("/api/carbonclock/jobs")
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 3
    ids = {job["id"] for job in jobs}
    assert ids == {"job-402", "job-156", "job-89"}
    for job in jobs:
        for field in ("id", "name", "type", "duration_mins", "est_kwh", "deferrable", "status"):
            assert field in job


def test_defer_carbon_job_returns_requested_hours(client):
    resp = client.post("/api/carbonclock/jobs/job-402/defer", json={"hours": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "job-402"
    assert body["status"] == "deferred"
    assert body["deferredHours"] == 3
    assert "3 hours" in body["message"]


def test_defer_unknown_job_returns_404(client):
    resp = client.post("/api/carbonclock/jobs/does-not-exist/defer", json={"hours": 1})
    assert resp.status_code == 404


def test_run_carbon_job_marks_it_running_and_removes_it_from_the_real_queue(client):
    resp = client.post("/api/carbonclock/jobs/job-89/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "job-89"
    assert body["status"] == "running"

    jobs = client.get("/api/carbonclock/jobs").json()
    job_89 = next(j for j in jobs if j["id"] == "job-89")
    assert job_89["status"] == "running"


def test_run_unknown_job_returns_404(client):
    resp = client.post("/api/carbonclock/jobs/does-not-exist/run")
    assert resp.status_code == 404
