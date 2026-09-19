"""
Real telemetry ingestion: one sample per poll cycle from each laptop's
agent (../../agent/agent.py), stored as latest value + rolling history per
host. This is the only place that knows what an agent's HTTP payload
looks like -- everything downstream (threshold.py, hotspot.py) works on
plain dicts/lists, not on this module's types.
"""

from collections import deque
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

# The 4 resources the adaptive idle threshold watches, mapped onto the
# real fields a laptop agent reports. cpu/mem are direct OS percentages;
# diskIO/network are throughput the agent itself normalizes to 0-100
# against a configured max, so the classifier sees the same kind of
# bounded signal regardless of the machine's actual hardware.
RESOURCE_FIELDS: dict[str, str] = {
    "cpu": "cpuPercent",
    "mem": "memPercent",
    "diskIO": "diskIoPercent",
    "network": "networkPercent",
}

_EXTRA_HISTORY_FIELDS = ("cpuTempC",)


class TelemetrySample(BaseModel):
    hostId: str
    timestamp: str
    cpuPercent: float
    memPercent: float
    diskIoPercent: float
    networkPercent: float
    cpuFreqMhz: float
    cpuFreqMaxMhz: float
    cpuTempC: Optional[float] = None
    idleSeconds: float = 0.0
    batteryPercent: Optional[float] = None


class TelemetryRegistry:
    """Latest sample + rolling history per real host, keyed by hostId.
    Hosts aren't pre-registered -- a host becomes known the first time it
    posts a sample, since we don't fix machine ids in advance."""

    def __init__(self, *, history_len: int = 240) -> None:
        self._history_len = history_len
        self._latest: dict[str, TelemetrySample] = {}
        self._received_at: dict[str, datetime] = {}
        self._history: dict[str, dict[str, deque]] = {}

    def ingest(self, sample: TelemetrySample, *, received_at: Optional[datetime] = None) -> None:
        received_at = received_at or datetime.now(timezone.utc)
        self._latest[sample.hostId] = sample
        self._received_at[sample.hostId] = received_at
        host_history = self._history.setdefault(sample.hostId, {})
        for field_name in (*RESOURCE_FIELDS.values(), *_EXTRA_HISTORY_FIELDS):
            value = getattr(sample, field_name)
            if value is None:
                continue
            host_history.setdefault(field_name, deque(maxlen=self._history_len)).append(value)

    def known_hosts(self) -> list[str]:
        return list(self._latest.keys())

    def is_stale(self, host_id: str, now: datetime, *, max_age_seconds: float) -> bool:
        """No sample ever received, or the last one older than
        max_age_seconds, both count as stale: trust nothing until proven
        fresh (fail-safe-open)."""
        received = self._received_at.get(host_id)
        if received is None:
            return True
        return (now - received).total_seconds() > max_age_seconds

    def latest(self, host_id: str) -> Optional[TelemetrySample]:
        return self._latest.get(host_id)

    def current_resources(self, host_id: str) -> dict[str, float]:
        sample = self._latest[host_id]
        return {resource: getattr(sample, field_name) for resource, field_name in RESOURCE_FIELDS.items()}

    def history(self, host_id: str, resource: str, n: int) -> list[float]:
        return self.field_history(host_id, RESOURCE_FIELDS[resource], n)

    def field_history(self, host_id: str, field_name: str, n: int) -> list[float]:
        values = self._history.get(host_id, {}).get(field_name)
        if not values:
            return []
        return list(values)[-n:]
