import asyncio
import uuid as uuidlib

from server.core.events import Event, EventBus
from server.core.orchestrator import GOVERNANCE_GUIDANCE, Orchestrator
from server.tools import ingest_event


async def _capture(bus: EventBus, evt_type: str):
    seen = []

    async def h(evt: Event):
        seen.append(evt)

    await bus.subscribe(evt_type, h)
    return seen


def test_ingest_event_valid_publishes_and_returns_ack(monkeypatch):
    # Inject a fresh bus into the tool
    bus = EventBus()
    monkeypatch.setattr(ingest_event, "bus", bus)

    # Capture events
    seen = asyncio.run(_capture(bus, "conversation.message"))

    req = {
        "type": "conversation.message",
        "projectId": "p1",
        "role": "user",
        "content": "hello world",
    }
    resp = asyncio.run(ingest_event.handler(req))

    assert resp["status"] == "ok"
    assert resp["type"] == "conversation.message"
    assert resp["projectId"] == "p1"
    # requestId is UUID
    uuidlib.UUID(resp["requestId"])

    assert bus.events_published_total["conversation.message"] == 1
    # one handler consumed
    assert len(seen) == 1
    assert seen[0].payload["role"] == "user"
    assert seen[0].payload["content"] == "hello world"


def test_ingest_event_rejects_missing_content(monkeypatch):
    bus = EventBus()
    monkeypatch.setattr(ingest_event, "bus", bus)

    req = {
        "type": "conversation.message",
        "projectId": "p1",
        # missing content
    }
    resp = asyncio.run(ingest_event.handler(req))

    assert "error" in resp
    assert resp["error"]["code"] == "ERR.BAD_REQUEST"
    assert bus.events_published_total["conversation.message"] == 0


def test_ingest_event_length_cap(monkeypatch):
    bus = EventBus()
    monkeypatch.setattr(ingest_event, "bus", bus)
    # enforce tiny cap without re-importing module
    monkeypatch.setattr(ingest_event, "MAX_CONTENT", 1)

    req = {
        "type": "conversation.message",
        "projectId": "p1",
        "content": "too long",  # length > 1
    }
    resp = asyncio.run(ingest_event.handler(req))

    assert "error" in resp
    assert resp["error"]["code"] == "ERR.BAD_REQUEST"
    assert "exceeds max length" in resp["error"]["message"]


def test_ingest_event_role_normalization(monkeypatch):
    bus = EventBus()
    monkeypatch.setattr(ingest_event, "bus", bus)
    seen = asyncio.run(_capture(bus, "conversation.message"))

    req = {
        "type": "conversation.message",
        "projectId": "p1",
        "role": "User",
        "content": "hi",
    }
    asyncio.run(ingest_event.handler(req))

    assert len(seen) == 1
    assert seen[0].payload["role"] == "user"


def test_ingest_event_project_id_normalization(monkeypatch):
    bus = EventBus()
    monkeypatch.setattr(ingest_event, "bus", bus)
    seen = asyncio.run(_capture(bus, "conversation.message"))

    req = {
        "type": "conversation.message",
        "projectId": "  Project-XYZ  ",
        "role": "user",
        "content": "hi",
    }

    resp = asyncio.run(ingest_event.handler(req))

    assert resp["status"] == "ok"
    assert resp["projectId"] == "project-xyz"
    assert len(seen) == 1
    assert seen[0].project_id == "project-xyz"


def test_ingest_event_project_id_invalid_rejected(monkeypatch):
    bus = EventBus()
    monkeypatch.setattr(ingest_event, "bus", bus)

    req = {
        "type": "conversation.message",
        "projectId": "Invalid Project!",
        "role": "user",
        "content": "hi",
    }

    resp = asyncio.run(ingest_event.handler(req))

    assert "error" in resp
    assert resp["error"]["code"] == "ERR.BAD_REQUEST"
    assert "projectId" in resp["error"]["message"]

def test_conversation_event_emits_governance_guidance(monkeypatch):
    bus = EventBus()
    orch = Orchestrator(bus)
    monkeypatch.setattr(ingest_event, "bus", bus)

    governance_seen = asyncio.run(_capture(bus, GOVERNANCE_GUIDANCE))
    asyncio.run(orch.start())

    req = {
        "type": "conversation.message",
        "projectId": "p1",
        "role": "user",
        "content": "I want to build a secure REST API with authentication",
    }
    resp = asyncio.run(ingest_event.handler(req))

    assert resp["status"] == "ok"
    assert len(governance_seen) == 1

    evt = governance_seen[0]
    assert evt.type == GOVERNANCE_GUIDANCE
    assert evt.project_id == "p1"
    payload = evt.payload
    assert isinstance(payload, dict)
    assert payload.get("content")
    assert payload.get("source", {}).get("request_id") == resp["requestId"]

    asyncio.run(orch.stop())
