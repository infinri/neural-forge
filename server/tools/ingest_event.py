"""
Ingest Event tool

Accepts external (MCP/REST) requests and publishes internal events to the EventBus.
Phase 1: support conversation.message with basic payload validation.

Request (camelCase):
  {
    "type": "conversation.message",   # required
    "projectId": "string",            # required
    "role": "user|assistant|system",  # optional (normalized to lowercase)
    "content": "string"                # required, length-capped by env
  }

Response:
  {
    "requestId": "uuid",
    "serverVersion": "1.x.x",
    "timestamp": "UTC ISO8601 Z",
    "status": "ok",
    "type": "conversation.message",
    "projectId": "..."
  }

Errors use the standard tool error envelope with code ERR.BAD_REQUEST.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict

from server.core import bus
from server.core.events import Event
from server.utils.time import utc_now_iso_z

SERVER_VERSION = "1.3.0"
SUPPORTED_TYPES = {"conversation.message"}
MAX_CONTENT = int(os.getenv("INGEST_EVENT_MAX_CONTENT_CHARS", "100000"))


async def handler(req: Dict[str, Any]):
    request_id = str(uuid.uuid4())
    ts = utc_now_iso_z()

    def bad(msg: str):
        return {
            "error": {"code": "ERR.BAD_REQUEST", "message": msg},
            "requestId": request_id,
            "serverVersion": SERVER_VERSION,
            "timestamp": ts,
        }

    evt_type = req.get("type")
    project_id = req.get("projectId")
    role = req.get("role")
    content = req.get("content")

    if not isinstance(evt_type, str) or not evt_type.strip():
        return bad("type (string) is required")
    if evt_type not in SUPPORTED_TYPES:
        return bad(f"unsupported event type: {evt_type}")
    if not isinstance(project_id, str) or not project_id.strip():
        return bad("projectId (string) is required")
    if role is not None and not isinstance(role, str):
        return bad("role must be a string if provided")
    if not isinstance(content, str) or not content:
        return bad("content (string) is required")
    if len(content) > MAX_CONTENT:
        return bad(f"content exceeds max length ({MAX_CONTENT})")

    norm_role = role.lower() if isinstance(role, str) else None

    # Publish to EventBus
    payload = {"role": norm_role, "content": content}
    # Test hook: propagate force_error if provided to exercise error path
    if isinstance(req.get("force_error"), bool) and req["force_error"]:
        payload["force_error"] = True
    await bus.publish(
        Event(
            type=evt_type,
            project_id=project_id,
            payload=payload,
            ts=time.time(),
            request_id=request_id,
        )
    )

    return {
        "requestId": request_id,
        "serverVersion": SERVER_VERSION,
        "timestamp": ts,
        "status": "ok",
        "type": evt_type,
        "projectId": project_id,
    }
