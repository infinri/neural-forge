import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text

from server.core import orchestrator
from server.core.orchestrator import (
    WATCHDOG_ACTIONS_TOTAL,
    WATCHDOG_DURATION,
    WATCHDOG_ERRORS_TOTAL,
    WATCHDOG_SCANS_TOTAL,
)
from server.db.engine import get_async_engine
from server.db.repo import (
    fetch_governance_token_metrics_pg,
    watchdog_count_stale_inprogress_pg,
    watchdog_fail_stale_inprogress_pg,
    watchdog_list_stale_inprogress_pg,
    watchdog_requeue_stale_inprogress_pg,
)
from server.observability.tracing import (
    get_tracing_status,
    instrument_fastapi_app,
    is_tracing_enabled,
    setup_tracing,
)
from server.utils.logger import log_json
from server.utils.time import utc_now_iso_z

_PLACEHOLDER_TOKENS = {"change-me", "dev"}
MCP_TOKEN = (os.getenv("MCP_TOKEN") or "").strip()
TOOLS: Dict[str, Any] = {}
SERVER_VERSION = "1.3.0"

# Metrics
REQ_COUNTER = Counter("mcp_requests_total", "Total MCP requests", ["endpoint"])
REQ_LATENCY = Histogram("mcp_request_duration_seconds", "Request latency", ["endpoint"])
ERR_COUNTER = Counter("mcp_errors_total", "Total MCP errors", ["endpoint", "status_code"])

def _truthy(v: str | None) -> bool:
    if v is None:
        return False
    return v.strip().lower() in ("1", "true", "yes", "on")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Prod-safety: disallow placeholder or missing token unless explicitly overridden
    allow_insecure_dev = _truthy(os.getenv("ALLOW_INSECURE_DEV"))
    normalized_token = MCP_TOKEN.lower()
    if not MCP_TOKEN:
        log_json("error", "startup.mcp_token_missing", allow_insecure_dev=allow_insecure_dev)
        raise RuntimeError("MCP_TOKEN environment variable is required")
    if normalized_token in _PLACEHOLDER_TOKENS:
        if allow_insecure_dev:
            log_json(
                "warning",
                "startup.using_placeholder_token",
                allow_insecure_dev=True,
                placeholder_token=True,
            )
        else:
            log_json("error", "startup.placeholder_token_blocked", placeholder_token=True)
            raise RuntimeError(
                "MCP_TOKEN must be set to a unique value (set ALLOW_INSECURE_DEV=true to override)"
            )
    # Tracing init (optional)
    try:
        if is_tracing_enabled():
            if setup_tracing("neural-forge-mcp", SERVER_VERSION):
                instrument_fastapi_app(app)
    except Exception as e:
        log_json("warning", "otel.init_failed", error=str(e))
    # Start orchestrator if enabled
    orch_flag = os.getenv("ORCHESTRATOR_ENABLED", "true")
    if _truthy(orch_flag):
        await orchestrator.start()
    else:
        log_json("info", "orchestrator.disabled", reason="ORCHESTRATOR_ENABLED=false")
    try:
        yield
    finally:
        orch_flag = os.getenv("ORCHESTRATOR_ENABLED", "true")
        if _truthy(orch_flag) and orchestrator.is_running:
            await orchestrator.stop()

app = FastAPI(title="Windsurf MCP Memory/Planning", lifespan=lifespan)

def require_auth(auth: str | None, request: Request | None = None):
    supplied = None
    if auth and auth.startswith("Bearer "):
        supplied = auth.split(" ", 1)[1].strip()
    elif request is not None:
        supplied = request.query_params.get("token")
    if not supplied:
        raise HTTPException(status_code=401, detail="ERR.UNAUTHORIZED")
    if supplied != MCP_TOKEN:
        raise HTTPException(status_code=403, detail="ERR.FORBIDDEN")

@app.get("/get_capabilities")
async def get_capabilities(request: Request, authorization: str | None = Header(None)):
    require_auth(authorization, request)
    REQ_COUNTER.labels("get_capabilities").inc()
    return {"serverVersion": SERVER_VERSION, "tools": sorted(list(TOOLS.keys()))}

