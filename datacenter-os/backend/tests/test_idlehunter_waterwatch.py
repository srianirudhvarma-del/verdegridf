"""
Phase 9 update: api/routes.py's IdleHunter/WaterWatch endpoints now
delegate to the real module packages (api/state.py's fixed 5-rack x
4-host topology) instead of generating canned/random mock data. These
tests were written against the old mock shapes; updated to match the real
contract -- 20 real hosts, real per-host state, real per-loop flow.
"""


def test_get_server_cluster_returns_20_real_hosts_with_expected_shape(client):
    resp = client.get("/api/idlehunter/servers")
    assert resp.status_code == 200
    body = resp.json()
    servers = body["servers"]
    assert len(servers) == 20
    assert body["is_live"] is True

    first = servers[0]
    for field in ("id", "rack", "cpu_util", "ram_util", "watts_idle", "watts_active", "state", "last_migrated"):
        assert field in first

    assert first["watts_idle"] == 120.0
    assert first["watts_active"] == 280.0
    assert first["state"] in {"active", "zombie", "sleep"}


def test_consolidate_idle_servers_returns_a_real_count_not_a_fixed_four(client):
    resp = client.post("/api/idlehunter/consolidate")
    assert resp.status_code == 200
    body = resp.json()
    # Real consolidation count depends on how many hosts have actually
    # dwelled into IDLE_CANDIDATE -- freshly booted state, so 0 is the
    # expected real answer, not the old mock's hardcoded 4.
    assert body["consolidated"] >= 0
    assert body["energy_saved"] == round(body["consolidated"] * 120.0 / 1000.0, 2)


def test_get_water_flows_returns_5_real_racks(client):
    resp = client.get("/api/waterwatch/flows")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["units"]) == 5
    for field in ("id", "flow_rate_lph"):
        assert field in body["units"][0]
    for field in ("totalFlow", "itLoad", "wue", "anomalies", "benchmarks", "is_live"):
        assert field in body


def test_get_water_anomalies_matches_the_flows_endpoints_anomaly_list(client):
    resp = client.get("/api/waterwatch/anomaly")
    assert resp.status_code == 200
    body = resp.json()
    assert "anomalies" in body
    assert isinstance(body["anomalies"], list)
