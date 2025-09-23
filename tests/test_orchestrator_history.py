import asyncio
import importlib
import time

import pytest

from server.core.events import Event, EventBus
from server.core.orchestrator import CONV_MSG, Orchestrator

orchestrator_module = importlib.import_module("server.core.orchestrator")


async def _emit_history(orch: Orchestrator, event: Event) -> None:
    await orch._maybe_emit_governance(event, event.payload)


def _make_event(project_id: str, content: str) -> Event:
    return Event(
        type=CONV_MSG,
        project_id=project_id,
        payload={"content": content},
        ts=time.time(),
    )


@pytest.fixture(autouse=True)
def _reset_governance(monkeypatch):
    async def _noop(*args, **kwargs):  # noqa: ANN001, ARG001 - test stub
        return None

    monkeypatch.setattr(orchestrator_module, "activate_pre_action_governance", _noop)


def test_history_eviction_by_capacity(monkeypatch):
    limit = 10
    monkeypatch.setattr(orchestrator_module, "_HISTORY_MAX_PROJECTS", limit)
    monkeypatch.setattr(orchestrator_module, "_HISTORY_IDLE_TTL_SECONDS", 3600)

    bus = EventBus()
    orch = Orchestrator(bus)

    total_projects = limit * 5
    for idx in range(total_projects):
        event = _make_event(f"Project-{idx}", f"msg-{idx}")
        asyncio.run(_emit_history(orch, event))

    assert len(orch._recent_history) == limit
    expected = [f"project-{idx}" for idx in range(total_projects - limit, total_projects)]
    assert list(orch._recent_history.keys()) == expected


def test_history_eviction_by_ttl(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "_HISTORY_MAX_PROJECTS", 100)
    monkeypatch.setattr(orchestrator_module, "_HISTORY_IDLE_TTL_SECONDS", 5)

    clock = {"value": 0.0}

    def fake_monotonic() -> float:
        return clock["value"]

    monkeypatch.setattr(orchestrator_module.time, "monotonic", fake_monotonic)

    bus = EventBus()
    orch = Orchestrator(bus)

    first = _make_event("Project-1", "first")
    asyncio.run(_emit_history(orch, first))
    assert "project-1" in orch._recent_history

    clock["value"] = 10.0  # advance beyond TTL
    second = _make_event("Project-2", "second")
    asyncio.run(_emit_history(orch, second))

    assert "project-1" not in orch._recent_history
    assert "project-2" in orch._recent_history