@app.get("/register")
async def register_get():
    # Some MCP clients probe a registration endpoint before establishing SSE.
    # We don't require auth here; this is a harmless capability probe.
    return {"status": "ok", "serverVersion": SERVER_VERSION}

@app.post("/register")
async def register_post():
    # Accept POST as well to avoid 404s from clients that POST to /register.
    return {"status": "ok", "serverVersion": SERVER_VERSION}

@app.get("/sse")
async def sse(request: Request, authorization: str | None = Header(None)):
    require_auth(authorization, request)
    async def eventgen():
        yield "event: ready\ndata: {}\n\n"
        while True:
            await asyncio.sleep(10)
            yield "event: heartbeat\ndata: {}\n\n"
    return StreamingResponse(eventgen(), media_type="text/event-stream")

@app.post("/sse")
async def sse_post(request: Request, authorization: str | None = Header(None)):
    """Handle MCP JSON-RPC messages over SSE POST"""
    require_auth(authorization, request)
    
    try:
        message = await request.json()
        response = await handle_mcp_message(message)
        return response
    except Exception as e:
        print(f"SSE POST error: {e}")
        return {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": message.get("id")}

async def handle_mcp_message(message: dict) -> dict:
    """Handle MCP JSON-RPC protocol messages"""
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params", {})
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "logging": {}
                },
                "serverInfo": {
                    "name": "neural-forge-mcp",
                    "version": SERVER_VERSION
                }
            }
        }
    
    elif method == "tools/list":
        tools = [
            {
                "name": "activate_governance",
                "description": "Activate pre-action governance analysis for AI planning/coding activities",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_message": {"type": "string"},
                        "conversation_history": {"type": "array", "items": {"type": "string"}},
                        "force_activation": {"type": "boolean"}
                    },
                    "required": ["user_message"]
                }
            },
            {
                "name": "add_memory",
                "description": "Add a new memory item",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"},
                        "content": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "metadata": {"type": "object"}
                    },
                    "required": ["projectId", "content"]
                }
            },
            {
                "name": "ingest_event",
                "description": "Ingest a conversation message event and publish to internal EventBus",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["conversation.message"]},
                        "projectId": {"type": "string"},
                        "role": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["type", "projectId", "content"]
                }
            },
            {
                "name": "get_memory",
                "description": "Retrieve a memory item by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"}
                    },
                    "required": ["id"]
                }
            },
            {
                "name": "search_memory",
                "description": "Search memory items",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"},
                        "query": {"type": "string"},
                        "limit": {"type": "integer"}
                    },
                    "required": ["projectId", "query"]
                }
            },
            {
                "name": "get_governance_policies",
                "description": "Get Neural Forge governance policies",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"}
                    },
                    "required": ["projectId"]
                }
            },
            {
                "name": "get_active_tokens",
                "description": "Get active Neural Forge tokens",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"}
                    },
                    "required": ["projectId"]
                }
            },
            {
                "name": "get_token_metrics",
                "description": "Inspect historical governance token effectiveness metrics",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"},
                        "tokenIds": {"type": "array", "items": {"type": "string"}},
                        "minActivations": {"type": "integer"},
                        "limit": {"type": "integer"}
                    }
                }
            },
            {
                "name": "get_rules",
                "description": "Get Neural Forge engineering rules",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"}
                    },
                    "required": ["projectId"]
                }
            },
            {
                "name": "enqueue_task",
                "description": "Enqueue a new task for planning",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"},
                        "taskType": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                        "metadata": {"type": "object"}
                    },
                    "required": ["projectId", "taskType", "description"]
                }
            },
            {
                "name": "get_next_task",
                "description": "Get the next task from the queue",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"}
                    },
                    "required": ["projectId"]
                }
            },
            {
                "name": "update_task_status",
                "description": "Update task status and progress",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "taskId": {"type": "string"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "failed"]},
                        "progress": {"type": "number", "minimum": 0, "maximum": 100},
                        "notes": {"type": "string"}
                    },
                    "required": ["taskId", "status"]
                }
            },
            {
                "name": "save_diff",
                "description": "Save code diff for tracking changes",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"},
                        "filePath": {"type": "string"},
                        "diff": {"type": "string"},
                        "description": {"type": "string"},
                        "metadata": {"type": "object"}
                    },
                    "required": ["projectId", "filePath", "diff"]
                }
            },
            {
                "name": "list_recent",
                "description": "List recent diffs and changes",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100}
                    },
                    "required": ["projectId"]
                }
            },
            {
                "name": "log_error",
                "description": "Log error for debugging and monitoring",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "projectId": {"type": "string"},
                        "level": {"type": "string", "enum": ["debug", "info", "warning", "error", "critical"]},
                        "message": {"type": "string"},
                        "context": {"type": "object"}
                    },
                    "required": ["projectId", "level", "message"]
                }
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": tools
            }
        }
    
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        # Map MCP tool calls to our REST endpoints
        if tool_name in TOOLS:
            try:
                result = await TOOLS[tool_name](tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2)
                            }
                        ]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool not found: {tool_name}"
                }
            }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health():
    """Basic health endpoint exposing orchestrator running state.

    No auth required: safe to probe by infra/monitoring.
    """
    tracing = get_tracing_status()
    # Determine DB backend and status (concise probe)
    backend = "postgresql"
    db_status = "unknown"
    engine = get_async_engine()
    if engine is not None:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            db_status = "up"
        except Exception:
            db_status = "down"
    else:
        # PostgreSQL-only mode: if no engine configured, report down
        db_status = "down"

    # Only return a concise subset in health to keep payload small
    return {
        "serverVersion": SERVER_VERSION,
        "orchestratorRunning": orchestrator.is_running,
        "tracing": {
            "enabled": tracing.get("enabled", False),
            "initialized": tracing.get("initialized", False),
            "exporter": tracing.get("exporter"),
        },
        "db": {"backend": backend, "status": db_status},
        "status": "ok",
    }

