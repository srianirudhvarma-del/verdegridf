from tests.conftest import make_snapshot


def test_get_thermal_snapshot_returns_an_8x8_grid(client):
    """
    Phase 9: the snapshot is now a real 8x8 grid interpolated (SHOULD
    HAVE #23) from 5 real per-rack sensor readings, with each cell
    honestly flagged real vs interpolated -- not a flat list of 64 fake
    cells.
    """
    resp = client.get("/api/thermaltrace/snapshot")
    assert resp.status_code == 200
    body = resp.json()
    grid = body["grid"]
    assert len(grid) == 8
    assert all(len(row) == 8 for row in grid)
    for field in ("row", "col", "inlet_temp", "outlet_temp", "is_interpolated"):
        assert field in grid[0][0]
    # Exactly 5 real sensor readings; the rest must be flagged interpolated.
    real_cells = sum(1 for row in grid for cell in row if not cell["is_interpolated"])
    assert real_cells == 5


class TestActionApprovalQueue:
    """MUST HAVE #22, exposed via the API for the first time in Phase 9."""

    def test_pending_actions_are_seeded_and_real(self, client):
        resp = client.get("/api/thermaltrace/actions")
        assert resp.status_code == 200
        actions = resp.json()
        assert len(actions) >= 1
        for action in actions:
            assert action["status"] == "pending"

    def test_approve_transitions_a_real_action_to_approved(self, client):
        actions = client.get("/api/thermaltrace/actions").json()
        target = actions[0]["id"]

        resp = client.post(f"/api/thermaltrace/actions/{target}/approve", json={"operatorId": "op1"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        # No longer in the pending list.
        remaining_ids = {a["id"] for a in client.get("/api/thermaltrace/actions").json()}
        assert target not in remaining_ids

    def test_approve_unknown_action_returns_400(self, client):
        resp = client.post("/api/thermaltrace/actions/does-not-exist/approve", json={})
        assert resp.status_code == 400


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
            assert abs(cell["inlet_temp"] - 25.0) < 0.01 or abs(cell["inlet_temp"] - 26.0) < 0.01

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
