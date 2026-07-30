"""VerticalManifest — the single object a vertical package exposes.

A deployment activates exactly one vertical (O3). The kernel discovers installed
verticals via the `noesis.verticals` entry-point group and builds its registries
from the manifest — no kernel edits per vertical.

This is the P0 skeleton: `name` + declared capability slots. Each slot is filled
in as its owning phase lands its contract (connectors P1; retrieval/gating P2;
persona/authority/structured-tools/extraction P3). Slots are Optional so a
partial manifest is valid early; `VerticalConformance` (conformance/runner.py)
enforces completeness per phase.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VerticalManifest:
    # Identity
    name: str

    # Capability slots — typed contracts are attached as each phase lands them.
    # Kept as opaque Optionals at P0 so the skeleton is usable before P1/P2/P3.
    entity_types: tuple[str, ...] = ()          # P1: declared entity taxonomy
    scope_dimensions: tuple[str, ...] = ()      # P2: scope/routing facets
    connectors: dict[str, Any] = field(default_factory=dict)      # P1
    fetch_strategies: dict[str, Any] = field(default_factory=dict)  # P1
    retrieval_sources: dict[str, Any] = field(default_factory=dict)  # P2
    gating_policy: Any | None = None            # P2: 10th-seam gating/routing
    authority_policy: Any | None = None         # P3
    persona: Any | None = None                  # P3: prompt pack
    structured_tools: dict[str, Any] = field(default_factory=dict)  # P3
    extraction_schema: Any | None = None        # P3
    deliverable_kinds: dict[str, Any] = field(default_factory=dict)  # P4
    eval_gold: dict[str, Any] = field(default_factory=dict)      # gold + vocab

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("VerticalManifest.name must be a non-empty string")
