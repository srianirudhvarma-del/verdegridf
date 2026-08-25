"""
lightspeed/topology.py -- SHOULD HAVE #19: automatic LLDP-based topology
discovery.

Poll LLDP neighbor tables per switch on a slower interval (topology
doesn't change often); build/update the network graph automatically
instead of a manually maintained config file. No real switch LLDP access
exists; get_neighbors() is supplied by the caller, same adapter pattern
every other module uses for its telemetry source (Phase 0 Decision #1).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

# Methodology: "e.g., every 5 min -- topology doesn't change often."
DEFAULT_LLDP_POLL_INTERVAL_SECONDS = 5 * 60.0


@dataclass(frozen=True)
class LldpNeighbor:
    localSwitch: str
    localPort: str
    remoteSwitch: str
    remotePort: str


class TopologyGraph:
    """Built/updated automatically from polled LLDP neighbor tables."""

    def __init__(self) -> None:
        self._edges: set[tuple[str, str]] = set()

    def ingest_neighbors(self, neighbors: list[LldpNeighbor]) -> None:
        for neighbor in neighbors:
            self._edges.add(tuple(sorted((neighbor.localSwitch, neighbor.remoteSwitch))))

    def neighbors_of(self, switch: str) -> set[str]:
        result = set()
        for a, b in self._edges:
            if a == switch:
                result.add(b)
            elif b == switch:
                result.add(a)
        return result

    def edges(self) -> set[tuple[str, str]]:
        return set(self._edges)


class LldpTopologyDiscovery:
    """Combines the slow poll cadence with graph building/updating."""

    def __init__(
        self,
        get_neighbors: Callable[[], list[LldpNeighbor]],
        *,
        poll_interval_seconds: float = DEFAULT_LLDP_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._get_neighbors = get_neighbors
        self.poll_interval_seconds = poll_interval_seconds
        self.graph = TopologyGraph()
        self._last_polled: Optional[datetime] = None

    def poll(self, at: datetime) -> bool:
        """Returns True if it actually refreshed the graph this call."""
        if self._last_polled is not None and (at - self._last_polled).total_seconds() < self.poll_interval_seconds:
            return False
        self.graph.ingest_neighbors(self._get_neighbors())
        self._last_polled = at
        return True
