from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import app.state as state
from app.telemetry import TelemetrySample

router = APIRouter(prefix="/api", tags=["laptop-monitor"])


class CommandAckRequest(BaseModel):
    result: str  # "executed" | "declined" | "failed"
    detail: str = ""


class ActionDecisionRequest(BaseModel):
    operatorId: str = "operator"


@router.get("/status")
async def status():
    return {"status": "operational", "knownHosts": state.telemetry_registry.known_hosts()}


@router.post("/telemetry")
async def ingest_telemetry(sample: TelemetrySample):
    """A laptop's agent posts one sample per poll cycle here. Hosts
    self-register on first ingest -- there's no fixed machine list."""
    state.telemetry_registry.ingest(sample)
    return {"ok": True, "knownHosts": state.telemetry_registry.known_hosts()}


@router.get("/hosts")
async def list_hosts():
    now = datetime.now(timezone.utc)
    hosts = []
    for host_id in state.telemetry_registry.known_hosts():
        sample = state.telemetry_registry.latest(host_id)
        hosts.append(
            {
                "hostId": host_id,
                "lastSample": sample.model_dump() if sample else None,
                "isIdle": state.orchestrator.is_idle(host_id),
                "stale": state.telemetry_registry.is_stale(host_id, now, max_age_seconds=state.STALE_SECONDS),
                "lastAck": state.command_queue.last_ack_for_host(host_id),
            }
        )
    return hosts


@router.get("/commands/{host_id}")
async def poll_command(host_id: str):
    """The agent polls this every cycle; a command, once returned, is
    removed from the queue."""
    command = state.command_queue.poll(host_id)
    if command is None:
        return {"type": "none"}
    return {"id": command.id, "type": command.type, "payload": command.payload, "issuedAt": command.issuedAt}


@router.post("/commands/{command_id}/ack")
async def ack_command(command_id: str, request: CommandAckRequest):
    try:
        return state.command_queue.ack(command_id, request.result, request.detail)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/actions")
async def get_pending_actions():
    """The supervised fan-speed approval queue."""
    return [r.model_dump() for r in state.action_queue.pending()]


@router.post("/actions/{action_id}/approve")
async def approve_action(action_id: str, request: ActionDecisionRequest):
    try:
        rec = state.action_queue.approve(action_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # The approval this endpoint already required IS the human sign-off:
    # queue the real command now; the laptop's own agent executes it and
    # acks back via /commands/{id}/ack.
    state.command_queue.enqueue(rec.hostId, "fan_max_on", {"recommendationId": rec.id})
    state.orchestrator.mark_fan_executed(rec.hostId)
    return rec.model_dump()


@router.post("/actions/{action_id}/reject")
async def reject_action(action_id: str, request: ActionDecisionRequest):
    try:
        rec = state.action_queue.reject(action_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return rec.model_dump()
