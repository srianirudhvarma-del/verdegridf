def test_get_carbon_intensity_falls_back_to_mock_without_api_key(client, monkeypatch):
    monkeypatch.delenv("ELECTRICITYMAP_API_KEY", raising=False)
    monkeypatch.delenv("VITE_ELECTRICITY_API_KEY", raising=False)

    resp = client.get("/api/carbonclock/intensity")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "mock"
    assert body["carbonIntensity"] == 250
    assert body["zone"] == "IN-SO"


def test_get_job_queue_returns_three_seeded_jobs(client):
    resp = client.get("/api/carbonclock/jobs")
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) == 3
    ids = {job["id"] for job in jobs}
    assert ids == {"402", "156", "89"}


def test_defer_carbon_job_returns_requested_hours(client):
    resp = client.post("/api/carbonclock/jobs/402/defer", json={"hours": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "402"
    assert body["status"] == "deferred"
    assert body["deferredHours"] == 3
    assert "3 hours" in body["message"]


def test_defer_carbon_job_defaults_hours_to_zero(client):
    resp = client.post("/api/carbonclock/jobs/402/defer", json={})
    assert resp.status_code == 200
    assert resp.json()["deferredHours"] == 0


def test_run_carbon_job(client):
    resp = client.post("/api/carbonclock/jobs/89/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "89"
    assert body["status"] == "running"
