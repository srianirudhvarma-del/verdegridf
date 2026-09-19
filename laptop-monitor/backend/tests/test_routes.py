import app.state as state

HOST = "route-test-laptop"


def make_payload(**overrides):
    payload = dict(
        hostId=HOST, timestamp="2026-01-01T00:00:00+00:00",
        cpuPercent=12.0, memPercent=22.0, diskIoPercent=3.0, networkPercent=4.0,
        cpuFreqMhz=2100.0, cpuFreqMaxMhz=4800.0, cpuTempC=55.0, idleSeconds=0.0,
    )
    payload.update(overrides)
    return payload


def test_ingest_then_host_is_known(client):
    resp = client.post("/api/telemetry", json=make_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert HOST in body["knownHosts"]


def test_no_command_returns_type_none(client):
    client.post("/api/telemetry", json=make_payload())
    resp = client.get(f"/api/commands/{HOST}")
    assert resp.status_code == 200
    assert resp.json() == {"type": "none"}


def test_command_round_trip_and_ack(client):
    client.post("/api/telemetry", json=make_payload())
    command = state.command_queue.enqueue(HOST, "sleep_prompt", {"idleMinutes": 15.0})

    resp = client.get(f"/api/commands/{HOST}")
    body = resp.json()
    assert body["id"] == command.id
    assert body["type"] == "sleep_prompt"
    assert client.get(f"/api/commands/{HOST}").json() == {"type": "none"}

    ack_resp = client.post(f"/api/commands/{command.id}/ack", json={"result": "declined"})
    assert ack_resp.status_code == 200
    assert ack_resp.json()["result"] == "declined"


def test_ack_unknown_command_404s(client):
    resp = client.post("/api/commands/does-not-exist/ack", json={"result": "executed"})
    assert resp.status_code == 404


def test_list_hosts_reflects_ingested_sample(client):
    client.post("/api/telemetry", json=make_payload(cpuPercent=77.0))
    resp = client.get("/api/hosts")
    entries = {h["hostId"]: h for h in resp.json()}
    assert HOST in entries
    assert entries[HOST]["lastSample"]["cpuPercent"] == 77.0
    assert entries[HOST]["stale"] is False


def test_approving_fan_recommendation_queues_fan_max_on(client):
    client.post("/api/telemetry", json=make_payload())

    from app.actions import ActionRecommendation

    rec_id = f"route-test-fan-{HOST}"
    state.action_queue.submit(
        ActionRecommendation(id=rec_id, type="raise_fan_speed", hostId=HOST, predictedBenefit="test")
    )

    resp = client.post(f"/api/actions/{rec_id}/approve", json={"operatorId": "tester"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    command_resp = client.get(f"/api/commands/{HOST}")
    body = command_resp.json()
    assert body["type"] == "fan_max_on"
    assert body["payload"]["recommendationId"] == rec_id


def test_reject_action(client):
    from app.actions import ActionRecommendation

    rec_id = "route-test-reject"
    state.action_queue.submit(
        ActionRecommendation(id=rec_id, type="raise_fan_speed", hostId=HOST, predictedBenefit="test")
    )
    resp = client.post(f"/api/actions/{rec_id}/reject", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert client.get(f"/api/commands/{HOST}").json() == {"type": "none"}
