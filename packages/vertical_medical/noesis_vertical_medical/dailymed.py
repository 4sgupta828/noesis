"""DailyMed connector — authoritative SPL drug labels (Tier-1, public domain).

dailymed.nlm.nih.gov (NLM, 158k SPLs). The list endpoint gives setid+title; the
per-SPL text is fetched on demand. source_key='dailymed'. Complements openFDA
labels (same SPL source, NLM-authoritative). Fixture-injectable for offline tests.
"""
from __future__ import annotations

V2 = "https://dailymed.nlm.nih.gov/dailymed/services/v2"


class DailyMedConnector:
    key = "dailymed"

    class _Http:
        egress_class="datacenter"; engine="http"; proxy_enabled=False
        async def fetch(self, url, **o):
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as c:
                r=await c.get(url); r.raise_for_status(); return r.content

    def __init__(self, *, spls: list[dict] | None = None, page_size: int = 50):
        self.fetch_strategy=self._Http(); self._page_size=page_size
        # spls: list of {setid,title, [text]} — fixtures may carry text
        self._by_id={s["setid"]: s for s in (spls or [])}

    async def _list(self, limit):
        import httpx
        url=f"{V2}/spls.json?pagesize={min(limit,self._page_size)}"
        async with httpx.AsyncClient(timeout=30.0) as c:
            r=await c.get(url); r.raise_for_status()
            return r.json().get("data",[])

    def _facets(self, s):
        return {"source_kind":"drug_label"}

    async def discover_entities(self, window):
        from noesis_kernel.contract.dto import EntityRef
        if not (window or {}).get("query") and self._by_id:
            items=list(self._by_id.values())
        else:
            items=await self._list(int((window or {}).get("limit",self._page_size)))
            for s in items: self._by_id.setdefault(s["setid"], s)
        return [EntityRef(source_key=self.key, native_id=s["setid"], title=s.get("title",""),
                          facets=self._facets(s)) for s in items]

    async def list_documents(self, entity):
        from noesis_kernel.contract.dto import DocumentRef
        return [DocumentRef(source_key=self.key, native_id=entity.native_id, title=entity.title,
                            content_type="text/markdown", facets={"source_kind":"drug_label"},
                            entity_ids=(entity.native_id,))]

    async def fetch_artifact(self, doc):
        s=self._by_id.get(doc.native_id, {})
        text=s.get("text")
        if not text:
            # live: fetch the SPL's structured sections (JSON) and join their titles/text
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as c:
                r=await c.get(f"{V2}/spls/{doc.native_id}.json")
                text = r.text if r.status_code==200 else ""
        md=f"# {s.get('title','Drug label')} — DailyMed SPL\n\n{(text or 'Structured product label.').strip()[:6000]}\n"
        return md.encode("utf-8")
