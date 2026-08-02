"""ExaWebSearch — a real WebSearchClient over the Exa (exa.ai) neural search API.

Same port as TavilyWebSearch: returns WebResult with a `body` (page text) so the provenance
gate can verify a cited quote exists in the fetched page. Lazy httpx call; optional dep. Wrap
in a cassette for free replay. Auth via the `x-api-key` header; content requested inline so a
single call returns both the ranked results and their text.
"""
from __future__ import annotations

import os

from .websearch import WebResult

EXA_URL = "https://api.exa.ai/search"


class ExaWebSearch:
    def __init__(self, *, api_key: str | None = None, timeout: float = 10.0,
                 include_domains: list[str] | None = None):
        self._api_key = api_key or os.environ.get("EXA_API_KEY", "")
        self._timeout = timeout
        # Restrict results to a whitelist of trusted domains (the VERTICAL supplies these — e.g.
        # peer-reviewed journals, guideline bodies, gov/authoritative sources). Empty → open web.
        self._include_domains = [d for d in (include_domains or []) if d]

    async def search(self, query: str, *, max_results: int = 8) -> list[WebResult]:
        import httpx
        payload = {
            "query": query,
            "numResults": max_results,
            "type": "auto",                       # let Exa pick neural vs keyword
            "contents": {"text": {"maxCharacters": 4000}},   # inline page text for provenance
        }
        if self._include_domains:
            payload["includeDomains"] = self._include_domains   # trusted-sources-only
        headers = {"x-api-key": self._api_key, "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(EXA_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        out: list[WebResult] = []
        for r in data.get("results", []):
            text = r.get("text") or ""
            out.append(WebResult(
                url=r.get("url", ""),
                title=r.get("title") or r.get("url", ""),
                snippet=(text[:400] if text else (r.get("summary") or "")),
                body=text or r.get("summary") or "",
            ))
        return out
