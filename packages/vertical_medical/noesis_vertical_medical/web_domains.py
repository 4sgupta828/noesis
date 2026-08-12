"""Trusted web-search domains for the medical vertical.

When web search is on, results are restricted to this whitelist so the corpus is augmented only
with HIGH-QUALITY, authoritative medical sources — peer-reviewed journals, systematic-review /
guideline bodies, and government/authoritative databases — never the open (unvetted) web.

Domain knowledge lives in the vertical (Rule 18); the kernel's Exa client only applies the list.
"""
from __future__ import annotations

# NOTE: this list gates EXA SEARCH, and Exa serves its own cached page text — publisher bot-walls
# (OUP/Silverchair/Elsevier) do NOT limit what can be searched, only what we can fetch directly.
# So the frontier here is quality judgment, not fetchability. Bar: peer-reviewed, professional
# society, guideline body, government/regulator, or professional-grade reference. Deliberately
# excluded: consumer health portals, ad-driven aggregators, preprint-only servers.
TRUSTED_WEB_DOMAINS: tuple[str, ...] = (
    # Government / regulators / authoritative databases
    "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov",
    "clinicaltrials.gov", "nih.gov", "cdc.gov", "fda.gov", "who.int",
    "cancer.gov", "medlineplus.gov", "europepmc.org", "dailymed.nlm.nih.gov",
    "ahrq.gov", "ema.europa.eu", "ecdc.europa.eu", "samhsa.gov", "cms.gov",
    # Peer-reviewed journals / publishers
    "nejm.org", "jamanetwork.com", "thelancet.com", "bmj.com", "annals.org",
    "nature.com", "science.org", "cell.com", "academic.oup.com", "onlinelibrary.wiley.com",
    "ahajournals.org", "diabetesjournals.org", "ascopubs.org", "atsjournals.org",
    "erj.ersjournals.com", "gutjnl.bmj.com", "jns.org", "neurology.org", "blood.org",
    "ashpublications.org", "acpjournals.org", "sciencedirect.com", "springer.com",
    "link.springer.com", "plos.org", "jacc.org", "gastrojournal.org",
    "journal-of-hepatology.eu", "publications.aap.org", "chestjournal.org",
    # Systematic reviews & clinical guidelines / HTA
    "cochranelibrary.com", "nice.org.uk", "nccn.org", "uptodate.com",
    "uspreventiveservicestaskforce.org", "sign.ac.uk", "cda-amc.ca",
    # Major professional societies — cardio/pulm/renal/endo
    "acc.org", "heart.org", "escardio.org", "hrsonline.org", "goldcopd.org",
    "ginasthma.org", "thoracic.org", "chestnet.org", "ersnet.org",
    "kdigo.org", "kidney.org", "asn-online.org",
    "diabetes.org", "easd.org", "endocrine.org", "thyroid.org",
    # oncology / heme
    "asco.org", "esmo.org", "cancer.org", "hematology.org",
    # ID / immuno / allergy
    "idsociety.org", "aaaai.org", "acaai.org",
    # GI / hepatology
    "gastro.org", "gi.org", "asge.org", "aasld.org", "easl.eu",
    # neuro / psych / geriatrics / sleep
    "aan.com", "psychiatry.org", "americangeriatrics.org", "aasm.org",
    # rheum / derm / MSK / eyes / ENT
    "rheumatology.org", "eular.org", "aad.org", "aaos.org", "aao.org", "entnet.org",
    # OB-GYN / peds / urology / anesthesia-critical care / primary care / pharmacy / radiology
    "acog.org", "aap.org", "auanet.org", "asahq.org", "sccm.org",
    "aafp.org", "acponline.org", "ashp.org", "acr.org",
    # Professional-grade clinical reference
    "mayoclinic.org", "clevelandclinic.org", "merckmanuals.com", "radiopaedia.org",
    # India — government / regulators / programmes / societies (Noesis IN, spec D-6: without
    # these the web leg is structurally blind to Indian guidance in IN mode)
    "icmr.gov.in", "main.icmr.nic.in", "stw.icmr.org.in", "mohfw.gov.in", "nhm.gov.in",
    "cdsco.gov.in", "tbcindia.gov.in", "nvbdcp.gov.in", "ncdc.gov.in", "janaushadhi.gov.in",
    "apiindia.org", "iapindia.org", "fogsi.org", "csi.org.in",
    "ijmr.org.in", "indianpediatrics.net", "japi.org",
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
    "sign.ac.uk":                           {"pub_type": "practice guideline"},
    "cda-amc.ca":                           {"pub_type": "practice guideline"},
    "ahrq.gov":                             {"pub_type": "practice guideline"},
    "ema.europa.eu":                        {"pub_type": "practice guideline"},   # regulatory = normative
    # journals / societies / references: venue label only (observability + dedup preference),
    # NO design default — tier comes from the work's self-declared type
    "nejm.org": {"source_kind": "journal"}, "jamanetwork.com": {"source_kind": "journal"},
    "thelancet.com": {"source_kind": "journal"}, "bmj.com": {"source_kind": "journal"},
    "ahajournals.org": {"source_kind": "journal"}, "academic.oup.com": {"source_kind": "journal"},
    "jacc.org": {"source_kind": "journal"}, "plos.org": {"source_kind": "journal"},
    "gastrojournal.org": {"source_kind": "journal"}, "chestjournal.org": {"source_kind": "journal"},
    "link.springer.com": {"source_kind": "journal"}, "publications.aap.org": {"source_kind": "journal"},
    "ncbi.nlm.nih.gov": {"source_kind": "article"}, "europepmc.org": {"source_kind": "article"},
    "mayoclinic.org": {"source_kind": "reference"}, "clevelandclinic.org": {"source_kind": "reference"},
    "medlineplus.gov": {"source_kind": "reference"}, "merckmanuals.com": {"source_kind": "reference"},
    "radiopaedia.org": {"source_kind": "reference"},
    # India (D-6): government guidance/programme bodies = normative; source_country stamped so
    # the tier-aware IN boost sees them; journals get venue label only (tier self-declared)
    "icmr.gov.in": {"pub_type": "practice guideline", "source_country": "IN"},
    "main.icmr.nic.in": {"pub_type": "practice guideline", "source_country": "IN"},
    "stw.icmr.org.in": {"pub_type": "practice guideline", "source_country": "IN"},
    "mohfw.gov.in": {"pub_type": "practice guideline", "source_country": "IN"},
    "nhm.gov.in": {"pub_type": "practice guideline", "source_country": "IN"},
    "cdsco.gov.in": {"pub_type": "practice guideline", "source_country": "IN"},  # regulatory = normative
    "tbcindia.gov.in": {"pub_type": "practice guideline", "source_country": "IN"},
    "nvbdcp.gov.in": {"pub_type": "practice guideline", "source_country": "IN"},
    "ncdc.gov.in": {"pub_type": "practice guideline", "source_country": "IN"},
    "janaushadhi.gov.in": {"source_kind": "reference", "source_country": "IN"},
    "apiindia.org": {"source_kind": "journal", "source_country": "IN"},
    "iapindia.org": {"source_kind": "journal", "source_country": "IN"},
    "fogsi.org": {"source_kind": "journal", "source_country": "IN"},
    "csi.org.in": {"source_kind": "journal", "source_country": "IN"},
    "ijmr.org.in": {"source_kind": "journal", "source_country": "IN"},
    "indianpediatrics.net": {"source_kind": "journal", "source_country": "IN"},
    "japi.org": {"source_kind": "journal", "source_country": "IN"},
}
