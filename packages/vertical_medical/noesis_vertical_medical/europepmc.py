"""Europe PMC connector — the published literature (Tier-1, public, no auth).

Europe PMC REST search (spans PubMed/MEDLINE/PMC). Each article → one citable
markdown doc (title + abstract) with facets {pub_type, journal, year,
open_access, source_db}. source_key='europepmc' so every block is tagged to it.
Abstract-level now; OA full text is a follow-up via the fullTextXML endpoint.
"""
from __future__ import annotations

import urllib.parse

SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
REST = "https://www.ebi.ac.uk/europepmc/webservices/rest"
_FULLTEXT_CAP = 35000          # chars of parsed body kept (abstracts stay tiny; OA full text is big)


def _fulltext_url(r: dict) -> str:
    """OA full-text XML endpoint, only for open-access articles present in PMC."""
    pmcid = (r.get("pmcid") or "").strip()      # e.g. "PMC3257301" (prefix included)
    if r.get("isOpenAccess") == "Y" and pmcid:
        return f"{REST}/{pmcid}/fullTextXML"     # note: NO /PMC/ source segment (that 404s)
    return ""


def _xml_to_text(xml_bytes: bytes) -> str:
    """Flatten JATS <body> into plain text — section titles + paragraphs only. Skips the reference
    list, tables, and figures (citation/markup noise) so a cited quote lands in clean prose.
    Fail-safe: any parse error → '' (caller falls back to the abstract). This is structural text
    extraction, not a semantic decision (Rule 18)."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:   # noqa: BLE001
        return ""
    body = root.find(".//{*}body")
    if body is None:
        return ""
    for rl in body.findall(".//{*}ref-list"):      # drop reference dumps
        for child in list(rl):
            rl.remove(child)
    out: list[str] = []
    for el in body.iter():
        tag = el.tag.split("}")[-1]
        if tag == "title":
            t = " ".join("".join(el.itertext()).split()).strip()
            if t:
                out.append(f"## {t}")
        elif tag == "p":
            t = " ".join("".join(el.itertext()).split()).strip()
            if t:
                out.append(t)
    return "\n\n".join(out).strip()


def _facets(r: dict) -> dict:
    f = {
        "source_kind": "article",
        "source_db": (r.get("source") or "").lower(),          # MED / PMC / …
        "open_access": "yes" if r.get("isOpenAccess") == "Y" else "no",
    }
    if r.get("pubYear"):
        f["year"] = str(r["pubYear"])
    jt = r.get("journalTitle") or (r.get("journalInfo") or {}).get("journal", {}).get("title")
    if jt:
        f["journal"] = jt.lower()
    pt = r.get("pubTypeList", {}).get("pubType") if isinstance(r.get("pubTypeList"), dict) else None
    if pt:
        f["pub_type"] = (pt[0] if isinstance(pt, list) else pt).lower()
    return {k: v for k, v in f.items() if v}


def _markdown(r: dict) -> str:
    parts = [f"# {r.get('title', 'Untitled').rstrip('.')}", ""]
    meta = []
    if r.get("authorString"):
        meta.append(f"Authors: {r['authorString']}")
    jt = r.get("journalTitle")
    if jt:
        meta.append(f"Journal: {jt} ({r.get('pubYear','')})")
    if r.get("doi"):
        meta.append(f"DOI: {r['doi']}")
    if meta:
        parts += ["\n".join(meta), ""]
    if r.get("abstractText"):
        parts += ["## Abstract", "", r["abstractText"].strip()]
    return "\n".join(parts).strip() + "\n"


def _art_id(r: dict) -> str:
    src = r.get("source", "MED")
    return f"{src}:{r.get('id') or r.get('pmid') or ''}"


class EuropePmcConnector:
    key = "europepmc"

    class _Http:
        egress_class = "datacenter"; engine = "http"; proxy_enabled = False
        async def fetch(self, url: str, **o) -> bytes:  # noqa: ANN003
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get(url); r.raise_for_status(); return r.content

    def __init__(self, *, articles: list[dict] | None = None, page_size: int = 100,
                 full_text: bool = False):
        self.fetch_strategy = self._Http()
        self._page_size = page_size
        self._full_text = full_text     # OFF → abstract-only (byte-identical to pre-change)
        self._by_id: dict[str, dict] = {}
        for a in articles or []:
            self._by_id[_art_id(a)] = a

    async def _fetch_fulltext(self, r: dict) -> str:
        """Fetch + flatten the OA full text for an article. Fail-safe → '' (fall back to abstract)."""
        url = _fulltext_url(r)
        if not url:
            return ""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=40.0) as c:
                resp = await c.get(url)
            if resp.status_code != 200:
                return ""
            return _xml_to_text(resp.content)[:_FULLTEXT_CAP]
        except Exception:   # noqa: BLE001
            return ""

    async def _fetch(self, query: str, limit: int) -> list[dict]:
        import httpx
        out: list[dict] = []
        cursor = "*"
        q = urllib.parse.quote(query)
        async with httpx.AsyncClient(timeout=30.0) as c:
            while len(out) < limit:
                n = min(100, limit - len(out))
                url = (f"{SEARCH}?query={q}&format=json&resultType=core"
                       f"&pageSize={n}&cursorMark={urllib.parse.quote(cursor)}")
                r = await c.get(url); r.raise_for_status()
                d = r.json()
                batch = d.get("resultList", {}).get("result", [])
                if not batch:
                    break
                out.extend(batch)
                nxt = d.get("nextCursorMark")
                if not nxt or nxt == cursor:
                    break
                cursor = nxt
        return out[:limit]

    async def discover_entities(self, window: dict):
        from noesis_kernel.contract.dto import EntityRef
        if not (window or {}).get("query") and self._by_id:
            arts = list(self._by_id.values())
        else:
            arts = await self._fetch((window or {}).get("query", "medicine"),
                                     int((window or {}).get("limit", self._page_size)))
            for a in arts:
                self._by_id[_art_id(a)] = a
        return [EntityRef(source_key=self.key, native_id=_art_id(a),
                          title=a.get("title", ""), facets=_facets(a)) for a in arts]

    async def list_documents(self, entity):
        from noesis_kernel.contract.dto import DocumentRef
        a = self._by_id.get(entity.native_id)
        return [DocumentRef(source_key=self.key, native_id=entity.native_id,
                            title=entity.title, content_type="text/markdown",
                            facets=_facets(a) if a else dict(entity.facets),
                            entity_ids=(entity.native_id,))]

    async def fetch_artifact(self, doc) -> bytes:
        r = self._by_id[doc.native_id]
        md = _markdown(r)
        if self._full_text:                       # OA full text appended after the abstract
            ft = await self._fetch_fulltext(r)
            if ft:
                md = md.rstrip() + "\n\n## Full text\n\n" + ft + "\n"
        return md.encode("utf-8")
