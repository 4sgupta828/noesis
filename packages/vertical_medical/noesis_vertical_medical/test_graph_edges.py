"""Curated-edge contract: every endpoint is an EXACT registry label, every relation is in the
vocabulary, identities are unique, no self-loops — a wrong-node curated edge would poison
retrieval expansion (spec eval gate, structural half)."""
from noesis_kernel.graph.store import edge_identity

from noesis_vertical_medical.coverage import COVERED_CONDITIONS
from noesis_vertical_medical.graph import CURATED_EDGES, GRAPH_RELATIONS, NEW_CONDITION_NODES


def test_endpoints_are_registry_labels_or_declared_new_nodes():
    known = {c["name"] for c in COVERED_CONDITIONS} | set(NEW_CONDITION_NODES)
    for e in CURATED_EDGES:
        assert e["subject"] in known, f"unknown subject {e['subject']!r}"
        assert e["object"] in known, f"unknown object {e['object']!r}"


def test_masquerade_edges_point_at_askable_cover_stories_and_carry_discriminators():
    registry = {c["name"] for c in COVERED_CONDITIONS}
    known = registry | set(NEW_CONDITION_NODES)
    masq = [e for e in CURATED_EDGES
            if e["relation"] in ("mimics", "underlies_presentation_of")]
    assert len(masq) >= 20
    covered_covers = sum(1 for e in masq if e["object"] in registry)
    assert covered_covers >= len(masq) - 2   # cover stories are overwhelmingly ASKED topics
    for e in masq:
        assert e["object"] in known, f"unknown cover story: {e['object']!r}"
        assert e.get("distinguished_by"), f"masquerade edge without discriminator: {e}"


def test_relations_valid_no_self_loops_unique_identity():
    seen = set()
    for e in CURATED_EDGES:
        assert e["relation"] in GRAPH_RELATIONS, f"unknown relation {e['relation']!r}"
        assert e["subject"].lower() != e["object"].lower(), f"self-loop {e['subject']!r}"
        eid = edge_identity(e["subject"], e["relation"], e["object"], e.get("context_topic", ""))
        assert eid not in seen, f"duplicate edge {e['subject']} {e['relation']} {e['object']}"
        seen.add(eid)


def test_labels_are_established_and_hierarchy_has_no_chains():
    narrow_subjects = {e["subject"] for e in CURATED_EDGES if e["relation"] == "narrower_than"}
    for e in CURATED_EDGES:
        assert e["label"] == "established"      # curated P0 = textbook-tier only
        if e["relation"] == "narrower_than":
            # traversal is ONE level (store.py) — a parent that is itself narrower_than
            # something would silently truncate the hierarchy
            assert e["object"] not in narrow_subjects, f"chained hierarchy at {e}"
