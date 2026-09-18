"""
netpulse/routing.py

MUST HAVE #16 -- explicit fail-safe-open controller/optimizer failure
story. Architectural rule, not just code: the optimizer only ever adds a
preference weight on top of the existing loop-free routing (BGP/ECMP) --
it never replaces or removes the default path. If the optimizer stops
heartbeating, the switch-side agent reverts any active overrides to
default ECMP automatically.

MUST HAVE #17 -- scope automatic rerouting to the narrow, pre-validated
case.

flow.latencySensitive needs the PowerPrune cross-wire the methodology
scopes as SHOULD HAVE #21 ("map each flow's source/destination IP to its
owning VM via an IP->VM lookup table synced from the hypervisor, then call
PowerPrune's WorkloadTag API"). That automatic IP->VM discovery is Phase 7
work. What MUST HAVE #17 actually needs -- never auto-reroute a
latency-sensitive flow -- doesn't require the auto-discovery step: the
classification lookup itself already exists (shared/classification.py,
Phase 0), keyed generically by "VM id, job id, or flow's owning VM id"
per its own docstring. resolve_latency_sensitivity() below reuses that
real store; callers just have to supply the owning VM id themselves until
SHOULD HAVE #21 automates the IP->VM mapping.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from netpulse.congestion import CongestionTracker
from netpulse.flow import Flow
from shared.classification import WorkloadClassificationStore, classification_store

DEFAULT_HEALTH_CHECK_TIMEOUT_SECONDS = 30.0
DEFAULT_ALT_PATH_THRESHOLD_PCT = 60.0


# ---------------------------------------------------------------------------
# MUST HAVE #16 -- fail-safe-open watchdog
# ---------------------------------------------------------------------------


@dataclass
class PathPreferenceOverride:
    link: str
    flowKey: tuple
    altPath: str


class OptimizerWatchdog:
    def __init__(self, *, health_check_timeout_seconds: float = DEFAULT_HEALTH_CHECK_TIMEOUT_SECONDS) -> None:
        self.health_check_timeout_seconds = health_check_timeout_seconds
        self.last_heartbeat: Optional[datetime] = None
        self._overrides: list[PathPreferenceOverride] = []

    def heartbeat(self, at: datetime) -> None:
        self.last_heartbeat = at

    def apply_override(self, override: PathPreferenceOverride) -> None:
        self._overrides.append(override)

    def is_optimizer_healthy(self, at: datetime) -> bool:
        if self.last_heartbeat is None:
            return False
        return (at - self.last_heartbeat).total_seconds() <= self.health_check_timeout_seconds

    def active_overrides(self, at: datetime) -> list[PathPreferenceOverride]:
        """
        Underlying traffic always flows via default ECMP/BGP; this is the
        list of *additional* preference overrides currently in effect.
        Always empty (falls back to default ECMP only) whenever the
        optimizer is unhealthy, regardless of what was previously applied
        -- the fail-safe-open story is that traffic never depends on the
        optimizer being up.
        """
        if not self.is_optimizer_healthy(at):
            return []
        return list(self._overrides)

    def revert_all(self) -> None:
        self._overrides.clear()


# ---------------------------------------------------------------------------
# MUST HAVE #17 -- scope auto-reroute to the narrow, pre-validated case
# ---------------------------------------------------------------------------


def resolve_latency_sensitivity(
    owning_vm_id: str,
    *,
    store: WorkloadClassificationStore = classification_store,
) -> bool:
    """flow.latencySensitive = (classification !== "deferrable")."""
    return not store.is_deferrable(owning_vm_id)


def tag_latency_sensitivity(
    flow: Flow,
    owning_vm_id: str,
    *,
    store: WorkloadClassificationStore = classification_store,
) -> Flow:
    return flow.model_copy(update={"latencySensitive": resolve_latency_sensitivity(owning_vm_id, store=store)})


def auto_reroute_allowed(
    flow: Flow,
    current_link: str,
    congestion: CongestionTracker,
    alt_path_utilization_pct: Optional[float],
    *,
    at: datetime,
    alt_path_threshold_pct: float = DEFAULT_ALT_PATH_THRESHOLD_PCT,
) -> bool:
    """
    autoReroute(flow) allowed only if ALL true:
      flow.isElephant == true
      flow.latencySensitive == false
      congestionConfirmed(flow.currentLink) == true
      exists altPath with utilization < altPathThresholdPct
    else: recommend only, require operator approval via UI action.
    """
    if not flow.isElephant:
        return False
    if flow.latencySensitive is not False:
        # Fail-safe-open: unclassified (None) is treated the same as
        # latency-sensitive (True) -- never assume it's safe to reroute.
        return False
    if not congestion.congestion_confirmed(current_link, at):
        return False
    if alt_path_utilization_pct is None or alt_path_utilization_pct >= alt_path_threshold_pct:
        return False
    return True


# ---------------------------------------------------------------------------
# SHOULD HAVE #21 -- latency-sensitivity tagging cross-wired with
# PowerPrune, automating the IP->VM mapping this module's docstring above
# deferred from Phase 5.
# ---------------------------------------------------------------------------


class IpToVmLookup:
    """
    Simple IP->VM lookup table, synced from the hypervisor. A real
    implementation would sync this from vCenter/libvirt; no real
    hypervisor access exists here, so callers populate/update the mapping
    directly (the same adapter-boundary pattern used everywhere else in
    this codebase).
    """

    def __init__(self) -> None:
        self._ip_to_vm: dict[str, str] = {}

    def sync(self, mapping: dict[str, str]) -> None:
        self._ip_to_vm.update(mapping)

    def lookup(self, ip: str) -> Optional[str]:
        return self._ip_to_vm.get(ip)


def auto_tag_latency_sensitivity(
    flow: Flow,
    lookup: IpToVmLookup,
    *,
    store: WorkloadClassificationStore = classification_store,
) -> Flow:
    """
    Maps flow.srcIp to its owning VM via the IP->VM lookup table, then
    resolves latency sensitivity through the same shared classification
    store MUST HAVE #17's resolve_latency_sensitivity() already uses. If
    the owning VM can't be resolved (no mapping synced yet), the flow is
    returned unchanged -- latencySensitive stays None, never assumed
    non-latency-sensitive just because the lookup came up empty.
    """
    owning_vm_id = lookup.lookup(flow.srcIp)
    if owning_vm_id is None:
        return flow
    return tag_latency_sensitivity(flow, owning_vm_id, store=store)
