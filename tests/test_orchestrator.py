import asyncio
import time

from server.core.events import Event, EventBus
from server.core.orchestrator import Orchestrator


def _evt(payload: dict | None = None) -> Event:
    return Event(
        type="conversation.message",
        project_id="p1",
        payload=payload or {"content": "hi"},
        ts=time.time(),
    )


def test_orchestrator_lifecycle():
    bus = EventBus()
    orch = Orchestrator(bus)

    assert orch.is_running is False
    asyncio.run(orch.start())
    assert orch.is_running is True
    asyncio.run(orch.stop())
    assert orch.is_running is False


def test_orchestrator_handles_conversation_message():
    bus = EventBus()
    orch = Orchestrator(bus)

    asyncio.run(orch.start())
    asyncio.run(bus.publish(_evt({"content": "hello"})))

    assert orch.events_handled_total["conversation.message"] == 1
    asyncio.run(orch.stop())


def test_orchestrator_error_path_is_counted():
    bus = EventBus()
    orch = Orchestrator(bus)

    asyncio.run(orch.start())
    asyncio.run(bus.publish(_evt({"force_error": True})))

    assert orch.handler_errors_total["conversation.message"] == 1
    asyncio.run(orch.stop())
