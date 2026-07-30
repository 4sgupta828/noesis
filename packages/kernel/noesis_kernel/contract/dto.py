"""Generic, domain-neutral core DTOs — the anti-anchor.

These are the shapes that flow through the kernel pipeline. They carry a generic
`facets` bag (dimension→value) instead of named domain columns, so porting an
algorithm from a domain-specific system can never smuggle domain-specific column
names into the kernel. A vertical decides what facet keys mean; the kernel only
ever does `facets.get(k)` / `facets ⊇ filter`.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

# A facet map: caller/vertical-defined dimension name → value. The kernel treats
# keys and values as opaque strings and never hardcodes one.
Facets = dict[str, str]


@dataclass(frozen=True)
class EntityRef:
    """A thing a source is *about* (a case, a bill, an issuer — vertical decides)."""
    source_key: str
    native_id: str
    title: str = ""
    facets: Facets = field(default_factory=dict)
    dates: dict[str, str] = field(default_factory=dict)  # role → ISO date
    extra: dict = field(default_factory=dict)            # vertical passthrough


@dataclass(frozen=True)
class DocumentRef:
    """A fetchable artifact belonging to zero or more entities (n:m)."""
    source_key: str
    native_id: str
    title: str = ""
    content_type: str = "application/pdf"
    entity_ids: tuple[str, ...] = ()
    facets: Facets = field(default_factory=dict)
    dates: dict[str, str] = field(default_factory=dict)
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Locator:
    """Where a quote/fact lives, so a claim can be provenance-verified.

    `kind` selects the verification path a vertical's CitationVerifier supports:
    "block_span" (PDF/HTML text), "fact_coordinate" (e.g. XBRL cell), "row_cell"
    (table), "registry_row" (structured store), "url" (web). `ref` is an opaque
    dict the matching verifier understands.
    """
    kind: str
    document_id: str
    ref: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BlockHit:
    """A retrieved chunk of evidence — domain-neutral."""
    document_id: str
    block_id: str
    text: str
    score: float = 0.0
    facets: Facets = field(default_factory=dict)
    locator: Locator | None = None


class Capability(str, enum.Enum):
    RETRIEVAL = "retrieval"
    PRECISION = "precision"
    STRUCTURED = "structured"
    MONITOR = "monitor"
