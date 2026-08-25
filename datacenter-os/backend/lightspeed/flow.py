"""
lightspeed/flow.py -- MUST HAVE #14: flow-level ("elephant flow") detection.

Real collection would poll edge-switch flow tables every 5-10s via
sFlow/NetFlow/IPFIX (or an SNMP flow-stats extension); classify_flow()
operates on whatever byte-count/timing data that pipeline produces, so it
doesn't need to know which collection method was used.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

DEFAULT_ELEPHANT_THRESHOLD_BYTES = 10 * 1024 * 1024  # ~10MB/interval, tune per fabric
DEFAULT_MIN_DURATION_SECONDS = 10.0


class Flow(BaseModel):
    srcIp: str
    dstIp: str
    srcPort: int
    dstPort: int
    proto: str
    bytesLastInterval: float
    firstSeen: str
    lastSeen: str
    isElephant: bool = False
    # Populated only by the IdleHunter cross-wire (lightspeed/routing.py's
    # resolve_latency_sensitivity) -- None means "not yet classified,"
    # never treated as "safe to auto-reroute."
    latencySensitive: Optional[bool] = None


def classify_flow(
    src_ip: str,
    dst_ip: str,
    src_port: int,
    dst_port: int,
    proto: str,
    bytes_last_interval: float,
    first_seen: str,
    last_seen: str,
    *,
    elephant_threshold_bytes: float = DEFAULT_ELEPHANT_THRESHOLD_BYTES,
    min_duration_seconds: float = DEFAULT_MIN_DURATION_SECONDS,
) -> Flow:
    """
    isElephant = bytesLastInterval > elephantThresholdBytes
                 AND (now - firstSeen) > minDurationSeconds
    """
    duration_seconds = (datetime.fromisoformat(last_seen) - datetime.fromisoformat(first_seen)).total_seconds()
    is_elephant = bytes_last_interval > elephant_threshold_bytes and duration_seconds > min_duration_seconds

    return Flow(
        srcIp=src_ip,
        dstIp=dst_ip,
        srcPort=src_port,
        dstPort=dst_port,
        proto=proto,
        bytesLastInterval=bytes_last_interval,
        firstSeen=first_seen,
        lastSeen=last_seen,
        isElephant=is_elephant,
    )
