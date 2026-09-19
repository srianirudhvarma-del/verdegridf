"""
app/netpulse.py -- elephant-flow detection, analogous to VerdeGrid's
NetPulse (>10MB/interval sustained >10s on a network link) but applied to
a laptop's own aggregate network throughput.

VerdeGrid's version flags a large flow on a specific link between two
racks; a laptop doesn't have per-process network attribution available
cross-platform without extra privileged tooling (psutil doesn't expose
it reliably, especially on Windows), so this operates one level up:
sustained high throughput on the machine as a whole, over several
consecutive samples -- the same "sustained, not momentary" shape as
VerdeGrid's own check, just measured against the whole host instead of
a single link.
"""

from typing import Literal

NetworkStatus = Literal["normal", "elephant_flow"]

DEFAULT_ELEPHANT_THRESHOLD_PERCENT = 70.0
DEFAULT_ELEPHANT_SUSTAINED_SAMPLES = 3


class ElephantFlowTracker:
    def __init__(
        self,
        *,
        threshold_percent: float = DEFAULT_ELEPHANT_THRESHOLD_PERCENT,
        sustained_samples: int = DEFAULT_ELEPHANT_SUSTAINED_SAMPLES,
    ) -> None:
        if sustained_samples < 1:
            raise ValueError("sustained_samples must be >= 1")
        self.threshold_percent = threshold_percent
        self.sustained_samples = sustained_samples
        self._consecutive_high = 0
        self.status: NetworkStatus = "normal"

    def observe(self, network_percent: float) -> NetworkStatus:
        if network_percent >= self.threshold_percent:
            self._consecutive_high += 1
            if self._consecutive_high >= self.sustained_samples:
                self.status = "elephant_flow"
        else:
            self._consecutive_high = 0
            self.status = "normal"
        return self.status
