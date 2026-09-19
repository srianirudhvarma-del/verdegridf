"""
Supervised approval queue for anything that would touch real hardware
beyond a sleep prompt (currently: raising fan speed). Every recommendation
requires an explicit operator approval, every time -- there is no
auto-execute path. That's a deliberate, permanent choice for this project
(unlike a full trust-ladder system): fan actuation touches BIOS/EC-level
hardware control, so a human stays in the loop every time, not just until
enough approvals accumulate.
"""

from typing import Literal, Optional

from pydantic import BaseModel

ActionType = Literal["raise_fan_speed"]
ActionStatus = Literal["pending", "approved", "rejected"]


class ActionRecommendation(BaseModel):
    id: str
    type: ActionType
    hostId: str
    predictedBenefit: str
    status: ActionStatus = "pending"


class ActionQueue:
    def __init__(self) -> None:
        self._recommendations: dict[str, ActionRecommendation] = {}

    def submit(self, recommendation: ActionRecommendation) -> ActionRecommendation:
        self._recommendations[recommendation.id] = recommendation
        return recommendation

    def approve(self, recommendation_id: str) -> ActionRecommendation:
        rec = self._require_pending(recommendation_id)
        rec = rec.model_copy(update={"status": "approved"})
        self._recommendations[rec.id] = rec
        return rec

    def reject(self, recommendation_id: str) -> ActionRecommendation:
        rec = self._require_pending(recommendation_id)
        rec = rec.model_copy(update={"status": "rejected"})
        self._recommendations[rec.id] = rec
        return rec

    def get(self, recommendation_id: str) -> Optional[ActionRecommendation]:
        return self._recommendations.get(recommendation_id)

    def pending(self) -> list[ActionRecommendation]:
        return [r for r in self._recommendations.values() if r.status == "pending"]

    def _require_pending(self, recommendation_id: str) -> ActionRecommendation:
        rec = self._recommendations.get(recommendation_id)
        if rec is None:
            raise KeyError(f"unknown recommendation: {recommendation_id!r}")
        if rec.status != "pending":
            raise ValueError(f"recommendation {recommendation_id!r} is not pending (status={rec.status!r})")
        return rec
