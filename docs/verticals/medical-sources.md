# Medical Vertical — Canonical Source Discovery

> Verified against official docs (Aug 2026). The source landscape defines the vertical:
> it drives the connectors, the authority policy, the entity taxonomy, and the scope model.
> Two axes matter: **ingestibility** (can we legally/technically pull it) and **authority**
> (where it sits on the evidence pyramid). They are often inversely correlated — the
> highest-authority sources are the most license-gated.

## Ingestion tiers (build order)

### Tier 1 — public JSON, no/low auth, permissive license → ingest immediately
| Source | Endpoint | Auth | Entity | License |
|---|---|---|---|---|
| **ClinicalTrials.gov v2** | `clinicaltrials.gov/api/v2/` | none | trial (NCT) | public domain |
| **openFDA** | `api.fda.gov` (`/drug/label`, `/drug/event` FAERS, `/device/event`) | free key raises limits (240/min·120k/day) | drug label, adverse event, recall | public info |
| **CDC** | `data.cdc.gov` (SODA) + MMWR RSS | none (optional token) | surveillance, MMWR report | public domain |
| **DailyMed** | `dailymed.nlm.nih.gov/.../services/v2/` + bulk SPL | none | drug label (SPL) | public domain |
| **Europe PMC** | `ebi.ac.uk/europepmc/webservices/rest/` | none | article + OA full text | per-article CC |
| **RxNorm / RxNav** | `rxnav.nlm.nih.gov/REST/` | none | drug concept (RxCUI) | free |

### Tier 2 — no auth but XML-first / rate-shaped
PubMed E-utilities (`eutils.ncbi.nlm.nih.gov`, free key → 10 req/s, XML) · MeSH (SPARQL/RDF) ·
PMC OA bulk (FTP/S3 `pmc-oa-opendata`, per-article CC — respect NC flags) · ICD-10-CM (CMS/CDC bulk files).

### Tier 3 — free but registration/OAuth gate
ICD-11 WHO (free OAuth2, **CC BY-ND** = no derivatives) · **UMLS** (free license + key; unlocks
cross-vocab + SNOMED + RxNorm) · LOINC (free account) · USPSTF (email approval).

### Tier 4 — license-gated, NOT freely ingestible (licensed connectors only)
| Source | Path to access |
|---|---|
| **Cochrane** (systematic reviews) | Wiley commercial license; **Cochrane Library API via AWS Marketplace**; only per-review CC-BY OA subset reusable without it |
| **NICE** (UK guidelines) | signed Syndication licence + API key + monthly approval |
| **NCCN Guidelines** | **NCCN Developer API (XML/JSON)** behind Per-Project/Annual license |
| **NEJM** | NEJM Group content-licensing program (incl. LLM training datasets); abstracts free via PubMed |
| **JAMA** (subscription titles) | AMA content license / registered TDM license. **JAMA Network Open is CC-BY OA** → freely ingestible via PMC |
| **SNOMED CT** | Affiliate License (free in member countries incl. US) or via UMLS; Snowstorm FHIR server |
| **WHO guidelines** | no clean API — document ingestion; per-doc license (often CC BY-NC-SA 3.0 IGO) |
| **UpToDate, Embase, ClinicalKey** | proprietary subscription — no open API. Do not scrape. |

## Authority hierarchy (→ the vertical's authority policy)

**A. Controlling for practice (evidence synthesis + guidelines) — highest:**
Cochrane systematic reviews (apex) · NICE · WHO · USPSTF · CDC · (licensed) NCCN.
_Irony: the top authority tier is the hardest to ingest. CDC is the one apex source that is
freely + programmatically open._

**B. Primary evidence (RCTs / trials / studies):**
ClinicalTrials.gov (trial record) · PubMed / Europe PMC / PMC OA (primary literature) ·
openFDA/FAERS (post-market safety). Strongest programmatic access; lower on the pyramid than A.
NEJM / JAMA sit here at the top of *primary* evidence — but license-gated.

**C. Terminology / ontology (normalization backbone, not clinical authority):**
UMLS (cross-map hub) · SNOMED CT (concepts) · RxNorm (drugs) · LOINC (labs) ·
ICD-10/11 (diagnoses) · MeSH (literature indexing). Used to normalize + link entities across A/B.

## The open vs licensed connector split (platform design)
Both kinds implement the **same `Connector` interface**. The difference is a `license` gate +
credentials, not code. Open connectors ship now; licensed connectors slot in behind a flag once a
contract lands. The authority policy ranks premium sources (Cochrane/NCCN/NEJM/JAMA) at the top but
marks them gated — the vertical answers from open sources by default and lights up the premium tier
when licensed. (This is exactly how OpenEvidence's "Official AI Partner of NEJM/JAMA/NCCN/Cochrane"
works: negotiated licenses, not downloads.)

## Recommended build order
1. **Corpus from Tier 1** (ClinicalTrials.gov, openFDA, CDC, DailyMed, Europe PMC, RxNorm) — primary
   evidence + drug/safety + public-health guidance, zero license friction.
2. **UMLS/RxNorm/MeSH** early as the normalization backbone (one free UMLS key unlocks SNOMED + RxNorm).
3. **Defer** the gated guideline tier (Cochrane, NICE, WHO, USPSTF, NCCN, NEJM, JAMA) to a
   licensing/partnership workstream; treat WHO/guidelines initially as document ingestion.

## Verification caveats
Rate limits/auth confirmed on official pages for E-utilities, openFDA, DailyMed, RxNorm, UMLS, MeSH,
ICD, LOINC, SNOMED, CDC, NICE, USPSTF, Cochrane. Europe PMC (~10 req/s) and ClinicalTrials.gov
(~1 req/s) courtesy limits are community-sourced, not official. Verify per-document license at
ingestion for ICD-11 (CC BY-ND), LOINC redistribution, and WHO/NICE variants.
