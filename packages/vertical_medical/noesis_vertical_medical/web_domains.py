"""Trusted web-search domains for the medical vertical.

When web search is on, results are restricted to this whitelist so the corpus is augmented only
with HIGH-QUALITY, authoritative medical sources — peer-reviewed journals, systematic-review /
guideline bodies, and government/authoritative databases — never the open (unvetted) web.

Domain knowledge lives in the vertical (Rule 18); the kernel's Exa client only applies the list.
"""
from __future__ import annotations

TRUSTED_WEB_DOMAINS: tuple[str, ...] = (
    # Government / authoritative databases
    "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov",
    "clinicaltrials.gov", "nih.gov", "cdc.gov", "fda.gov", "who.int",
    "cancer.gov", "medlineplus.gov", "europepmc.org", "dailymed.nlm.nih.gov",
    # Peer-reviewed journals
    "nejm.org", "jamanetwork.com", "thelancet.com", "bmj.com", "annals.org",
    "nature.com", "science.org", "cell.com", "academic.oup.com", "onlinelibrary.wiley.com",
    "ahajournals.org", "diabetesjournals.org", "ascopubs.org", "atsjournals.org",
    "erj.ersjournals.com", "gutjnl.bmj.com", "jns.org", "neurology.org", "blood.org",
    "ashpublications.org", "acpjournals.org", "sciencedirect.com", "springer.com",
    # Systematic reviews & clinical guidelines
    "cochranelibrary.com", "nice.org.uk", "nccn.org", "uptodate.com",
    "uspreventiveservicestaskforce.org",
    # Major professional societies
    "acc.org", "heart.org", "escardio.org", "diabetes.org", "easd.org",
    "asco.org", "idsociety.org", "rheumatology.org", "aan.com", "aasld.org",
    "easl.eu", "goldcopd.org", "ginasthma.org", "kdigo.org",
    # Reputable clinical reference
    "mayoclinic.org", "clevelandclinic.org",
)

# Domain → facets stamped on every web block from that domain, so the SAME structural evidence
# classifier (`evidence_kind.classify`) and authority pyramid that grade corpus evidence also grade
# web evidence. CONSERVATIVE by design: only domains that are DEDICATED normative-guidance venues
# get a pub_type default ("practice guideline" → graded `guideline` by the classifier). Journal and
# society sites do NOT get a design default — a NEJM page may be an editorial, a society page may be
# news; their tier still comes from the work's own self-label (title/pub_type), which the classifier
# already reads. Venue authority ≠ study design; conflating them would over-rank.
WEB_DOMAIN_FACETS: dict[str, dict] = {
    # dedicated guideline / normative-guidance bodies → controlling tier by venue
    "kdigo.org":                            {"pub_type": "practice guideline"},
    "nice.org.uk":                          {"pub_type": "practice guideline"},
    "uspreventiveservicestaskforce.org":    {"pub_type": "practice guideline"},
    "goldcopd.org":                         {"pub_type": "practice guideline"},
    "ginasthma.org":                        {"pub_type": "practice guideline"},
    "nccn.org":                             {"pub_type": "practice guideline"},
    "who.int":                              {"pub_type": "practice guideline"},
    "cdc.gov":                              {"pub_type": "practice guideline"},
    "fda.gov":                              {"pub_type": "practice guideline"},   # regulatory = normative
    "cochranelibrary.com":                  {"pub_type": "systematic review"},
    # journals / societies / references: venue label only (observability + dedup preference),
    # NO design default — tier comes from the work's self-declared type
    "nejm.org": {"source_kind": "journal"}, "jamanetwork.com": {"source_kind": "journal"},
    "thelancet.com": {"source_kind": "journal"}, "bmj.com": {"source_kind": "journal"},
    "ahajournals.org": {"source_kind": "journal"}, "academic.oup.com": {"source_kind": "journal"},
    "ncbi.nlm.nih.gov": {"source_kind": "article"}, "europepmc.org": {"source_kind": "article"},
    "mayoclinic.org": {"source_kind": "reference"}, "clevelandclinic.org": {"source_kind": "reference"},
    "medlineplus.gov": {"source_kind": "reference"},
}