@app.get("/admin/stats")
async def admin_stats(
    request: Request,
    authorization: str | None = Header(None),
    projectId: str | None = None,
):
    """Admin: aggregate counts for key entities.

    Secured via MCP_TOKEN.
    Optional filter: projectId
    """
    require_auth(authorization, request)
    endpoint = "admin_stats"
    REQ_COUNTER.labels(endpoint).inc()
    try:
        with REQ_LATENCY.labels(endpoint).time():
            ts = utc_now_iso_z()
            engine = get_async_engine()
            backend = "postgresql"

            # Defaults
            mem_count = 0
            diffs_count = 0
            errors_count = 0
            tasks = {"queued": 0, "inProgress": 0, "done": 0, "failed": 0}

            if engine is None:
                raise HTTPException(status_code=503, detail="ERR.DB_UNAVAILABLE: DATABASE_URL not configured")

            # Postgres path
            where = []
            params: Dict[str, Any] = {}
            if projectId and projectId.strip():
                where.append("project_id = :project_id")
                params["project_id"] = projectId
            w = f" WHERE {' AND '.join(where)}" if where else ""
            async with engine.connect() as conn:
                r = await conn.execute(text(f"SELECT COUNT(*) FROM memory_entries{w}"), params)
                row_pg = r.fetchone()
                mem_count = int(row_pg[0]) if row_pg and row_pg[0] is not None else 0

                r = await conn.execute(text(f"SELECT status, COUNT(*) FROM tasks{w} GROUP BY status"), params)
                for st, cnt in r.fetchall():
                    key = "inProgress" if st == "in_progress" else st
                    if key in tasks:
                        tasks[key] = int(cnt)

                r = await conn.execute(text(f"SELECT COUNT(*) FROM diffs{w}"), params)
                row_pg = r.fetchone()
                diffs_count = int(row_pg[0]) if row_pg and row_pg[0] is not None else 0

                r = await conn.execute(text(f"SELECT COUNT(*) FROM errors{w}"), params)
                row_pg = r.fetchone()
                errors_count = int(row_pg[0]) if row_pg and row_pg[0] is not None else 0

            total_tasks = tasks["queued"] + tasks["inProgress"] + tasks["done"] + tasks["failed"]
            log_json("info", "admin_stats", backend=backend, projectId=projectId, status="ok")
            return {
                "serverVersion": SERVER_VERSION,
                "timestamp": ts,
                "db": {"backend": backend},
                "counts": {
                    "memoryEntries": mem_count,
                    "diffs": diffs_count,
                    "errors": errors_count,
                    "tasks": {
                        "queued": tasks["queued"],
                        "inProgress": tasks["inProgress"],
                        "done": tasks["done"],
                        "failed": tasks["failed"],
                        "total": total_tasks,
                    },
                },
            }
    except HTTPException as e:
        ERR_COUNTER.labels(endpoint, str(e.status_code)).inc()
        log_json("error", "admin_stats_http_error", status_code=e.status_code)
        raise e
    except Exception as e:
        ERR_COUNTER.labels(endpoint, "500").inc()
        log_json("error", "admin_stats_exception", error=str(e))
        raise HTTPException(status_code=500, detail=f"ERR.UNAVAILABLE: {e}")

