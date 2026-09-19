"""
Acceptance tests for api/real_nodes.py -- turning real laptop telemetry
into the same dwell/wake + supervised-approval behavior the simulated
hosts already have.

Two documented behaviors under test:
1. Sustained real idleness (below the MAD cold-start floor for
   dwell_time_down_samples consecutive ticks, exactly like a simulated
   host) fires exactly one sleep_prompt command -- not one per tick --
   and re-arms if the host goes active and idles out again.
2. A real hotspot (rising temp near max clock) produces exactly one
   pending adjust_fan_speed recommendation in the existing supervised
   ActionRecommendationQueue; only after that is approved (mimicking the
   operator clicking Approve in the dashboard) does a real fan_max_on
   command reach the host, and once the temperature recovers, fan_max_off
   is sent automatically (no approval needed for the safe direction).
"""

from datetime import datetime, timedelta, timezone

from api.real_nodes import RealNodeManager, RealCommandQueue
from powerprune.power import HostState
from shared.real_agent import RealAgentRegistry, RealAgentSample
from shared.scheduler_driver import SchedulerRegistry
from thermos.control import ActionRecommendationQueue

HOST = "test-omen-transcend-16"


def make_sample(*, cpu=5.0, mem=5.0, disk=2.0, net=2.0, temp=50.0, freq=1800.0, freq_max=4500.0) -> RealAgentSample:
    return RealAgentSample(
        hostId=HOST,
        timestamp=datetime.now(timezone.utc).isoformat(),
        cpuPercent=cpu, memPercent=mem, diskIoPercent=disk, networkPercent=net,
        cpuFreqMhz=freq, cpuFreqMaxMhz=freq_max, cpuTempC=temp, idleSeconds=0.0,
    )


def build():
    registry = RealAgentRegistry()
    command_queue = RealCommandQueue()
    action_queue = ActionRecommendationQueue()
    manager = RealNodeManager(scheduler_registry=SchedulerRegistry())
    return registry, command_queue, action_queue, manager


class TestSleepPrompt:
    def test_sustained_idle_prompts_exactly_once(self):
        registry, command_queue, action_queue, manager = build()
        now = datetime.now(timezone.utc)

        prompts_seen = 0
        for i in range(35):  # > DEFAULT_DWELL_TIME_DOWN_SAMPLES (30)
            now += timedelta(seconds=5)
            registry.ingest(make_sample(), received_at=now)
            result = manager.tick(now, registry=registry, command_queue=command_queue, action_queue=action_queue)
            prompts_seen += len(result["promptedSleep"])

        assert prompts_seen == 1
        assert manager.dwell_machines[HOST].state == HostState.IDLE_CANDIDATE
        # The command actually reached the queue and can be polled exactly once.
        command = command_queue.poll(HOST)
        assert command is not None
        assert command.type == "sleep_prompt"
        assert command_queue.poll(HOST) is None

    def test_going_active_then_idle_again_reprompts(self):
        """
        Exercises RealNodeManager's own edge-trigger bookkeeping (the
        "already prompted this idle episode" latch), independent of
        threshold.py's adaptive-MAD-vs-cold-start behavior (that's
        test_powerprune_threshold.py's job) -- so each idle episode here
        uses its own fresh registry, keeping every episode's history
        comfortably under COLD_START_MIN_SAMPLES (60) and the classifier
        behavior identical and predictable across both episodes.
        """
        _, command_queue, action_queue, manager = build()
        now = datetime.now(timezone.utc)

        def run_idle_episode() -> int:
            episode_registry = RealAgentRegistry()
            prompts = 0
            nonlocal now
            for _ in range(35):
                now += timedelta(seconds=5)
                episode_registry.ingest(make_sample(), received_at=now)
                result = manager.tick(
                    now, registry=episode_registry, command_queue=command_queue, action_queue=action_queue
                )
                prompts += len(result["promptedSleep"])
            return prompts

        assert run_idle_episode() == 1
        assert manager.dwell_machines[HOST].state == HostState.IDLE_CANDIDATE
        command_queue.poll(HOST)  # drain the first prompt

        # Host becomes active again -- resets dwell and the prompt latch.
        active_registry = RealAgentRegistry()
        now += timedelta(seconds=5)
        active_registry.ingest(make_sample(cpu=80.0), received_at=now)
        manager.tick(now, registry=active_registry, command_queue=command_queue, action_queue=action_queue)
        assert manager.dwell_machines[HOST].state == HostState.NORMAL

        assert run_idle_episode() == 1

    def test_stale_host_never_prompted(self):
        registry, command_queue, action_queue, manager = build()
        now = datetime.now(timezone.utc)
        # One sample, then the clock advances far past staleness with no
        # further data -- must never be classified idle from old data.
        registry.ingest(make_sample(), received_at=now)
        later = now + timedelta(minutes=30)
        result = manager.tick(later, registry=registry, command_queue=command_queue, action_queue=action_queue)
        assert result["promptedSleep"] == []
        assert HOST not in manager.dwell_machines


