"""
shared/classification.py

Shared workload-classification logic reused by PowerPrune, GridSync, and
NetPulse (methodology Section 1 & 2). This module owns *tag resolution and
storage* -- looking up a workload's protected/deferrable status and applying
the fail-safe-open default. It does not own any module's domain algorithm
(e.g. PowerPrune's MAD threshold, GridSync's deadline enforcement) --
those consume this module's output in later phases.

RULE (from methodology Section 0 & 2): every classification defaults to the
safest state. A workload with no tag, or a tag whose classification is
"unclassified", is always "protected". Nothing here ever infers
"deferrable" on its own -- deferrable only comes from an explicit,
already-validated WorkloadTag.
"""

from typing import Optional

from shared.contracts import WorkloadTag

EffectiveClassification = str  # "protected" | "deferrable" -- see WorkloadTag.effective_classification


def resolve_classification(tag: Optional[WorkloadTag]) -> EffectiveClassification:
    """
    Fail-safe-open resolution: no tag, or an unclassified tag, reads as
    "protected". Only an explicit "deferrable" tag reads as "deferrable".
    """
    if tag is None:
        return "protected"
    return tag.effective_classification


def is_deferrable(tag: Optional[WorkloadTag]) -> bool:
    return resolve_classification(tag) == "deferrable"


class WorkloadClassificationStore:
    """
    In-memory registry of WorkloadTag by workloadId, shared by every module
    that needs to know whether a given VM/job/flow-owning-VM is protected or
    deferrable. Modules should read through this store rather than keeping
    their own copies, so an operator override in one module is visible to
    all of them.
    """

    def __init__(self) -> None:
        self._tags: dict[str, WorkloadTag] = {}

    def set_tag(self, tag: WorkloadTag) -> None:
        self._tags[tag.workloadId] = tag

    def get_tag(self, workload_id: str) -> Optional[WorkloadTag]:
        return self._tags.get(workload_id)

    def classification_for(self, workload_id: str) -> EffectiveClassification:
        """Resolve a workloadId straight to its fail-safe-open classification."""
        return resolve_classification(self.get_tag(workload_id))

    def is_deferrable(self, workload_id: str) -> bool:
        return self.classification_for(workload_id) == "deferrable"

    def clear(self) -> None:
        self._tags.clear()


# Process-wide singleton, mirroring shared.eventbus.event_bus -- modules
# import this rather than constructing their own store, so an operator
# override made through one module's API is visible to every module.
classification_store = WorkloadClassificationStore()
