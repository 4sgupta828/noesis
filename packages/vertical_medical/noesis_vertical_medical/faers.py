"""openFDA FAERS connector — real-world adverse-event reports (Tier-1, public).

api.fda.gov/drug/event (20M+ reports). Each report → a compact citable doc: the
drug(s) + reported reaction(s) + seriousness. source_key='faers' so blocks are
tagged. Terse by nature — supports claims like "reaction X was reported for
drug Y", span-verified against the report.
"""
from __future__ import annotations

import os

API = "https://api.fda.gov/drug/event.json"


def _first(v):
    return (v[0] if isinstance(v, list) and v else v) or ""


def report_id(r: dict) -> str:
    return r.get("safetyreportid") or r.get("safetyreportversion") or str(id(r))


def _drugs(r: dict) -> list[str]:
    out = []
    for d in r.get("patient", {}).get("drug", []):
        g = _first((d.get("openfda") or {}).get("generic_name"))
        out.append((g or d.get("medicinalproduct") or "").strip())
    return [x for x in out if x]


def _reactions(r: dict) -> list[str]:
    return [x.get("reactionmeddrapt", "") for x in r.get("patient", {}).get("reaction", []) if x.get("reactionmeddrapt")]


def facets(r: dict) -> dict:
    drugs = _drugs(r)
    f = {"source_kind": "adverse_event", "serious": "yes" if str(r.get("serious")) == "1" else "no"}
    if drugs:
        f["generic"] = drugs[0].lower()
    if r.get("receivedate", "")[:4].isdigit():
        f["year"] = r["receivedate"][:4]
    return f


def title(r: dict) -> str:
    d = _drugs(r)
    return f"Adverse event report — {d[0] if d else 'drug'}"


def markdown(r: dict) -> str:
    drugs = _drugs(r); reactions = _reactions(r)
    parts = [f"# {title(r)}", "", "## Adverse Event Report"]
    if drugs:
        parts.append(f"Suspect drug(s): {', '.join(drugs)}.")
    if reactions:
        parts.append(f"Reported reaction(s): {', '.join(reactions)}.")
    parts.append(f"Seriousness: {'serious' if str(r.get('serious'))=='1' else 'non-serious'}.")
    if r.get("receivedate"):
        parts.append(f"Report received: {r['receivedate']}.")
    return "\n".join(parts).strip() + "\n"


class FaersConnector:
    key = "faers"

    class _Http:
        egress_class="datacenter"; engine="http"; proxy_enabled=False
        async def fetch(self, url, **o):
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as c:
                r=await c.get(url); r.raise_for_status(); return r.content

    def __init__(self, *, reports: list[dict] | None = None, page_size: int = 100):
        self.fetch_strategy=self._Http(); self._page_size=page_size
        self._by_id={report_id(r): r for r in (reports or [])}

    async def _fetch(self, term, limit):
        import httpx
        key=os.environ.get("OPENFDA_API_KEY",""); out=[]; skip=0
        async with httpx.AsyncClient(timeout=30.0) as c:
            while len(out)<limit:
                n=min(100, limit-len(out))
                base=f"search={term}&" if term else ""
                url=f"{API}?{base}limit={n}&skip={skip}"+(f"&api_key={key}" if key else "")
                r=await c.get(url)
                if r.status_code==404: break
                r.raise_for_status(); res=r.json().get("results",[])
                if not res: break
                out.extend(res); skip+=len(res)
                if len(res)<n or skip>=25000: break
        return out[:limit]

    async def discover_entities(self, window):
        from noesis_kernel.contract.dto import EntityRef
        if not (window or {}).get("query") and self._by_id:
            recs=list(self._by_id.values())
        else:
            recs=await self._fetch((window or {}).get("query",""), int((window or {}).get("limit",self._page_size)))
            for r in recs: self._by_id[report_id(r)]=r
        return [EntityRef(source_key=self.key, native_id=report_id(r), title=title(r), facets=facets(r)) for r in recs]

    async def list_documents(self, entity):
        from noesis_kernel.contract.dto import DocumentRef
        r=self._by_id.get(entity.native_id)
        return [DocumentRef(source_key=self.key, native_id=entity.native_id, title=entity.title,
                            content_type="text/markdown", facets=facets(r) if r else dict(entity.facets),
                            entity_ids=(entity.native_id,))]

    async def fetch_artifact(self, doc):
        return markdown(self._by_id[doc.native_id]).encode("utf-8")
