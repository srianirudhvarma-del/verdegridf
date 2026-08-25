from tests.conftest import make_snapshot


def test_get_thermal_snapshot_returns_64_cell_grid(client):
    resp = client.get("/api/thermaltrace/snapshot")
    assert resp.status_code == 200
    grid = resp.json()
    assert len(grid) == 64  # 8x8
    for field in ("id", "x", "y", "inlet_celsius", "outlet_celsius"):
        assert field in grid[0]


class TestPredictValidation:
    def test_rejects_zero_snapshots(self, client):
        resp = client.post("/api/thermaltrace/predict", json={"snapshots": []})
        assert resp.status_code == 400
        assert "At least 2 snapshots" in resp.json()["detail"]

    def test_rejects_single_snapshot(self, client):
        resp = client.post("/api/thermaltrace/predict", json={"snapshots": [make_snapshot()]})
        assert resp.status_code == 400
        assert "At least 2 snapshots" in resp.json()["detail"]

    def test_rejects_more_than_200_snapshots(self, client):
        snapshots = [make_snapshot() for _ in range(201)]
        resp = client.post("/api/thermaltrace/predict", json={"snapshots": snapshots})
        assert resp.status_code == 400
        assert "Too many snapshots" in resp.json()["detail"]

    def test_accepts_exactly_200_snapshots(self, client):
        snapshots = [make_snapshot() for _ in range(200)]
        resp = client.post("/api/thermaltrace/predict", json={"snapshots": snapshots})
        assert resp.status_code == 200

    def test_rejects_empty_cell_grid(self, client):
        """Regression test: an empty first snapshot used to silently return
        an empty prediction with confidence 0.5 instead of a clear error."""
        resp = client.post("/api/thermaltrace/predict", json={"snapshots": [[], []]})
        assert resp.status_code == 400
        assert "at least one cell" in resp.json()["detail"]


class TestPredictLogic:
    def test_flat_trend_produces_stable_prediction_near_last_value(self, client):
        # Two identical snapshots -> zero slope -> prediction == last value.
        snap = make_snapshot(inlet_base=25.0, outlet_base=30.0, num_cells=2)
        resp = client.post("/api/thermaltrace/predict", json={"snapshots": [snap, snap]})
        assert resp.status_code == 200
        body = resp.json()

        assert len(body["predicted_grid"]) == 2
        for cell in body["predicted_grid"]:
            assert abs(cell["inlet_celsius"] - 25.0) < 0.01 or abs(cell["inlet_celsius"] - 26.0) < 0.01

    def test_rising_trend_flags_hotspot(self, client):
        # Sharp upward trend should push predicted inlet above the 35C hotspot threshold.
        snap_a = make_snapshot(inlet_base=30.0, outlet_base=32.0, num_cells=1)
        snap_b = make_snapshot(inlet_base=40.0, outlet_base=42.0, num_cells=1)
        resp = client.post("/api/thermaltrace/predict", json={"snapshots": [snap_a, snap_b]})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["hotspots"]) == 1
        assert body["hotspots"][0]["severity"] in ("medium", "high")

    def test_confidence_is_between_0_and_1(self, client):
        snap_a = make_snapshot(num_cells=3)
        snap_b = make_snapshot(inlet_base=26.0, outlet_base=31.0, num_cells=3)
        resp = client.post("/api/thermaltrace/predict", json={"snapshots": [snap_a, snap_b]})
        assert resp.status_code == 200
        assert 0.0 <= resp.json()["confidence"] <= 1.0

    def test_mismatched_cell_counts_across_snapshots_does_not_crash(self, client):
        # Second snapshot has fewer cells than the first; positions beyond its
        # length should simply be skipped rather than raising an IndexError.
        snap_a = make_snapshot(num_cells=4)
        snap_b = make_snapshot(num_cells=2)
        resp = client.post("/api/thermaltrace/predict", json={"snapshots": [snap_a, snap_b]})
        assert resp.status_code == 200
        # Only the first 2 positions have >= 2 readings, so only 2 predicted cells.
        assert len(resp.json()["predicted_grid"]) == 2
