import asyncio
import json
import os
import time
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from server.core import orchestrator
from server.utils.logger import log_json

app = FastAPI(title="Windsurf MCP Memory/Planning")

MCP_TOKEN = os.getenv("MCP_TOKEN", "change-me")
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

@app.on_event("startup")
async def _app_startup() -> None:
    # Prod-safety: disallow default token when not in dev
    env = os.getenv("ENV", "dev").strip().lower()
    if env != "dev" and MCP_TOKEN == "change-me":
        log_json("error", "startup.invalid_token_in_prod", env=env)
        raise RuntimeError("MCP_TOKEN must not be 'change-me' when ENV != dev")
    # Start orchestrator if enabled
    orch_flag = os.getenv("ORCHESTRATOR_ENABLED", "true")
    if _truthy(orch_flag):
        await orchestrator.start()
    else:
        log_json("info", "orchestrator.disabled", reason="ORCHESTRATOR_ENABLED=false")

@app.on_event("shutdown")
async def _app_shutdown() -> None:
    orch_flag = os.getenv("ORCHESTRATOR_ENABLED", "true")
    if _truthy(orch_flag) and orchestrator.is_running:
        await orchestrator.stop()

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
    return {
        "serverVersion": SERVER_VERSION,
        "orchestratorRunning": orchestrator.is_running,
        "status": "ok",
    }

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
})

@app.post("/tool/{name}")
async def tool(name: str, request: Request, authorization: str | None = Header(None)):
    require_auth(authorization, request)
    if name not in TOOLS:
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
        return JSONResponse(merged)
    except HTTPException as e:
        ERR_COUNTER.labels(name, str(e.status_code)).inc()
        log_json(
            "error",
            "tool_http_error",
            endpoint=name,
            requestId=request_id,
            status_code=e.status_code,
        )
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
        raise HTTPException(status_code=500, detail=f"ERR.UNAVAILABLE: {e}")
