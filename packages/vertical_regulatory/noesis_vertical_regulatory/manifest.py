"""Assemble the regulatory VerticalManifest — the single object the kernel loads.

citation_verifier is None: the vertical emits only `block_span` locators, which
the kernel verifies itself (BlockSpanVerifier). A vertical supplies a verifier
only when it adds a NEW locator kind (e.g. financial's fact_coordinate).
"""
from __future__ import annotations

from noesis_kernel.contract.manifest import VerticalManifest

from . import entities
from .authority import RegulatoryAuthorityPolicy
from .connector import RegulatoryConnector
from .eval_gold import GOLD
from .gating import RegulatoryGatingPolicy
from .persona import RegulatoryPersona
from .scope import SCOPE_DIMENSION
from .source import RegulatoryRetrievalSource
from .ui import RegulatoryUI


def build_manifest() -> VerticalManifest:
    return VerticalManifest(
        name="regulatory",
        entity_types=entities.ENTITY_TYPES,
        scope_dimensions=(SCOPE_DIMENSION, "year"),
        connectors={"regulatory": RegulatoryConnector()},
        retrieval_sources={"regulatory": RegulatoryRetrievalSource()},
        gating_policy=RegulatoryGatingPolicy(),
        citation_verifier=None,           # block_span handled by the kernel
        persona=RegulatoryPersona(),
        authority_policy=RegulatoryAuthorityPolicy(),
        ui=RegulatoryUI(),
        eval_gold=dict(GOLD),
    )
