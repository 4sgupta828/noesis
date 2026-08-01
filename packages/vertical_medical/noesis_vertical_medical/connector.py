"""ClinicalTrials.gov v2 connector — the first medical source (public domain).

discover_entities → query /studies (or use injected fixture records); one
EntityRef per trial (NCT) with narrowing facets. list_documents → one synthesized
trial document per trial. fetch_artifact → the assembled markdown bytes. Live use
hits the API over HttpStrategy; tests inject `studies` so they run offline.
"""
from __future__ import annotations

from noesis_kernel.contract.dto import DocumentRef, EntityRef

from . import trial_doc

API_BASE = "https://clinicaltrials.gov/api/v2"


class HttpStrategy:
    egress_class = "datacenter"
    engine = "http"
    proxy_enabled = False
    async def fetch(self, url: str, **opts) -> bytes:  # noqa: ANN003
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content


class ClinicalTrialsConnector:
    key = "clinicaltrials"

    def __init__(self, *, studies: list[dict] | None = None, page_size: int = 50):
        self.fetch_strategy = HttpStrategy()
        self._page_size = page_size
        # NCT -> raw study record (populated by discover, or injected for tests)
        self._by_nct: dict[str, dict] = {}
        if studies:
            for s in studies:
                self._by_nct[trial_doc.nct_id(s)] = s

    async def _fetch_studies(self, term: str, limit: int) -> list[dict]:
        import httpx
        studies: list[dict] = []
        token: str | None = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            while len(studies) < limit:
                page = min(100, limit - len(studies))   # v2 max pageSize = 100
                url = (f"{API_BASE}/studies?query.term={term}"
                       f"&pageSize={page}&countTotal=false")
                if token:
                    url += f"&pageToken={token}"
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
                batch = data.get("studies", [])
                if not batch:
                    break
                studies.extend(batch)
                token = data.get("nextPageToken")
                if not token:
                    break
        return studies[:limit]

    async def discover_entities(self, window: dict) -> list[EntityRef]:
        # offline / injected fixture: use whatever was preloaded
        if not window.get("query") and self._by_nct:
            studies = list(self._by_nct.values())
        else:
            term = (window or {}).get("query", "").strip() or "clinical trial"
            limit = int((window or {}).get("limit", self._page_size))
            studies = await self._fetch_studies(term, limit)
            for s in studies:
                self._by_nct[trial_doc.nct_id(s)] = s

        refs: list[EntityRef] = []
        for s in studies:
            nct = trial_doc.nct_id(s)
            if not nct:
                continue
            refs.append(EntityRef(
                source_key=self.key, native_id=nct, title=trial_doc.title(s),
                facets=trial_doc.facets(s),
            ))
        return refs

    async def list_documents(self, entity: EntityRef) -> list[DocumentRef]:
        s = self._by_nct.get(entity.native_id)
        return [DocumentRef(
            source_key=self.key, native_id=entity.native_id,
            title=entity.title, content_type="text/markdown",
            facets=trial_doc.facets(s) if s else dict(entity.facets),
            entity_ids=(entity.native_id,),
        )]

    async def fetch_artifact(self, doc: DocumentRef) -> bytes:
        s = self._by_nct.get(doc.native_id)
        if s is None:                                   # live fetch by NCT if not cached
            raw = await self.fetch_strategy.fetch(f"{API_BASE}/studies/{doc.native_id}")
            import json
            s = json.loads(raw)
            self._by_nct[doc.native_id] = s
        return trial_doc.to_markdown(s).encode("utf-8")
