"""Process-wide singletons -- one registry/queue/orchestrator per running
backend process, shared by every request and by the background tick loop."""

import httpx

from app.actions import ActionQueue
from app.commands import CommandQueue
from app.gridsync import GridSyncScheduler
from app.orchestrator import Orchestrator
from app.telemetry import TelemetryRegistry

telemetry_registry = TelemetryRegistry()
command_queue = CommandQueue()
action_queue = ActionQueue()
orchestrator = Orchestrator()
gridsync_scheduler = GridSyncScheduler()
# One reusable client for GridSync's real (infrequent) HTTP calls to the
# carbon-intensity API -- created once here rather than per-tick.
http_client = httpx.Client()

STALE_SECONDS = 20.0
