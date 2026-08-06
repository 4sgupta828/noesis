"""AnthropicLLM: a max_tokens cutoff must surface a CLEAR truncation error, not an opaque
pydantic ValidationError from a half-emitted tool call."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from noesis_kernel.providers.anthropic_llm import AnthropicLLM
from noesis_kernel.research.react import ComposedAnswer


class _FakeMessages:
    def __init__(self, resp):
        self._resp = resp

    def create(self, **kw):
        return self._resp


def _llm_with(resp):
    llm = AnthropicLLM(model="test", api_key="x")
    llm._client = SimpleNamespace(messages=_FakeMessages(resp))   # pre-set → _ensure() is a no-op
    return llm


def test_truncation_raises_clear_error():
    resp = SimpleNamespace(
        stop_reason="max_tokens",
        content=[SimpleNamespace(type="tool_use", name="emit", input={})],  # partial/empty input
        usage=SimpleNamespace(input_tokens=10, output_tokens=2048))
    llm = _llm_with(resp)
    with pytest.raises(RuntimeError, match="truncated"):
        asyncio.run(llm.complete(system="s", messages=[{"role": "user", "content": "q"}],
                                 response_format=ComposedAnswer, max_tokens=2048))


def test_normal_completion_parses():
    resp = SimpleNamespace(
        stop_reason="tool_use",
        content=[SimpleNamespace(type="tool_use", name="emit",
                                 input={"answer": "The answer [1].", "directly_addresses": True, "gap_note": ""})],
        usage=SimpleNamespace(input_tokens=10, output_tokens=20))
    llm = _llm_with(resp)
    out = asyncio.run(llm.complete(system="s", messages=[{"role": "user", "content": "q"}],
                                   response_format=ComposedAnswer, max_tokens=8000))
    assert out.parsed.answer == "The answer [1]."
    assert out.output_tokens == 20
