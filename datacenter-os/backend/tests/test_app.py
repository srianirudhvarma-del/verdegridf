def test_lifespan_starts_and_stops_the_scheduler_driver_loop_without_crashing():
    """
    Phase 8c: the app's lifespan starts an async loop that calls
    shared.scheduler_driver.tick() on a real interval. This doesn't wait
    for real wall-clock ticks -- entering/exiting the TestClient context
    manager triggers FastAPI's startup/shutdown events, which is enough to
    prove the loop starts (and gets a chance to run its first tick, since
    the loop ticks immediately before its first sleep) and shuts down
    cleanly, with no unhandled exception either way.
    """
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
    # No exception escaping the `with` block is the pass condition -- both
    # lifespan startup and the cancelled-task shutdown completed cleanly.


def test_root_status(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "DatacenterOS API is running"


def test_api_status(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "operational"
    assert "idlehunter" in body["modules"]
    assert "noisemesh" in body["modules"]


def test_cors_never_combines_wildcard_origin_with_credentials():
    """
    Regression test: allow_origins=['*'] + allow_credentials=True is both a
    security misconfiguration and rejected by browsers outright. Whatever
    origins are configured, credentials must never be on alongside '*'.
    """
    import main

    cors_kwargs = None
    for m in main.app.user_middleware:
        if "CORSMiddleware" in str(m.cls):
            cors_kwargs = m.kwargs
    assert cors_kwargs is not None, "CORSMiddleware should be configured"

    if cors_kwargs.get("allow_origins") == ["*"]:
        assert cors_kwargs.get("allow_credentials") is False
    else:
        # Current default: an explicit allow-list, no wildcard.
        assert "*" not in cors_kwargs.get("allow_origins", [])
