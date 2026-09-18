import pytest

from thermos.control import ActionRecommendation, ActionRecommendationQueue


def make_rec(rec_id, action_type="adjust_setpoint", rack_id="rack-1"):
    return ActionRecommendation(
        id=rec_id, type=action_type, rackId=rack_id, magnitude=1.5, predictedBenefit="0.3C headroom"
    )


def test_new_recommendation_always_starts_pending():
    queue = ActionRecommendationQueue()
    rec = queue.submit(make_rec("rec-1"))
    assert rec.status == "pending"


def test_approve_transitions_to_approved():
    queue = ActionRecommendationQueue()
    queue.submit(make_rec("rec-1"))
    rec = queue.approve("rec-1")
    assert rec.status == "approved"


def test_reject_transitions_to_rejected():
    queue = ActionRecommendationQueue()
    queue.submit(make_rec("rec-1"))
    rec = queue.reject("rec-1")
    assert rec.status == "rejected"


def test_cannot_approve_a_recommendation_twice():
    queue = ActionRecommendationQueue()
    queue.submit(make_rec("rec-1"))
    queue.approve("rec-1")
    with pytest.raises(ValueError):
        queue.approve("rec-1")


# ---------------------------------------------------------------------------
# Acceptance test: every recommendation requires approval, every time,
# until the trust ladder is explicitly enabled by an operator.
# ---------------------------------------------------------------------------


def test_recommendations_require_approval_every_time_below_the_threshold():
    queue = ActionRecommendationQueue(trust_ladder_threshold=3)
    for i in range(5):
        rec = queue.submit(make_rec(f"rec-{i}"))
        assert rec.status == "pending"
        queue.approve(f"rec-{i}")


def test_reaching_the_threshold_does_not_silently_enable_auto_execute():
    queue = ActionRecommendationQueue(trust_ladder_threshold=3)
    for i in range(3):
        queue.submit(make_rec(f"rec-{i}"))
        queue.approve(f"rec-{i}")

    assert queue.is_trust_ladder_eligible("adjust_setpoint") is True
    assert queue.is_auto_execute_enabled("adjust_setpoint") is False

    # a new recommendation still requires approval -- eligibility alone
    # changes nothing about behavior.
    rec = queue.submit(make_rec("rec-next"))
    assert rec.status == "pending"


def test_enabling_auto_execute_before_eligible_raises():
    queue = ActionRecommendationQueue(trust_ladder_threshold=3)
    queue.submit(make_rec("rec-1"))
    queue.approve("rec-1")

    with pytest.raises(ValueError):
        queue.enable_auto_execute("adjust_setpoint")


def test_explicit_enable_after_eligibility_bypasses_the_queue():
    queue = ActionRecommendationQueue(trust_ladder_threshold=2)
    queue.submit(make_rec("rec-1"))
    queue.approve("rec-1")
    queue.submit(make_rec("rec-2"))
    queue.approve("rec-2")

    queue.enable_auto_execute("adjust_setpoint")
    assert queue.is_auto_execute_enabled("adjust_setpoint") is True

    rec = queue.submit(make_rec("rec-3"))
    assert rec.status == "auto_executed"


def test_trust_ladder_is_scoped_per_action_type():
    queue = ActionRecommendationQueue(trust_ladder_threshold=2)
    queue.submit(make_rec("rec-1", action_type="adjust_setpoint"))
    queue.approve("rec-1")
    queue.submit(make_rec("rec-2", action_type="adjust_setpoint"))
    queue.approve("rec-2")

    assert queue.is_trust_ladder_eligible("adjust_setpoint") is True
    assert queue.is_trust_ladder_eligible("adjust_fan_speed") is False


def test_rejection_resets_the_consecutive_approval_streak():
    queue = ActionRecommendationQueue(trust_ladder_threshold=3)
    queue.submit(make_rec("rec-1"))
    queue.approve("rec-1")
    queue.submit(make_rec("rec-2"))
    queue.approve("rec-2")
    queue.submit(make_rec("rec-3"))
    queue.reject("rec-3")  # breaks the streak

    queue.submit(make_rec("rec-4"))
    queue.approve("rec-4")

    assert queue.is_trust_ladder_eligible("adjust_setpoint") is False  # only 1 consecutive approval since the reject


def test_overriding_an_auto_executed_action_revokes_trust_immediately():
    queue = ActionRecommendationQueue(trust_ladder_threshold=2)
    queue.submit(make_rec("rec-1"))
    queue.approve("rec-1")
    queue.submit(make_rec("rec-2"))
    queue.approve("rec-2")
    queue.enable_auto_execute("adjust_setpoint")

    rec = queue.submit(make_rec("rec-3"))
    assert rec.status == "auto_executed"

    queue.override_auto_executed("rec-3")

    assert queue.is_auto_execute_enabled("adjust_setpoint") is False
    assert queue.is_trust_ladder_eligible("adjust_setpoint") is False

    # a new recommendation of that type must go back through the queue.
    next_rec = queue.submit(make_rec("rec-4"))
    assert next_rec.status == "pending"


def test_pending_lists_only_undecided_recommendations():
    queue = ActionRecommendationQueue()
    queue.submit(make_rec("rec-1"))
    queue.submit(make_rec("rec-2"))
    queue.approve("rec-1")

    pending_ids = [r.id for r in queue.pending()]
    assert pending_ids == ["rec-2"]