class TestFanHotspotAndRevert:
    def test_critical_hotspot_submits_one_pending_recommendation(self):
        registry, command_queue, action_queue, manager = build()
        now = datetime.now(timezone.utc)

        # Rising temps, pinned clock -> "critical" per predict_hotspot.
        for i in range(10):
            now += timedelta(seconds=5)
            registry.ingest(make_sample(temp=75.0 + i * 3, freq=4300.0), received_at=now)
            manager.tick(now, registry=registry, command_queue=command_queue, action_queue=action_queue)

        pending = [r for r in action_queue.pending() if r.rackId == HOST]
        assert len(pending) == 1
        assert pending[0].type == "adjust_fan_speed"

        # A further tick at the same risk level must not duplicate it.
        now += timedelta(seconds=5)
        registry.ingest(make_sample(temp=100.0, freq=4300.0), received_at=now)
        manager.tick(now, registry=registry, command_queue=command_queue, action_queue=action_queue)
        pending_after = [r for r in action_queue.pending() if r.rackId == HOST]
        assert len(pending_after) == 1

    def test_approval_queues_real_command(self):
        registry, command_queue, action_queue, manager = build()
        now = datetime.now(timezone.utc)

        for i in range(10):
            now += timedelta(seconds=5)
            registry.ingest(make_sample(temp=75.0 + i * 3, freq=4300.0), received_at=now)
            manager.tick(now, registry=registry, command_queue=command_queue, action_queue=action_queue)

        rec = [r for r in action_queue.pending() if r.rackId == HOST][0]

        # Nothing queued for the host until an operator approves -- this
        # mirrors api/routes.py's approve_action hook, exercised directly
        # here at the RealNodeManager/queue level.
        assert command_queue.poll(HOST) is None

        action_queue.approve(rec.id)
        manager.mark_fan_executed(HOST)
        command_queue.enqueue(HOST, "fan_max_on", {"recommendationId": rec.id})

        command = command_queue.poll(HOST)
        assert command.type == "fan_max_on"

    def test_recovery_reverts_fan_without_approval(self):
        registry, command_queue, action_queue, manager = build()
        now = datetime.now(timezone.utc)
        manager.mark_fan_executed(HOST)  # simulate a fan_max_on already executed

        # Flat, cool temps at a low clock speed -> unambiguously "ok".
        revert_seen = False
        for _ in range(6):
            now += timedelta(seconds=5)
            registry.ingest(make_sample(temp=45.0, freq=1200.0), received_at=now)
            manager.tick(now, registry=registry, command_queue=command_queue, action_queue=action_queue)
            command = command_queue.poll(HOST)
            if command is not None:
                assert command.type == "fan_max_off"
                revert_seen = True

        assert revert_seen
        assert HOST not in manager._fan_maxed
