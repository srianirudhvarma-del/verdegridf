"""
shared/eventbus.py

Minimal in-process pub/sub standing in for the methodology's "shared internal
event bus" (Section 0/2). No real message broker exists yet -- this is a
same-process substitute with the same publish/subscribe shape, so it can be
swapped for a real bus later without touching module logic.

Only the 5 topics in shared.contracts.Topic are valid. Publishing or
subscribing to anything else is a programming error, not a runtime
condition modules should handle -- it raises immediately.
"""

import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

from shared.contracts import TOPICS

Handler = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._validate_topic(topic)
        self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        self._validate_topic(topic)
        try:
            self._subscribers[topic].remove(handler)
        except ValueError:
            pass

    def publish(self, topic: str, payload: Any) -> None:
        """
        Synchronously calls every subscriber for `topic`, in subscription
        order. A handler that raises is logged and skipped -- it does not
        stop the remaining handlers from running, since one broken
        subscriber must never block the others (fail-safe-open for the
        bus itself).
        """
        self._validate_topic(topic)
        for handler in list(self._subscribers[topic]):
            try:
                handler(payload)
            except Exception:
                logger.exception("Subscriber to %r raised; continuing to next subscriber", topic)

    @staticmethod
    def _validate_topic(topic: str) -> None:
        if topic not in TOPICS:
            raise ValueError(f"Unknown topic: {topic!r}. Valid topics: {sorted(TOPICS)}")


# Process-wide singleton. Modules import this rather than constructing their
# own EventBus, so publishers and subscribers actually share a bus.
event_bus = EventBus()
