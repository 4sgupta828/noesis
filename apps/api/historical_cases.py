"""Historical Cases — a CURATED registry of real, documented landmark medical cases.

Each case is a REAL case from the past (not a hypothetical vignette) whose correct clinical
decision is historically established. Noesis answers the de-contextualized decision `question`;
a clinician then grades that answer against the `reference` (the historically-correct decision)
using a structured rubric. Curated content only — no LLM, no PII. Extend toward the top-100 by
appending entries and (optionally) clusters. `id` is a stable slug (the run/eval key); never
rename an existing id (it would orphan its stored answer + evaluations).

Selection basis (locked with the user 2026-08-18): landmark documented cases whose lesson matters
most across the human population, spread across five clinical clusters.
"""
from __future__ import annotations

# Meaningful clusters (ordered). `key` is stable; `label` is display text.
CLUSTERS: tuple[dict, ...] = (
    {"key": "antimicrobial", "label": "Antimicrobial therapy is curative"},
    {"key": "public_health", "label": "Public health — stop transmission at the source"},
    {"key": "replacement", "label": "Replace the missing factor"},
    {"key": "safety", "label": "Patient safety & pharmacovigilance"},
    {"key": "frontier", "label": "Frontier cures"},
)

CASES: tuple[dict, ...] = (
    # ---- Antimicrobial therapy is curative ----
    {"id": "penicillin-alexander", "cluster": "antimicrobial", "year": 1941,
     "title": "Albert Alexander — the first patient treated with penicillin (1941)",
     "case": ("Oxford, 1941. Albert Alexander, a police constable, developed overwhelming "
              "staphylococcal and streptococcal sepsis from a small facial wound, with spreading "
              "abscesses, bacteraemia and loss of an eye. He was near death when given the first "
              "clinical course of penicillin; he improved dramatically over days — then relapsed "
              "and died when the tiny, hand-purified supply ran out."),
     "question": ("A previously healthy adult has overwhelming bacterial sepsis spreading from a "
                  "skin and facial infection, with abscesses and bacteraemia. What is the correct "
                  "management, and why do the adequacy and full duration of antimicrobial therapy "
                  "matter?"),
     "reference": ("Prompt, effective antimicrobial therapy targeting the likely pathogen PLUS "
                   "source control (drainage of abscesses); ensure an ADEQUATE dose and a FULL "
                   "course. Alexander's relapse and death when penicillin was stopped early "
                   "established both that antibiotics are curative for bacterial sepsis and that "
                   "under-dosing / early cessation loses the cure.")},
    {"id": "hpylori-marshall", "cluster": "antimicrobial", "year": 1984,
     "title": "Barry Marshall — peptic ulcer disease is an infection (1984)",
     "case": ("Perth, 1984. Gastroenterologist Barry Marshall, unable to infect an animal model, "
              "drank a culture of Helicobacter pylori, developed acute gastritis, and demonstrated "
              "the organism could be eradicated with antimicrobials — overturning the dogma that "
              "ulcers were caused by stress and acid alone. He and Robin Warren won the 2005 Nobel "
              "Prize."),
     "question": ("An adult with recurrent peptic ulcer disease tests positive for Helicobacter "
                  "pylori. What is the correct treatment approach, and why is acid suppression "
                  "alone insufficient?"),
     "reference": ("H. pylori ERADICATION with a combination antibiotic regimen (e.g. "
                   "clarithromycin- or bismuth-based quadruple therapy) plus a PPI — then confirm "
                   "eradication. Acid suppression alone relieves symptoms but does not cure the "
                   "underlying infection, so ulcers recur; eradication makes the disease curable.")},

    # ---- Public health — stop transmission at the source ----
    {"id": "cholera-snow", "cluster": "public_health", "year": 1854,
     "title": "John Snow — the Broad Street pump and cholera (1854)",
     "case": ("Soho, London, 1854. During a lethal cholera outbreak, John Snow mapped deaths and "
              "traced them to a single contaminated public water pump on Broad Street. He "
              "persuaded the authorities to remove the pump handle; the outbreak abated. This "
              "established cholera as waterborne and founded modern epidemiology."),
     "question": ("A tight cluster of patients in one neighbourhood develop severe acute watery "
                  "diarrhoea with rapid dehydration and deaths, all sharing one public water "
                  "source. What are the correct clinical and public-health decisions?"),
     "reference": ("Recognise cholera / waterborne transmission: SOURCE CONTROL — identify and "
                   "shut off or decontaminate the implicated water supply (the population-level "
                   "cure) — plus aggressive oral/IV rehydration (and antibiotics in severe cases) "
                   "for those affected. The decisive act is removing the source, not only treating "
                   "individuals.")},
    {"id": "handwashing-semmelweis", "cluster": "public_health", "year": 1847,
     "title": "Ignaz Semmelweis — hand hygiene and childbed fever (1847)",
     "case": ("Vienna General Hospital, 1847. Maternal deaths from puerperal (childbed) fever were "
              "far higher on the ward staffed by doctors and students who came directly from "
              "performing autopsies than on the midwives' ward. Semmelweis introduced handwashing "
              "in chlorinated lime between the morgue and the delivery room; mortality fell "
              "sharply — the foundation of antisepsis and infection control."),
     "question": ("On a maternity ward, deaths from postpartum fever are dramatically higher among "
                  "patients cared for by clinicians who arrive directly from performing autopsies. "
                  "What intervention is correct, and what is the mechanism?"),
     "reference": ("HAND HYGIENE / antisepsis between contacts — clinicians are transmitting "
                   "infectious material from cadavers to patients on their hands. Hand "
                   "decontamination between every patient contact is the correct, decisive "
                   "intervention and the basis of modern infection prevention.")},

    # ---- Replace the missing factor ----
    {"id": "insulin-thompson", "cluster": "replacement", "year": 1922,
     "title": "Leonard Thompson — the first patient treated with insulin (1922)",
     "case": ("Toronto, 1922. Leonard Thompson, a 14-year-old dying of type 1 diabetes, was "
              "emaciated and in ketoacidosis. Banting, Best, Collip and Macleod gave him purified "
              "pancreatic extract (insulin); his blood glucose fell, ketosis cleared, and he "
              "recovered — turning a uniformly fatal disease into a treatable one."),
     "question": ("An emaciated adolescent presents with marked hyperglycaemia, ketosis and "
                  "acidosis (new type 1 diabetes / diabetic ketoacidosis). What is the definitive "
                  "treatment and the immediate management?"),
     "reference": ("INSULIN replacement is the definitive treatment (type 1 diabetes is absolute "
                   "insulin deficiency). Acute DKA management: IV fluids, an IV insulin infusion, "
                   "and careful potassium replacement (give potassium with insulin once K⁺ is not "
                   "high), while treating the precipitant and monitoring for cerebral oedema.")},
    {"id": "pernicious-anemia-minot-murphy", "cluster": "replacement", "year": 1926,
     "title": "Minot & Murphy — pernicious anaemia reversed by liver therapy (1926)",
     "case": ("Boston, 1926. George Minot and William Murphy showed that patients with pernicious "
              "anaemia — until then a fatal, progressive megaloblastic anaemia with neurological "
              "decline — recovered when fed large amounts of liver. The active factor was later "
              "identified as vitamin B12; they shared the 1934 Nobel Prize."),
     "question": ("An adult has a progressive macrocytic (megaloblastic) anaemia with fatigue, "
                  "glossitis and neurological symptoms, and a previously 'incurable' course. What "
                  "is the correct treatment once B12 deficiency is identified?"),
     "reference": ("Vitamin B12 (cobalamin) REPLACEMENT — historically dietary liver, now "
                   "parenteral or high-dose oral B12 — corrects the megaloblastic anaemia and, if "
                   "given early, the neurological damage. Identify the cause (e.g. autoimmune "
                   "intrinsic-factor deficiency = pernicious anaemia) and do not treat with folate "
                   "alone, which can mask B12 deficiency while neurology progresses.")},

    # ---- Patient safety & pharmacovigilance ----
    {"id": "serotonin-libby-zion", "cluster": "safety", "year": 1984,
     "title": "Libby Zion — a fatal drug interaction and serotonin syndrome (1984)",
     "case": ("New York, 1984. Libby Zion, an 18-year-old, died after receiving meperidine "
              "(pethidine) while already taking the MAO inhibitor phenelzine, developing agitation, "
              "rigidity and hyperthermia. The case reshaped US residency duty-hour rules and "
              "highlighted lethal drug–drug interactions."),
     "question": ("An agitated, febrile patient taking an MAO-inhibitor antidepressant is given "
                  "meperidine (pethidine) and develops rigidity, hyperthermia, tremor and clonus. "
                  "What is the diagnosis, the correct management, and what should have been "
                  "avoided?"),
     "reference": ("SEROTONIN SYNDROME from a serotonergic drug interaction. Stop all serotonergic "
                   "agents; aggressive supportive care (cooling, IV fluids, sedation with "
                   "benzodiazepines), and cyproheptadine in moderate–severe cases. The correct "
                   "prescribing decision is to AVOID meperidine (and other serotonergic drugs) in "
                   "a patient on an MAOI — a well-established contraindicated combination.")},
    {"id": "hm-bilateral-temporal", "cluster": "safety", "year": 1953,
     "title": "Henry Molaison ('H.M.') — the limits of bilateral temporal-lobe surgery (1953)",
     "case": ("1953. To treat intractable epilepsy, Henry Molaison underwent bilateral removal of "
              "the medial temporal lobes, including the hippocampi. His seizures improved but he "
              "was left with profound, permanent anterograde amnesia — unable to form new "
              "memories. His case defined the hippocampus's role in memory and the limits of "
              "resective surgery."),
     "question": ("A patient with intractable epilepsy is being considered for bilateral medial "
                  "temporal-lobe (hippocampal) resection. What is the critical risk and the correct "
                  "surgical decision?"),
     "reference": ("Do NOT perform bilateral medial temporal-lobe resection: removing both "
                   "hippocampi causes devastating, permanent anterograde amnesia. The correct "
                   "approach is a unilateral, function-sparing procedure guided by lateralisation "
                   "and memory testing (e.g. Wada / neuropsychological assessment) to preserve "
                   "memory. H.M. established both memory localisation and this surgical limit.")},

    # ---- Frontier cures ----
    {"id": "leukemia-farber", "cluster": "frontier", "year": 1948,
     "title": "Sidney Farber — the first remissions in childhood leukaemia (1948)",
     "case": ("Boston, 1948. Childhood acute lymphoblastic leukaemia (ALL) was uniformly and "
              "rapidly fatal. Sidney Farber used the antifolate aminopterin and induced the first "
              "temporary remissions — proof that a drug could push leukaemia back, and the seed of "
              "modern combination chemotherapy that now cures most childhood ALL."),
     "question": ("A child presents with acute lymphoblastic leukaemia, historically a uniformly "
                  "fatal disease. What class of therapy can induce remission, and what is the "
                  "modern trajectory of treatment?"),
     "reference": ("ANTIMETABOLITE / antifolate chemotherapy (aminopterin, then methotrexate) can "
                   "induce remission — the founding proof of chemotherapy. Modern care uses "
                   "risk-adapted MULTI-AGENT combination chemotherapy (induction, consolidation, "
                   "maintenance, CNS prophylaxis), curing the large majority of childhood ALL.")},
    {"id": "kidney-transplant-herrick", "cluster": "frontier", "year": 1954,
     "title": "The Herrick twins — the first successful kidney transplant (1954)",
     "case": ("Boston, 1954. Richard Herrick had end-stage kidney failure; his healthy identical "
              "twin Ronald donated a kidney. Joseph Murray performed the first successful human "
              "organ transplant — successful precisely because an identical-twin graft provoked no "
              "immune rejection, defining transplant immunology. Murray later won the Nobel Prize."),
     "question": ("A patient with end-stage renal failure has a healthy identical twin willing to "
                  "donate. What is the definitive treatment, and why is the donor choice pivotal to "
                  "success?"),
     "reference": ("Kidney TRANSPLANTATION is the definitive treatment; an HLA-identical (identical "
                   "twin) donor is pivotal because the graft is not rejected without "
                   "immunosuppression. This case established transplantation and framed the central "
                   "problem — overcoming immunologic rejection — that immunosuppression later "
                   "solved for non-identical donors.")},
)

_CASE_BY_ID = {c["id"]: c for c in CASES}


def all_cases() -> list[dict]:
    return [dict(c) for c in CASES]


def all_clusters() -> list[dict]:
    return [dict(c) for c in CLUSTERS]


def get_case(case_id: str) -> dict | None:
    c = _CASE_BY_ID.get(case_id)
    return dict(c) if c else None
