# Noesis IN eval slice (spec D-8)

`slice-india-dev-24-v1.jsonl` — 24 India-practice vignettes DERIVED FROM PUBLIC national
programme guidance (NTEP, NVBDCP, DIPSI, Anemia Mukt Bharat, NRCP, NLEP, IDSP-adjacent).
**NOT NEET-PG material** (D-8: copyright + contamination). Includes the mandated adversarial
cases: India-vs-global conflict (in-21), banned-FDC regulatory (in-15), brand dosing hazard
(in-17), and an unknown brand that must trigger abstention (in-20).

STATUS: **curator drafts — PENDING INDIAN-CLINICIAN REVIEW (launch dependency per D-8).**
Held-out per Rule 5: these questions never appear in any prompt, fixture, or brand-table note.

Launch gate protocol (D-8): run the slice with IN mode OFF then ON (same runner as
`evals/realworld/run.py`, judge with `evals/realworld/judge.py`), score as PAIRED
per-question deltas (sign test, not means) + the K-QA global no-harm check. IN mode must be
strictly better on India-governed questions and neutral elsewhere.
