"""openFDA drug-label connector — second medical source (Tier-1, public).

FDA Structured Product Labels via api.fda.gov/drug/label. Each label → one citable
markdown "drug document" (indications, dosage, warnings, adverse reactions) with
facets {generic, brand, route, product_type, manufacturer}. Entity = drug label
(by SPL set_id). A free API key (env OPENFDA_API_KEY) just raises rate limits.
"""
from __future__ import annotations

import os

API = "https://api.fda.gov/drug/label.json"

_SECTIONS = [
    ("indications_and_usage", "Indications and Usage"),
    ("dosage_and_administration", "Dosage and Administration"),
    ("warnings", "Warnings"),
    ("contraindications", "Contraindications"),
    ("adverse_reactions", "Adverse Reactions"),
    ("drug_interactions", "Drug Interactions"),
]


def _first(v):
    return (v[0] if isinstance(v, list) and v else v) or ""


def label_id(rec: dict) -> str:
    return rec.get("set_id") or rec.get("id") or ""


def label_title(rec: dict) -> str:
    of = rec.get("openfda", {})
    brand = _first(of.get("brand_name"))
    generic = _first(of.get("generic_name"))
    return (brand or generic or "Drug label").strip()


def label_facets(rec: dict) -> dict:
    of = rec.get("openfda", {})
    f = {
        "generic": _first(of.get("generic_name")).lower(),
        "brand": _first(of.get("brand_name")).lower(),
        "route": _first(of.get("route")).lower(),
        "product_type": _first(of.get("product_type")).lower(),
        "manufacturer": _first(of.get("manufacturer_name")).lower(),
        "source_kind": "drug_label",
    }
    return {k: v for k, v in f.items() if v}


def label_markdown(rec: dict) -> str:
    parts = [f"# {label_title(rec)} — Drug Label", ""]
    of = rec.get("openfda", {})
    ident = []
    if of.get("generic_name"):
        ident.append(f"Generic: {_first(of['generic_name'])}")
    if of.get("route"):
        ident.append(f"Route: {_first(of['route'])}")
    if of.get("manufacturer_name"):
        ident.append(f"Manufacturer: {_first(of['manufacturer_name'])}")
    if ident:
        parts += ["\n".join(ident), ""]
    for field, heading in _SECTIONS:
        text = _first(rec.get(field))
        if text and text.strip():
            parts += [f"## {heading}", "", text.strip()[:4000], ""]
    return "\n".join(parts).strip() + "\n"


class OpenFdaConnector:
    key = "openfda"

    class _Http:
        egress_class = "datacenter"; engine = "http"; proxy_enabled = False
        async def fetch(self, url: str, **o) -> bytes:  # noqa: ANN003
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get(url); r.raise_for_status(); return r.content

    def __init__(self, *, labels: list[dict] | None = None, page_size: int = 50):
        self.fetch_strategy = self._Http()
        self._page_size = page_size
        self._by_id: dict[str, dict] = {}
        for rec in labels or []:
            self._by_id[label_id(rec)] = rec

    async def _fetch(self, term: str, limit: int) -> list[dict]:
        import httpx
        key = os.environ.get("OPENFDA_API_KEY", "")
        q = f'?search={term}&limit={min(limit, self._page_size)}' if term else f'?limit={min(limit, self._page_size)}'
        url = API + q + (f"&api_key={key}" if key else "")
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(url); r.raise_for_status()
            return r.json().get("results", [])

    async def discover_entities(self, window: dict):
        from noesis_kernel.contract.dto import EntityRef
        if not (window or {}).get("query") and self._by_id:
            recs = list(self._by_id.values())
        else:
            term = (window or {}).get("query", "")
            recs = await self._fetch(term, int((window or {}).get("limit", self._page_size)))
            for rec in recs:
                self._by_id[label_id(rec)] = rec
        out = []
        for rec in recs:
            sid = label_id(rec)
            if sid:
                out.append(EntityRef(source_key=self.key, native_id=sid,
                                     title=label_title(rec), facets=label_facets(rec)))
        return out

    async def list_documents(self, entity):
        from noesis_kernel.contract.dto import DocumentRef
        rec = self._by_id.get(entity.native_id)
        return [DocumentRef(source_key=self.key, native_id=entity.native_id,
                            title=entity.title, content_type="text/markdown",
                            facets=label_facets(rec) if rec else dict(entity.facets),
                            entity_ids=(entity.native_id,))]

    async def fetch_artifact(self, doc) -> bytes:
        rec = self._by_id[doc.native_id]
        return label_markdown(rec).encode("utf-8")
