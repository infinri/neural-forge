"""
Orchestrator: subscribes to EventBus and coordinates processing of conversation events.

Phase 1 scope:
- Singleton orchestrator with start/stop and running state
- Subscribes to "conversation.message" events
- Stub handler updates in-memory metrics, logs, and exercises error path
- Background loop stub for future work/task processing
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, DefaultDict, Dict

from prometheus_client import Counter

from server.core.events import Event, EventBus, bus
from server.utils.logger import log_json

CONV_MSG = "conversation.message"


class Orchestrator:
    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._running = False
        self._lock = asyncio.Lock()
        self._bg_task: asyncio.Task | None = None
        # Metrics: Phase 1 in-memory
        self.events_handled_total: DefaultDict[str, int] = defaultdict(int)
        self.handler_errors_total: DefaultDict[str, int] = defaultdict(int)

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                return
            # Subscribe handlers
            await self._bus.subscribe(CONV_MSG, self._handle_conversation_message)
            self._running = True
            # Background loop stub
            self._bg_task = asyncio.create_task(self._run())
            log_json("info", "orchestrator.start_ok")

    async def stop(self) -> None:
        async with self._lock:
            if not self._running:
                return
            try:
                await self._bus.unsubscribe(CONV_MSG, self._handle_conversation_message)
            finally:
                self._running = False
                if self._bg_task:
                    self._bg_task.cancel()
                    try:
                        await self._bg_task
                    except asyncio.CancelledError:
                        pass
                    self._bg_task = None
                log_json("info", "orchestrator.stop_ok")

    async def _run(self) -> None:
        # Background loop stub for future processing
        try:
            while self._running:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass

    async def _handle_conversation_message(self, event: Event) -> None:
        # Structured log with content length to avoid logging full content by default
        content_len = 0
        try:
            payload: Dict[str, Any] = event.payload or {}
            msg = payload.get("content")
            content_len = len(msg) if isinstance(msg, str) else 0
            # Test-only hook: allow forcing an error to verify error path
            if payload.get("force_error"):
                raise RuntimeError("forced_error")

            # TODO: parse role, route by role/type in later phases
            self.events_handled_total[event.type] += 1
            log_json(
                "info",
                "orchestrator.handle",
                evt_type=event.type,
                project_id=event.project_id,
                request_id=event.request_id,
                content_len=content_len,
            )
        except Exception as e:  # noqa: BLE001 - intended isolation for handlers
            self.handler_errors_total[event.type] += 1
            ORCH_HANDLER_ERRORS.labels(event.type).inc()
            log_json(
                "error",
                "orchestrator.handler_error",
                evt_type=event.type,
                project_id=event.project_id,
                request_id=event.request_id,
                error=str(e),
            )
            # Re-raise to allow EventBus to record handler error metrics; EventBus
            # will isolate and continue with other handlers per design.
            raise


# Singleton orchestrator
orchestrator = Orchestrator(bus)

# Prometheus counter for orchestrator handler errors
ORCH_HANDLER_ERRORS = Counter(
    "orchestrator_handler_errors_total",
    "Total orchestrator handler errors",
    ["type"],
)
