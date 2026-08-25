"""
thermaltrace/maintenance.py -- SHOULD HAVE #25: predictive maintenance for
cooling equipment.

track fan/pump runHours and (if available) current-draw signature over time
flag maintenance_due if runHours > ratedServiceInterval
   OR current-draw trend deviates from its own historical baseline by > X%
   (simple trend/Z-score, same pattern as WaterWatch's sensor-drift check)
"""

from dataclasses import dataclass
from typing import Optional

# The methodology doesn't give an exact number for "X%" -- a documented
# default, same pattern as WaterWatch's sensor-drift threshold.
DEFAULT_CURRENT_DRAW_DEVIATION_THRESHOLD_PCT = 15.0


@dataclass
class MaintenanceFlag:
    equipmentId: str
    reason: str


def check_maintenance_due(
    equipment_id: str,
    run_hours: float,
    rated_service_interval_hours: float,
    current_draw_baseline: Optional[float],
    current_draw_latest: Optional[float],
    *,
    deviation_threshold_pct: float = DEFAULT_CURRENT_DRAW_DEVIATION_THRESHOLD_PCT,
) -> Optional[MaintenanceFlag]:
    if run_hours > rated_service_interval_hours:
        return MaintenanceFlag(
            equipmentId=equipment_id,
            reason=f"runHours {run_hours} exceeds rated service interval {rated_service_interval_hours}",
        )

    if current_draw_baseline is not None and current_draw_latest is not None and current_draw_baseline > 0:
        deviation_pct = abs(current_draw_latest - current_draw_baseline) / current_draw_baseline * 100.0
        if deviation_pct > deviation_threshold_pct:
            return MaintenanceFlag(
                equipmentId=equipment_id,
                reason=f"current-draw deviates {deviation_pct:.1f}% from its historical baseline (> {deviation_threshold_pct}%)",
            )

    return None
