"""Offline tests for the regulatory vertical's stable, panel-independent pieces."""
from __future__ import annotations

from noesis_kernel.contract.protocols import Persona, UIContract

from noesis_vertical_regulatory import entities, scope
from noesis_vertical_regulatory.persona import RegulatoryPersona
from noesis_vertical_regulatory.ui import RegulatoryUI


def test_scope_validation_allowlist() -> None:
    assert scope.validate_scope({"jurisdiction": "oh"}) == {"jurisdiction": "OH"}
    assert scope.validate_scope({"jurisdiction": "Narnia"}) == {}   # fail-safe drop
    assert scope.normalize_jurisdiction("ca") == "CA"
    assert scope.normalize_jurisdiction("zz") is None


def test_docket_format_detection() -> None:
    assert entities.looks_like_docket("see docket 24-1009-EL-AIR for details")
    assert not entities.looks_like_docket("no docket here")
    assert entities.ENTITY_TYPES == ("case", "filing", "party")


def test_persona_satisfies_kernel_protocol() -> None:
    p = RegulatoryPersona()
    assert isinstance(p, Persona)
    assert "regulatory" in p.system_prompt().lower()
    assert "search_evidence" in p.tool_descriptions()


def test_ui_satisfies_kernel_protocol() -> None:
    ui = RegulatoryUI()
    assert isinstance(ui, UIContract)
    assert any(v.entity_type == "case" for v in ui.entity_views())
    assert ui.citation_renderers()["block_span"]
