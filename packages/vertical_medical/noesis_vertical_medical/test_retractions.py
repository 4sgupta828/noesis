"""Retraction detector — held-out contract tests (fake transport; the live API shape was verified
manually against PMID 9500320, which carries pubType 'Retracted Publication')."""
from __future__ import annotations

import asyncio

from noesis_vertical_medical.retractions import (_parse_doc_id, find_retracted_ext_ids,
                                                 retraction_lineage)


def test_doc_id_parsing_tolerates_both_forms_and_rejects_others():
    assert _parse_doc_id("europepmc:MED:9500320") == ("MED", "9500320")
    assert _parse_doc_id("europepmc:9500320") == ("MED", "9500320")
    assert _parse_doc_id("clinicaltrials:NCT01") is None
    assert _parse_doc_id("https://kdigo.org/x.pdf") is None


def _fake_fetch(retracted: dict):
    calls = []

    async def fetch(url, params):
        calls.append(params["query"])
        hits = [{"id": i, "title": t} for i, t in retracted.items()
                if f"EXT_ID:{i}" in params["query"]]
        return {"resultList": {"result": hits}}
    fetch.calls = calls
    return fetch


def test_find_retracted_batches_and_returns_only_retracted():
    fetch = _fake_fetch({"9500320": "MMR paper"})
    ids = [str(n) for n in range(100, 190)]              # 90 ids -> 3 batches of 40
    got = asyncio.run(find_retracted_ext_ids(ids + ["9500320"], batch=40, fetch=fetch))
    assert got == {"9500320": "MMR paper"}
    assert len(fetch.calls) == 3                          # ceil(91/40)
    assert all('PUB_TYPE:"Retracted Publication"' in q for q in fetch.calls)


def test_retraction_lineage_maps_back_to_document_ids_with_title_subject():
    fetch = _fake_fetch({"9500320": "MMR paper"})
    rels = asyncio.run(retraction_lineage(
        ["europepmc:MED:9500320", "europepmc:MED:26773022", "clinicaltrials:NCT07596329"],
        fetch=fetch))
    assert rels == [{"old_document_id": "europepmc:MED:9500320", "new_document_id": "",
                     "relation": "retracted", "subjects": ["MMR paper"]}]
