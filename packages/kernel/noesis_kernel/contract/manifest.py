"""VerticalManifest — the single object a vertical package exposes.

A deployment activates exactly one vertical (O3). The kernel discovers installed
verticals via the `noesis.verticals` entry-point group and builds its registries
from the manifest — no kernel edits per vertical.

Slots are TYPED against contract/protocols.py (not `Any`), so `VerticalConformance`
can assert structural conformance and a new domain cannot be bolted on with a
mis-shaped component. Slots are Optional/empty so a partial manifest is valid in
early phases; conformance enforces completeness per phase.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .protocols import (
    CitationVerifier,
    Connector,
    GatingPolicy,
    Parser,
    Persona,
    RetrievalSource,
    UIContract,
)


@dataclass(frozen=True)
class VerticalManifest:
    # Identity
    name: str

    # Taxonomy / scope (declared vocabulary — plain data)
    entity_types: tuple[str, ...] = ()          # P1
    scope_dimensions: tuple[str, ...] = ()      # P2 (facet keys the vertical uses)

    # Acquisition (P1)
    connectors: dict[str, Connector] = field(default_factory=dict)
    parsers: tuple[Parser, ...] = ()

    # Retrieval + policy (P2)
    retrieval_sources: dict[str, RetrievalSource] = field(default_factory=dict)
    gating_policy: GatingPolicy | None = None
    citation_verifier: CitationVerifier | None = None

    # Language + authority (P3)
    persona: Persona | None = None
    authority_policy: object | None = None      # typed in P3 (authority contract)
    structured_tools: dict[str, object] = field(default_factory=dict)
    extraction_schema: object | None = None

    # Presentation (P4)
    ui: UIContract | None = None
    deliverable_kinds: dict[str, object] = field(default_factory=dict)
    # Optional vertical-supplied directive that shapes the synthesized answer's
    # STRUCTURE (e.g. markdown sections a domain audience expects). Generic, opaque
    # prose — the kernel only threads it into the grounded-compose step; all domain
    # wording lives in the vertical. None → the kernel's default flat-prose answer.
    answer_format: str | None = None
    # Optional vertical-supplied instruction for the VISION pre-step: how to DESCRIBE a
    # user-uploaded image (color/shape/borders/texture/distribution), producing a labeled
    # visual observation — never a diagnosis. Opaque prose; the kernel only threads it into
    # the vision call. None → no vision pre-step (images ignored).
    vision_prompt: str | None = None
    # Optional vertical-supplied instruction for the on-demand LAYMAN re-explanation (rephrase
    # a grounded answer for a non-expert, adding no new facts). None → feature unavailable.
    layman_prompt: str | None = None
    # Optional vertical-supplied instruction for the GAP-FILL planner: given a question the corpus
    # could not fully answer + its coverage gaps + the available connector KEYS, propose concrete
    # ingest jobs ({connector, query, limit}) plus gold-standard sources to recommend. Describes
    # what each connector fetches + what high-quality evidence looks like in this domain. Opaque
    # prose; the kernel only threads it into the planner call. None → self-healing unavailable.
    gap_prompt: str | None = None
    # Optional vertical-supplied instruction for SUGGESTED FOLLOW-UP questions: given a Q&A, propose
    # a few next questions that deepen discovery, understanding, and action for this domain. Opaque
    # prose; the kernel only threads it into the suggest call. None → no suggestions surfaced.
    suggest_prompt: str | None = None

    # Held-out eval gold + vocab
    eval_gold: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("VerticalManifest.name must be a non-empty string")
