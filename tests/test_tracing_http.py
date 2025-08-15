import pytest

# Skip if OpenTelemetry not installed
pytest.importorskip("opentelemetry")

from fastapi.testclient import TestClient
import os
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
try:  # OTel >=1.25 doesn't re-export InMemorySpanExporter at package root
    from opentelemetry.sdk.trace.export import InMemorySpanExporter  # type: ignore[attr-defined]
except Exception:
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Ensure env is set before importing the app (prevent app tracing init; we'll control provider/exporter)
os.environ.setdefault("MCP_TOKEN", "dev")
os.environ.setdefault("TRACING_ENABLED", "false")
from server.main import app


@pytest.fixture()
def otel_http_memory_provider(monkeypatch):
    # Keep app tracing init disabled; we will enable domain gating via monkeypatch
    monkeypatch.setenv("TRACING_ENABLED", "false")
    # Ensure auth works in tests
    monkeypatch.setenv("MCP_TOKEN", "dev")
    # Force gating in domain code regardless of env to create spans
    import server.observability.tracing as tracingmod
    import server.core.events as eventsmod
    import server.core.orchestrator as orchmod
    monkeypatch.setattr(tracingmod, "is_tracing_enabled", lambda: True, raising=False)
    monkeypatch.setattr(eventsmod, "is_tracing_enabled", lambda: True, raising=False)
    monkeypatch.setattr(orchmod, "is_tracing_enabled", lambda: True, raising=False)
    # Configure a clean SDK provider and attach in-memory exporter BEFORE instrumentation
    exporter = InMemorySpanExporter()
    try:
        provider = TracerProvider(resource=Resource.create({"service.name": "test-http"}))
        trace.set_tracer_provider(provider)
    except Exception:
        provider = None
    # Always attach exporter to the effective provider in use
    current = trace.get_tracer_provider()
    try:  # type: ignore[attr-defined]
        current.add_span_processor(SimpleSpanProcessor(exporter))
    except Exception:
        if provider is not None:
            provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Instrument FastAPI at test-time (since app lifespan won't)
    try:
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        # Ignore if already instrumented
        pass

    yield exporter

    # No teardown of global provider here to avoid cross-test interference


def _post_ingest(client: TestClient, content: str, force_error: bool = False):
    payload = {
        "type": "conversation.message",
        "projectId": "p-http",
        "role": "user",
        "content": content,
    }
    if force_error:
        payload["force_error"] = True
    return client.post("/tool/ingest_event", headers={"Authorization": "Bearer dev"}, json=payload)


def test_http_ingest_event_emits_http_and_domain_spans(otel_http_memory_provider):
    exporter: InMemorySpanExporter = otel_http_memory_provider
    with TestClient(app) as client:
        r = _post_ingest(client, "hello from http")
        assert r.status_code == 200

    spans = exporter.get_finished_spans()
    names = {s.name for s in spans}

    # Domain spans present
    assert "EventBus.publish" in names
    assert "Orchestrator.handle" in names

    # HTTP server span present (naming may vary by instrumentation version)
    http_spans = [s for s in spans if (s.attributes.get("http.method") == "POST") or ("/tool" in s.name)]
    assert http_spans, f"expected HTTP server span, got: {[s.name for s in spans]}"


def test_http_ingest_event_error_marks_handle_span(otel_http_memory_provider):
    exporter: InMemorySpanExporter = otel_http_memory_provider
    with TestClient(app) as client:
        r = _post_ingest(client, "boom", force_error=True)
        # Endpoint still returns 200; errors are handled inside orchestrator
        assert r.status_code == 200

    spans = exporter.get_finished_spans()
    handle_spans = [s for s in spans if s.name == "Orchestrator.handle"]
    assert handle_spans, "expected Orchestrator.handle span"
    hs = handle_spans[0]
    assert getattr(hs.status, "status_code", None) is not None
    assert str(hs.status.status_code).endswith("ERROR")
