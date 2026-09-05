"""BraveWebSearch — parsing, whitelist post-filter, body fetch + fallback. No network (MockTransport)."""
from __future__ import annotations

import json

import httpx
import pytest

from noesis_kernel.providers.brave_web import BRAVE_URL, BraveWebSearch, html_to_text

_PAGE_HTML = """<html><head><title>T</title><style>.x{color:red}</style>
<script>var a = 1 &lt; 2;</script></head><body><nav>menu</nav>
<h1>Metformin &amp; eGFR</h1><p>Continue at a reduced dose (maximum 1,000 mg daily) when eGFR is 30&ndash;44.</p>
<p>Do not initiate below 45.</p></body></html>"""

_BRAVE_JSON = {
    "type": "search",
    "web": {"results": [
        {"url": "https://www.drugs.com/dosage/metformin.html", "title": "Metformin Dosage",
         "description": "Dose titration: <strong>500 mg</strong> weekly", "page_age": "2025-07-21T00:00:00",
         "extra_snippets": ["eGFR greater than 45: No dose adjustments recommended", ""]},
        {"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7043977/", "title": "Metformin and CKD",
         "description": "Checking your browser", "extra_snippets": ["Reduce to 1,000 mg/day at eGFR 30-44"]},
        {"url": "https://kdigo.org/guidelines/diabetes-ckd/", "title": "KDIGO Diabetes in CKD",
         "description": "Guideline", "page_age": "2022-11-01T00:00:00"},
    ]},
}


def _transport(*, pages: dict[str, tuple[int, str, str]] | None = None, api_status: int = 200,
               calls: list | None = None) -> httpx.MockTransport:
    pages = pages or {}

    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        if str(request.url).startswith(BRAVE_URL):
            assert request.headers["X-Subscription-Token"] == "test-key"
            assert request.url.params["extra_snippets"] == "true"
            return httpx.Response(api_status, json=_BRAVE_JSON if api_status == 200 else {"message": "no"})
        status, ctype, body = pages.get(str(request.url), (404, "text/html", ""))
        return httpx.Response(status, headers={"content-type": ctype}, content=body.encode())

    return httpx.MockTransport(handler)


def test_html_to_text_strips_scripts_tags_entities() -> None:
    t = html_to_text(_PAGE_HTML)
    assert "var a" not in t and "color:red" not in t
    assert "Metformin & eGFR" in t
    assert "maximum 1,000 mg daily) when eGFR is 30–44." in t
    assert "\nDo not initiate below 45." in t         # block close → newline (chunk boundary)


@pytest.mark.asyncio
async def test_search_parses_and_fetches_bodies() -> None:
    pages = {"https://www.drugs.com/dosage/metformin.html": (200, "text/html; charset=utf-8", _PAGE_HTML)}
    ws = BraveWebSearch(api_key="test-key", min_interval=0, transport=_transport(pages=pages))
    res = await ws.search("metformin eGFR 30-45", max_results=8)
    assert [r.url for r in res] == [r["url"] for r in _BRAVE_JSON["web"]["results"]]
    first = res[0]
    assert first.title == "Metformin Dosage"
    assert first.snippet == "Dose titration: 500 mg weekly"           # decorations stripped
    assert first.published == "2025-07-21T00:00:00"
    assert first.highlights == ("eGFR greater than 45: No dose adjustments recommended",)   # blanks dropped
    assert "maximum 1,000 mg daily" in (first.body or "")             # fetched page text is the body
    # bot-walled / 404 page → snippets become the body so the span-check still has verbatim text
    pmc = res[1]
    assert pmc.body == "Reduce to 1,000 mg/day at eGFR 30-44"
    # no snippets, no page → description is the body of last resort
    assert res[2].body == "Guideline"


@pytest.mark.asyncio
async def test_whitelist_post_filter_and_overfetch() -> None:
    calls: list[httpx.Request] = []
    ws = BraveWebSearch(api_key="test-key", min_interval=0, fetch_bodies=False,
                        include_domains=["ncbi.nlm.nih.gov", "kdigo.org"], transport=_transport(calls=calls))
    res = await ws.search("q", max_results=5)
    assert [r.url for r in res] == ["https://pmc.ncbi.nlm.nih.gov/articles/PMC7043977/",
                                    "https://kdigo.org/guidelines/diabetes-ckd/"]
    assert calls[0].url.params["count"] == "15"           # 3× over-fetch when a whitelist thins results
    assert len(calls) == 1                                # fetch_bodies=False → no page requests


@pytest.mark.asyncio
async def test_non_retryable_status_raises_immediately() -> None:
    ws = BraveWebSearch(api_key="test-key", min_interval=0, transport=_transport(api_status=401))
    with pytest.raises(httpx.HTTPStatusError):
        await ws.search("q")


@pytest.mark.asyncio
async def test_rate_limit_is_retried(monkeypatch) -> None:
    n = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        n["i"] += 1
        if n["i"] < 3:
            return httpx.Response(429, json={"message": "slow down"})
        return httpx.Response(200, json=_BRAVE_JSON)

    import noesis_kernel.providers.brave_web as mod

    async def _no_sleep(_s):        # keep the test instant
        return None
    monkeypatch.setattr(mod.asyncio, "sleep", _no_sleep)
    ws = BraveWebSearch(api_key="test-key", min_interval=0, fetch_bodies=False,
                        transport=httpx.MockTransport(handler))
    res = await ws.search("q", max_results=2)
    assert n["i"] == 3 and len(res) == 2
