"""v3-P0 expander contract: masquerade legs (incoming mimics/underlies edges) outrank
comorbidity edges when the question names the cover story; per-relation templates carry the
hidden topic + discriminator; manifests_as stays dark; outgoing masquerade edges are skipped."""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from noesis_kernel.graph.store import GraphStore, build_adjacency, edge_identity  # noqa: E402


def _e(subj, rel, obj, *, ctx="", dx="", conf=1.0):
    return {"id": edge_identity(subj, rel, obj, ctx), "subject": subj,
            "subject_norm": " ".join(subj.lower().split()), "relation": rel,
            "object": obj, "object_norm": " ".join(obj.lower().split()),
            "context_topic": ctx, "distinguished_by": dx, "label": "established",
            "provenance": "curated", "confidence": conf}


EDGES = [
    _e("hypertension", "increases_risk_of", "heart failure"),                # comorbidity noise
    _e("coronary artery disease", "causes", "heart failure"),
    _e("atrial fibrillation", "comorbid_with", "heart failure"),
    _e("cardiac amyloidosis", "underlies_presentation_of", "heart failure",
       ctx="HFpEF phenotype", dx="LVH with low-voltage ECG"),
    _e("cardiac sarcoidosis", "underlies_presentation_of", "heart failure",
       dx="AV block in a young patient"),
    _e("heart failure", "manifests_as", "fatigue"),                          # dark relation
]


def _fake_store():
    g = GraphStore.__new__(GraphStore)
    adj = build_adjacency(EDGES)

    async def _adj():
        return adj
    g._adjacency = _adj
    return g


def _expander(monkeypatch_env):
    os.environ["NOESIS_GRAPH"] = "1"
    os.environ["NOESIS_GRAPH_EXPAND"] = "late"
    import api.app as appmod
    appmod._GRAPH_STORE = _fake_store()
    return appmod._make_graph_expander()


def test_masquerade_legs_win_the_cap_with_discriminated_templates():
    exp = _expander(None)
    got = asyncio.run(exp("Patient with heart failure with preserved ejection fraction "
                          "not responding to standard therapy"))
    queries = [leg["query"] for leg in got["legs"]]
    assert len(queries) == 2 and got["late"] is True
    assert queries[0].startswith("cardiac amyloidosis presenting as heart failure")
    assert "low-voltage ECG" in queries[0]                       # discriminator in the query
    assert queries[1].startswith("cardiac sarcoidosis presenting as heart failure")
    # comorbidity edges (hypertension/CAD/AF) were outranked; manifests_as never legs
    assert not any("fatigue" in q for q in queries)


def test_outgoing_masquerade_edge_is_skipped_for_the_masquerader_itself():
    exp = _expander(None)
    got = asyncio.run(exp("management of cardiac amyloidosis"))
    # asking about the masquerader: its cover-story leg adds nothing — no legs from
    # the outgoing underlies edge (and nothing else is adjacent)
    assert got is None or all(
        not leg["query"].startswith("cardiac amyloidosis presenting")
        for leg in got["legs"])
