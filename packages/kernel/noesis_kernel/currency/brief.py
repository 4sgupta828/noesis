"""Evidence Pulse change-brief composer — the DOMAIN-GENERIC mechanism (Rule 18).

On event APPROVAL (never on a shadow event), one LLM call turns a bare change event into a written
"what changed / what it means / what it replaced" brief. The vertical owns the wording (the prompt
is injected); the kernel owns the discipline: EVERY claim's quote is re-checked against its cited
block through the SAME span-verification gate the answer engine uses (BlockSpanVerifier).

ALL-OR-NOTHING: if any claim fails the gate (a fabricated / paraphrased quote, or a block the model
invented), the whole brief is discarded and `ok` is False — the caller then leaves the event's brief
empty and retries on the next scan. An unverified brief is NEVER returned (spec: "never an
unverified brief").
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from noesis_kernel.contract.dto import Locator
from noesis_kernel.research.provenance import BlockSpanVerifier


class _BriefClaim(BaseModel):
    text: str = ""          # one factual sentence from the brief
    block_id: str = ""      # the source block it came from
    quote: str = ""         # a verbatim span from that block backing the sentence


class _BriefOut(BaseModel):
    brief_md: str = ""
    claims: list[_BriefClaim] = field(default_factory=list)  # type: ignore[assignment]


@dataclass
class ComposedBrief:
    brief_md: str
    claims: list[dict]      # [{text, block_id, quote, document_id}] — all span-verified
    ok: bool                # True only if brief_md is non-empty AND every claim verified


_EMPTY = ComposedBrief("", [], ok=False)


async def compose_change_brief(
    *,
    prompt: str,                    # the vertical's CHANGE_BRIEF_PROMPT (Rule 18: judgment injected)
    llm,                            # LLM client with async .complete(system, messages, response_format, max_tokens)
    blocks: list[dict],             # [{document_id, block_id, text}] — the changed doc's blocks (+ old's for a replacement)
    verifier: BlockSpanVerifier,    # built from the corpus source's make_block_loader (tenant-scoped)
    relation: str = "",             # the event relation (retracted · superseded_by · …) for framing
    subjects: list[str] | None = None,
    max_tokens: int = 1500,
) -> ComposedBrief:
    """One LLM call → written brief + cited claims, every quote re-checked against its source block.
    Returns ok=False with empty content on ANY verification miss (the caller stores nothing and
    retries next cycle)."""
    if not prompt or not blocks:
        return _EMPTY

    id_to_doc = {b["block_id"]: b["document_id"] for b in blocks}
    header = f"CHANGE: relation={relation or 'unknown'}"
    if subjects:
        header += f"; subjects={', '.join(subjects)}"
    context = header + "\n\nSOURCE BLOCKS:\n" + "\n\n".join(
        f'[{b["block_id"]}] {b["text"]}' for b in blocks)

    try:
        comp = await llm.complete(
            system=prompt,
            messages=[{"role": "user", "content": context}],
            response_format=_BriefOut,
            max_tokens=max_tokens,
        )
    except Exception:   # noqa: BLE001 — a failed compose is a no-op; the event keeps its empty brief
        return _EMPTY

    out: _BriefOut = comp.parsed
    verified: list[dict] = []
    for c in out.claims:
        doc_id = id_to_doc.get(c.block_id)
        if not doc_id:                          # cited a block that wasn't provided → reject whole brief
            return _EMPTY
        loc = Locator(kind="block_span", document_id=doc_id, ref={"block_id": c.block_id})
        if not verifier.verify(c.quote, loc):   # fabricated / paraphrased span → reject whole brief
            return _EMPTY
        verified.append({"text": c.text, "block_id": c.block_id,
                         "quote": c.quote, "document_id": doc_id})

    brief_md = (out.brief_md or "").strip()
    if not brief_md or not verified:            # nothing grounded to show
        return _EMPTY
    return ComposedBrief(brief_md, verified, ok=True)
