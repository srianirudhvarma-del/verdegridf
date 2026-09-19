"""
Route-level tests for the real-hardware endpoints in api/routes.py:
POST /real/telemetry, GET /real/commands/{host}, POST
/real/commands/{id}/ack, GET /real/hosts, and the approve_action hook that
turns an approved real adjust_fan_speed recommendation into a real
fan_max_on command.

Uses the shared `client` fixture (tests/conftest.py), which runs against
the same process-wide api.state singletons production code uses -- exactly
like the existing tests/test_thermos.py does for the simulated action
queue. A distinct host id (not one of the simulated rackN-srvN ids) keeps
this test isolated from the pre-seeded rec-1/rec-2 demo recommendations.
"""

import api.state as state


HOST = "route-test-victus-15"


def make_payload(**overrides):
    payload = dict(
        hostId=HOST,
        timestamp="2026-01-01T00:00:00+00:00",
        cpuPercent=12.0,
        memPercent=22.0,
        diskIoPercent=3.0,
        networkPercent=4.0,
        cpuFreqMhz=2100.0,
        cpuFreqMaxMhz=4800.0,
        cpuTempC=55.0,
        idleSeconds=0.0,
    )
    payload.update(overrides)
    return payload


def test_ingest_then_host_is_known(client):
    resp = client.post("/api/real/telemetry", json=make_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert HOST in body["knownHosts"]


def test_no_command_returns_type_none(client):
    client.post("/api/real/telemetry", json=make_payload())
    resp = client.get(f"/api/real/commands/{HOST}")
    assert resp.status_code == 200
    assert resp.json() == {"type": "none"}


def test_command_round_trip_and_ack(client):
    client.post("/api/real/telemetry", json=make_payload())
    command = state.real_command_queue.enqueue(HOST, "sleep_prompt", {"idleMinutes": 15.0})

    resp = client.get(f"/api/real/commands/{HOST}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == command.id
    assert body["type"] == "sleep_prompt"

    # Polled once -> gone.
    assert client.get(f"/api/real/commands/{HOST}").json() == {"type": "none"}

    ack_resp = client.post(f"/api/real/commands/{command.id}/ack", json={"result": "declined"})
    assert ack_resp.status_code == 200
    assert ack_resp.json()["result"] == "declined"


def test_ack_unknown_command_404s(client):
    resp = client.post("/api/real/commands/does-not-exist/ack", json={"result": "executed"})
    assert resp.status_code == 404


def test_list_real_hosts_reflects_ingested_sample(client):
    client.post("/api/real/telemetry", json=make_payload(cpuPercent=77.0))
    resp = client.get("/api/real/hosts")
    assert resp.status_code == 200
    entries = {h["hostId"]: h for h in resp.json()}
    assert HOST in entries
    assert entries[HOST]["lastSample"]["cpuPercent"] == 77.0
    assert entries[HOST]["stale"] is False


def test_approving_real_host_fan_recommendation_queues_fan_max_on(client):
    client.post("/api/real/telemetry", json=make_payload())

    from thermos.control import ActionRecommendation

    rec_id = f"route-test-fan-{HOST}"
    state.action_recommendation_queue.submit(
        ActionRecommendation(
            id=rec_id, type="adjust_fan_speed", rackId=HOST, magnitude=100.0,
            predictedBenefit="test",
        )
    )

    resp = client.post(f"/api/thermos/actions/{rec_id}/approve", json={"operatorId": "tester"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    command_resp = client.get(f"/api/real/commands/{HOST}")
    body = command_resp.json()
    assert body["type"] == "fan_max_on"
    assert body["payload"]["recommendationId"] == rec_id


def test_approving_simulated_rack_fan_recommendation_queues_no_real_command(client):
    """rec-2 (seeded in api/state.py) targets rack4, a simulated rack --
    approving it must never touch the real command queue."""
    resp = client.get(f"/api/real/commands/rack4")
    assert resp.json() == {"type": "none"}
    # rec-2 may already be approved by an earlier test in this session;
    # only assert the invariant that matters: rack4 never gets a real command.
    client.post("/api/thermos/actions/rec-2/approve", json={"operatorId": "tester"})
    assert client.get("/api/real/commands/rack4").json() == {"type": "none"}
