import asyncio
import importlib
import sys
import time
from types import SimpleNamespace

import pytest

import server.memory.semantic as semantic


@pytest.mark.asyncio
async def test_compute_embedding_mock_inline(monkeypatch):
    monkeypatch.setenv("SEMANTIC_MODEL", "mock")
    module = importlib.reload(semantic)
    try:
        async def fail_to_thread(*args, **kwargs):
            raise AssertionError("mock embedder should not offload to a thread")

        monkeypatch.setattr(module.asyncio, "to_thread", fail_to_thread)

        start = time.perf_counter()
        result = await module.compute_embedding("hello world")
        duration = time.perf_counter() - start

        assert isinstance(result, list)
        assert len(result) == module.get_dimension()
        assert duration < 0.1
    finally:
        monkeypatch.delenv("SEMANTIC_MODEL", raising=False)
        module._embedder = None
        importlib.reload(module)


@pytest.mark.asyncio
async def test_compute_embedding_minilm_offloads(monkeypatch):
    dimension = semantic.get_dimension()

    class FakeSentenceTransformer:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def encode(self, inputs):
            time.sleep(0.2)
            return [[float(i) for i in range(dimension)]]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    monkeypatch.setenv("SEMANTIC_MODEL", "minilm")
    module = importlib.reload(semantic)

    original_to_thread = module.asyncio.to_thread
    calls = {"count": 0}

    async def tracked_to_thread(*args, **kwargs):
        calls["count"] += 1
        return await original_to_thread(*args, **kwargs)

    monkeypatch.setattr(module.asyncio, "to_thread", tracked_to_thread)

    try:
        start = time.perf_counter()
        task = asyncio.create_task(module.compute_embedding("blocking"))

        await asyncio.sleep(0.05)
        mid = time.perf_counter()

        assert calls["count"] == 1
        assert not task.done()

        result = await task
        duration = time.perf_counter() - start

        assert isinstance(result, list)
        assert len(result) == module.get_dimension()
        assert duration >= 0.2
        assert mid - start < 0.2
    finally:
        monkeypatch.delenv("SEMANTIC_MODEL", raising=False)
        module._embedder = None
        importlib.reload(module)
