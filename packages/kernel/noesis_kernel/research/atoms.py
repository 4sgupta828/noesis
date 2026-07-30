"""Evidence atoms — the ReAct loop's working memory.

Each retrieved BlockHit becomes an Atom with a stable id the LLM cites. An atom
carries its locator so a claim citing it can be provenance-verified. Domain-free.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from noesis_kernel.contract.dto import BlockHit, Facets, Locator


@dataclass(frozen=True)
class Atom:
    atom_id: str
    document_id: str
    block_id: str
    text: str
    locator: Locator | None = None
    facets: Facets = field(default_factory=dict)


class AtomStore:
    def __init__(self) -> None:
        self._atoms: dict[str, Atom] = {}
        self._n = 0

    def add_hits(self, hits: list[BlockHit]) -> list[Atom]:
        added: list[Atom] = []
        for h in hits:
            # dedupe by (document_id, block_id) — same block cited once
            existing = next(
                (a for a in self._atoms.values()
                 if a.document_id == h.document_id and a.block_id == h.block_id),
                None,
            )
            if existing is not None:
                continue
            self._n += 1
            atom = Atom(
                atom_id=f"a{self._n}",
                document_id=h.document_id,
                block_id=h.block_id,
                text=h.text,
                locator=h.locator,
                facets=dict(h.facets),
            )
            self._atoms[atom.atom_id] = atom
            added.append(atom)
        return added

    def get(self, atom_id: str) -> Atom | None:
        return self._atoms.get(atom_id)

    def all(self) -> list[Atom]:
        return list(self._atoms.values())
