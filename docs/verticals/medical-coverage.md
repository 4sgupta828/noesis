# Medical Vertical — Coverage Ledger

> Living record of what data we've ingested and what's still to cover. Updated as
> ingestion proceeds. Corpus lives in the fresh `noesis-db` pgvector table
> `rs_block` (port 5434); raw artifacts in Cloudflare R2 (`medicaldata/medical/`);
> embeddings OpenAI text-embedding-3-small (1536-d).

**Last updated:** 2026-08-01 (head deep-ingest COMPLETE — 16 top conditions)
**Corpus size:** **98,422 blocks / 10,266 docs.** By source: clinicaltrials 88,159 ·
europepmc 5,990 · openfda 4,147 · faers 99 · cdc 27.

## Sources (connectors)

| Source | Kind | Tier | Status |
|---|---|---|---|
| ClinicalTrials.gov v2 | trials | open | ✅ live (paginated) |
| openFDA drug label | drug labels | open | ✅ live |
| Europe PMC | literature (abstracts) | open | ✅ live · ⬜ OA full-text TODO |
| openFDA FAERS | adverse events | open | ✅ live (thin so far) |
| DailyMed | SPL labels | open | ✅ connector · ⬜ not yet bulk-ingested |
| CDC (data.cdc.gov) | public health | open | ✅ connector (thin) |
| RxNorm | drug normalization | open | ✅ utility · ⬜ not yet wired into ingest facets |
| **Licensed tier** (Cochrane, NICE, NCCN, NEJM, JAMA) | reviews/guidelines/journals | **licensed** | ⬜ needs contracts |

## Conditions — covered

**Head deep-ingest (✅ 2026-08-01, ~300 trials + 150 papers each):**

| Group | Conditions | Depth |
|---|---|---|
| Oncology | lung · prostate · colorectal · leukemia · lymphoma · melanoma | deep (~4.6–5.4k blocks/condition) |
| Cardiovascular | coronary artery disease · atrial fibrillation · stroke | deep |
| Infectious | HIV · hepatitis C | deep |
| Respiratory/Immuno | asthma · rheumatoid arthritis | deep |
| Neuro/Psych | Alzheimer disease · depression · Parkinson disease | deep |

**Earlier batch:**

| Condition | Trials | Papers | Depth |
|---|---|---|---|
| Type 2 diabetes | ~1,000 | ~200 | deep (reference) |
| Breast cancer | ~100 | ~120 | medium |
| Obesity | ~85 | ~120 | medium |
| COPD | ~90 | ~120 | medium |
| Hypertension | ~48 | ~120 | shallow |
| Heart failure | ~41 | ~120 | shallow |
| Chronic kidney disease | ~? | ~120 | shallow |

## Conditions — TO COVER (next head, then long tail)

**Remaining head (high research volume):**
- Oncology: pancreatic, ovarian, bladder, kidney (RCC), glioblastoma, multiple myeloma, head & neck
- Cardio-metabolic: hyperlipidemia, hyperlipidemia/CAD prevention, PAD, VTE, hypertension (deepen)
- Infectious: COVID-19, tuberculosis, sepsis, hepatitis B, influenza
- Neuro/Psych: multiple sclerosis, epilepsy, migraine, schizophrenia, anxiety, bipolar, ALS
- Immuno/Rheum: psoriasis, IBD (Crohn's/UC), lupus, ankylosing spondylitis, asthma (deepen)
- Renal/GI/other: NASH/MASH, GERD, osteoporosis, anemia, chronic pain

**Long tail (deferred, per plan):** rare diseases, pediatric-specific, region-specific, sub-indications.

## Depth / quality TODO
- Deepen shallow head conditions (hypertension, heart failure, CKD) to ≥300 trials.
- Targeted drug-label ingest by class/route (e.g. inhalers for COPD) — random 500-drug sample leaves gaps (COPD-inhaler query currently refuses).
- Europe PMC **OA full-text** (deeper than abstracts).
- Wire **RxNorm** facet enrichment (rxcui) into ingest for cross-source drug linking.
- FAERS breadth (more drugs) — currently only metformin (~99 reports).
- DailyMed bulk ingest (authoritative labels).

## Notes
- Diabetes stays the deepest (reference build). Cost so far trivial (~$0.5 OpenAI total).
- Retrieval + grounded answers verified live across diabetes, heart failure, breast cancer,
  RA, and the new head conditions.
- Per-source citation tagging + source-utility stats (`retrieved`/`cited`) live.
- **Opioid/controlled-substance safety questions are refused by the MODEL itself** (Claude
  safety behavior), not by our pipeline — verified: "adverse effects of hydrocodone" grounds
  0/3, while "treatments studied for RA/T2D" ground ~3/3. Not a verifier/retrieval bug; the
  UI now shows an honest metadata-driven abstention notice (retrieved-N-passages) in these cases.
