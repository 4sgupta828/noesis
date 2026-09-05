"""BraveWebSearch — a real WebSearchClient over the Brave Search API (api.search.brave.com).

Same port as ExaWebSearch / TavilyWebSearch. Brave returns ranked results plus query-aware
`extra_snippets`, but NOT the page text — and the provenance gate needs the fetched body to verify
that a cited quote exists in the page. So after the search we FETCH each result page directly
(bounded, concurrent) and reduce the HTML to text; a bot-walled page falls back to its snippets as
the body, which are still verbatim spans from the page. Highlights = Brave's extra snippets.

Domain whitelist: Brave has no include-domains parameter, so the vertical-supplied list is applied
as a post-filter over an over-fetched result set (count up to 20). Empty list → open web.

Rate limits: the entry plans allow ~1 request/second, so calls are throttled in-process
(min-interval gate, `NOESIS_BRAVE_MIN_INTERVAL`) and 429/5xx/transport errors are retried with a
short backoff. Lazy httpx import; wrap in a cassette for free replay.
"""
from __future__ import annotations

import asyncio
import html as _html
import os
import re
import time

from .websearch import WebResult

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
_BRAVE_MAX_COUNT = 20                      # API hard cap per request
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/124.0 Safari/537.36 NoesisBot/1.0")

_DROP_BLOCK_RE = re.compile(r"<(script|style|noscript|svg|template|iframe)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_BREAK_RE = re.compile(r"<\s*(br\s*/?|/p|/div|/li|/tr|/h[1-6]|/section|/article|/blockquote|/td|/th)\s*>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACES_RE = re.compile(r"[ \t\r\f\v ]+")
_BLANKS_RE = re.compile(r"\n\s*\n+")


def html_to_text(raw: str, *, max_chars: int = 4000) -> str:
    """Reduce an HTML page to readable text: drop script/style blocks, turn block-level closes into
    newlines, strip the remaining tags, unescape entities, collapse whitespace. Deliberately
    dependency-free (no bs4/lxml) — good enough for span verification, not for layout."""
    if not raw:
        return ""
    s = _DROP_BLOCK_RE.sub(" ", raw)
    s = _BREAK_RE.sub("\n", s)
    s = _TAG_RE.sub(" ", s)
    s = _html.unescape(s)
    s = _SPACES_RE.sub(" ", s)
    s = "\n".join(line.strip() for line in s.split("\n"))
    s = _BLANKS_RE.sub("\n", s).strip()
    return s[:max_chars]


def _host_of(url: str) -> str:
    m = re.match(r"https?://([^/:?#]+)", url or "")
    return m.group(1).lower() if m else ""


def _allowed(url: str, domains: list[str]) -> bool:
    if not domains:
        return True
    host = _host_of(url)
    return any(host == d or host.endswith("." + d) for d in domains)


class BraveWebSearch:
    # process-wide throttle shared by every instance (one API key → one rate limit)
    _gate: asyncio.Lock | None = None
    _last_call: float = 0.0

    def __init__(self, *, api_key: str | None = None, timeout: float = 10.0,
                 include_domains: list[str] | None = None, fetch_bodies: bool = True,
                 body_timeout: float = 6.0, body_chars: int = 4000, min_interval: float | None = None,
                 transport=None):
        self._api_key = api_key or os.environ.get("BRAVE_API_KEY", "")
        self._timeout = timeout
        self._include_domains = [d.strip().lower() for d in (include_domains or []) if d and d.strip()]
        self._fetch_bodies = fetch_bodies
        self._body_timeout = body_timeout
        self._body_chars = body_chars
        self._min_interval = (float(os.environ.get("NOESIS_BRAVE_MIN_INTERVAL", "1.0"))
                              if min_interval is None else min_interval)
        self._transport = transport          # tests: httpx.MockTransport

    # ---- throttle -------------------------------------------------------------------------
    async def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        cls = type(self)
        if cls._gate is None:
            cls._gate = asyncio.Lock()
        async with cls._gate:
            wait = cls._last_call + self._min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            cls._last_call = time.monotonic()

    # ---- search ---------------------------------------------------------------------------
    async def search(self, query: str, *, max_results: int = 8) -> list[WebResult]:
        import httpx
        # over-fetch when a whitelist will thin the results; Brave caps count at 20
        count = min(_BRAVE_MAX_COUNT, max_results * 3 if self._include_domains else max_results)
        params = {"q": query, "count": max(1, count), "extra_snippets": "true",
                  "text_decorations": "false"}
        headers = {"Accept": "application/json", "Accept-Encoding": "gzip",
                   "X-Subscription-Token": self._api_key}
        data = None
        last_err: Exception | None = None
        for attempt in range(3):
            await self._throttle()
            try:
                async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                    resp = await client.get(BRAVE_URL, params=params, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                break
            except httpx.HTTPStatusError as e:
                last_err = e
                if e.response.status_code != 429 and e.response.status_code < 500:
                    raise                      # genuine request problem (auth, bad params) — no retry
            except httpx.HTTPError as e:       # timeouts / connect errors — transient
                last_err = e
            await asyncio.sleep(0.75 * (attempt + 1))
        if data is None:
            raise last_err or RuntimeError("brave search failed")

        raw = ((data.get("web") or {}).get("results")) or []
        picked = [r for r in raw if r.get("url") and _allowed(r["url"], self._include_domains)][:max_results]
        bodies: list[str] = [""] * len(picked)
        if self._fetch_bodies and picked:
            bodies = await self._fetch_all([r["url"] for r in picked])

        out: list[WebResult] = []
        for r, body in zip(picked, bodies):
            desc = html_to_text(r.get("description") or "", max_chars=600)
            snippets = tuple(html_to_text(h, max_chars=1200) for h in (r.get("extra_snippets") or []) if h)
            snippets = tuple(h for h in snippets if h)
            text = body or "\n".join(snippets) or desc
            out.append(WebResult(
                url=r["url"],
                title=html_to_text(r.get("title") or "", max_chars=300) or r["url"],
                snippet=desc or text[:400],
                body=text,
                published=r.get("page_age") or None,   # ISO timestamp when Brave dates the page
                highlights=snippets,
            ))
        return out

    # ---- page bodies ----------------------------------------------------------------------
    async def _fetch_all(self, urls: list[str]) -> list[str]:
        import httpx
        sem = asyncio.Semaphore(6)
        headers = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
                   "Accept-Language": "en"}

        async def one(url: str) -> str:
            async with sem:
                try:
                    async with httpx.AsyncClient(timeout=self._body_timeout, follow_redirects=True,
                                                 transport=self._transport, headers=headers) as client:
                        resp = await client.get(url)
                        if resp.status_code != 200:
                            return ""
                        ctype = (resp.headers.get("content-type") or "").lower()
                        if "html" not in ctype and "text/plain" not in ctype and "xml" not in ctype:
                            return ""                      # PDFs/binaries: snippets carry the body
                        raw = resp.content[:600_000].decode(resp.encoding or "utf-8", errors="ignore")
                        return html_to_text(raw, max_chars=self._body_chars) if "html" in ctype or "xml" in ctype \
                            else raw[: self._body_chars]
                except Exception:      # noqa: BLE001 — a body fetch must never sink the search
                    return ""

        return list(await asyncio.gather(*(one(u) for u in urls)))
