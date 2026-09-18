"""
Shared cross-module data contracts (methodology Section 2).

Pydantic translation of the TypeScript interfaces in
VerdeGrid-Implementation-Methodology.md, Section 2. Field names/shapes are
kept identical to the source spec. These are the only types modules should
use to talk to each other -- no module reaches into another module's
internal state directly.
"""

from typing import Literal, Optional

from pydantic import BaseModel, model_validator

WorkloadClassification = Literal["protected", "deferrable", "unclassified"]
TagSource = Literal["operator", "inferred", "default"]
ThermalStatus = Literal["ok", "constrained", "critical"]

Topic = Literal[
    "idlehunter.capacity.updated",
    "idlehunter.workload.classified",
    "thermaltrace.headroom.updated",
    "carbonclock.job.scheduled",
    "lightspeed.flow.classified",
    # Section 2's Topic list is the minimal starting set ("even if backed by
    # simple REST polling initially"); later MUST HAVE items name additional
    # topics explicitly. carbonclock.prewake.requested comes from Phase 3's
    # MUST HAVE #9 (cross-wiring with IdleHunter's capacity forecast).
    "carbonclock.prewake.requested",
]

# The full set of valid topics, for validation / iteration by the event bus.
TOPICS: frozenset[str] = frozenset(
    {
        "idlehunter.capacity.updated",
        "idlehunter.workload.classified",
        "thermaltrace.headroom.updated",
        "carbonclock.job.scheduled",
        "lightspeed.flow.classified",
        "carbonclock.prewake.requested",
    }
)


class WorkloadTag(BaseModel):
    """
    shared/contracts/workload.ts -> WorkloadTag

    RULE: any consumer treats a missing/unclassified tag as "protected".
    Never assume deferrable. See `effective_classification`.
    """

    workloadId: str
    classification: WorkloadClassification
    maxDelayMinutes: Optional[int] = None
    source: TagSource
    updatedAt: str

    @model_validator(mode="after")
    def _require_max_delay_for_deferrable(self) -> "WorkloadTag":
        if self.classification == "deferrable" and self.maxDelayMinutes is None:
            raise ValueError("maxDelayMinutes is required when classification is 'deferrable'")
        return self

    @property
    def effective_classification(self) -> Literal["protected", "deferrable"]:
        """Fail-safe-open read: 'unclassified' collapses to 'protected'."""
        if self.classification == "deferrable":
            return "deferrable"
        return "protected"


class CapacityForecast(BaseModel):
    """
    shared/contracts/capacity.ts -> CapacityForecast

    Published by IdleHunter, consumed by CarbonClock, WaterWatch
    (baseline correlation), and LightSpeed.
    """

    timestampRangeStart: str
    timestampRangeEnd: str
    poweredOnHostCount: int
    availableCpuCapacity: float
    availableMemCapacity: float
    standbyHostCount: int
    estimatedWakeLatencySeconds: float


class ThermalHeadroom(BaseModel):
    """
    shared/contracts/thermal.ts -> ThermalHeadroom

    Published by ThermalTrace, consumed by IdleHunter (avoid consolidating
    into constrained racks).
    """

    rackId: str
    timestamp: str
    headroomCelsius: float
    status: ThermalStatus
