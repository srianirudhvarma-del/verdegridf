"""
thermos/control.py -- MUST HAVE #22: supervised (human-approved)
closed-loop control.

Every ActionRecommendation requires explicit operator approval before
execution, every time, until the trust ladder is explicitly enabled by an
operator for that action type. Trust-ladder eligibility (M consecutive
approvals with no overrides/reversals) only makes enabling the toggle
*valid* -- it is never flipped automatically. This is the same
fail-safe-open shape as every other classification in this codebase:
nothing escalates its own privilege silently.
"""

from typing import Literal, Optional

from pydantic import BaseModel

ActionType = Literal["adjust_setpoint", "adjust_fan_speed", "defer_job"]
ActionStatus = Literal["pending", "approved", "rejected", "auto_executed"]


class ActionRecommendation(BaseModel):
    id: str
    type: ActionType
    rackId: str
    magnitude: float
    predictedBenefit: str
    status: ActionStatus = "pending"


# Methodology: "after M consecutive operator approvals of the same type
# with no overrides/reversals." M isn't given an exact number -- a
# documented default, tunable per deployment.
DEFAULT_TRUST_LADDER_THRESHOLD = 5


class ActionRecommendationQueue:
    def __init__(self, *, trust_ladder_threshold: int = DEFAULT_TRUST_LADDER_THRESHOLD) -> None:
        if trust_ladder_threshold < 1:
            raise ValueError("trust_ladder_threshold must be >= 1")
        self.trust_ladder_threshold = trust_ladder_threshold
        self._recommendations: dict[str, ActionRecommendation] = {}
        self._consecutive_approvals: dict[ActionType, int] = {}
        self._auto_execute_enabled: set[ActionType] = set()

    def submit(self, recommendation: ActionRecommendation) -> ActionRecommendation:
        """
        A recommendation of a type with auto-execute already enabled
        bypasses the approval queue; everything else always starts
        "pending", regardless of how many past approvals that type has.
        """
        status: ActionStatus = "auto_executed" if recommendation.type in self._auto_execute_enabled else "pending"
        recommendation = recommendation.model_copy(update={"status": status})
        self._recommendations[recommendation.id] = recommendation
        return recommendation

    def approve(self, recommendation_id: str) -> ActionRecommendation:
        rec = self._require_pending(recommendation_id)
        rec = rec.model_copy(update={"status": "approved"})
        self._recommendations[rec.id] = rec
        self._consecutive_approvals[rec.type] = self._consecutive_approvals.get(rec.type, 0) + 1
        return rec

    def reject(self, recommendation_id: str) -> ActionRecommendation:
        rec = self._require_pending(recommendation_id)
        rec = rec.model_copy(update={"status": "rejected"})
        self._recommendations[rec.id] = rec
        self._record_override(rec.type)
        return rec

    def override_auto_executed(self, recommendation_id: str) -> ActionRecommendation:
        """
        An operator reverses a previously auto-executed action -- exactly
        the "reversal" that breaks trust. Resets the consecutive-approval
        streak and immediately revokes auto-execute for the type; an
        operator must explicitly re-opt-in later, after rebuilding trust.
        """
        rec = self._recommendations.get(recommendation_id)
        if rec is None or rec.status != "auto_executed":
            raise ValueError(f"recommendation {recommendation_id!r} is not auto_executed")
        rec = rec.model_copy(update={"status": "rejected"})
        self._recommendations[rec.id] = rec
        self._record_override(rec.type)
        return rec

    def _record_override(self, action_type: ActionType) -> None:
        self._consecutive_approvals[action_type] = 0
        self._auto_execute_enabled.discard(action_type)

    def is_trust_ladder_eligible(self, action_type: ActionType) -> bool:
        return self._consecutive_approvals.get(action_type, 0) >= self.trust_ladder_threshold

    def enable_auto_execute(self, action_type: ActionType) -> None:
        """The explicit operator opt-in. Hitting the threshold only makes this call valid -- it never happens on its own."""
        if not self.is_trust_ladder_eligible(action_type):
            raise ValueError(
                f"{action_type!r} is not yet trust-ladder eligible "
                f"({self._consecutive_approvals.get(action_type, 0)}/{self.trust_ladder_threshold} consecutive approvals)"
            )
        self._auto_execute_enabled.add(action_type)

    def disable_auto_execute(self, action_type: ActionType) -> None:
        self._auto_execute_enabled.discard(action_type)

    def is_auto_execute_enabled(self, action_type: ActionType) -> bool:
        return action_type in self._auto_execute_enabled

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
