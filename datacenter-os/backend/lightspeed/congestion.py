"""
lightspeed/congestion.py -- MUST HAVE #15: dwell-time/hysteresis before any
reroute.

congestionConfirmed(link) =
    utilization(link) > congestionThresholdPct (default 80%)
    for >= dwellTimeSeconds consecutively (default 30-60s)
onRerouteExecuted(link, flow):
    startCooldown(link, flow, cooldownSeconds=300)  // no repeat reroute of
                                                      // the same flow/link
                                                      // for 5 min
"""

from datetime import datetime, timedelta

from lightspeed.flow import Flow

DEFAULT_CONGESTION_THRESHOLD_PCT = 80.0
DEFAULT_DWELL_TIME_SECONDS = 45.0  # methodology default range: 30-60s
DEFAULT_COOLDOWN_SECONDS = 300.0

FlowKey = tuple[str, str, int, int, str]


def flow_key(flow: Flow) -> FlowKey:
    return (flow.srcIp, flow.dstIp, flow.srcPort, flow.dstPort, flow.proto)


class CongestionTracker:
    """Per-link consecutive-congestion dwell timer + per-(link, flow) reroute cooldown."""

    def __init__(
        self,
        *,
        congestion_threshold_pct: float = DEFAULT_CONGESTION_THRESHOLD_PCT,
        dwell_time_seconds: float = DEFAULT_DWELL_TIME_SECONDS,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        self.congestion_threshold_pct = congestion_threshold_pct
        self.dwell_time_seconds = dwell_time_seconds
        self.cooldown_seconds = cooldown_seconds
        self._congested_since: dict[str, datetime] = {}
        self._cooldown_expiry: dict[tuple[str, FlowKey], datetime] = {}

    def observe_utilization(self, link: str, utilization_pct: float, at: datetime) -> None:
        """Feed one utilization sample for `link`. Non-congested samples reset the dwell timer."""
        if utilization_pct > self.congestion_threshold_pct:
            self._congested_since.setdefault(link, at)
        else:
            self._congested_since.pop(link, None)

    def congestion_confirmed(self, link: str, at: datetime) -> bool:
        started = self._congested_since.get(link)
        if started is None:
            return False
        return (at - started).total_seconds() >= self.dwell_time_seconds

    def is_in_cooldown(self, link: str, flow: Flow, at: datetime) -> bool:
        expiry = self._cooldown_expiry.get((link, flow_key(flow)))
        return expiry is not None and at < expiry

    def on_reroute_executed(self, link: str, flow: Flow, at: datetime) -> None:
        self._cooldown_expiry[(link, flow_key(flow))] = at + timedelta(seconds=self.cooldown_seconds)
