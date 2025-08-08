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
