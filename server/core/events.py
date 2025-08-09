"""
Event Bus: in-memory async pub/sub for Neural Forge Phase 1

- Event: typed, project-scoped, carries payload and request_id for traceability
- EventBus: subscribe/unsubscribe/publish with per-type handler registry
- Metrics: in-memory counters for published/consumed/errors by event type
- Logging: structured logs via server.utils.logger.log_json

Phase 1 scope: pure in-memory; no external broker or DB. Safe defaults, error isolation.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, DefaultDict, Dict, List, Optional

from prometheus_client import Counter

from server.utils.logger import log_json


@dataclass(slots=True)
class Event:
    """Event model.

    Attributes:
        type: Event type, e.g. "conversation.message".
        project_id: Project identifier for multi-tenant isolation.
        payload: Arbitrary event payload (must be JSON-serializable if logged).
        ts: Event timestamp (epoch seconds, float).
        request_id: Optional correlation/request id for tracing across components.
    """

    type: str
    project_id: str
    payload: Dict[str, Any]
    ts: float
    request_id: Optional[str] = None


Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Lightweight async EventBus with per-type subscriptions.

    Handlers are awaited sequentially per publish to ensure deterministic ordering.
    Errors in a handler are isolated: they are logged and counted, but do not stop
    other handlers from running.
    """

    def __init__(self) -> None:
        self._handlers: DefaultDict[str, List[Handler]] = defaultdict(list)
        # In-memory counters (Phase 1). Prometheus metrics are wired in app layer later.
        self.events_published_total: DefaultDict[str, int] = defaultdict(int)
        self.events_consumed_total: DefaultDict[str, int] = defaultdict(int)
        self.event_handler_errors_total: DefaultDict[str, int] = defaultdict(int)
        # Simple lock to serialize subscribe/unsubscribe modifications if needed.
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, handler: Handler) -> None:
        """Register an async handler for an event type.

        Note: idempotent add (no duplicate entries) by identity.
        """
        async with self._lock:
            handlers = self._handlers[event_type]
            if handler not in handlers:
                handlers.append(handler)
                log_json(
                    "info",
                    "eventbus.subscribe",
                    evt_type=event_type,
                    handler=str(getattr(handler, "__name__", repr(handler))),
                )

    async def unsubscribe(self, event_type: str, handler: Handler) -> None:
        """Remove a previously-registered handler if present."""
        async with self._lock:
            handlers = self._handlers.get(event_type)
            if handlers and handler in handlers:
                handlers.remove(handler)
                log_json(
                    "info",
                    "eventbus.unsubscribe",
                    evt_type=event_type,
                    handler=str(getattr(handler, "__name__", repr(handler))),
                )

    async def publish(self, event: Event) -> None:
        """Publish an event and synchronously await all handlers for that type.

        Handlers are executed sequentially in registration order.
        """
        evt_type = event.type
        self.events_published_total[evt_type] += 1
        EVENTS_PUBLISHED.labels(evt_type).inc()
        log_json(
            "info",
            "eventbus.publish",
            evt_type=evt_type,
            project_id=event.project_id,
            request_id=event.request_id,
            phase="publish",
        )
        # Snapshot handlers to avoid holding lock during handler execution
        handlers = list(self._handlers.get(evt_type, ()))
        for h in handlers:
            try:
                await h(event)
                self.events_consumed_total[evt_type] += 1
                EVENTS_CONSUMED.labels(evt_type).inc()
                log_json(
                    "info",
                    "eventbus.consume",
                    evt_type=evt_type,
                    project_id=event.project_id,
                    request_id=event.request_id,
                    phase="consume",
                )
            except Exception as e:  # noqa: BLE001 - log and continue by design
                self.event_handler_errors_total[evt_type] += 1
                EVENT_HANDLER_ERRORS.labels(evt_type).inc()
                log_json(
                    "error",
                    "eventbus.handler_error",
                    evt_type=evt_type,
                    project_id=event.project_id,
                    request_id=event.request_id,
                    error=str(e),
                    phase="error",
                )

    # Convenience helper for immediate publish without a pre-built Event
    async def publish_simple(
        self,
        *,
        type: str,
        project_id: str,
        payload: Dict[str, Any],
        request_id: Optional[str] = None,
        ts: Optional[float] = None,
    ) -> None:
        await self.publish(
            Event(
                type=type,
                project_id=project_id,
                payload=payload,
                ts=ts if ts is not None else time.time(),
                request_id=request_id,
            )
        )


# Singleton instance used across the app in Phase 1
bus = EventBus()

# Prometheus counters (module-level to avoid circular imports)
EVENTS_PUBLISHED = Counter("events_published_total", "Total events published", ["type"])
EVENTS_CONSUMED = Counter("events_consumed_total", "Total events consumed", ["type"])
EVENT_HANDLER_ERRORS = Counter("event_handler_errors_total", "Total event handler errors", ["type"])
