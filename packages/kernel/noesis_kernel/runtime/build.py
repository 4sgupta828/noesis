"""Build providers by mode, and discover the active vertical.

Providers are always cassette-wrapped: `replay` (default) runs offline for free;
`record`/`live` use the real Anthropic/OpenAI/Tavily backends. So the same code
path serves dev/CI/eval and production — credits are opt-in via NOESIS_PROVIDER_MODE.
"""
from __future__ import annotations

import os
from pathlib import Path

from noesis_kernel.providers.anthropic_llm import AnthropicLLM
from noesis_kernel.providers.base import ProviderMode, resolve_mode
from noesis_kernel.providers.embeddings import (
    OPENAI_EMBED_DIM,
    CassetteEmbedder,
    Embedder,
    OpenAIEmbedder,
)
from noesis_kernel.providers.llm import CassetteLLM, LLMClient
from noesis_kernel.providers.web_tavily import TavilyWebSearch
from noesis_kernel.providers.websearch import CassetteWebSearch, WebSearchClient


def default_cassette_root() -> Path:
    return Path(os.environ.get("NOESIS_CASSETTE_ROOT", "evals/cassettes"))


def _route_by_name(model: str | None) -> str | None:
    """A model NAME picks its provider — so an explicit `claude-*` stays Anthropic even when the global
    provider is switched to deepseek, and vice versa (mirrors eigen)."""
    mn = (model or "").lower()
    if mn.startswith("deepseek"):
        return "deepseek"
    if mn.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if mn.startswith("claude"):
        return "anthropic"
    return None


def _build_inner_llm(model: str | None) -> LLMClient:
    """Provider seam. `NOESIS_LLM_PROVIDER` (default 'anthropic') selects the family; `NOESIS_LLM_MODEL`
    the model. An explicit model name overrides the provider (see `_route_by_name`). DeepSeek and OpenAI
    reuse the OpenAI-protocol client (DeepSeek is OpenAI-compatible via base_url). Default (no provider
    env, no model) → AnthropicLLM() exactly as before → byte-identical."""
    provider = _route_by_name(model) or os.environ.get("NOESIS_LLM_PROVIDER", "anthropic").strip().lower()
    if provider == "deepseek":
        from noesis_kernel.providers.openai_client import OpenAILLMClient
        return OpenAILLMClient(
            model=model or os.environ.get("NOESIS_LLM_MODEL", "deepseek-chat"),
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url=os.environ.get("NOESIS_DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    if provider == "openai":
        from noesis_kernel.providers.openai_client import OpenAILLMClient
        return OpenAILLMClient(model=model or os.environ.get("NOESIS_LLM_MODEL", "gpt-4o"))
    return AnthropicLLM(model=model) if model else AnthropicLLM()


def build_llm(*, mode: ProviderMode | str | None = None, cassette_root: Path | None = None,
              model: str | None = None) -> LLMClient:
    m = resolve_mode(mode)
    inner = None if m is ProviderMode.REPLAY else _build_inner_llm(model)
    return CassetteLLM(inner, cassette_root=cassette_root or default_cassette_root(),
                       namespace="llm", mode=m)


def build_embedder(*, mode: ProviderMode | str | None = None, cassette_root: Path | None = None,
                   dim: int = OPENAI_EMBED_DIM) -> Embedder:
    m = resolve_mode(mode)
    inner = None if m is ProviderMode.REPLAY else OpenAIEmbedder(dim=dim)
    return CassetteEmbedder(inner, cassette_root=cassette_root or default_cassette_root(),
                            namespace="embed", dim=dim, mode=m)


def build_web(*, mode: ProviderMode | str | None = None,
              cassette_root: Path | None = None,
              domains: tuple[str, ...] | list[str] | None = None) -> WebSearchClient:
    m = resolve_mode(mode)
    # Prefer Exa (neural search) when its key is set; else Tavily. Same WebSearchClient port.
    # `domains` (from the vertical) restricts Exa to a trusted-sources whitelist.
    inner = None
    if m is not ProviderMode.REPLAY:
        if os.environ.get("EXA_API_KEY"):
            from noesis_kernel.providers.exa_web import ExaWebSearch
            inner = ExaWebSearch(include_domains=list(domains or []))
        else:
            inner = TavilyWebSearch()
    return CassetteWebSearch(inner, cassette_root=cassette_root or default_cassette_root(),
                             namespace="web", mode=m)


def load_active_vertical(name: str | None = None):
    """Discover installed verticals via the `noesis.verticals` entry point and
    return the one named by NOESIS_ACTIVE_VERTICAL (single-vertical-per-deployment)."""
    from importlib.metadata import entry_points

    want = name or os.environ.get("NOESIS_ACTIVE_VERTICAL")
    eps = list(entry_points(group="noesis.verticals"))
    if not eps:
        raise RuntimeError("no noesis.verticals installed")
    ep = next((e for e in eps if e.name == want), None) if want else eps[0]
    if ep is None:
        raise RuntimeError(f"active vertical {want!r} not found (have: {[e.name for e in eps]})")
    return ep.load()
