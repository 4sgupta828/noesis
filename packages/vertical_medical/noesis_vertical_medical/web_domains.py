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
