import asyncio
import time
from typing import List

from server.core import Event, EventBus


def _make_event(evt_type: str = "conversation.message", project_id: str = "p1") -> Event:
    return Event(type=evt_type, project_id=project_id, payload={"msg": "hi"}, ts=time.time())


def test_publish_subscribe_single_handler():
    bus = EventBus()
    seen: List[Event] = []

    async def handler(evt: Event) -> None:
        seen.append(evt)

    asyncio.run(bus.subscribe("conversation.message", handler))
    asyncio.run(bus.publish(_make_event()))

    assert len(seen) == 1
    assert seen[0].payload["msg"] == "hi"
    assert bus.events_published_total["conversation.message"] == 1
    assert bus.events_consumed_total["conversation.message"] == 1
    assert bus.event_handler_errors_total["conversation.message"] == 0


def test_multiple_handlers_fifo_order():
    bus = EventBus()
    calls: List[str] = []

    async def h1(evt: Event) -> None:
        calls.append("h1")

    async def h2(evt: Event) -> None:
        calls.append("h2")

    asyncio.run(bus.subscribe("conversation.message", h1))
    asyncio.run(bus.subscribe("conversation.message", h2))
    asyncio.run(bus.publish(_make_event()))

    assert calls == ["h1", "h2"], f"Handlers executed out of order: {calls}"
    assert bus.events_published_total["conversation.message"] == 1
    assert bus.events_consumed_total["conversation.message"] == 2
    assert bus.event_handler_errors_total["conversation.message"] == 0


def test_handler_error_isolated():
    bus = EventBus()
    calls: List[str] = []

    async def bad(evt: Event) -> None:
        calls.append("bad")
        raise RuntimeError("boom")

    async def good(evt: Event) -> None:
        calls.append("good")

    asyncio.run(bus.subscribe("conversation.message", bad))
    asyncio.run(bus.subscribe("conversation.message", good))
    asyncio.run(bus.publish(_make_event()))

    # Both handlers were invoked; error isolated and counted
    assert calls == ["bad", "good"]
    assert bus.events_published_total["conversation.message"] == 1
    assert bus.events_consumed_total["conversation.message"] == 1  # only good succeeded
    assert bus.event_handler_errors_total["conversation.message"] == 1


def test_unsubscribe_stops_invocation():
    bus = EventBus()
    calls: List[str] = []

    async def h(evt: Event) -> None:
        calls.append("h")

    asyncio.run(bus.subscribe("conversation.message", h))
    asyncio.run(bus.unsubscribe("conversation.message", h))
    asyncio.run(bus.publish(_make_event()))

    assert calls == []
    assert bus.events_published_total["conversation.message"] == 1
    assert bus.events_consumed_total["conversation.message"] == 0
    assert bus.event_handler_errors_total["conversation.message"] == 0
