import os
from typing import Any, Dict, Optional

# Lazy imports inside functions to avoid hard dependency at import time
from server.utils.logger import log_json

# Module-level tracing state for health/reporting
_TRACING_STATE: Dict[str, Any] = {
    "enabled": False,
    "initialized": False,
    "exporter": None,           # "otlp_http" | "console" | None
    "endpoint": None,           # exporter endpoint if applicable
    "instrumented_fastapi": False,
    "resource": {},             # resolved resource attributes
}


def _truthy(v: Optional[str]) -> bool:
    if v is None:
        return False
    return v.strip().lower() in ("1", "true", "yes", "on")


def is_tracing_enabled() -> bool:
    explicit = os.getenv("TRACING_ENABLED")
    if explicit is not None:
        return _truthy(explicit)
    # Default enabled in dev, disabled otherwise
    env = os.getenv("ENV", "dev").strip().lower()
    return env == "dev"


def _parse_headers_env(raw: Optional[str]) -> Dict[str, str]:
    if not raw:
        return {}
    headers: Dict[str, str] = {}
    for pair in raw.split(","):
        if not pair:
            continue
        if "=" in pair:
            k, v = pair.split("=", 1)
            headers[k.strip()] = v.strip()
    return headers


def setup_tracing(service_name: str, service_version: str) -> bool:
    """Initialize OpenTelemetry tracing if enabled.

    Returns True if tracing was successfully initialized, False otherwise.
    """
    if not is_tracing_enabled():
        # reflect disabled state for health
        _TRACING_STATE.update({
            "enabled": False,
            "initialized": False,
            "exporter": None,
            "endpoint": None,
            "resource": {},
        })
        return False

    try:
        from opentelemetry import trace

        # Prefer HTTP exporter; fall back to console if not configured
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as OTLPHTTPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
    except Exception as e:  # pragma: no cover - only when deps missing
        log_json("warning", "otel.import_failed", error=str(e))
        _TRACING_STATE.update({
            "enabled": True,
            "initialized": False,
            "exporter": None,
            "endpoint": None,
            "resource": {},
        })
        return False

    # Build resource
    env = os.getenv("ENV", "dev").strip().lower()
    resource_attrs: Dict[str, Any] = {
        "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
        "service.version": service_version,
        "deployment.environment": env,
    }
    # Allow additional attributes via env, e.g. "region=us-east-1,team=forge"
    extra = os.getenv("OTEL_RESOURCE_ATTRIBUTES")
    if extra:
        for pair in extra.split(","):
            if not pair:
                continue
            if "=" in pair:
                k, v = pair.split("=", 1)
                resource_attrs[k.strip()] = v.strip()

    resource = Resource.create(resource_attrs)

    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # Configure exporter
    endpoint = (
        os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    )
    headers = _parse_headers_env(os.getenv("OTEL_EXPORTER_OTLP_HEADERS"))

    if endpoint:
        exporter = OTLPHTTPSpanExporter(endpoint=endpoint, headers=headers)
        log_json("info", "otel.exporter.otlp_http_configured", endpoint=endpoint)
        exporter_name = "otlp_http"
    else:
        exporter = ConsoleSpanExporter()
        log_json("info", "otel.exporter.console_configured")
        exporter_name = "console"

    provider.add_span_processor(BatchSpanProcessor(exporter))

    _TRACING_STATE.update({
        "enabled": True,
        "initialized": True,
        "exporter": exporter_name,
        "endpoint": endpoint,
        "resource": resource_attrs,
    })

    log_json("info", "otel.tracing_initialized", enabled=True)
    return True


def instrument_fastapi_app(app: Any) -> None:
    """Instrument FastAPI app with OpenTelemetry if libs are available."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except Exception as e:  # pragma: no cover - only when deps missing
        log_json("warning", "otel.fastapi_instrumentor_missing", error=str(e))
        return

    try:
        FastAPIInstrumentor.instrument_app(app)
        _TRACING_STATE["instrumented_fastapi"] = True
        log_json("info", "otel.fastapi_instrumented")
    except Exception as e:  # pragma: no cover
        log_json("error", "otel.fastapi_instrumentation_failed", error=str(e))


def get_tracing_status() -> Dict[str, Any]:
    """Return current tracing status for health reporting."""
    # Shallow copy to avoid accidental external mutation
    return {
        "enabled": bool(_TRACING_STATE.get("enabled")),
        "initialized": bool(_TRACING_STATE.get("initialized")),
        "exporter": _TRACING_STATE.get("exporter"),
        "endpoint": _TRACING_STATE.get("endpoint"),
        "instrumented_fastapi": bool(_TRACING_STATE.get("instrumented_fastapi")),
        "resource": dict(_TRACING_STATE.get("resource") or {}),
    }
