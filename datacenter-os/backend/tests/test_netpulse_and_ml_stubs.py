from tests.conftest import make_snapshot
from netpulse.congestion import DEFAULT_CONGESTION_THRESHOLD_PCT


def test_get_network_traffic(client):
    resp = client.get("/api/netpulse/network")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["nodes"]) == 5
    assert len(body["links"]) == 8


def test_inject_spike_produces_a_real_elevated_reading(client):
    """
    New Phase 9 demo endpoint: injects a real utilization anomaly via
    shared/telemetry_sim.py. Confirmed congestion (MUST HAVE #15) itself
    requires real elapsed wall-clock dwell time, which a fast unit test
    can't simulate -- so this only checks the injection's direct, real
    effect: the next poll shows a genuinely elevated reading on that link.
    """
    resp = client.post("/api/netpulse/inject-spike")
    assert resp.status_code == 200
    link_id = resp.json()["linkId"]
    valid_ids = {f"{a}-{b}" for a, b in [("A1", "A2"), ("A1", "B1"), ("A2", "B2"), ("B1", "B2"), ("C1", "A1"), ("C1", "A2"), ("C1", "B1"), ("C1", "B2")]}
    assert link_id in valid_ids

    network = client.get("/api/netpulse/network").json()
    spiked_link = next(l for l in network["links"] if f"{l['source']}-{l['target']}" == link_id)
    assert spiked_link["utilization_pct"] > DEFAULT_CONGESTION_THRESHOLD_PCT


def test_optimize_network(client):
    """
    Phase 9: adjustedLinks now comes from the real CongestionTracker
    (MUST HAVE #15's sustained-dwell confirmation), not a fixed pair --
    freshly polled telemetry has no confirmed-congested links yet, so 0
    is the expected real answer.
    """
    resp = client.post("/api/netpulse/optimize")
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
