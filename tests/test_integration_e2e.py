import os
import logging
from fastapi.testclient import TestClient

from server.utils.logger import get_logger


class _CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append({
            "message": record.getMessage(),
            "extra": getattr(record, "extra_dict", {}),
            "level": record.levelname.lower(),
        })


def _client():
    os.environ["ENV"] = "dev"
    os.environ["MCP_TOKEN"] = "dev"
    os.environ["ORCHESTRATOR_ENABLED"] = "true"
    from server.main import app
    return TestClient(app)


def test_ingest_event_to_orchestrator_log_and_metrics_flow():
    # Attach capture handler to structured logger
    logger = get_logger()
    cap = _CaptureHandler()
    logger.addHandler(cap)
    try:
        with _client() as c:
            content = "hello e2e"
            payload = {
                "type": "conversation.message",
                "projectId": "p-e2e",
                "content": content,
            }
            r = c.post("/tool/ingest_event", headers={"Authorization": "Bearer dev"}, json=payload)
            assert r.status_code == 200

            # Verify publish and consume markers present
            msgs = [rec["message"] for rec in cap.records]
            assert any(m == "eventbus.publish" for m in msgs)
            assert any(m == "eventbus.consume" for m in msgs)

            # Verify orchestrator handler log includes content_len and identifiers
            orch = [rec for rec in cap.records if rec["message"] == "orchestrator.handle"]
            assert len(orch) >= 1
            found = False
            for rec in orch:
                extra = rec["extra"] or {}
                if extra.get("evt_type") == "conversation.message" and \
                   extra.get("project_id") == "p-e2e" and \
                   extra.get("content_len") == len(content):
                    found = True
                    break
            assert found, f"orchestrator.handle log with expected fields not found: {orch}"
    finally:
        logger.removeHandler(cap)
