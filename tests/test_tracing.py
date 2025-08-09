import asyncio
import json

import pytest

# Skip entire module if OpenTelemetry not installed
pytest.importorskip("opentelemetry")

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import InMemorySpanExporter, SimpleSpanProcessor

from server.core.events import Event, bus
from server.core.orchestrator import CONV_MSG, orchestrator
from server.utils.logger import log_json


@pytest.fixture()
def otel_memory_provider(monkeypatch):
    # Enable tracing gates in code paths
    monkeypatch.setenv("TRACING_ENABLED", "true")
    # Configure SDK with in-memory exporter
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    # Reset provider after test to avoid cross-test contamination
    trace.set_tracer_provider(TracerProvider(resource=Resource.create({"service.name": "reset"})))


@pytest.mark.asyncio
async def test_publish_and_handle_spans_created_and_attributes(otel_memory_provider):
    exporter: InMemorySpanExporter = otel_memory_provider
    # Start orchestrator (subscribes handler)
    await orchestrator.start()
    try:
        # Publish a normal event
        await bus.publish(
            Event(
                type=CONV_MSG,
                project_id="p1",
                payload={"content": "hello"},
                ts=0.0,
                request_id="r-123",
            )
        )
        # Allow tasks to process
        await asyncio.sleep(0)
    finally:
        await orchestrator.stop()

    spans = exporter.get_finished_spans()
    # Expect at least two spans: EventBus.publish and Orchestrator.handle
    names = [s.name for s in spans]
    assert "EventBus.publish" in names
    assert "Orchestrator.handle" in names

    # Verify attributes on handle span
    handle_spans = [s for s in spans if s.name == "Orchestrator.handle"]
    assert handle_spans, "expected handle span"
    hs = handle_spans[0]
    assert hs.attributes.get("evt_type") == CONV_MSG
    assert hs.attributes.get("project_id") == "p1"
    assert hs.attributes.get("request_id") == "r-123"
    assert hs.attributes.get("phase") == "consume"


@pytest.mark.asyncio
async def test_error_span_status_on_handler_exception(otel_memory_provider):
    exporter: InMemorySpanExporter = otel_memory_provider
    await orchestrator.start()
    try:
        await bus.publish(
            Event(
                type=CONV_MSG,
                project_id="p1",
                payload={"content": "boom", "force_error": True},
                ts=0.0,
                request_id="r-err",
            )
        )
        await asyncio.sleep(0)
    finally:
        await orchestrator.stop()

    spans = exporter.get_finished_spans()
    handle_spans = [s for s in spans if s.name == "Orchestrator.handle"]
    assert handle_spans, "expected handle span"
    hs = handle_spans[0]
    # ERROR status expected
    # In OpenTelemetry Python SDK, StatusCode.ERROR is stored as Status.status_code == StatusCode.ERROR
    assert getattr(hs.status, "status_code", None) is not None
    assert str(hs.status.status_code).endswith("ERROR")


def test_log_correlation_in_span(otel_memory_provider, capsys):
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("log-corr-test"):
        log_json("info", "test.trace.msg", foo="bar")
    # Capture stdout and parse JSON lines, find our message
    out = capsys.readouterr().out.strip().splitlines()
    records = [json.loads(line) for line in out if line.strip()]
    ours = [r for r in records if r.get("message") == "test.trace.msg"]
    assert ours, f"did not find our log message in output: {out}"
    rec = ours[-1]
    # Ensure trace/span ids present and look like hex strings
    assert rec.get("trace_id") and isinstance(rec["trace_id"], str)
    assert rec.get("span_id") and isinstance(rec["span_id"], str)
    assert len(rec["trace_id"]) == 32
    assert len(rec["span_id"]) == 16
