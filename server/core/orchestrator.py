"""
Orchestrator: subscribes to EventBus and coordinates processing of conversation events.

Phase 1 scope:
- Singleton orchestrator with start/stop and running state
- Subscribes to "conversation.message" events
- Stub handler updates in-memory metrics, logs, and exercises error path
- Background loop stub for future work/task processing

Watchdog (optional):
- Periodically scans for stale in-progress tasks and requeues or fails them
- Fully gated by environment variables to avoid impacting tests by default
"""
from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict, deque
from typing import Any, DefaultDict, Dict

from prometheus_client import Counter, Histogram

import server.observability.tracing as otel_tracing
from server.core.events import Event, EventBus, bus
from server.db.engine import get_async_engine
from server.db.repo import (
    watchdog_fail_stale_inprogress_pg,
    watchdog_requeue_stale_inprogress_pg,
)
from server.governance import activate_pre_action_governance
from server.utils.logger import log_json

CONV_MSG = "conversation.message"
GOVERNANCE_GUIDANCE = "governance.guidance"
_HISTORY_MAX_LEN = 5


class Orchestrator:
    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._running = False
        self._lock = asyncio.Lock()
        self._bg_task: asyncio.Task | None = None
        self._watchdog_task: asyncio.Task | None = None
        # Metrics: Phase 1 in-memory
        self.events_handled_total: DefaultDict[str, int] = defaultdict(int)
        self.handler_errors_total: DefaultDict[str, int] = defaultdict(int)
        self._recent_history: DefaultDict[str, deque[str]] = defaultdict(
            lambda: deque(maxlen=_HISTORY_MAX_LEN)
        )

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
            # Optional watchdog
            if _truthy(os.getenv("TASK_WATCHDOG_ENABLED", "false")):
                self._watchdog_task = asyncio.create_task(self._watchdog_loop())
                log_json("info", "watchdog.enabled")
            else:
                log_json("info", "watchdog.disabled")

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
                if self._watchdog_task:
                    self._watchdog_task.cancel()
                    try:
                        await self._watchdog_task
                    except asyncio.CancelledError:
                        pass
                    self._watchdog_task = None
                log_json("info", "orchestrator.stop_ok")

    async def _run(self) -> None:
        # Background loop stub for future processing
        try:
            while self._running:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass

    async def _watchdog_loop(self) -> None:
        """Periodic scanner that requeues or fails stale in-progress tasks.

        Controlled via env:
        - TASK_WATCHDOG_ENABLED: bool (default false)
        - TASK_WATCHDOG_ACTION: 'requeue' | 'fail' (default 'requeue')
        - TASK_WATCHDOG_TTL_SECONDS: int (default 600)
        - TASK_WATCHDOG_INTERVAL_SECONDS: int (default 30)
        - TASK_WATCHDOG_BATCH_LIMIT: int (default 100)
        - TASK_WATCHDOG_PROJECT_ID: optional str filter
        """
        try:
            while self._running:
                # Read each iteration to allow dynamic changes without restart
                enabled = _truthy(os.getenv("TASK_WATCHDOG_ENABLED", "false"))
                interval_s = _to_int(os.getenv("TASK_WATCHDOG_INTERVAL_SECONDS", "30"), 30)
                if not enabled:
                    await asyncio.sleep(max(1, interval_s))
                    continue

                action = (os.getenv("TASK_WATCHDOG_ACTION", "requeue") or "requeue").strip().lower()
                ttl_s = _to_int(os.getenv("TASK_WATCHDOG_TTL_SECONDS", "600"), 600)
                limit = _to_int(os.getenv("TASK_WATCHDOG_BATCH_LIMIT", "100"), 100)
                project_id = os.getenv("TASK_WATCHDOG_PROJECT_ID")

                gate_enabled = False
                try:
                    gate_enabled = bool(otel_tracing.is_tracing_enabled())
                except Exception:
                    gate_enabled = False
                provider_is_sdk = False
                try:
                    from opentelemetry import trace as _t

                    prov = _t.get_tracer_provider()
                    provider_is_sdk = hasattr(prov, "add_span_processor")
                except Exception:
                    provider_is_sdk = False

                _span_cm = None
                _span_obj = None
                if gate_enabled or provider_is_sdk:
                    try:
                        from opentelemetry import trace
                        tracer = trace.get_tracer("neural-forge")
                        _span_cm = tracer.start_as_current_span("Watchdog.scan")
                        _span_obj = _span_cm.__enter__()
                        try:
                            _span_obj.set_attribute("phase", "scan")
                            _span_obj.set_attribute("action", action)
                            _span_obj.set_attribute("ttl_seconds", int(ttl_s))
                            _span_obj.set_attribute("limit", int(limit))
                            if project_id:
                                _span_obj.set_attribute("project_id", project_id)
                        except Exception:
                            pass
                    except Exception:
                        _span_cm = None
                        _span_obj = None

                start = time.perf_counter()
                affected = 0
                engine = get_async_engine()
                if engine is None:
                    try:
                        log_json("warning", "watchdog.no_db")
                    except Exception:
                        pass
                    WATCHDOG_ERRORS_TOTAL.labels(action).inc()
                    await asyncio.sleep(max(1, interval_s))
                    if _span_cm is not None:
                        try:
                            _span_cm.__exit__(None, None, None)
                        except Exception:
                            pass
                    continue

                try:
                    if action == "fail":
                        affected = await watchdog_fail_stale_inprogress_pg(
                            engine,
                            ttl_seconds=ttl_s,
                            limit=limit,
                            project_id=project_id if project_id and project_id.strip() else None,
                            reason="ttl_exceeded",
                        )
                    else:
                        affected = await watchdog_requeue_stale_inprogress_pg(
                            engine,
                            ttl_seconds=ttl_s,
                            limit=limit,
                            project_id=project_id if project_id and project_id.strip() else None,
                        )
                    duration = time.perf_counter() - start
                    WATCHDOG_SCANS_TOTAL.labels(action).inc()
                    WATCHDOG_DURATION.labels(action).observe(duration)
                    outcome = "ok" if affected > 0 else "none"
                    WATCHDOG_ACTIONS_TOTAL.labels(action, outcome).inc()
                    try:
                        log_json(
                            "info",
                            "watchdog.scan",
                            action=action,
                            ttlSeconds=int(ttl_s),
                            limit=int(limit),
                            affected=int(affected),
                            projectId=project_id,
                            durationMs=int(duration * 1000),
                        )
                    except Exception:
                        pass
                    if _span_obj is not None:
                        try:
                            _span_obj.set_attribute("affected", int(affected))
                            _span_obj.set_attribute("duration_ms", int(duration * 1000))
                        except Exception:
                            pass
                except Exception as e:
                    WATCHDOG_ERRORS_TOTAL.labels(action).inc()
                    try:
                        log_json("error", "watchdog.scan_error", action=action, error=str(e))
                    except Exception:
                        pass
                    if _span_obj is not None:
                        try:
                            from opentelemetry.trace import Status, StatusCode

                            _span_obj.record_exception(e)
                            _span_obj.set_status(Status(StatusCode.ERROR))
                        except Exception:
                            pass
                finally:
                    if _span_cm is not None:
                        try:
                            _span_cm.__exit__(None, None, None)
                        except Exception:
                            pass
                await asyncio.sleep(max(1, interval_s))
        except asyncio.CancelledError:
            pass

    async def _handle_conversation_message(self, event: Event) -> None:
        # Structured log with content length to avoid logging full content by default
        content_len = 0
        _span_cm = None
        _span_obj = None
        try:
            _gate = bool(otel_tracing.is_tracing_enabled())
        except Exception:
            _gate = False
        # Also honor an active SDK tracer provider set by tests or runtime instrumentation
        _provider_is_sdk = False
        try:
            from opentelemetry import trace as _t
            prov = _t.get_tracer_provider()
            # Heuristic: SDK providers expose add_span_processor
            _provider_is_sdk = hasattr(prov, "add_span_processor")
        except Exception:
            _provider_is_sdk = False
        try:
            log_json("info", "orchestrator.gate_dbg", enabled=_gate, provider_is_sdk=_provider_is_sdk)
        except Exception:
            pass
        if _gate or _provider_is_sdk:
            try:
                from opentelemetry import trace

                tracer = trace.get_tracer("neural-forge")
                links = []
                # Best-effort link to upstream context; never fail span creation due to linking
                try:
                    if event.traceparent:
                        from opentelemetry.propagate import get_global_textmap
                        from opentelemetry.trace import Link

                        carrier = {"traceparent": event.traceparent}
                        ctx = get_global_textmap().extract(carrier)
                        parent_span = trace.get_current_span(ctx)
                        parent_sc = parent_span.get_span_context()
                        if parent_sc and getattr(parent_sc, "is_valid", False):
                            links = [Link(parent_sc)]
                except Exception:
                    links = []
                # Create child span with start_as_current_span for reliable activation
                _span_cm = tracer.start_as_current_span("Orchestrator.handle", links=links)
                _span_obj = _span_cm.__enter__()
                try:
                    sc = _span_obj.get_span_context()
                    from opentelemetry import trace as _t
                    cur = _t.get_current_span()
                    cur_sc = cur.get_span_context() if cur else None
                    log_json(
                        "info",
                        "orchestrator.span_started_dbg",
                        created_span_id=f"{sc.span_id:016x}" if getattr(sc, "span_id", None) is not None else None,
                        created_trace_id=f"{sc.trace_id:032x}" if getattr(sc, "trace_id", None) is not None else None,
                        current_span_id=f"{cur_sc.span_id:016x}" if cur_sc and getattr(cur_sc, "span_id", None) is not None else None,
                        current_trace_id=f"{cur_sc.trace_id:032x}" if cur_sc and getattr(cur_sc, "trace_id", None) is not None else None,
                    )
                except Exception:
                    pass
            except Exception as e:
                _span_cm = None
                _span_obj = None
                try:
                    log_json("error", "orchestrator.span_start_error", error=str(e))
                except Exception:
                    pass
        try:
            payload: Dict[str, Any] = event.payload or {}
            msg = payload.get("content")
            content_len = len(msg) if isinstance(msg, str) else 0
            # Test-only hook: allow forcing an error to verify error path
            if payload.get("force_error"):
                raise RuntimeError("forced_error")

            # TODO: parse role, route by role/type in later phases
            self.events_handled_total[event.type] += 1
            if _span_obj is not None:
                _span_obj.set_attribute("evt_type", event.type)
                _span_obj.set_attribute("project_id", event.project_id)
                if event.request_id:
                    _span_obj.set_attribute("request_id", event.request_id)
                _span_obj.set_attribute("content_len", content_len)
                _span_obj.set_attribute("phase", "consume")
            log_json(
                "info",
                "orchestrator.handle",
                evt_type=event.type,
                project_id=event.project_id,
                request_id=event.request_id,
                content_len=content_len,
            )
            await self._maybe_emit_governance(event, payload)
        except Exception as e:  # noqa: BLE001 - intended isolation for handlers
            self.handler_errors_total[event.type] += 1
            ORCH_HANDLER_ERRORS.labels(event.type).inc()
            if _span_obj is not None:
                try:
                    from opentelemetry.trace import Status, StatusCode

                    _span_obj.record_exception(e)
                    _span_obj.set_status(Status(StatusCode.ERROR))
                except Exception:
                    pass
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
        finally:
            if _span_cm is not None:
                try:
                    _span_cm.__exit__(None, None, None)
                except Exception:
                    pass

    async def _maybe_emit_governance(self, event: Event, payload: Dict[str, Any]) -> None:
        content = payload.get("content") if isinstance(payload, dict) else None
        if not isinstance(content, str) or not content.strip():
            return

        history = self._recent_history[event.project_id]
        history_snapshot = list(history)
        guidance: str | None
        try:
            guidance = await activate_pre_action_governance(
                content, history_snapshot, project_id=event.project_id
            )
        except Exception as exc:  # noqa: BLE001 - best-effort governance
            guidance = None
            try:
                log_json(
                    "error",
                    "orchestrator.governance_error",
                    project_id=event.project_id,
                    request_id=event.request_id,
                    error=str(exc),
                )
            except Exception:
                pass
        finally:
            history.append(content)

        if not guidance:
            return

        try:
            log_json(
                "info",
                "orchestrator.governance_emitted",
                project_id=event.project_id,
                request_id=event.request_id,
            )
        except Exception:
            pass

        source = {
            "type": event.type,
            "request_id": event.request_id,
            "role": payload.get("role") if isinstance(payload, dict) else None,
        }
        governance_event = Event(
            type=GOVERNANCE_GUIDANCE,
            project_id=event.project_id,
            payload={"content": guidance, "source": source},
            ts=time.time(),
            request_id=event.request_id,
            traceparent=event.traceparent,
        )
        try:
            await self._bus.publish(governance_event)
        except Exception as exc:  # noqa: BLE001 - avoid failing primary handler
            try:
                log_json(
                    "error",
                    "orchestrator.governance_publish_error",
                    project_id=event.project_id,
                    request_id=event.request_id,
                    error=str(exc),
                )
            except Exception:
                pass


# Singleton orchestrator
orchestrator = Orchestrator(bus)

# Prometheus counter for orchestrator handler errors
ORCH_HANDLER_ERRORS = Counter(
    "orchestrator_handler_errors_total",
    "Total orchestrator handler errors",
    ["type"],
)

# Watchdog metrics
WATCHDOG_SCANS_TOTAL = Counter(
    "tasks_watchdog_scans_total",
    "Total watchdog scan iterations",
    ["action"],
)
WATCHDOG_ACTIONS_TOTAL = Counter(
    "tasks_watchdog_actions_total",
    "Watchdog actions outcome counts",
    ["action", "outcome"],
)
WATCHDOG_ERRORS_TOTAL = Counter(
    "tasks_watchdog_errors_total",
    "Watchdog errors",
    ["action"],
)
WATCHDOG_DURATION = Histogram(
    "tasks_watchdog_scan_duration_seconds",
    "Duration of watchdog scans",
    ["action"],
)


def _truthy(v: str | None) -> bool:
    if v is None:
        return False
    return v.strip().lower() in ("1", "true", "yes", "on")


def _to_int(val: str | None, default: int) -> int:
    try:
        return int(val) if val is not None else int(default)
    except Exception:
        return int(default)
