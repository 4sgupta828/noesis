"""Provider-seam routing (DeepSeek swap, mirrors eigen). No network — only class selection."""
from __future__ import annotations

import os

import pytest

from noesis_kernel.providers.anthropic_llm import AnthropicLLM
from noesis_kernel.runtime.build import _build_inner_llm, _route_by_name


def _clear(monkeypatch):
    for k in ("NOESIS_LLM_PROVIDER", "NOESIS_LLM_MODEL", "DEEPSEEK_API_KEY", "NOESIS_DEEPSEEK_BASE_URL"):
        monkeypatch.delenv(k, raising=False)


def test_default_is_anthropic_byte_identical(monkeypatch):
    _clear(monkeypatch)
    assert isinstance(_build_inner_llm(None), AnthropicLLM)


def test_provider_env_selects_deepseek(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("NOESIS_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    llm = _build_inner_llm(None)
    from noesis_kernel.providers.openai_client import OpenAILLMClient
    assert isinstance(llm, OpenAILLMClient)
    assert llm._model == "deepseek-chat"                       # default model for the family
    assert llm._base_url == "https://api.deepseek.com"          # DeepSeek endpoint


def test_model_name_overrides_provider(monkeypatch):
    _clear(monkeypatch)
    # global provider is deepseek, but an explicit claude-* model stays Anthropic (cheap-model escape)
    monkeypatch.setenv("NOESIS_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert isinstance(_build_inner_llm("claude-haiku-4-5-20251001"), AnthropicLLM)
    # and a deepseek-* model name routes to DeepSeek even with no provider env
    _clear(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    from noesis_kernel.providers.openai_client import OpenAILLMClient
    assert isinstance(_build_inner_llm("deepseek-reasoner"), OpenAILLMClient)


@pytest.mark.parametrize("name,expected", [
    ("deepseek-chat", "deepseek"), ("deepseek-reasoner", "deepseek"),
    ("gpt-4o", "openai"), ("o3-mini", "openai"),
    ("claude-sonnet-5", "anthropic"), (None, None), ("", None), ("mistral-large", None),
])
def test_route_by_name(name, expected):
    assert _route_by_name(name) == expected
