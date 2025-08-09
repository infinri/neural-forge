import pytest

# Skip if OpenTelemetry not installed
pytest.importorskip("opentelemetry")

from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import InMemorySpanExporter, SimpleSpanProcessor

from server.main import app


@pytest.fixture()
def otel_http_memory_provider(monkeypatch):
    # Prevent app lifespan from overriding provider/exporter
    monkeypatch.setenv("TRACING_ENABLED", "false")
    # Configure in-memory exporter and provider for test
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test-http"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Instrument FastAPI at test-time (since app lifespan won't)
    FastAPIInstrumentor.instrument_app(app)

    yield exporter

    # Reset provider after test
    trace.set_tracer_provider(TracerProvider(resource=Resource.create({"service.name": "reset"})))


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
