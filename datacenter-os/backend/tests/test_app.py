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
