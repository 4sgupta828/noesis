"""Assemble the medical VerticalManifest."""
from __future__ import annotations

from noesis_kernel.contract.manifest import VerticalManifest

from . import entities
from .answer_format import MEDICAL_ANSWER_FORMAT
from .vision import MEDICAL_VISION_PROMPT
from .layman import MEDICAL_LAYMAN_PROMPT
from .gaps import MEDICAL_GAP_PROMPT
from .suggest import MEDICAL_SUGGEST_PROMPT
from .authority import MedicalAuthorityPolicy
from .connector import ClinicalTrialsConnector
from .openfda import OpenFdaConnector
from .europepmc import EuropePmcConnector
from .faers import FaersConnector
from .dailymed import DailyMedConnector
from .cdc import CdcConnector
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
        connectors={
            "clinicaltrials": ClinicalTrialsConnector(studies=sample_studies()),
            "openfda": OpenFdaConnector(),
            "europepmc": EuropePmcConnector(),
            "faers": FaersConnector(),
            "dailymed": DailyMedConnector(),
            "cdc": CdcConnector(),
        },
        retrieval_sources={"clinicaltrials": MedicalRetrievalSource()},
        gating_policy=MedicalGatingPolicy(),
        citation_verifier=None,       # block_span handled by the kernel
        persona=MedicalPersona(),
        authority_policy=MedicalAuthorityPolicy(),
        ui=MedicalUI(),
        answer_format=MEDICAL_ANSWER_FORMAT,
        vision_prompt=MEDICAL_VISION_PROMPT,
        layman_prompt=MEDICAL_LAYMAN_PROMPT,
        gap_prompt=MEDICAL_GAP_PROMPT,
        suggest_prompt=MEDICAL_SUGGEST_PROMPT,
        eval_gold=dict(GOLD),
    )
