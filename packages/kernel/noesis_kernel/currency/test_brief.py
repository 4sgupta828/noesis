"""Unit tests for the change-brief composer's crown-jewel discipline: the all-or-nothing span gate.
Uses a FAKE LLM (no credits) + the REAL BlockSpanVerifier over in-memory blocks (no DB)."""
import asyncio

from noesis_kernel.currency.brief import _BriefClaim, _BriefOut, compose_change_brief
from noesis_kernel.research.provenance import BlockSpanVerifier

_BLOCKS = {
    ("doc:new", "b1"): "Finerenone reduced cardiovascular events versus placebo in FIDELIO-DKD.",
    ("doc:new", "b2"): "Hyperkalemia occurred more often with finerenone than with placebo.",
}
_BLOCK_ARGS = [
    {"document_id": d, "block_id": b, "text": t} for (d, b), t in _BLOCKS.items()
]


def _loader(document_id, block_id):
    return _BLOCKS.get((document_id, block_id))


class _FakeLLM:
    """Returns a canned structured result; ignores the prompt/messages (we test verification)."""
    def __init__(self, out):
        self._out = out

    async def complete(self, *, system, messages, response_format, max_tokens):
        class _R:
            parsed = self._out
        return _R()


def _run(out):
    return asyncio.run(compose_change_brief(
        prompt="PROMPT", llm=_FakeLLM(out), blocks=_BLOCK_ARGS,
        verifier=BlockSpanVerifier(_loader), relation="retracted"))


def test_verified_brief_is_accepted():
    out = _BriefOut(brief_md="**What changed** The paper was retracted.", claims=[
        _BriefClaim(text="CV events fell.", block_id="b1",
                    quote="Finerenone reduced cardiovascular events versus placebo"),
        _BriefClaim(text="Hyperkalemia was more common.", block_id="b2",
                    quote="Hyperkalemia occurred more often with finerenone"),
    ])
    res = _run(out)
    assert res.ok is True
    assert len(res.claims) == 2
    assert all(c["document_id"] == "doc:new" for c in res.claims)


def test_corrupted_quote_rejects_whole_brief():
    # one good claim + one FABRICATED quote → the entire brief is discarded (all-or-nothing).
    out = _BriefOut(brief_md="**What changed** ...", claims=[
        _BriefClaim(text="CV events fell.", block_id="b1",
                    quote="Finerenone reduced cardiovascular events versus placebo"),
        _BriefClaim(text="Made up.", block_id="b2",
                    quote="Finerenone cures kidney disease completely"),  # not in the block
    ])
    res = _run(out)
    assert res.ok is False
    assert res.brief_md == "" and res.claims == []


def test_claim_citing_unknown_block_rejected():
    out = _BriefOut(brief_md="x", claims=[
        _BriefClaim(text="t", block_id="b99", quote="anything")])
    assert _run(out).ok is False


def test_empty_brief_rejected():
    assert _run(_BriefOut(brief_md="", claims=[])).ok is False


def test_quote_matching_is_whitespace_tolerant():
    # reflowed whitespace still matches (normalize collapses it) — provenance, not formatting.
    out = _BriefOut(brief_md="**What changed** ...", claims=[
        _BriefClaim(text="CV events fell.", block_id="b1",
                    quote="Finerenone   reduced\n cardiovascular events")])
    assert _run(out).ok is True
