"""Medical QuestionContract derivation directive (Evidence Contract stage 3).

The VERTICAL half of the question-contract split: this prompt owns ALL the clinical
vocabulary — what counts as an enumerable candidate set, which standard-of-care defaults a
practitioner would consider even when the asker didn't name them, and which safety/interaction
axes the evidence must cover (for exploratory questions: which dimensions a complete answer
must not miss). The kernel (noesis_kernel.research.contract) supplies only the mechanics: it
makes one small structured call with this prompt, expands the result into retrieval legs
(per-entity for enumerative, axis-only for exploratory), and slot-matches claims — all with
generic code.
"""

MEDICAL_CONTRACT_PROMPT = """You derive a QUESTION CONTRACT for a clinical research question: the SHAPE of evidence a complete, safe answer requires. You never answer the question itself.

Decide `mode`:
- "enumerative" — the question demands ENUMERATING and weighing concrete candidate items: choosing among drugs or interventions ("which antibiotics are safest for…", "options for treating X in Y", "what can be used instead of Z"), a best/safest/preferred-agent question over a therapeutic class, or a comparison across named alternatives.
- "exploratory" — everything else: a single-subject lookup (one drug's dose, one trial's result), a mechanism/why question, a diagnosis/workup question, or an open overview. For exploratory questions leave `entities` empty, but DO fill `axes` (see below).

For an exploratory question, fill `axes` with 2–4 short retrieval-friendly phrases naming the DIMENSIONS a complete answer must cover — the must-not-miss causes, mechanisms, or safety facets a practicing clinician would demand be addressed, including the ones the asker did not name. E.g. for "why is my CKD patient fatigued": anemia and iron deficiency in CKD, uremia and dialysis adequacy, hypothyroidism in kidney disease, medication causes of fatigue. For a workup question: the key differentials and the first-line tests. For a single-fact lookup where one dimension suffices, one or two axes are enough — never pad. Leave `entities` empty for exploratory questions.

Set `is_diagnostic` = true (exploratory only) when the question is fundamentally about IDENTIFYING THE DIAGNOSIS — it asks for a differential diagnosis, "what could be causing this / what is this", or the INITIAL WORKUP of an undifferentiated presentation (a patient with symptoms/signs not yet diagnosed). Set it false when the diagnosis is already known and the question is about managing it, or for a mechanism/lookup/overview question. For a diagnostic question, make the `axes` the leading differentials and the key discriminating tests.

For an enumerative question, fill `entities` with the CONCRETE candidate items a practicing clinician would actually consider — specific drug or intervention names, not classes alone. INCLUDE the reasonable standard-of-care defaults the asker did not name: e.g. for empiric antibiotic choice, the specific first-line agents commonly used in that clinical setting (such as a beta-lactam, a fluoroquinolone, trimethoprim-sulfamethoxazole, nitrofurantoin — whichever fit the scenario); for antihypertensive choice, the specific first-line classes' representative agents. Use generic (INN) names. Give 4–8 entities, each a short name.

MANDATORY inclusions for enumerative contracts — these are not optional considerations:
- If the population has compromised organ function (renal, hepatic, cardiac), INCLUDE as entities the commonly-considered agents NOTABLE FOR RISK to that organ (e.g. aminoglycosides such as gentamicin/amikacin for renal compromise) — the answer must be able to warn against them, which requires their evidence.
- If the population implies STANDING TREATMENTS (transplant → immunosuppressants such as tacrolimus/cyclosporine; anticoagulated → anticoagulants; HIV → antiretrovirals), one axis MUST name the interaction with those specific standing treatments.

Fill `axes` with the evidence dimensions the answer MUST cover for EACH candidate, as short retrieval-friendly phrases (2–4 axes). Always consider:
- the dimension the question explicitly asks about (e.g. "dosing in renal impairment", "efficacy for prophylaxis");
- SAFETY/RISK axes for this population — organ toxicity relevant to the case (nephrotoxicity, hepatotoxicity, QT prolongation), contraindications, boxed warnings;
- INTERACTION axes with the population's STANDING TREATMENTS where applicable — e.g. for transplant recipients, interactions with immunosuppressants (tacrolimus, cyclosporine, mycophenolate); for anticoagulated patients, bleeding-relevant interactions; for patients on antiretrovirals, CYP-mediated interactions.

Keep each entity and axis SHORT — they are combined verbatim into search queries. Do not answer the question, recommend an agent, or add prose; derive only the contract."""
