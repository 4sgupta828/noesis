"""CDC connector — public-health datasets/guidance (Tier-1, public domain).

data.cdc.gov catalog (Socrata). The one apex-authority source that is freely +
programmatically open. Each catalog entry → a citable doc (name + description).
source_key='cdc'. Dataset-level metadata now; per-record/MMWR text is a follow-up.
"""
from __future__ import annotations


class CdcConnector:
    key = "cdc"
    CATALOG = "https://data.cdc.gov/api/catalog/v1"

    class _Http:
        egress_class="datacenter"; engine="http"; proxy_enabled=False
        async def fetch(self, url, **o):
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as c:
                r=await c.get(url); r.raise_for_status(); return r.content

    def __init__(self, *, datasets: list[dict] | None = None, page_size: int = 50):
        self.fetch_strategy=self._Http(); self._page_size=page_size
        self._by_id={d["id"]: d for d in (datasets or [])}

    async def _fetch(self, q, limit):
        import httpx, urllib.parse
        url=f"{self.CATALOG}?q={urllib.parse.quote(q)}&limit={min(limit,self._page_size)}"
        async with httpx.AsyncClient(timeout=30.0) as c:
            r=await c.get(url); r.raise_for_status()
            return [{"id":x["resource"]["id"],"name":x["resource"]["name"],
                     "description":x["resource"].get("description",""),
                     "updatedAt":x["resource"].get("updatedAt","")} for x in r.json().get("results",[])]

    def _facets(self, d):
        f={"source_kind":"public_health"}
        if (d.get("updatedAt") or "")[:4].isdigit(): f["year"]=d["updatedAt"][:4]
        return f

    async def discover_entities(self, window):
        from noesis_kernel.contract.dto import EntityRef
        if not (window or {}).get("query") and self._by_id:
            ds=list(self._by_id.values())
        else:
            ds=await self._fetch((window or {}).get("query","MMWR"), int((window or {}).get("limit",self._page_size)))
            for d in ds: self._by_id[d["id"]]=d
        return [EntityRef(source_key=self.key, native_id=d["id"], title=d["name"], facets=self._facets(d)) for d in ds]

    async def list_documents(self, entity):
        from noesis_kernel.contract.dto import DocumentRef
        d=self._by_id.get(entity.native_id)
        return [DocumentRef(source_key=self.key, native_id=entity.native_id, title=entity.title,
                            content_type="text/markdown", facets=self._facets(d) if d else dict(entity.facets),
                            entity_ids=(entity.native_id,))]

    async def fetch_artifact(self, doc):
        d=self._by_id[doc.native_id]
        md=f"# {d['name']}\n\n## Description\n\n{(d.get('description') or 'CDC public health dataset.').strip()}\n"
        return md.encode("utf-8")
