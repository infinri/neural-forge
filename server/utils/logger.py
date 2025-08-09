import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        # If OpenTelemetry is available and a span is active, enrich with trace/span ids
        try:
            from opentelemetry import trace  # type: ignore

            span = trace.get_current_span()
            sc = span.get_span_context() if span else None
            if sc and getattr(sc, "is_valid", False):
                # IDs are integers; format as zero-padded hex per spec
                base["trace_id"] = f"{sc.trace_id:032x}"
                base["span_id"] = f"{sc.span_id:016x}"
        except Exception:
            # Stay silent if otel missing or context invalid
            pass
        # Include extras if present
        if hasattr(record, "extra_dict") and isinstance(record.extra_dict, dict):
            base.update(record.extra_dict)
        return json.dumps(base, ensure_ascii=False)

_logger = None

def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    logger = logging.getLogger("mcp")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.propagate = False
    _logger = logger
    return logger

def log_json(level: str, message: str, **extra: Any) -> None:
    logger = get_logger()
    rec = logger.makeRecord(logger.name, getattr(logging, level.upper(), logging.INFO),
                            fn="", lno=0, msg=message, args=(), exc_info=None)
    setattr(rec, "extra_dict", extra)
    logger.handle(rec)
