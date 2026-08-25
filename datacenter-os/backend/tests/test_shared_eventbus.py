import pytest

from shared.eventbus import EventBus


def test_subscriber_receives_published_payload():
    bus = EventBus()
    received = []
    bus.subscribe("idlehunter.capacity.updated", received.append)

    bus.publish("idlehunter.capacity.updated", {"poweredOnHostCount": 40})

    assert received == [{"poweredOnHostCount": 40}]


def test_multiple_subscribers_all_receive_the_event_in_order():
    bus = EventBus()
    order = []
    bus.subscribe("lightspeed.flow.classified", lambda p: order.append(("first", p)))
    bus.subscribe("lightspeed.flow.classified", lambda p: order.append(("second", p)))

    bus.publish("lightspeed.flow.classified", "flow-123")

    assert order == [("first", "flow-123"), ("second", "flow-123")]


def test_subscriber_only_receives_events_for_its_topic():
    bus = EventBus()
    capacity_events = []
    headroom_events = []
    bus.subscribe("idlehunter.capacity.updated", capacity_events.append)
    bus.subscribe("thermaltrace.headroom.updated", headroom_events.append)

    bus.publish("idlehunter.capacity.updated", "capacity-payload")

    assert capacity_events == ["capacity-payload"]
    assert headroom_events == []


def test_unsubscribe_stops_further_delivery():
    bus = EventBus()
    received = []

    def handler(payload):
        received.append(payload)

    bus.subscribe("carbonclock.job.scheduled", handler)
    bus.publish("carbonclock.job.scheduled", "job-1")
    bus.unsubscribe("carbonclock.job.scheduled", handler)
    bus.publish("carbonclock.job.scheduled", "job-2")

    assert received == ["job-1"]


def test_publishing_to_unknown_topic_raises():
    bus = EventBus()
    with pytest.raises(ValueError):
        bus.publish("not.a.real.topic", {})


def test_subscribing_to_unknown_topic_raises():
    bus = EventBus()
    with pytest.raises(ValueError):
        bus.subscribe("not.a.real.topic", lambda payload: None)


def test_one_failing_subscriber_does_not_block_the_others():
    bus = EventBus()
    received = []

    def broken_handler(payload):
        raise RuntimeError("boom")

    bus.subscribe("idlehunter.workload.classified", broken_handler)
    bus.subscribe("idlehunter.workload.classified", received.append)

    bus.publish("idlehunter.workload.classified", "vm-1")

    assert received == ["vm-1"]
