"""Voices — what clinicians and researchers have SAID, as a browsing surface.

Separate from answers by construction. The blocks this module searches carry
`source_kind="transcript"`, which the medical manifest lists in `non_evidence_facets`, so the
retrieval source refuses them for every research request. Nothing here can ground a clinical claim;
this surface answers a different question — who is saying what, and where practice is moving.
"""
from .search import VOICE_SOURCE_KEYS, build_query, dedupe, moment, terms, tsqueries

__all__ = ["VOICE_SOURCE_KEYS", "build_query", "dedupe", "moment", "terms", "tsqueries"]
