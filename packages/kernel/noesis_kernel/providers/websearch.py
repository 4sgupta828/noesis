"""Web-search provider port + deterministic fake.

Mechanism only — which sites/providers to curate is a vertical concern and is
supplied through the vertical contract, never hardcoded here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class WebResult:
    url: str
    title: str
    snippet: str
    body: str | None = None


@runtime_checkable
class WebSearchClient(Protocol):
    async def search(self, query: str, *, max_results: int = 10) -> list[WebResult]: ...


class FakeWebSearch:
    """Offline web search returning canned results per query (tests)."""

    def __init__(self, canned: dict[str, list[WebResult]] | None = None):
        self._canned = canned or {}

    async def search(self, query: str, *, max_results: int = 10) -> list[WebResult]:
        return self._canned.get(query, [])[:max_results]
