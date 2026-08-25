"""
idlehunter/power.py -- MUST HAVE #5: asymmetric dwell-time / wake policy.

NORMAL --(idle-candidate for >= dwellTimeDownSamples)--> IDLE_CANDIDATE
IDLE_CANDIDATE --(migration+consolidation succeeds)--> STANDBY
STANDBY --(high-water-mark breach OR any overloaded sample elsewhere)--> WAKING
WAKING --(BMC wake confirmed + host rejoins hypervisor pool)--> NORMAL

Asymmetric by design: powering a host down requires sustained dwell
(dwellTimeDownSamples consecutive idle-candidate samples, ~15-20 min at
30-60s cadence); waking it back up requires a single triggering sample, no
dwell -- matches VMware DPM's own default philosophy of "slow to sleep,
fast to wake."
"""

from enum import Enum

from idlehunter.threshold import HostStatus

# Methodology default: 20-40 samples of continuous idle-candidate status at
# 30-60s cadence (~15-20 min).
DEFAULT_DWELL_TIME_DOWN_SAMPLES = 30


class HostState(str, Enum):
    NORMAL = "NORMAL"
    IDLE_CANDIDATE = "IDLE_CANDIDATE"
    STANDBY = "STANDBY"
    WAKING = "WAKING"


class InvalidTransition(Exception):
    pass


class DwellStateMachine:
    def __init__(self, host_id: str, *, dwell_time_down_samples: int = DEFAULT_DWELL_TIME_DOWN_SAMPLES) -> None:
        if dwell_time_down_samples < 1:
            raise ValueError("dwell_time_down_samples must be >= 1")
        self.host_id = host_id
        self.dwell_time_down_samples = dwell_time_down_samples
        self.state = HostState.NORMAL
        self._consecutive_idle_samples = 0
        self.wake_reason: str | None = None

    def observe(self, status: HostStatus) -> HostState:
        """
        Feed one HostUtilizationState.status sample. Only meaningful while
        NORMAL or IDLE_CANDIDATE -- once a host is STANDBY/WAKING it isn't
        being polled for utilization the same way.
        """
        if self.state == HostState.NORMAL:
            if status == "idle-candidate":
                self._consecutive_idle_samples += 1
                if self._consecutive_idle_samples >= self.dwell_time_down_samples:
                    self.state = HostState.IDLE_CANDIDATE
            else:
                self._consecutive_idle_samples = 0
        elif self.state == HostState.IDLE_CANDIDATE:
            if status != "idle-candidate":
                # Host became active again before consolidation completed.
                self.state = HostState.NORMAL
                self._consecutive_idle_samples = 0
        return self.state

    def consolidation_succeeded(self) -> HostState:
        """IDLE_CANDIDATE -> STANDBY once migration + power-down completes."""
        if self.state != HostState.IDLE_CANDIDATE:
            raise InvalidTransition(f"Cannot power down host in state {self.state}")
        self.state = HostState.STANDBY
        self._consecutive_idle_samples = 0
        return self.state

    def request_wake(self, reason: str) -> HostState:
        """
        STANDBY -> WAKING. Asymmetric: fires on a single triggering sample
        (high-water-mark breach or an overloaded sample elsewhere) -- no
        dwell required, unlike the power-down path.
        """
        if self.state != HostState.STANDBY:
            raise InvalidTransition(f"Cannot wake host in state {self.state}")
        self.state = HostState.WAKING
        self.wake_reason = reason
        return self.state

    def wake_confirmed(self) -> HostState:
        """WAKING -> NORMAL once BMC wake is confirmed and the host rejoins the pool."""
        if self.state != HostState.WAKING:
            raise InvalidTransition(f"Cannot confirm wake for host in state {self.state}")
        self.state = HostState.NORMAL
        self.wake_reason = None
        return self.state
