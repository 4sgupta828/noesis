"""Web-search provider seam routing (Brave / Exa / Tavily). No network — class selection only."""
from __future__ import annotations

import pytest

from noesis_kernel.providers.brave_web import BraveWebSearch
from noesis_kernel.providers.exa_web import ExaWebSearch
from noesis_kernel.providers.web_tavily import TavilyWebSearch
from noesis_kernel.runtime.build import _build_inner_web, _web_provider


def _clear(monkeypatch):
    for k in ("NOESIS_WEB_PROVIDER", "BRAVE_API_KEY", "EXA_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_default_without_keys_is_tavily(monkeypatch):
    _clear(monkeypatch)
    assert _web_provider() == "tavily"
    assert isinstance(_build_inner_web(), TavilyWebSearch)


def test_brave_key_wins_over_exa_key(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("EXA_API_KEY", "x")
    assert isinstance(_build_inner_web(("kdigo.org",)), ExaWebSearch)
    monkeypatch.setenv("BRAVE_API_KEY", "b")
    ws = _build_inner_web(("kdigo.org", "nice.org.uk"))
    assert isinstance(ws, BraveWebSearch)
    assert ws._include_domains == ["kdigo.org", "nice.org.uk"]      # vertical whitelist reaches the client


def test_explicit_provider_overrides_keys(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("BRAVE_API_KEY", "b")
    monkeypatch.setenv("NOESIS_WEB_PROVIDER", "exa")
    assert isinstance(_build_inner_web(), ExaWebSearch)
    monkeypatch.setenv("NOESIS_WEB_PROVIDER", "bogus")
    with pytest.raises(ValueError):
        _build_inner_web()
