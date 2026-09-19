"""
Dwell-timer idle tracker: a host must be classified "idle-candidate" for
`dwell_samples` CONSECUTIVE ticks before it's treated as genuinely idle --
matches VMware DPM's own "slow to sleep" philosophy, so a machine that
dips idle for a few seconds (a paused video, a slow page load) never
triggers a sleep prompt. Any non-idle sample resets the counter to zero
immediately -- no partial credit.

Edge-triggered: `should_prompt()` returns True exactly once per idle
episode (the tick where the dwell requirement is first met), then stays
False until the host goes non-idle and idles out again.
"""

from app.threshold import HostStatus


class IdleTracker:
    def __init__(self, host_id: str, *, dwell_samples: int = 30) -> None:
        if dwell_samples < 1:
            raise ValueError("dwell_samples must be >= 1")
        self.host_id = host_id
        self.dwell_samples = dwell_samples
        self.is_idle = False
        self._consecutive_idle = 0
        self._prompted_this_episode = False

    def observe(self, status: HostStatus) -> bool:
        """Feed one classification sample. Returns True on the single
        tick a new idle episode first crosses the dwell requirement."""
        if status == "idle-candidate":
            self._consecutive_idle += 1
            if self._consecutive_idle >= self.dwell_samples:
                self.is_idle = True
                if not self._prompted_this_episode:
                    self._prompted_this_episode = True
                    return True
        else:
            self._consecutive_idle = 0
            self.is_idle = False
            self._prompted_this_episode = False
        return False
