"""
powerprune/threshold.py -- MUST HAVE #1: adaptive multi-resource threshold.

Replaces the old fixed "15% CPU-only" idle check with a per-resource Median
Absolute Deviation (MAD) adaptive threshold (Beloglazov & Buyya pattern),
across all 4 resources (cpu, mem, diskIO, network). A host is only an
idle-candidate if ALL resources are below their adaptive floor -- a
CPU-idle-but-memory-bound host must never qualify.

Pure algorithm module: operates on plain per-resource history lists, no
dependency on powerprune/telemetry.py, so it's independently testable and
reusable against any adapter's output.
"""

import statistics
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

RESOURCES = ("cpu", "mem", "diskIO", "network")

# Methodology default: rolling window of N=60 samples (~30-60 min at 30-60s cadence).
COLD_START_MIN_SAMPLES = 60

# Methodology default sensitivity constant s=2.5, exposed as config.
DEFAULT_SENSITIVITY = 2.5

# COLD START: static defaults used until enough history accumulates (documented, not hidden).
COLD_START_LOWER = {"cpu": 15.0, "mem": 20.0, "diskIO": 10.0, "network": 10.0}

# The methodology only specifies cold-start *lower* (idle-candidate floor) defaults.
# It leaves the cold-start overload ceiling unspecified; we use a conservative fixed
# ceiling per resource until adaptive MAD thresholds have enough history to compute
# their own upper bound. This is a documented simplification, not a hidden default.
COLD_START_UPPER = {"cpu": 90.0, "mem": 90.0, "diskIO": 90.0, "network": 90.0}

HostStatus = Literal["normal", "idle-candidate", "overloaded"]


class ResourceThreshold(BaseModel):
    lower: float
    upper: float


class HostUtilizationState(BaseModel):
    hostId: str
    timestamp: str
    resources: dict[str, float]
    thresholds: dict[str, ResourceThreshold]
    status: HostStatus


def compute_resource_threshold(
    resource: str,
    history: list[float],
    *,
    sensitivity: float = DEFAULT_SENSITIVITY,
) -> ResourceThreshold:
    """One resource's adaptive MAD threshold, with a static cold-start fallback."""
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
    timestamp: str | None = None,
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

    return HostUtilizationState(
        hostId=host_id,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        resources=current,
        thresholds=thresholds,
        status=status,
    )
