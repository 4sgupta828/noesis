"""Retraction detection — STRUCTURAL, zero-LLM (Evidence Pulse P1, first real detector).

Europe PMC records a publisher-declared "Retracted Publication" pubType on withdrawn papers
(verified live: PMID 9500320 carries it; `PUB_TYPE:"Retracted Publication"` is queryable). For the
corpus's held Europe PMC documents, batched EXT_ID queries return exactly the retracted subset —
publisher-declared fact, not judgment, so events auto-approve (spec A4: high-confidence only) and
their blocks are EXCLUDED from grounding by the currency layer.

Rule 18 split: this module owns the medical-source knowledge (where retraction facts live and how
to read them); the kernel CurrencyStore owns the ledger/stamps it feeds.
"""
from __future__ import annotations

import re

EPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_DOC_ID_RE = re.compile(r"^europepmc:(?:(?P<src>[A-Z]+):)?(?P<ext>\w+)$")


def _parse_doc_id(document_id: str) -> tuple[str, str] | None:
    """'europepmc:MED:9500320' (or 'europepmc:9500320') -> (src, ext_id); None if not EuropePMC."""
    m = _DOC_ID_RE.match(document_id or "")
    if not m:
        return None
    return (m.group("src") or "MED", m.group("ext"))


async def find_retracted_ext_ids(ext_ids: list[str], *, src: str = "MED",
                                 batch: int = 40, fetch=None) -> set[str]:
    """Batched Europe PMC lookups: which of these EXT_IDs are retracted publications?
    `fetch(url, params) -> dict` is injectable for tests; defaults to httpx."""
    if fetch is None:
        import httpx

        async def fetch(url, params):   # pragma: no cover — thin transport
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get(url, params=params)
                r.raise_for_status()
                return r.json()
    retracted: set[str] = set()
    ids = [i for i in ext_ids if i]
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        q = ("(" + " OR ".join(f"EXT_ID:{x}" for x in chunk) + ")"
             + f' AND SRC:{src} AND PUB_TYPE:"Retracted Publication"')
        data = await fetch(EPMC_SEARCH, {"query": q, "format": "json", "pageSize": str(batch)})
        for r in ((data.get("resultList") or {}).get("result") or []):
            rid = str(r.get("id") or "")
            if rid:
                retracted.add(rid)
    return retracted


async def retraction_lineage(document_ids: list[str], *, fetch=None) -> list[dict]:
    """For the corpus's Europe PMC document ids, return kernel-currency `retracted` relations for
    every held paper the publisher has withdrawn. Non-EuropePMC ids are ignored; unknown ids are
    simply not retracted (absence never fires an event)."""
    by_src: dict[str, dict[str, str]] = {}          # src -> ext_id -> document_id
    for did in document_ids or []:
        parsed = _parse_doc_id(did)
        if parsed:
            src, ext = parsed
            by_src.setdefault(src, {})[ext] = did
    out: list[dict] = []
    for src, mapping in by_src.items():
        hit = await find_retracted_ext_ids(sorted(mapping), src=src, fetch=fetch)
        for ext in sorted(hit):
            out.append({"old_document_id": mapping[ext], "new_document_id": "",
                        "relation": "retracted", "subjects": []})
    return out