@app.get("/admin/memory_meta")
async def admin_memory_meta(
    request: Request,
    authorization: str | None = Header(None),
    projectId: str | None = None,
    quarantinedOnly: bool = False,
    limit: int = 100,
    offset: int = 0,
):
    """Admin: list memory metadata without content.

    Secured via MCP_TOKEN.
    Filters: projectId (optional), quarantinedOnly (bool)
    Pagination: limit (<=500), offset
    """
    require_auth(authorization, request)
    endpoint = "admin_memory_meta"
    REQ_COUNTER.labels(endpoint).inc()
    # sanitize
    if limit <= 0 or limit > 500:
        limit = 100
    if offset < 0:
        offset = 0
    try:
        with REQ_LATENCY.labels(endpoint).time():
            ts = utc_now_iso_z()
            engine = get_async_engine()
            backend = "postgresql" if engine is not None else "sqlite"
            items: list[Dict[str, Any]] = []

            if engine is None:
                raise HTTPException(status_code=503, detail="ERR.DB_UNAVAILABLE: DATABASE_URL not configured")

            cond = []
            params: Dict[str, Any] = {"limit": int(limit), "offset": int(offset)}
            if projectId and projectId.strip():
                cond.append("project_id = :project_id")
                params["project_id"] = projectId
            if quarantinedOnly:
                cond.append("quarantined = TRUE")
            where = f" WHERE {' AND '.join(cond)}" if cond else ""
            q_pg = text(
                f"""
                SELECT id, project_id, quarantined, created_at, LENGTH(content) AS size
                FROM memory_entries
                {where}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            )
            async with engine.connect() as conn:
                res = await conn.execute(q_pg, params)
                rows_pg = res.fetchall()
            for r_pg in rows_pg:
                created = r_pg[3]
                items.append({
                    "id": r_pg[0],
                    "projectId": r_pg[1],
                    "quarantined": bool(r_pg[2]),
                    "createdAt": created.isoformat() if hasattr(created, "isoformat") else str(created),
                    "size": int(r_pg[4]) if r_pg[4] is not None else 0,
                })

            log_json("info", "admin_memory_meta", backend=backend, projectId=projectId, count=len(items))
            return {
                "serverVersion": SERVER_VERSION,
                "timestamp": ts,
                "db": {"backend": backend},
                "items": items,
                "count": len(items),
                "limit": limit,
                "offset": offset,
            }
    except HTTPException as e:
        ERR_COUNTER.labels(endpoint, str(e.status_code)).inc()
        log_json("error", "admin_memory_meta_http_error", status_code=e.status_code)
        raise e
    except Exception as e:
        ERR_COUNTER.labels(endpoint, "500").inc()
        log_json("error", "admin_memory_meta_exception", error=str(e))
        raise HTTPException(status_code=500, detail=f"ERR.UNAVAILABLE: {e}")

@app.post("/admin/watchdog/scan")
async def admin_watchdog_scan(
    request: Request,
    authorization: str | None = Header(None),
    action: str | None = None,
    ttlSeconds: int | None = None,
    limit: int | None = None,
    projectId: str | None = None,
):
    """Admin: manually trigger a Postgres watchdog scan.

    Secured via MCP_TOKEN. Parameters can be provided via query or defaulted from env:
    - action: 'requeue' | 'fail' (default from TASK_WATCHDOG_ACTION or 'requeue')
    - ttlSeconds: staleness threshold (default from TASK_WATCHDOG_TTL_SECONDS or 600)
    - limit: maximum tasks to process (default from TASK_WATCHDOG_BATCH_LIMIT or 100)
    - projectId: optional filter (default from TASK_WATCHDOG_PROJECT_ID)
    """
    require_auth(authorization, request)
    endpoint = "admin_watchdog_scan"
    REQ_COUNTER.labels(endpoint).inc()
    try:
        with REQ_LATENCY.labels(endpoint).time():
            engine = get_async_engine()
            if engine is None:
                raise HTTPException(status_code=503, detail="ERR.DB_UNAVAILABLE: DATABASE_URL not configured")

            # Resolve parameters from args or environment
            act = (action or os.getenv("TASK_WATCHDOG_ACTION", "requeue") or "requeue").strip().lower()
            ttl_s = int(ttlSeconds) if ttlSeconds is not None else int(os.getenv("TASK_WATCHDOG_TTL_SECONDS", "600"))
            limit_n = int(limit) if limit is not None else int(os.getenv("TASK_WATCHDOG_BATCH_LIMIT", "100"))
            proj = projectId if (projectId and projectId.strip()) else os.getenv("TASK_WATCHDOG_PROJECT_ID")
            proj = proj if (proj and proj.strip()) else None

            start = time.perf_counter()
            affected = 0
            if act == "fail":
                affected = await watchdog_fail_stale_inprogress_pg(
                    engine,
                    ttl_seconds=ttl_s,
                    limit=limit_n,
                    project_id=proj,
                    reason="manual_admin",
                )
            else:
                affected = await watchdog_requeue_stale_inprogress_pg(
                    engine,
                    ttl_seconds=ttl_s,
                    limit=limit_n,
                    project_id=proj,
                )

            duration = time.perf_counter() - start
            WATCHDOG_SCANS_TOTAL.labels(act).inc()
            WATCHDOG_DURATION.labels(act).observe(duration)
            outcome = "ok" if affected > 0 else "none"
            WATCHDOG_ACTIONS_TOTAL.labels(act, outcome).inc()

            log_json(
                "info",
                "admin_watchdog_scan",
                action=act,
                ttlSeconds=int(ttl_s),
                limit=int(limit_n),
                affected=int(affected),
                projectId=proj,
                durationMs=int(duration * 1000),
            )
            return {
                "serverVersion": SERVER_VERSION,
                "status": "ok",
                "action": act,
                "ttlSeconds": int(ttl_s),
                "limit": int(limit_n),
                "projectId": proj,
                "affected": int(affected),
                "durationMs": int(duration * 1000),
            }
    except HTTPException as e:
        ERR_COUNTER.labels(endpoint, str(e.status_code)).inc()
        log_json("error", "admin_watchdog_scan_http_error", status_code=e.status_code)
        raise e
    except Exception as e:
        # Best-effort to attribute watchdog error to an action label
        try:
            label_val = (action or os.getenv("TASK_WATCHDOG_ACTION", "requeue") or "requeue").strip().lower()
            WATCHDOG_ERRORS_TOTAL.labels(label_val).inc()
        except Exception:
            pass
        ERR_COUNTER.labels(endpoint, "500").inc()
        log_json("error", "admin_watchdog_scan_exception", error=str(e))
        raise HTTPException(status_code=500, detail=f"ERR.UNAVAILABLE: {e}")

@app.get("/admin/watchdog/preview")
async def admin_watchdog_preview(
    request: Request,
    authorization: str | None = Header(None),
    ttlSeconds: int | None = None,
    limit: int | None = None,
    projectId: str | None = None,
):
    """Admin: preview stale in-progress tasks targeted by the watchdog.

    Secured via MCP_TOKEN. Parameters can be provided via query or defaulted from env:
    - ttlSeconds: staleness threshold (default from TASK_WATCHDOG_TTL_SECONDS or 600)
    - limit: maximum tasks to list (default from TASK_WATCHDOG_BATCH_LIMIT or 100)
    - projectId: optional filter (default from TASK_WATCHDOG_PROJECT_ID)
    """
    require_auth(authorization, request)
    endpoint = "admin_watchdog_preview"
    REQ_COUNTER.labels(endpoint).inc()
    try:
        with REQ_LATENCY.labels(endpoint).time():
            engine = get_async_engine()
            if engine is None:
                raise HTTPException(status_code=503, detail="ERR.DB_UNAVAILABLE: DATABASE_URL not configured")

            # Resolve parameters from args or environment
            ttl_s = int(ttlSeconds) if ttlSeconds is not None else int(os.getenv("TASK_WATCHDOG_TTL_SECONDS", "600"))
            limit_n = int(limit) if limit is not None else int(os.getenv("TASK_WATCHDOG_BATCH_LIMIT", "100"))
            proj = projectId if (projectId and projectId.strip()) else os.getenv("TASK_WATCHDOG_PROJECT_ID")
            proj = proj if (proj and proj.strip()) else None

            count = await watchdog_count_stale_inprogress_pg(
                engine,
                ttl_seconds=ttl_s,
                project_id=proj,
            )
            items = await watchdog_list_stale_inprogress_pg(
                engine,
                ttl_seconds=ttl_s,
                limit=limit_n,
                project_id=proj,
            )

            log_json(
                "info",
                "admin_watchdog_preview",
                ttlSeconds=int(ttl_s),
                limit=int(limit_n),
                projectId=proj,
                count=int(count),
                sampleCount=len(items),
            )
            return {
                "serverVersion": SERVER_VERSION,
                "status": "ok",
                "ttlSeconds": int(ttl_s),
                "limit": int(limit_n),
                "projectId": proj,
                "count": int(count),
                "items": items,
            }
    except HTTPException as e:
        ERR_COUNTER.labels(endpoint, str(e.status_code)).inc()
        log_json("error", "admin_watchdog_preview_http_error", status_code=e.status_code)
        raise e
    except Exception as e:
        ERR_COUNTER.labels(endpoint, "500").inc()
        log_json("error", "admin_watchdog_preview_exception", error=str(e))
        raise HTTPException(status_code=500, detail=f"ERR.UNAVAILABLE: {e}")

@app.get("/admin/token_metrics")
async def admin_token_metrics(
    request: Request,
    authorization: str | None = Header(None),
    projectId: str | None = None,
    tokenId: list[str] | None = Query(None),
    minActivations: int = 0,
    limit: int = 50,
):
    """Admin: inspect governance token effectiveness metrics."""

    require_auth(authorization, request)
    endpoint = "admin_token_metrics"
    REQ_COUNTER.labels(endpoint).inc()

    try:
        with REQ_LATENCY.labels(endpoint).time():
            ts = utc_now_iso_z()
            engine = get_async_engine()
            if engine is None:
                raise HTTPException(status_code=503, detail="ERR.DB_UNAVAILABLE: DATABASE_URL not configured")

            try:
                limit_val = int(limit)
            except Exception:
                limit_val = 50
            limit_val = max(1, min(limit_val, 500))

            try:
                min_act = max(0, int(minActivations))
            except Exception:
                min_act = 0

            token_filters = None
            if tokenId:
                token_filters = [tid for tid in tokenId if isinstance(tid, str) and tid.strip()]
                if token_filters:
                    token_filters = [tid.strip() for tid in token_filters]

            metrics = await fetch_governance_token_metrics_pg(
                engine,
                token_ids=token_filters,
                project_id=projectId,
                min_activation_count=min_act,
                limit=limit_val,
            )

            log_json(
                "info",
                "admin_token_metrics",
                projectId=projectId,
                count=len(metrics),
                minActivations=min_act,
                limit=limit_val,
            )

            return {
                "serverVersion": SERVER_VERSION,
                "timestamp": ts,
                "projectId": projectId or "global",
                "minActivations": min_act,
                "limit": limit_val,
                "count": len(metrics),
                "items": metrics,
                "tokenIds": token_filters,
            }
    except HTTPException as e:
        ERR_COUNTER.labels(endpoint, str(e.status_code)).inc()
        log_json("error", "admin_token_metrics_http_error", status_code=e.status_code)
        raise e
    except Exception as e:
        ERR_COUNTER.labels(endpoint, "500").inc()
        log_json("error", "admin_token_metrics_exception", error=str(e))
        raise HTTPException(status_code=500, detail=f"ERR.UNAVAILABLE: {e}")

# Tool registration stubs
from .tools import (
    activate_governance,
    add_memory,
    enqueue_task,
    get_active_tokens,
    get_governance_policies,
    get_memory,
    get_next_task,
    get_rules,
    get_token_metrics,
    ingest_event,
    list_recent,
    log_error,
    save_diff,
    search_memory,
    update_task_status,
)

TOOLS.update({
    "activate_governance": activate_governance.activate_governance,
    "add_memory": add_memory.handler,
    "ingest_event": ingest_event.handler,
    "get_memory": get_memory.handler,
    "search_memory": search_memory.handler,
    "save_diff": save_diff.handler,
    "log_error": log_error.handler,
    "list_recent": list_recent.handler,
    "enqueue_task": enqueue_task.handler,
    "get_next_task": get_next_task.handler,
    "update_task_status": update_task_status.handler,
    "get_rules": get_rules.handler,
    "get_governance_policies": get_governance_policies.handler,
    "get_active_tokens": get_active_tokens.handler,
    "get_token_metrics": get_token_metrics.handler,
})

@app.post("/tool/{name}")
async def tool(name: str, request: Request, authorization: str | None = Header(None)):
    # Manually create a minimal HTTP server span if no current HTTP span exists.
    # This ensures tests can observe an HTTP span even when FastAPI instrumentation
    # is disabled in app lifespan and instrumented ad-hoc in tests.
    otel_cm = None
    otel_span = None
    try:  # Lazy import to avoid hard dependency
        from opentelemetry import trace as _trace
        from opentelemetry.trace import SpanKind as _SpanKind
        current = _trace.get_current_span()
        has_active = False
        try:
            sc = current.get_span_context()  # type: ignore[attr-defined]
            has_active = bool(sc and getattr(sc, "is_valid", False))
        except Exception:
            has_active = False
        if not has_active:
            tracer = _trace.get_tracer("server.fastapi")
            route_template = "/tool/{name}"
            method = request.method
            path = request.url.path
            otel_cm = tracer.start_as_current_span(f"{method} {route_template}", kind=_SpanKind.SERVER)
            otel_span = otel_cm.__enter__()
            try:
                otel_span.set_attribute("http.method", method)
                otel_span.set_attribute("http.route", route_template)
                otel_span.set_attribute("http.target", path)
            except Exception:
                pass
    except Exception:
        otel_cm = None
        otel_span = None

    require_auth(authorization, request)
    if name not in TOOLS:
        # Set status on manual span if present
        if otel_span is not None:
            try:
                otel_span.set_attribute("http.status_code", 404)
            except Exception:
                pass
        raise HTTPException(status_code=404, detail="ERR.NOT_FOUND")

    payload = await request.json()
    request_id = None
    start = time.perf_counter()
    REQ_COUNTER.labels(name).inc()
    try:
        with REQ_LATENCY.labels(name).time():
            result = await TOOLS[name](payload)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        # Ensure consistent envelope fields
        merged = {"serverVersion": SERVER_VERSION, **result}
        # If handler already included elapsedMs, keep the measured one authoritative
        merged["elapsedMs"] = elapsed_ms
        request_id = merged.get("requestId")
        # Structured completion log
        log_json(
            "info",
            "tool_complete",
            endpoint=name,
            requestId=request_id,
            elapsedMs=elapsed_ms,
            status="ok",
        )
        response = JSONResponse(merged)
        if otel_span is not None:
            try:
                otel_span.set_attribute("http.status_code", int(response.status_code))
            except Exception:
                pass
        return response
    except HTTPException as e:
        ERR_COUNTER.labels(name, str(e.status_code)).inc()
        log_json(
            "error",
            "tool_http_error",
            endpoint=name,
            requestId=request_id,
            status_code=e.status_code,
        )
        if otel_span is not None:
            try:
                otel_span.set_attribute("http.status_code", int(e.status_code))
            except Exception:
                pass
        raise e
    except Exception as e:
        ERR_COUNTER.labels(name, "500").inc()
        log_json(
            "error",
            "tool_exception",
            endpoint=name,
            requestId=request_id,
            error=str(e),
        )
        if otel_span is not None:
            try:
                otel_span.set_attribute("http.status_code", 500)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"ERR.UNAVAILABLE: {e}")
    finally:
        if otel_cm is not None:
            try:
                otel_cm.__exit__(None, None, None)
            except Exception:
                pass
