import uuid
from typing import Any, Dict

from prometheus_client import Counter

import server.observability.tracing as otel_tracing
from server.db.engine import get_async_engine
from server.db.repo import claim_next_task_pg
from server.utils.logger import log_json
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"

# Prometheus metric (low-cardinality): result in {db_unavailable, none, claimed}
TASK_CLAIMS_TOTAL = Counter(
    "task_claims_total",
    "Total task claim attempts",
    ["result"],
)

async def handler(req: Dict[str, Any]):
    """Claim the next queued task and mark it in_progress.

    Request:
      {
        "projectId": "string" | null  # optional filter
      }
    """
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    project_id = req.get("projectId")
    # Start OTEL span if enabled or if a SDK provider is present
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
            _span_cm = tracer.start_as_current_span("Task.claim")
            _span_obj = _span_cm.__enter__()
            if _span_obj is not None:
                _span_obj.set_attribute("phase", "claim")
                if isinstance(project_id, str):
                    _span_obj.set_attribute("project_id", project_id)
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
            TASK_CLAIMS_TOTAL.labels("db_unavailable").inc()
            log_json(
                "error",
                "task.claim.db_unavailable",
                request_id=request_id,
                project_id=project_id,
            )
            resp = {
                "error": {"code": "ERR.DB_UNAVAILABLE", "message": "DATABASE_URL not configured"},
                "requestId": request_id,
                "serverVersion": SERVER_VERSION,
                "timestamp": ts,
            }
            return resp

        claimed = await claim_next_task_pg(
            engine,
            project_id=project_id if isinstance(project_id, str) else None,
        )
        if not claimed:
            if _span_obj is not None:
                try:
                    _span_obj.set_attribute("claimed", False)
                except Exception:
                    pass
            TASK_CLAIMS_TOTAL.labels("none").inc()
            log_json(
                "info",
                "task.claim.none",
                request_id=request_id,
                project_id=project_id,
            )
            resp = {
                "requestId": request_id,
                "serverVersion": SERVER_VERSION,
                "task": None,
                "timestamp": ts,
            }
        else:
            if _span_obj is not None:
                try:
                    _span_obj.set_attribute("claimed", True)
                    _span_obj.set_attribute("task_id", claimed.get("id"))
                except Exception:
                    pass
            TASK_CLAIMS_TOTAL.labels("claimed").inc()
            log_json(
                "info",
                "task.claim.ok",
                request_id=request_id,
                project_id=project_id,
                task_id=claimed.get("id"),
            )
            task = {
                "id": claimed["id"],
                "projectId": claimed["projectId"],
                "status": "in_progress",
                "payload": claimed["payload"],
                "createdAt": claimed["createdAt"],
            }
            resp = {
                "requestId": request_id,
                "serverVersion": SERVER_VERSION,
                "task": task,
                "timestamp": ts,
            }
    finally:
        if _span_cm is not None:
            try:
                _span_cm.__exit__(None, None, None)
            except Exception:
                pass

    return resp
