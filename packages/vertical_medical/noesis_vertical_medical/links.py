"""Canonical source URLs for medical citations (domain-specific → lives here).

Turns a stored document_id ("<source_key>:<native_id>") into the canonical source
page, so a finding links to the ACTUAL source (rendered natively by that site —
a ClinicalTrials.gov study page, a DailyMed label, a Europe PMC article, etc.).
A text-fragment (#:~:text=) deep-links to the cited quote where the browser
supports it, so the source opens scrolled to the citation.
"""
from __future__ import annotations

import urllib.parse


def _text_fragment(quote: str | None) -> str:
    if not quote:
        return ""
    # first sentence-ish / ~120 chars → a unique, encodable anchor
    snippet = quote.strip().split("\n")[0][:120]
    return "#:~:text=" + urllib.parse.quote(snippet)


def source_url(document_id: str, quote: str | None = None) -> str | None:
    """Canonical URL for a citation's document, or None if no clean page exists."""
    frag = _text_fragment(quote)
    # WEB findings store the full page URL as the document_id — that IS the canonical link. (Without
    # this, "https://…".partition(":") gives src="https", matches no case, and web claims lose their
    # link.) Deep-link to the quote where supported.
    if document_id.startswith("http://") or document_id.startswith("https://"):
        return document_id + frag
    src, _, native = document_id.partition(":")
    if not native:
        return None

    if src == "clinicaltrials":                       # native = NCT id
        return f"https://clinicaltrials.gov/study/{native}{frag}"
    if src in ("openfda", "dailymed"):                # native = SPL setid
        return (f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={native}{frag}")
    if src == "europepmc":                            # native = "MED:12345" / "PMC:..."
        db, _, ext = native.partition(":")
        if ext:
            return f"https://europepmc.org/article/{db}/{ext}{frag}"
        return f"https://europepmc.org/search?query={urllib.parse.quote(native)}"
    if src == "cdc":                                  # native = dataset id
        return f"https://data.cdc.gov/d/{native}"
    if src == "faers":                                # no clean per-report page
        return None
    if src in ("global_guidelines", "india_guidelines"):   # native = registry entry id → its url
        try:
            if src == "global_guidelines":
                from .global_guidelines import GLOBAL_GUIDELINES as _REG
            else:
                from .india_guidelines import INDIA_GUIDELINES as _REG
            for g in _REG:
                if g.get("id") == native:
                    return g.get("url") or None
        except Exception:   # noqa: BLE001
            return None
        return None
    return None
