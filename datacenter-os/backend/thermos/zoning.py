"""
thermos/zoning.py -- SHOULD HAVE #24: thermal zoning and adaptive
setpoints.

Cluster racks into zones based on measured airflow/thermal coupling
(correlation of temperature deltas between racks); allow a per-zone
setpoint rather than one facility-wide setpoint, feeding into the same
ActionRecommendation queue (thermos/control.py, MUST HAVE #22).
"""

import math
import statistics
from dataclasses import dataclass

from thermos.control import ActionRecommendation

DEFAULT_CORRELATION_THRESHOLD = 0.7
DEFAULT_FACILITY_SETPOINT_CELSIUS = 22.0


def temperature_delta_correlation(deltas_a: list[float], deltas_b: list[float]) -> float:
    """Pearson correlation between two racks' temperature-delta time series."""
    if len(deltas_a) != len(deltas_b) or len(deltas_a) < 2:
        raise ValueError("need two equal-length series of at least 2 samples")

    mean_a, mean_b = statistics.mean(deltas_a), statistics.mean(deltas_b)
    covariance = sum((a - mean_a) * (b - mean_b) for a, b in zip(deltas_a, deltas_b))
    std_a = math.sqrt(sum((a - mean_a) ** 2 for a in deltas_a))
    std_b = math.sqrt(sum((b - mean_b) ** 2 for b in deltas_b))

    if std_a == 0 or std_b == 0:
        return 0.0
    return covariance / (std_a * std_b)


def cluster_racks_into_zones(
    rack_ids: list[str],
    delta_series: dict[str, list[float]],
    *,
    correlation_threshold: float = DEFAULT_CORRELATION_THRESHOLD,
) -> dict[str, list[str]]:
    """
    Simple greedy clustering: a rack joins the first existing zone whose
    representative rack's temperature-delta series correlates with it
    above correlation_threshold; otherwise it starts a new zone. Not a
    full hierarchical-clustering implementation -- a documented, simple
    approach sufficient for grouping racks with real measured coupling.
    """
    zones: dict[str, list[str]] = {}

    for rack_id in rack_ids:
        placed = False
        for zone_id, members in zones.items():
            representative = members[0]
            correlation = temperature_delta_correlation(delta_series[rack_id], delta_series[representative])
            if correlation >= correlation_threshold:
                members.append(rack_id)
                placed = True
                break
        if not placed:
            zones[f"zone-{len(zones) + 1}"] = [rack_id]

    return zones


class ZoneSetpointRegistry:
    def __init__(self, *, default_setpoint_celsius: float = DEFAULT_FACILITY_SETPOINT_CELSIUS) -> None:
        self.default_setpoint_celsius = default_setpoint_celsius
        self._setpoints: dict[str, float] = {}

    def set_zone_setpoint(self, zone_id: str, setpoint_celsius: float) -> None:
        self._setpoints[zone_id] = setpoint_celsius

    def get_setpoint(self, zone_id: str) -> float:
        """Falls back to the facility-wide default for any zone without an explicit override."""
        return self._setpoints.get(zone_id, self.default_setpoint_celsius)


def build_setpoint_recommendation(
    recommendation_id: str,
    zone_id: str,
    rack_id: str,
    current_setpoint_celsius: float,
    target_setpoint_celsius: float,
) -> ActionRecommendation:
    """Feeds a zone-setpoint adjustment into the same supervised approval queue as any other action."""
    return ActionRecommendation(
        id=recommendation_id,
        type="adjust_setpoint",
        rackId=rack_id,
        magnitude=target_setpoint_celsius - current_setpoint_celsius,
        predictedBenefit=f"zone {zone_id} setpoint {current_setpoint_celsius}C -> {target_setpoint_celsius}C",
    )
