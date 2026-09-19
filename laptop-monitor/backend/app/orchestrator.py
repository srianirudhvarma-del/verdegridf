"""
Ties everything together on each tick: real telemetry -> MAD
classification -> idle dwell tracking -> sleep-prompt commands, and CPU
temp/clock -> hotspot prediction -> supervised fan-speed recommendations.

Fail-safe-open: a host with no fresh sample this tick (TelemetryRegistry
is_stale) is skipped entirely -- never classified idle from missing data,
never sent a stale command.
"""

from datetime import datetime
from typing import Optional

from app.actions import ActionQueue, ActionRecommendation
from app.commands import CommandQueue
from app.coolsense import CoolingAssessment, assess_cooling
from app.hotspot import predict_hotspot
from app.idle import IdleTracker
from app.netpulse import ElephantFlowTracker, NetworkStatus
from app.telemetry import TelemetryRegistry
from app.threshold import classify_host

DEFAULT_STALE_SECONDS = 20.0
DEFAULT_CRITICAL_TEMP_C = 92.0
DEFAULT_HOTSPOT_HORIZON_SECONDS = 60.0
DEFAULT_DWELL_SAMPLES = 30


class Orchestrator:
    def __init__(self) -> None:
        self._idle_trackers: dict[str, IdleTracker] = {}
        self._netpulse_trackers: dict[str, ElephantFlowTracker] = {}
        self._cooling_status: dict[str, CoolingAssessment] = {}
        self._fan_maxed: set[str] = set()

    def _idle_tracker_for(self, host_id: str, dwell_samples: int) -> IdleTracker:
        tracker = self._idle_trackers.get(host_id)
        if tracker is None:
            tracker = IdleTracker(host_id, dwell_samples=dwell_samples)
            self._idle_trackers[host_id] = tracker
        return tracker

    def _netpulse_tracker_for(self, host_id: str) -> ElephantFlowTracker:
        tracker = self._netpulse_trackers.get(host_id)
        if tracker is None:
            tracker = ElephantFlowTracker()
            self._netpulse_trackers[host_id] = tracker
        return tracker

    def mark_fan_executed(self, host_id: str) -> None:
        """Called once an approved raise_fan_speed recommendation has
        actually been turned into a real fan_max_on command -- lets a
        later tick know to send fan_max_off once the hotspot clears."""
        self._fan_maxed.add(host_id)

    def is_idle(self, host_id: str) -> bool:
        tracker = self._idle_trackers.get(host_id)
        return tracker.is_idle if tracker else False

    def network_status(self, host_id: str) -> NetworkStatus:
        tracker = self._netpulse_trackers.get(host_id)
        return tracker.status if tracker else "normal"

    def cooling_status(self, host_id: str) -> Optional[CoolingAssessment]:
        return self._cooling_status.get(host_id)

    def tick(
        self,
        now: datetime,
        *,
        registry: TelemetryRegistry,
        command_queue: CommandQueue,
        action_queue: ActionQueue,
        stale_seconds: float = DEFAULT_STALE_SECONDS,
        critical_temp_c: float = DEFAULT_CRITICAL_TEMP_C,
        hotspot_horizon_seconds: float = DEFAULT_HOTSPOT_HORIZON_SECONDS,
        dwell_samples: int = DEFAULT_DWELL_SAMPLES,
    ) -> dict:
        prompted_sleep: list[str] = []
        fan_events: list[tuple[str, str]] = []

        for host_id in registry.known_hosts():
            if registry.is_stale(host_id, now, max_age_seconds=stale_seconds):
                continue

            current = registry.current_resources(host_id)
            history = {resource: registry.history(host_id, resource, 120) for resource in current}
            status = classify_host(host_id, current, history).status

            tracker = self._idle_tracker_for(host_id, dwell_samples)
            if tracker.observe(status):
                idle_minutes = round(dwell_samples * stale_seconds / 60.0, 1)
                command_queue.enqueue(host_id, "sleep_prompt", {"idleMinutes": idle_minutes})
                prompted_sleep.append(host_id)

            # NetPulse: sustained-high-throughput check. Independent of
            # temperature data, so it runs regardless of whether this
            # host has a working temp sensor.
            self._netpulse_tracker_for(host_id).observe(current["network"])

            latest = registry.latest(host_id)
            temp_history = registry.field_history(host_id, "cpuTempC", 30)
            if latest is None or latest.cpuTempC is None or not temp_history:
                continue

            # CoolSense: is this host running hotter than ITS OWN
            # established temp-vs-load relationship predicts -- a
            # different question than the hotspot predictor below asks.
            self._cooling_status[host_id] = assess_cooling(
                host_id,
                registry.cpu_temp_pairs(host_id, 120),
                current_cpu=current["cpu"],
                current_temp=latest.cpuTempC,
            )

            prediction = predict_hotspot(
                host_id,
                temp_history,
                freq_current=latest.cpuFreqMhz,
                freq_max=latest.cpuFreqMaxMhz,
                critical_temp_c=critical_temp_c,
                horizon_seconds=hotspot_horizon_seconds,
                sample_interval_seconds=stale_seconds / 4.0,
            )

            if prediction.riskLevel == "critical" and host_id not in self._fan_maxed:
                already_pending = any(rec.hostId == host_id for rec in action_queue.pending())
                if not already_pending:
                    action_queue.submit(
                        ActionRecommendation(
                            id=f"fan-{host_id}-{int(now.timestamp())}",
                            type="raise_fan_speed",
                            hostId=host_id,
                            predictedBenefit=(
                                f"{host_id}: CPU {prediction.currentTempC:.1f}C now, projected "
                                f"{prediction.projectedTempC:.1f}C in {hotspot_horizon_seconds:.0f}s at "
                                f"{latest.cpuFreqMhz:.0f}/{latest.cpuFreqMaxMhz:.0f}MHz -- enable max fan mode"
                            ),
                        )
                    )
                    fan_events.append(("recommended", host_id))
            elif prediction.riskLevel == "ok" and host_id in self._fan_maxed:
                command_queue.enqueue(host_id, "fan_max_off", {"reason": "temperature back to normal"})
                self._fan_maxed.discard(host_id)
                fan_events.append(("reverted", host_id))

        return {"promptedSleep": prompted_sleep, "fanEvents": fan_events}
