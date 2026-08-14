"""Assemble the medical VerticalManifest."""
from __future__ import annotations

import os

from noesis_kernel.contract.manifest import VerticalManifest

from . import entities
from . import evidence_kind
from .specialists import (SPECIALISTS, DEFAULT_PANEL_IDS, PANEL_SYNTHESIS_DIRECTIVE,
                          PANEL_EXAMPLE_CASES, PANEL_ENUMERATIVE_ADDENDUM, PANEL_DECISION_ADDENDUM)
from .answer_format import (
    MEDICAL_ANSWER_FORMAT,
    MEDICAL_CLINICAL_SYNTHESIS_FORMAT,
    MEDICAL_ENUMERATIVE_COMPOSE_ADDENDUM,
    MEDICAL_PATIENT_FORMAT,
    MEDICAL_VISUAL_GUIDANCE,
    MEDICAL_CHART_GUIDANCE,
    MEDICAL_REASONING_FORMAT,
    MEDICAL_PATIENT_REASONING_FORMAT,
)
from .vision import MEDICAL_REPORT_PROMPT, MEDICAL_VISION_PROMPT
from .layman import MEDICAL_LAYMAN_PROMPT
from .gaps import MEDICAL_GAP_PROMPT
from .suggest import MEDICAL_SUGGEST_PROMPT
from .question_contract import MEDICAL_CONTRACT_PROMPT
from .refine import MEDICAL_REFINE_PROMPT
from .triage import MEDICAL_TRIAGE_PROMPT, MEDICAL_TRIAGE_PROMPT_V2
from .reasoned import REASONED_SCAFFOLD_PROMPT, REASONED_ANSWER_FORMAT
from .integrative import INTEGRATIVE_DIRECTIVE, INTEGRATIVE_QUERY_HINT
from .understanding import UNDERSTANDING_ANSWER_FORMAT, UNDERSTANDING_QUERY_HINT
from .web_domains import TRUSTED_WEB_DOMAINS, WEB_DOMAIN_FACETS
from .global_guidelines import declared_lineage
from .graph import CURATED_EDGES, GRAPH_RELATIONS, MAP_QUESTION_TOPICS_PROMPT
from .india_brands import INDIA_CONFLICT_DIRECTIVE, brand_context
from .pulse import (CANONIZE_TOPIC_PROMPT, SUGGEST_WATCHES_PROMPT, SUPERSESSION_JUDGE_PROMPT,
                    WATCH_TOPIC_PROMPT)
from .coverage import COVERED_CONDITIONS
from .authority import MedicalAuthorityPolicy
from .connector import ClinicalTrialsConnector
from .openfda import OpenFdaConnector
from .europepmc import EuropePmcConnector
from .faers import FaersConnector
from .dailymed import DailyMedConnector
from .cdc import CdcConnector
from .india_guidelines import IndiaGuidelinesConnector
from .global_guidelines import GlobalGuidelinesConnector
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
            "europepmc": EuropePmcConnector(
                full_text=os.environ.get("NOESIS_EPMC_FULLTEXT", "").lower() in ("1", "true", "yes")),
            "faers": FaersConnector(),
            "dailymed": DailyMedConnector(),
            "cdc": CdcConnector(),
            "india_guidelines": IndiaGuidelinesConnector(),   # ICMR + national-programme + society (source_country=IN)
            "global_guidelines": GlobalGuidelinesConnector(), # top-tier society/WHO/task-force guidance (source_country=global)
        },
        retrieval_sources={"clinicaltrials": MedicalRetrievalSource()},
        gating_policy=MedicalGatingPolicy(),
        citation_verifier=None,       # block_span handled by the kernel
        persona=MedicalPersona(),
        authority_policy=MedicalAuthorityPolicy(),
        ui=MedicalUI(),
        answer_format=MEDICAL_ANSWER_FORMAT,
        clinical_answer_format=MEDICAL_CLINICAL_SYNTHESIS_FORMAT,
        patient_answer_format=MEDICAL_PATIENT_FORMAT,
        visual_guidance=MEDICAL_VISUAL_GUIDANCE,
        chart_guidance=MEDICAL_CHART_GUIDANCE,
        reasoning_format=MEDICAL_REASONING_FORMAT,
        patient_reasoning_format=MEDICAL_PATIENT_REASONING_FORMAT,
        evidence_classifier=evidence_kind.classify,   # structural facets → evidence tier (Rule 18)
        panel_specialists=SPECIALISTS, panel_default_ids=DEFAULT_PANEL_IDS,
        panel_synthesis_directive=PANEL_SYNTHESIS_DIRECTIVE, panel_examples=PANEL_EXAMPLE_CASES,
        panel_enumerative_addendum=PANEL_ENUMERATIVE_ADDENDUM,
        panel_decision_addendum=PANEL_DECISION_ADDENDUM,
        vision_prompt=MEDICAL_VISION_PROMPT,
        report_prompt=MEDICAL_REPORT_PROMPT,
        layman_prompt=MEDICAL_LAYMAN_PROMPT,
        gap_prompt=MEDICAL_GAP_PROMPT,
        suggest_prompt=MEDICAL_SUGGEST_PROMPT,
        refine_prompt=MEDICAL_REFINE_PROMPT,
        contract_prompt=MEDICAL_CONTRACT_PROMPT,
        enumerative_compose_addendum=MEDICAL_ENUMERATIVE_COMPOSE_ADDENDUM,
        triage_prompt=MEDICAL_TRIAGE_PROMPT,
        triage_prompt_v2=MEDICAL_TRIAGE_PROMPT_V2,
        reasoned_scaffold_prompt=REASONED_SCAFFOLD_PROMPT,
        reasoned_answer_format=REASONED_ANSWER_FORMAT,
        integrative_prompt=INTEGRATIVE_DIRECTIVE,
        integrative_query_hint=INTEGRATIVE_QUERY_HINT,
        understanding_answer_format=UNDERSTANDING_ANSWER_FORMAT,
        understanding_query_hint=UNDERSTANDING_QUERY_HINT,
        web_domains=TRUSTED_WEB_DOMAINS,
        web_domain_facets=WEB_DOMAIN_FACETS,
        lineage=tuple(declared_lineage()),
        graph_relations=GRAPH_RELATIONS,
        graph_edges=CURATED_EDGES,
        graph_map_prompt=MAP_QUESTION_TOPICS_PROMPT,
        country_profiles={"IN": {"context_fn": brand_context,
                                 "directive": INDIA_CONFLICT_DIRECTIVE}},
        watch_topic_prompt=WATCH_TOPIC_PROMPT,
        watch_canonize_prompt=CANONIZE_TOPIC_PROMPT,
        watch_suggest_prompt=SUGGEST_WATCHES_PROMPT,
        supersession_judge_prompt=SUPERSESSION_JUDGE_PROMPT,
        watch_topic_seed=tuple(sorted({c["name"] for c in COVERED_CONDITIONS})),
        extraction_lenses=(
            "interventions/treatments/drugs studied",
            "outcomes, findings and effect sizes",
            "comparisons (vs placebo / standard of care / another drug)",
            "population / eligibility / subgroup",
            "safety, adverse effects and contraindications",
            "mechanism or trial design",
        ),
        eval_gold=dict(GOLD),
    )
