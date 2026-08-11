"""Curated-edge contract: every endpoint is an EXACT registry label, every relation is in the
vocabulary, identities are unique, no self-loops — a wrong-node curated edge would poison
retrieval expansion (spec eval gate, structural half)."""
from noesis_kernel.graph.store import edge_identity

from noesis_vertical_medical.coverage import COVERED_CONDITIONS
from noesis_vertical_medical.graph import CURATED_EDGES, GRAPH_RELATIONS


def test_endpoints_are_exact_registry_labels():
    registry = {c["name"] for c in COVERED_CONDITIONS}
    for e in CURATED_EDGES:
        assert e["subject"] in registry, f"unknown subject {e['subject']!r}"
        assert e["object"] in registry, f"unknown object {e['object']!r}"


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
