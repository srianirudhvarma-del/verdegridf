"""
powerprune/resilience.py -- SHOULD HAVE #6: failure-during-consolidation
handling.

Subscribes conceptually to hypervisor HA/failure events during an active
migration/consolidation window (callers invoke on_host_failure when their
own event source reports one). On failure: excludes the failed host from
future placement, marks every VM that was on it as top-priority (bypassing
the normal dwell/threshold gating), and logs the incident for audit.
"""

from dataclasses import dataclass


@dataclass
class FailureIncident:
    hostId: str
    timestamp: str
    vmsAffected: list[str]
    reason: str


class ConsolidationFailureHandler:
    def __init__(self) -> None:
        self._excluded_hosts: set[str] = set()
        self._priority_vms: set[str] = set()
        self._incidents: list[FailureIncident] = []

    def on_host_failure(
        self,
        host_id: str,
        vms_on_host: list[str],
        *,
        timestamp: str,
        reason: str = "hypervisor HA failure event",
    ) -> FailureIncident:
        self._excluded_hosts.add(host_id)
        self._priority_vms.update(vms_on_host)
        incident = FailureIncident(hostId=host_id, timestamp=timestamp, vmsAffected=list(vms_on_host), reason=reason)
        self._incidents.append(incident)
        return incident

    def is_host_excluded(self, host_id: str) -> bool:
        return host_id in self._excluded_hosts

    def filter_candidate_hosts(self, host_ids: list[str]) -> list[str]:
        """Re-run the placement optimizer excluding the failed host(s)."""
        return [h for h in host_ids if h not in self._excluded_hosts]

    def is_top_priority(self, vm_id: str) -> bool:
        """VMs that were on a failed host bypass the normal dwell/threshold gating."""
        return vm_id in self._priority_vms

    def clear_priority(self, vm_id: str) -> None:
        """Called once the VM has actually been re-placed -- no longer needs top-priority treatment."""
        self._priority_vms.discard(vm_id)

    def incidents(self) -> list[FailureIncident]:
        return list(self._incidents)
