import uuid
from typing import Any, Dict

from prometheus_client import Counter

import server.observability.tracing as otel_tracing
from server.db.engine import get_async_engine
from server.db.repo import update_task_status_pg
from server.utils.logger import log_json
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"

VALID_STATUSES = {"queued", "in_progress", "done", "failed"}

# Prometheus: updates by status and outcome
TASK_UPDATES_TOTAL = Counter(
    "task_updates_total",
    "Total task status updates",
    ["status", "outcome"],  # outcome: ok|not_found|db_unavailable
)

async def handler(req: Dict[str, Any]):
    """Update a task's status (typically to done/failed) with optional result.

    Request:
      {
        "id": "uuid",                # required
        "status": "done|failed|in_progress|queued",  # required
        "result": { ... } | null      # optional JSON object
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    task_id = req.get("id")
    status = req.get("status")
    result = req.get("result")

    def bad(msg: str):
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": msg},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    if not isinstance(task_id, str) or not task_id.strip():
        return bad("id (string) is required")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        return bad("status must be one of queued|in_progress|done|failed")
    if result is not None and not isinstance(result, dict):
        return bad("result must be an object if provided")
    # Start OTEL span if enabled or SDK provider present
    _span_cm = None
    _span_obj = None
    _gate = False
    _provider_is_sdk = False
    try:
        _gate = bool(otel_tracing.is_tracing_enabled())
    except Exception:
        _gate = False
    try:
        from opentelemetry import trace as _t  # type: ignore
        prov = _t.get_tracer_provider()
        _provider_is_sdk = hasattr(prov, "add_span_processor")
    except Exception:
        _provider_is_sdk = False
    if _gate or _provider_is_sdk:
        try:
            from opentelemetry import trace  # type: ignore

            tracer = trace.get_tracer("neural-forge")
            _span_cm = tracer.start_as_current_span("Task.update_status")
            _span_obj = _span_cm.__enter__()
            if _span_obj is not None:
                _span_obj.set_attribute("phase", "update")
                _span_obj.set_attribute("task_id", task_id)
                _span_obj.set_attribute("new_status", status)
        except Exception:
            _span_cm = None
            _span_obj = None

    resp: Dict[str, Any]
    try:
        engine = get_async_engine()
        if engine is None:
            if _span_obj is not None:
                try:
                    from opentelemetry.trace import Status, StatusCode  # type: ignore

                    _span_obj.set_attribute("db_available", False)
                    _span_obj.set_status(Status(StatusCode.ERROR))
                except Exception:
                    pass
            TASK_UPDATES_TOTAL.labels(status, "db_unavailable").inc()
            log_json("error", "task.update.db_unavailable", request_id=request_id, task_id=task_id, status=status)
            return {
                "error": {"code": "ERR.DB_UNAVAILABLE", "message": "DATABASE_URL not configured"},
                "requestId": request_id,
                "serverVersion": SERVER_VERSION,
                "timestamp": ts,
            }

        ok = await update_task_status_pg(
            engine,
            task_id=task_id.strip(),
            status=status,
            result=result,
        )
        if not ok:
            if _span_obj is not None:
                try:
                    _span_obj.set_attribute("update_ok", False)
                except Exception:
                    pass
            TASK_UPDATES_TOTAL.labels(status, "not_found").inc()
            log_json("warning", "task.update.not_found", request_id=request_id, task_id=task_id, status=status)
            resp = {
                "error": {"code": "ERR.NOT_FOUND", "message": "task not found"},
                "requestId": request_id,
                "serverVersion": SERVER_VERSION,
                "timestamp": ts,
            }
        else:
            if _span_obj is not None:
                try:
                    _span_obj.set_attribute("update_ok", True)
                except Exception:
                    pass
            TASK_UPDATES_TOTAL.labels(status, "ok").inc()
            log_json("info", "task.update.ok", request_id=request_id, task_id=task_id, status=status)
            resp = {
                "requestId": request_id,
                "serverVersion": SERVER_VERSION,
                "id": task_id,
                "status": status,
                "timestamp": ts,
            }
    finally:
        if _span_cm is not None:
            try:
                _span_cm.__exit__(None, None, None)
            except Exception:
                pass

    return resp
