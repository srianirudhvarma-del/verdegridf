"""
Commands the backend wants a specific laptop's agent to run. One pending
command per host at a time: an agent polls for its own commands, so
there's no benefit to queueing more than the latest actionable one, and
queueing would risk the agent later executing a stale sleep prompt whose
moment has already passed.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

CommandType = Literal["sleep_prompt", "fan_max_on", "fan_max_off"]


@dataclass
class Command:
    id: str
    hostId: str
    type: CommandType
    payload: dict
    issuedAt: str


class CommandQueue:
    def __init__(self) -> None:
        self._pending: dict[str, Command] = {}
        self._by_id: dict[str, Command] = {}
        self._acks: dict[str, dict] = {}

    def enqueue(self, host_id: str, type_: CommandType, payload: dict) -> Command:
        command = Command(
            id=str(uuid4()),
            hostId=host_id,
            type=type_,
            payload=payload,
            issuedAt=datetime.now(timezone.utc).isoformat(),
        )
        self._pending[host_id] = command
        self._by_id[command.id] = command
        return command

    def poll(self, host_id: str) -> Optional[Command]:
        """Pops the pending command for a host -- an agent that receives
        one is expected to act on it (or ack a decline), not see it again."""
        return self._pending.pop(host_id, None)

    def ack(self, command_id: str, result: str, detail: str = "") -> dict:
        command = self._by_id.get(command_id)
        if command is None:
            raise KeyError(f"unknown command: {command_id!r}")
        record = {
            "commandId": command_id,
            "hostId": command.hostId,
            "type": command.type,
            "result": result,
            "detail": detail,
        }
        self._acks[command_id] = record
        return record

    def last_ack_for_host(self, host_id: str) -> Optional[dict]:
        for record in reversed(list(self._acks.values())):
            if record["hostId"] == host_id:
                return record
        return None
