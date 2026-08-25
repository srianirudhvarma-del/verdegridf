def test_get_server_cluster_returns_100_servers_with_expected_shape(client):
    resp = client.get("/api/idlehunter/servers")
    assert resp.status_code == 200
    servers = resp.json()
    assert len(servers) == 100

    first = servers[0]
    for field in ("id", "rack", "cpu_util", "ram_util", "watts_idle", "watts_active", "last_migrated"):
        assert field in first

    assert first["watts_idle"] == 120.0
    assert first["watts_active"] == 280.0


def test_consolidate_idle_servers(client):
    resp = client.post("/api/idlehunter/consolidate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["consolidated"] == 4
    assert body["energy_saved"] == 75.0


def test_get_water_flows_returns_8_racks(client):
    resp = client.get("/api/waterwatch/flows")
    assert resp.status_code == 200
    flows = resp.json()
    assert len(flows) == 8
    for field in ("rack_id", "cooling_unit", "flow_rate_l_hr", "it_load_kw", "timestamp"):
        assert field in flows[0]


def test_get_water_anomalies(client):
    resp = client.get("/api/waterwatch/anomaly")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["anomalies"]) == 2
    assert {"rack_id", "type", "severity"} <= body["anomalies"][0].keys()
