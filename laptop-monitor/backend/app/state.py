"""Process-wide singletons -- one registry/queue/orchestrator per running
backend process, shared by every request and by the background tick loop."""

from app.actions import ActionQueue
from app.commands import CommandQueue
from app.orchestrator import Orchestrator
from app.telemetry import TelemetryRegistry

telemetry_registry = TelemetryRegistry()
command_queue = CommandQueue()
action_queue = ActionQueue()
orchestrator = Orchestrator()

STALE_SECONDS = 20.0
