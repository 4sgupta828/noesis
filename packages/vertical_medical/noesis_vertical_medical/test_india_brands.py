"""D-3 brand-resolver contract: structural, strength/FDC-aware, ABSTAINING."""
from noesis_vertical_medical.india_brands import BRANDS, brand_context, resolve_brands


def test_exact_strength_row_wins_over_family():
    r = resolve_brands("Can I take Dolo 650 with Augmentin 625?")
    by = {x["brand"]: x for x in r}
    assert by["Dolo 650"]["strength"] == "650 mg"
    assert by["Augmentin 625 Duo"]["components"] == ["amoxicillin", "clavulanic acid"]
    assert "500 mg + 125 mg" in by["Augmentin 625 Duo"]["strength"]


def test_family_without_strength_flags_unknown_never_guesses():
    r = resolve_brands("patient is on Augmentin and Thyronorm")
    by = {x["brand"]: x for x in r}
    assert by["Augmentin (family)"]["strength"].startswith("UNKNOWN")
    assert by["Thyronorm (family)"]["components"] == ["levothyroxine"]


def test_unknown_brand_abstains_and_no_false_positives():
    assert resolve_brands("Is Randomycin 500 safe in pregnancy?") == []
    assert resolve_brands("the pancreas produces insulin") == []      # 'pan' must not fire


def test_fdc_components_complete():
    r = resolve_brands("She takes Zerodol-SP after meals")
    assert r[0]["components"] == ["aceclofenac", "paracetamol", "serratiopeptidase"]


def test_context_line_is_planner_framing_not_evidence():
    ctx = brand_context("Should I continue Pan-D with Montair-LC?")
    assert "NOT evidence" in ctx and "never cite" in ctx
    assert "pantoprazole" in ctx and "montelukast" in ctx
    assert brand_context("no brands here at all") == ""


def test_table_hygiene():
    for key, (display, comps, strength, form) in BRANDS.items():
        assert key == key.lower().strip() and comps and display and form