"""The plugin thesis, proven: the regulatory manifest passes conformance and
drives the kernel ReAct loop to a grounded answer with ZERO kernel edits."""
from __future__ import annotations

import asyncio

from noesis_kernel.conformance.runner import run_conformance
from noesis_kernel.providers.embeddings import FakeEmbedder
from noesis_kernel.providers.llm import LLMResult
from noesis_kernel.research.budget import BudgetState
from noesis_kernel.research.react import AgentStep, ClaimOut, run_react

import noesis_vertical_regulatory as reg
from noesis_vertical_regulatory.eval_gold import GOLD
from noesis_vertical_regulatory.source import RegulatoryRetrievalSource


class _LLM:
    def __init__(self, steps): self._s = list(steps)
    async def complete(self, *, system, messages, response_format, max_tokens=2048, temperature=None):
        return LLMResult(parsed=self._s.pop(0), output_tokens=5)


# ---- the manifest is a real, conformant plugin ---------------------------

def test_manifest_passes_conformance_through_p4() -> None:
    rep = run_conformance(reg.manifest, phase="P4")
    assert rep.ok, rep.summary()


def test_entry_point_manifest_is_built() -> None:
    assert reg.manifest.name == "regulatory"
    assert "regulatory" in reg.manifest.retrieval_sources


# ---- drives the kernel loop to a GROUNDED answer (no kernel edits) --------

def test_regulatory_run_react_grounded_answer() -> None:
    emb = FakeEmbedder(dim=16)
    source = RegulatoryRetrievalSource(tenant_id="acme", embedder=emb)
    gold = GOLD["grounded_value"]
    llm = _LLM([
        AgentStep(action="search", query="approved return on equity"),
        AgentStep(action="answer", claims=[
            ClaimOut(text="approved ROE was 9.6 percent", atom_id="a1",
                     quote=gold["supporting_quote"]),
        ]),
    ])
    res = asyncio.run(run_react(
        question=gold["question"], llm=llm, embedder=emb, source=source,
        tenant_id="acme", budget=BudgetState(max_calls=10),
        system_prompt=reg.manifest.persona.system_prompt(),
    ))
    assert res.grounded
    assert res.verified_claims[0].quote == gold["supporting_quote"]


def test_gating_coverage_gap_is_real() -> None:
    # Adversarial: a jurisdiction the corpus lacks → a real coverage gap.
    from noesis_kernel.contract.dto import BlockHit
    g = reg.manifest.gating_policy
    oh_hit = BlockHit(document_id="d", block_id="b", text="t", facets={"jurisdiction": "OH"})
    assert g.coverage_gap("what was approved in CA?", [oh_hit]) is not None
    assert g.coverage_gap("what was approved in OH?", [oh_hit]) is None
    # gate applies to a docket-bearing question
    assert g.gate_applies("tell me about 24-1009-EL-AIR", {})


def test_blocks_carry_regulatory_metadata_and_narrow_search() -> None:
    from noesis_kernel.contract.dto import RetrievalRequest
    emb = FakeEmbedder(dim=16)
    source = RegulatoryRetrievalSource(tenant_id="acme", embedder=emb)
    q = "return on equity"

    # every block carries the regulatory narrowing facets + document provenance
    hits = asyncio.run(source.search(RetrievalRequest(query=q, tenant_id="acme")))
    assert hits
    f = hits[0].facets
    assert f["jurisdiction"] == "OH" and f["year"] == "2024"
    assert f["utility"] == "sample-electric" and f["filing_type"] == "rate_case"
    assert f["doc_family"] == "order"
    assert "Opinion and Order" in hits[0].document_title

    # narrow: matching facets return, a wrong facet filters out pre-ranking
    assert asyncio.run(source.search(RetrievalRequest(
        query=q, tenant_id="acme", facets={"utility": "sample-electric", "year": "2024"})))
    assert not asyncio.run(source.search(RetrievalRequest(
        query=q, tenant_id="acme", facets={"year": "2020"})))


def test_authority_ordering() -> None:
    a = reg.manifest.authority_policy
    assert a.outranks("order", "staff_report")
    assert a.outranks("staff_report", "application")
    assert a.is_controlling("order")
    assert not a.is_controlling("staff_report")
