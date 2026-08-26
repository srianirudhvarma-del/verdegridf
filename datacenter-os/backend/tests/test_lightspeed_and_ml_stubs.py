from tests.conftest import make_snapshot


def test_get_network_traffic(client):
    resp = client.get("/api/lightspeed/network")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["nodes"]) == 5
    assert len(body["links"]) == 8


def test_optimize_network(client):
    """
    Phase 9: adjustedLinks now comes from the real CongestionTracker
    (MUST HAVE #15's sustained-dwell confirmation), not a fixed pair --
    freshly polled telemetry has no confirmed-congested links yet, so 0
    is the expected real answer.
    """
    resp = client.post("/api/lightspeed/optimize")
    assert resp.status_code == 200
    body = resp.json()
    assert body["optimized"] is True
    assert isinstance(body["adjustedLinks"], list)


def test_ml_thermaltrace_predict_is_a_labeled_stub(client):
    """This endpoint is a known stub pending a real LSTM model — it should
    always return an empty, zero-confidence prediction rather than pretending
    to have real output."""
    resp = client.post(
        "/api/ml/thermaltrace/predict",
        json={"snapshots": [make_snapshot(), make_snapshot()]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["predicted_grid"] == []
    assert body["hotspots"] == []
    assert body["confidence"] == 0.0


def test_ml_noisemesh_classify_is_excluded(client):
    resp = client.post(
        "/api/ml/noisemesh/classify",
        json={"features": {"mfcc": [0.1, 0.2], "spectral_centroid": 1.0, "rms_energy": 0.5}},
    )
    assert resp.status_code == 501
    assert "not part of this implementation" in resp.json()["detail"]
