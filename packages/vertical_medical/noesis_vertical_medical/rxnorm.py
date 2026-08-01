"""RxNorm normalization utility — the drug-linking backbone (Tier-1, no auth).

Not a document corpus: RxNorm (RxNav) maps a drug name → a canonical RxCUI, so
the SAME drug links across trials, labels, papers, and adverse-event reports.
Used to ENRICH facets (add rxcui) during ingestion so cross-source queries and
filters resolve one drug identity. Cached; network only on a miss.
"""
from __future__ import annotations

REST = "https://rxnav.nlm.nih.gov/REST"


class RxNorm:
    def __init__(self):
        self._cache: dict[str, str | None] = {}

    async def rxcui(self, name: str) -> str | None:
        key = (name or "").strip().lower()
        if not key:
            return None
        if key in self._cache:
            return self._cache[key]
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15.0) as c:
                r = await c.get(f"{REST}/rxcui.json?name={key}")
                ids = r.json().get("idGroup", {}).get("rxnormId", []) if r.status_code == 200 else []
        except Exception:
            ids = []
        self._cache[key] = ids[0] if ids else None
        return self._cache[key]

    async def enrich(self, facets: dict, *, drug_key: str = "generic") -> dict:
        """Return facets + {rxcui} if the drug_key value resolves to an RxCUI."""
        name = facets.get(drug_key) or facets.get("intervention") or facets.get("brand")
        if name:
            cui = await self.rxcui(name)
            if cui:
                return {**facets, "rxcui": cui}
        return facets
