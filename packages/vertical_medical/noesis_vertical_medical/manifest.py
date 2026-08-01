"""Assemble the medical VerticalManifest."""
from __future__ import annotations

from noesis_kernel.contract.manifest import VerticalManifest

from . import entities
from .authority import MedicalAuthorityPolicy
from .connector import ClinicalTrialsConnector
from .eval_gold import GOLD
from .fixtures import sample_studies
from .gating import MedicalGatingPolicy
from .persona import MedicalPersona
from .scope import SCOPE_DIMENSION
from .source import MedicalRetrievalSource
from .ui import MedicalUI


def build_manifest() -> VerticalManifest:
    return VerticalManifest(
        name="medical",
        entity_types=entities.ENTITY_TYPES,
        scope_dimensions=(SCOPE_DIMENSION, "phase", "status"),
        connectors={"clinicaltrials": ClinicalTrialsConnector(studies=sample_studies())},
        retrieval_sources={"clinicaltrials": MedicalRetrievalSource()},
        gating_policy=MedicalGatingPolicy(),
        citation_verifier=None,       # block_span handled by the kernel
        persona=MedicalPersona(),
        authority_policy=MedicalAuthorityPolicy(),
        ui=MedicalUI(),
        eval_gold=dict(GOLD),
    )
