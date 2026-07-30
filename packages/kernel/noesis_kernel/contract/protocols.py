"""Typed Protocols a vertical implements — the real plugin contract.

These replace the opaque `Any` manifest slots so a new domain (financial,
legislative) is added purely by shipping a package that satisfies these
Protocols — zero kernel edits. All are `runtime_checkable` so conformance can
assert structural conformance of a manifest's declared components.

Nothing here names a domain concept; the vocabulary is always the vertical's
`facets`/`scope`/typed `extra`.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .dto import BlockHit, Capability, DocumentRef, EntityRef, Locator, RetrievalRequest


# ---- acquisition ---------------------------------------------------------

@runtime_checkable
class FetchStrategy(Protocol):
    """How a connector's requests reach the source. Encodes egress placement +
    anti-bot choreography as declared properties, not connector-buried logic."""
    egress_class: str           # "datacenter" | "residential"
    engine: str                 # "http" | "chromium" | "firefox"
    proxy_enabled: bool         # residential connectors force this off
    async def fetch(self, url: str, **opts: Any) -> bytes: ...


@runtime_checkable
class Connector(Protocol):
    """Source-specific selectors/API mapping + normalization ONLY.

    Scheduling/storage/retries/breaker belong to the kernel. Domain nouns live
    in the returned refs' `facets`/`extra`, never in the method surface.
    """
    key: str
    fetch_strategy: FetchStrategy
    async def discover_entities(self, window: dict) -> list[EntityRef]: ...
    async def list_documents(self, entity: EntityRef) -> list[DocumentRef]: ...
    async def fetch_artifact(self, doc: DocumentRef) -> bytes: ...
    # Optional: caption/collections enrichment + n:m membership (duck-typed).
    # async def fetch_entity_detail(self, entity: EntityRef) -> dict: ...


@runtime_checkable
class Parser(Protocol):
    """content_type → markdown/text. Kernel ships pdf/html; verticals add xbrl."""
    content_types: tuple[str, ...]
    def parse(self, raw: bytes, *, content_type: str) -> str: ...


# ---- retrieval + policy --------------------------------------------------

@runtime_checkable
class RetrievalSource(Protocol):
    key: str
    def capabilities(self) -> frozenset[Capability]: ...
    async def search(self, req: RetrievalRequest) -> list[BlockHit]: ...


@runtime_checkable
class GatingPolicy(Protocol):
    """The domain-neutral seam for 'when does the hard gate run / is this a
    coverage gap / is a web-floor warranted' — so no domain-format regex is ever
    inlined into the kernel loop."""
    def gate_applies(self, question: str, plan: dict) -> bool: ...
    def coverage_gap(self, question: str, hits: list[BlockHit]) -> str | None: ...


@runtime_checkable
class CitationVerifier(Protocol):
    """Provenance check per locator kind (block_span / fact_coordinate / row_cell
    / registry_row / url). Kernel owns span_check; verticals add fact-coordinate."""
    supported_kinds: tuple[str, ...]
    def verify(self, quote: str, locator: Locator) -> bool: ...


# ---- language + presentation --------------------------------------------

@runtime_checkable
class Persona(Protocol):
    """System prompt + tool descriptions (kept consistent with tool schemas)."""
    def system_prompt(self) -> str: ...
    def tool_descriptions(self) -> dict[str, str]: ...


@runtime_checkable
class EntityView(Protocol):
    """UI schema for one entity type: how to list it and show its detail.
    Presentation is DECLARED data (field specs), not code, so the app shell
    renders any vertical's entities without kernel/app edits."""
    entity_type: str
    def list_columns(self) -> list[dict]: ...     # [{key,label,kind}]
    def detail_sections(self) -> list[dict]: ...   # [{title, fields:[...]}]


@runtime_checkable
class UIContract(Protocol):
    """What a vertical declares so the responsive, minimal app shell renders a
    coherent, domain-appropriate UI with zero app edits."""
    def navigation(self) -> list[dict]: ...                 # nav entries
    def search_facets(self) -> list[dict]: ...              # filter controls
    def entity_views(self) -> list[EntityView]: ...         # list/detail schemas
    def citation_renderers(self) -> dict[str, str]: ...     # locator.kind → renderer id
    def deliverable_renderers(self) -> dict[str, str]: ...  # kind → renderer id
