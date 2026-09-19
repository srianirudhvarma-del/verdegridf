"""
Adaptive multi-resource idle threshold: a per-resource Median Absolute
Deviation (MAD) threshold (the standard Beloglazov & Buyya "adaptive
utilization threshold" pattern), across cpu/mem/diskIO/network. A host is
only "idle" if ALL FOUR resources are below their own adaptive floor -- a
CPU-idle-but-disk-churning machine (e.g. a backup running) must never
qualify.

Pure algorithm module: operates on plain dicts/lists, no dependency on
telemetry.py, so it's testable independent of any real or fake data
source.
"""

import statistics
from typing import Literal

from pydantic import BaseModel

RESOURCES = ("cpu", "mem", "diskIO", "network")

# Rolling window needed before the adaptive threshold takes over from the
# fixed cold-start floor below.
COLD_START_MIN_SAMPLES = 60

# Sensitivity constant (the Beloglazov & Buyya default is s=2.5).
DEFAULT_SENSITIVITY = 2.5

# Fixed floor used until enough history accumulates -- documented, not hidden.
COLD_START_LOWER = {"cpu": 15.0, "mem": 20.0, "diskIO": 10.0, "network": 10.0}
COLD_START_UPPER = {"cpu": 90.0, "mem": 90.0, "diskIO": 90.0, "network": 90.0}

HostStatus = Literal["normal", "idle-candidate", "overloaded"]


class ResourceThreshold(BaseModel):
    lower: float
    upper: float


class HostUtilizationState(BaseModel):
    hostId: str
    resources: dict[str, float]
    thresholds: dict[str, ResourceThreshold]
    status: HostStatus


def compute_resource_threshold(
    resource: str, history: list[float], *, sensitivity: float = DEFAULT_SENSITIVITY
) -> ResourceThreshold:
    if len(history) < COLD_START_MIN_SAMPLES:
        return ResourceThreshold(lower=COLD_START_LOWER[resource], upper=COLD_START_UPPER[resource])

    median = statistics.median(history)
    mad = statistics.median([abs(x - median) for x in history])
    lower = max(0.0, median - sensitivity * mad)
    upper = median + sensitivity * mad
    return ResourceThreshold(lower=lower, upper=upper)


def classify_host(
    host_id: str,
    current: dict[str, float],
    history: dict[str, list[float]],
    *,
    sensitivity: float = DEFAULT_SENSITIVITY,
) -> HostUtilizationState:
    """
    status = "overloaded"     if ANY resource current > upper
    status = "idle-candidate" if ALL resources current < lower
    status = "normal"         otherwise
    """
    thresholds = {
        resource: compute_resource_threshold(resource, history.get(resource, []), sensitivity=sensitivity)
        for resource in RESOURCES
    }

    overloaded = any(current[resource] > thresholds[resource].upper for resource in RESOURCES)
    idle_candidate = all(current[resource] < thresholds[resource].lower for resource in RESOURCES)

    if overloaded:
        status: HostStatus = "overloaded"
    elif idle_candidate:
        status = "idle-candidate"
    else:
        status = "normal"

    return HostUtilizationState(hostId=host_id, resources=current, thresholds=thresholds, status=status)
