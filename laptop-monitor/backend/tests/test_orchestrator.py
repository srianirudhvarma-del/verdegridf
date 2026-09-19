from datetime import datetime, timedelta, timezone

from app.actions import ActionQueue
from app.commands import CommandQueue
from app.orchestrator import Orchestrator
from app.telemetry import TelemetryRegistry, TelemetrySample

HOST = "test-laptop"


def make_sample(*, cpu=5.0, mem=5.0, disk=2.0, net=2.0, temp=50.0, freq=1800.0, freq_max=4500.0) -> TelemetrySample:
    return TelemetrySample(
        hostId=HOST, timestamp=datetime.now(timezone.utc).isoformat(),
        cpuPercent=cpu, memPercent=mem, diskIoPercent=disk, networkPercent=net,
        cpuFreqMhz=freq, cpuFreqMaxMhz=freq_max, cpuTempC=temp, idleSeconds=0.0,
    )


def build():
    return TelemetryRegistry(), CommandQueue(), ActionQueue(), Orchestrator()


class TestSleepPrompt:
    def test_sustained_idle_prompts_exactly_once(self):
        registry, commands, actions, orchestrator = build()
        now = datetime.now(timezone.utc)

        prompts = 0
        for _ in range(35):  # > default dwell (30)
            now += timedelta(seconds=5)
            registry.ingest(make_sample(), received_at=now)
            result = orchestrator.tick(now, registry=registry, command_queue=commands, action_queue=actions)
            prompts += len(result["promptedSleep"])

        assert prompts == 1
        assert orchestrator.is_idle(HOST)
        command = commands.poll(HOST)
        assert command is not None and command.type == "sleep_prompt"
        assert commands.poll(HOST) is None

    def test_stale_host_never_prompted(self):
        registry, commands, actions, orchestrator = build()
        now = datetime.now(timezone.utc)
        registry.ingest(make_sample(), received_at=now)
        later = now + timedelta(minutes=30)
        result = orchestrator.tick(later, registry=registry, command_queue=commands, action_queue=actions)
        assert result["promptedSleep"] == []
        assert not orchestrator.is_idle(HOST)

    def test_going_active_then_idle_again_reprompts(self):
        """Exercises the edge-trigger latch itself, independent of
        threshold.py's adaptive-MAD-vs-cold-start behavior -- each idle
        episode uses its own fresh registry so both stay under
        COLD_START_MIN_SAMPLES and behave identically."""
        _, commands, actions, orchestrator = build()
        now = datetime.now(timezone.utc)

        def run_idle_episode() -> int:
            nonlocal now
            episode_registry = TelemetryRegistry()
            prompts = 0
            for _ in range(35):
                now += timedelta(seconds=5)
                episode_registry.ingest(make_sample(), received_at=now)
                result = orchestrator.tick(now, registry=episode_registry, command_queue=commands, action_queue=actions)
                prompts += len(result["promptedSleep"])
            return prompts

        assert run_idle_episode() == 1
        commands.poll(HOST)

        active_registry = TelemetryRegistry()
        now += timedelta(seconds=5)
        active_registry.ingest(make_sample(cpu=80.0), received_at=now)
        orchestrator.tick(now, registry=active_registry, command_queue=commands, action_queue=actions)
        assert not orchestrator.is_idle(HOST)

        assert run_idle_episode() == 1


class TestFanHotspotAndRevert:
    def test_critical_hotspot_submits_one_pending_recommendation(self):
        registry, commands, actions, orchestrator = build()
        now = datetime.now(timezone.utc)

        for i in range(10):
            now += timedelta(seconds=5)
            registry.ingest(make_sample(temp=75.0 + i * 3, freq=4300.0), received_at=now)
            orchestrator.tick(now, registry=registry, command_queue=commands, action_queue=actions)

        pending = [r for r in actions.pending() if r.hostId == HOST]
        assert len(pending) == 1
        assert pending[0].type == "raise_fan_speed"

        now += timedelta(seconds=5)
        registry.ingest(make_sample(temp=100.0, freq=4300.0), received_at=now)
        orchestrator.tick(now, registry=registry, command_queue=commands, action_queue=actions)
        assert len([r for r in actions.pending() if r.hostId == HOST]) == 1

    def test_approval_queues_real_command(self):
        registry, commands, actions, orchestrator = build()
        now = datetime.now(timezone.utc)

        for i in range(10):
            now += timedelta(seconds=5)
            registry.ingest(make_sample(temp=75.0 + i * 3, freq=4300.0), received_at=now)
            orchestrator.tick(now, registry=registry, command_queue=commands, action_queue=actions)

        rec = [r for r in actions.pending() if r.hostId == HOST][0]
        assert commands.poll(HOST) is None  # nothing until approved

        actions.approve(rec.id)
        orchestrator.mark_fan_executed(HOST)
        commands.enqueue(HOST, "fan_max_on", {"recommendationId": rec.id})

        command = commands.poll(HOST)
        assert command.type == "fan_max_on"

    def test_recovery_reverts_fan_without_approval(self):
        registry, commands, actions, orchestrator = build()
        now = datetime.now(timezone.utc)
        orchestrator.mark_fan_executed(HOST)

        revert_seen = False
        for _ in range(6):
            now += timedelta(seconds=5)
            registry.ingest(make_sample(temp=45.0, freq=1200.0), received_at=now)
            orchestrator.tick(now, registry=registry, command_queue=commands, action_queue=actions)
            command = commands.poll(HOST)
            if command is not None:
                assert command.type == "fan_max_off"
                revert_seen = True

        assert revert_seen
        assert HOST not in orchestrator._fan_maxed
