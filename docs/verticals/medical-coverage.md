# Medical Vertical — Coverage Ledger

> Living record of what data we've ingested and what's still to cover. Updated as
> ingestion proceeds. Corpus lives in the fresh `noesis-db` pgvector table
> `rs_block` (port 5434); raw artifacts in Cloudflare R2 (`medicaldata/medical/`);
> embeddings OpenAI text-embedding-3-small (1536-d).

**Last updated:** 2026-08-02 (tier-2 deep-ingest COMPLETE — 31 more conditions; synced to prod)
**Corpus size:** **208,864 blocks / 21,858 docs.** By source: clinicaltrials 190,159 ·
europepmc 14,432 · openfda 4,147 · faers 99 · cdc 27.

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

**Tier-2 deep-ingest (✅ 2026-08-02, ~300 trials + 150 papers each):**

| Group | Conditions | Depth |
|---|---|---|
| Oncology | pancreatic · ovarian · bladder · renal cell carcinoma · glioblastoma · multiple myeloma · head & neck | deep |
| Cardiovascular | hyperlipidemia · peripheral artery disease · venous thromboembolism | deep |
| Infectious | COVID-19 · tuberculosis · sepsis · hepatitis B · influenza | deep |
| Neuro/Psych | multiple sclerosis · epilepsy · migraine · schizophrenia · anxiety disorder · bipolar disorder · ALS | deep |
| Immuno/Rheum | psoriasis · inflammatory bowel disease · systemic lupus erythematosus · ankylosing spondylitis | deep |
| Metabolic/GI | NASH/MASH · GERD · osteoporosis · anemia | deep |
| Other | chronic pain | deep |

## Conditions — TO COVER (tier-3 long tail)

- Oncology: cervical, esophageal, gastric, sarcoma
- Cardiovascular: pulmonary hypertension, valvular heart disease
- Infectious: malaria, HPV
- Neuro/Psych: Huntington disease, PTSD, ADHD
- Immuno/Rheum: Sjögren syndrome, vasculitis
- Metabolic/GI: celiac disease, gout
- Respiratory: pulmonary fibrosis, cystic fibrosis
- Renal: polycystic kidney disease

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
