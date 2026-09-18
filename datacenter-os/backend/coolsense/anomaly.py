"""
coolsense/anomaly.py

MUST HAVE #12's anomaly decision: a flow drop must be unexplained by a
workload change before it counts as a leak signal.

MUST HAVE #13 -- explicit maintenance-mode suppression: the anomaly engine
still logs the raw anomaly for audit, but suppresses the
notification/escalation while an operator-declared maintenance window is
active for that loop.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from coolsense.baseline import peer_z_score, z_score  # noqa: F401  (re-exported for convenience)

# Methodology's exact thresholds for MUST HAVE #12.
Z_FLOW_DROP_THRESHOLD = -2.5
PEER_Z_DIVERGENCE_THRESHOLD = 2.0

# The methodology doesn't give an exact number for "IdleHunter utilization
# delta ... within its own normal range" -- reusing the same z-score
# approach as the flow baseline itself (coolsense/baseline.py) is the
# natural, documented simplification: the rack's utilization delta gets
# baselined the same way, and this is the z-score magnitude below which a
# delta counts as "normal" (i.e. NOT a workload change big enough to
# explain a flow drop).
UTILIZATION_DELTA_NORMAL_Z_THRESHOLD = 2.0


def workload_delta_is_normal(utilization_delta_z: float, *, threshold: float = UTILIZATION_DELTA_NORMAL_Z_THRESHOLD) -> bool:
    """True if the rack's utilization didn't change enough to explain a flow drop."""
    return abs(utilization_delta_z) <= threshold


def detect_flow_anomaly(flow_z: float, flow_peer_z: float, utilization_delta_z: float) -> bool:
    """
    anomaly flagged if:
      z(flow) < -2.5  AND  |peerZ(flow)| > 2.0  AND  the utilization delta
      is within its own normal range (i.e. NOT explained by a workload
      change).
    """
    if not workload_delta_is_normal(utilization_delta_z):
        return False  # a real workload change explains the drop
    return flow_z < Z_FLOW_DROP_THRESHOLD and abs(flow_peer_z) > PEER_Z_DIVERGENCE_THRESHOLD


class MaintenanceWindow(BaseModel):
    loopId: str
    start: str
    end: str
    operatorId: str


class MaintenanceModeRegistry:
    def __init__(self) -> None:
        self._windows: list[MaintenanceWindow] = []

    def declare(self, window: MaintenanceWindow) -> None:
        self._windows.append(window)

    def is_active(self, loop_id: str, at: datetime) -> bool:
        for window in self._windows:
            if window.loopId != loop_id:
                continue
            start = datetime.fromisoformat(window.start)
            end = datetime.fromisoformat(window.end)
            if start <= at <= end:
                return True
        return False


@dataclass
class AnomalyEvent:
    loopId: str
    timestamp: str
    isAnomaly: bool
    suppressed: bool
    reason: str


def evaluate_and_log(
    loop_id: str,
    timestamp: str,
    flow_z: float,
    flow_peer_z: float,
    utilization_delta_z: float,
    maintenance: MaintenanceModeRegistry,
    audit_log: list[AnomalyEvent],
) -> AnomalyEvent:
    """
    Always appends the raw evaluation to audit_log, even when suppressed --
    the methodology's "still logs the raw anomaly for audit" requirement.
    Callers should gate any actual alert/escalation on `should_notify`,
    never on `isAnomaly` alone.
    """
    is_anomaly = detect_flow_anomaly(flow_z, flow_peer_z, utilization_delta_z)
    at = datetime.fromisoformat(timestamp)
    suppressed = is_anomaly and maintenance.is_active(loop_id, at)

    if suppressed:
        reason = "flow anomaly detected but suppressed: maintenance window active"
    elif is_anomaly:
        reason = "flow anomaly detected: unexplained by workload change"
    else:
        reason = "no anomaly"

    event = AnomalyEvent(loopId=loop_id, timestamp=timestamp, isAnomaly=is_anomaly, suppressed=suppressed, reason=reason)
    audit_log.append(event)
    return event


def should_notify(event: AnomalyEvent) -> bool:
    return event.isAnomaly and not event.suppressed


# ---------------------------------------------------------------------------
# SHOULD HAVE #14 -- physical leak-detection point sensors as a backstop
# ---------------------------------------------------------------------------


class PointSensorReading(BaseModel):
    sensorId: str
    loopId: str
    timestamp: str
    wet: bool


def evaluate_point_sensor(reading: PointSensorReading) -> Optional[AnomalyEvent]:
    """
    A hard trip-wire, not a Z-score input: any wet=True reading bypasses
    the statistical pipeline entirely and is Critical immediately, always
    -- including during an active maintenance window (a physical wet
    reading is never something maintenance mode should silence).
    """
    if not reading.wet:
        return None
    return AnomalyEvent(
        loopId=reading.loopId,
        timestamp=reading.timestamp,
        isAnomaly=True,
        suppressed=False,
        reason=f"point sensor {reading.sensorId} trip-wire: wet=True (Critical, bypasses statistical pipeline)",
    )
