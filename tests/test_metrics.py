import asyncio
import os
import re

from fastapi.testclient import TestClient


def _get_counter(metrics_text: str, name: str, labels: dict[str, str] | None = None) -> float:
    # Build a regex to match metric lines like:
    # events_published_total{type="conversation.message"} 3.0
    lbl = ""
    if labels:
        parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        lbl = "{" + ",".join(parts) + "}"
    pattern = rf"^{re.escape(name)}{re.escape(lbl)}\s+(\d+(?:\.\d+)?)$"
    for line in metrics_text.splitlines():
        m = re.match(pattern, line)
        if m:
            return float(m.group(1))
    return 0.0


def _client():
    os.environ["ENV"] = "dev"
    os.environ["MCP_TOKEN"] = "dev"
    os.environ["ORCHESTRATOR_ENABLED"] = "true"
    from server.main import app
    return TestClient(app)


def test_metrics_publish_consume_increment():
    with _client() as c:
        before = c.get("/metrics").text
        pub0 = _get_counter(before, "events_published_total", {"type": "conversation.message"})
        con0 = _get_counter(before, "events_consumed_total", {"type": "conversation.message"})

        # Trigger an event via REST tool
        payload = {
            "type": "conversation.message",
            "projectId": "p-metrics",
            "content": "hello metrics",
        }
        r = c.post("/tool/ingest_event", headers={"Authorization": "Bearer dev"}, json=payload)
        assert r.status_code == 200

        after = c.get("/metrics").text
        pub1 = _get_counter(after, "events_published_total", {"type": "conversation.message"})
        con1 = _get_counter(after, "events_consumed_total", {"type": "conversation.message"})

        assert pub1 >= pub0 + 1
        assert con1 >= con0 + 1


def test_metrics_error_path_increments_both_counters():
    # Force orchestrator handler error using payload.force_error
    with _client() as c:
        before = c.get("/metrics").text
        eb_err0 = _get_counter(before, "event_handler_errors_total", {"type": "conversation.message"})
        orch_err0 = _get_counter(before, "orchestrator_handler_errors_total", {"type": "conversation.message"})

        # Publish event directly to bus so we can add force_error flag
        from server.core import bus
        async def _go():
            await bus.publish_simple(
                type="conversation.message",
                project_id="p-error",
                payload={"content": "boom", "force_error": True},
                request_id="test-error",
            )
        asyncio.run(_go())

        after = c.get("/metrics").text
        eb_err1 = _get_counter(after, "event_handler_errors_total", {"type": "conversation.message"})
        orch_err1 = _get_counter(after, "orchestrator_handler_errors_total", {"type": "conversation.message"})

        assert eb_err1 >= eb_err0 + 1
        assert orch_err1 >= orch_err0 + 1
