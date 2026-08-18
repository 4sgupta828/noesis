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

# Meaningful clusters (ordered). `key` is stable; `label` is display text; `era` groups the board into
# Historical (pre-~1975 landmarks) vs Recent (last 4-5 decades).
CLUSTERS: tuple[dict, ...] = (
    {"key": "antimicrobial", "label": "Antimicrobial therapy is curative", "era": "historical"},
    {"key": "public_health", "label": "Public health — stop transmission at the source", "era": "historical"},
    {"key": "replacement", "label": "Replace the missing factor", "era": "historical"},
    {"key": "safety", "label": "Patient safety & pharmacovigilance", "era": "historical"},
    {"key": "frontier", "label": "Frontier cures", "era": "historical"},
    # ---- recent era (1975-2025) ----
    {"key": "emerging_infections", "label": "Emerging infections — recognize the new pathogen", "era": "recent"},
    {"key": "targeted_onco", "label": "Targeted & immuno-oncology", "era": "recent"},
    {"key": "reperfusion", "label": "Reperfusion & time-critical intervention", "era": "recent"},
    {"key": "human_factors", "label": "Patient safety & human factors", "era": "recent"},
    {"key": "frontier_recent", "label": "Transplant, gene & reproductive frontiers", "era": "recent"},
    {"key": "critical_care", "label": "Critical care & ventilation", "era": "recent"},
    # ---- recent era, tranche 2 clusters ----
    {"key": "chronic_cure", "label": "Turning fatal or chronic disease treatable", "era": "recent"},
    {"key": "neuromodulation", "label": "Neuromodulation & sensory restoration", "era": "recent"},
    {"key": "perinatal", "label": "Perinatal & neonatal", "era": "recent"},
    {"key": "minimally_invasive", "label": "Minimally invasive & endovascular surgery", "era": "recent"},
    {"key": "prevention_screening", "label": "Prevention, screening & genomic risk", "era": "recent"},
    # ---- recent era, tranche 3 clusters ----
    {"key": "global_health", "label": "Vaccines, eradication & global health", "era": "recent"},
    {"key": "amr_microbiome", "label": "Resistance, stewardship & the microbiome", "era": "recent"},
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

    # ============================ RECENT ERA (1975-2025), tranche 1 ============================
    # ---- Emerging infections — recognize the new pathogen ----
    {"id": "aids-index-1981", "cluster": "emerging_infections", "era": "recent", "year": 1981,
     "title": "The first AIDS cases — a new immunodeficiency (1981)",
     "case": ("June 1981. The CDC's MMWR reported Pneumocystis pneumonia and other opportunistic "
              "infections in previously healthy young men in Los Angeles — a pattern that made no "
              "sense in the immunocompetent. It was the sentinel signal of AIDS; the causative "
              "retrovirus (HIV) was identified in 1983-84."),
     "question": ("Previously healthy young adults present in a cluster with opportunistic infections "
                  "(e.g. Pneumocystis pneumonia) that normally occur only with severe immune "
                  "suppression, and standard work-ups find no known cause. How should this be "
                  "approached?"),
     "reference": ("Recognise a NOVEL acquired immunodeficiency rather than forcing the picture into "
                   "known diagnoses: investigate and report the cluster (public-health signal), pursue "
                   "the unifying cause, and treat/prophylax the opportunistic infections. Once HIV was "
                   "identified, the decisive treatment became combination antiretroviral therapy — "
                   "turning a fatal disease into a chronic one.")},
    {"id": "sars-urbani-2003", "cluster": "emerging_infections", "era": "recent", "year": 2003,
     "title": "SARS and Carlo Urbani — sound the alarm on a novel pathogen (2003)",
     "case": ("Hanoi, 2003. WHO physician Carlo Urbani recognised that a severe atypical pneumonia "
              "spreading among hospital staff was a new, highly transmissible disease (SARS). His "
              "early alert triggered isolation and global containment; he himself died of it."),
     "question": ("A severe atypical pneumonia is spreading rapidly among healthcare workers caring "
                  "for one index patient, not responding to usual treatment. What is the correct "
                  "clinical and public-health response?"),
     "reference": ("Treat it as a NOVEL transmissible respiratory pathogen: strict isolation and "
                   "airborne/contact infection control, protect and monitor exposed staff, and raise "
                   "an immediate public-health/global alert for containment and contact tracing — "
                   "supportive care for cases. Early recognition and reporting is the decisive act.")},
    {"id": "covid-index-2019", "cluster": "emerging_infections", "era": "recent", "year": 2019,
     "title": "COVID-19 — the first cluster of a novel coronavirus (2019)",
     "case": ("Wuhan, December 2019. A cluster of severe pneumonia of unknown cause was linked to a "
              "market; a novel coronavirus (SARS-CoV-2) was identified. It became a global pandemic."),
     "question": ("A geographic cluster of severe viral pneumonia of unknown cause emerges, with "
                  "evidence of person-to-person spread. What are the correct early clinical and "
                  "public-health decisions?"),
     "reference": ("Recognise a novel transmissible respiratory pathogen early: isolate cases and "
                   "trace contacts, protect healthcare workers (PPE), give supportive care with "
                   "attention to hypoxaemic respiratory failure / ARDS, and mount public-health "
                   "containment. Sequence and share the pathogen to enable diagnostics, vaccines and "
                   "treatment.")},
    {"id": "ebola-1976-2014", "cluster": "emerging_infections", "era": "recent", "year": 2014,
     "title": "Ebola virus disease — barrier care for a viral haemorrhagic fever (1976/2014)",
     "case": ("First identified near the Ebola River in 1976; the 2014-16 West African outbreak was "
              "the largest, with high mortality and healthcare-worker deaths from a highly lethal "
              "viral haemorrhagic fever spread by contact with body fluids."),
     "question": ("Patients present with a severe febrile illness progressing to bleeding and shock, "
                  "with clustering among caregivers and after funerals, in an outbreak setting. What "
                  "is the correct management?"),
     "reference": ("Suspect a viral haemorrhagic fever: rigorous BARRIER isolation and PPE, meticulous "
                   "infection control (including safe burials), aggressive supportive care "
                   "(fluid/electrolyte and organ support), contact tracing, and treatment at a "
                   "designated unit. Protecting caregivers and interrupting body-fluid transmission "
                   "is decisive; monoclonal antibodies and a vaccine later improved outcomes.")},

    # ---- Targeted & immuno-oncology ----
    {"id": "imatinib-cml-2001", "cluster": "targeted_onco", "era": "recent", "year": 2001,
     "title": "Imatinib for chronic myeloid leukaemia — targeted therapy (2001)",
     "case": ("~1998-2001. Brian Druker and colleagues developed imatinib (STI571), a small molecule "
              "targeting the BCR-ABL tyrosine kinase that drives chronic myeloid leukaemia — "
              "converting a once-fatal leukaemia into a manageable chronic disease."),
     "question": ("A patient has chronic myeloid leukaemia driven by the BCR-ABL fusion (Philadelphia "
                  "chromosome). What class of therapy is correct, and why is it a paradigm shift?"),
     "reference": ("A BCR-ABL TYROSINE-KINASE INHIBITOR (imatinib and successors) — molecularly "
                   "targeted therapy against the specific oncogenic driver, monitored by BCR-ABL "
                   "transcript levels. It established targeted therapy: match the drug to the tumour's "
                   "driver rather than using non-specific cytotoxics.")},
    {"id": "trastuzumab-her2-1998", "cluster": "targeted_onco", "era": "recent", "year": 1998,
     "title": "Trastuzumab for HER2-positive breast cancer — test then target (1998)",
     "case": ("Dennis Slamon's work led to trastuzumab (Herceptin), an antibody against HER2, "
              "approved 1998 for HER2-overexpressing metastatic breast cancer — the first therapy "
              "chosen by a molecular biomarker in a common solid tumour."),
     "question": ("A patient has metastatic breast cancer. How should the biology of the tumour guide "
                  "therapy, and what is the correct decision if it overexpresses HER2?"),
     "reference": ("TEST HER2 status and, if overexpressed/amplified, add HER2-TARGETED therapy "
                   "(trastuzumab ± others) to chemotherapy. It established biomarker-driven treatment "
                   "selection — test the tumour, then target the driver — in solid oncology.")},
    {"id": "cart-emily-2012", "cluster": "targeted_onco", "era": "recent", "year": 2012,
     "title": "Emily Whitehead — the first paediatric CAR-T for refractory leukaemia (2012)",
     "case": ("2012. Emily Whitehead, a child with relapsed/refractory B-cell acute lymphoblastic "
              "leukaemia, became the first paediatric patient treated with CD19-directed CAR-T cells; "
              "she achieved a durable remission, surviving a severe cytokine release storm."),
     "question": ("A child with B-cell ALL has relapsed after chemotherapy and transplant, with no "
                  "remaining standard options. What frontier therapy is appropriate, and what acute "
                  "toxicity must be anticipated?"),
     "reference": ("CD19-directed CAR-T CELL therapy (engineered autologous T cells) can induce "
                   "remission in refractory B-ALL. Anticipate and treat CYTOKINE RELEASE SYNDROME — "
                   "high fever, hypotension — with supportive care and the IL-6 blocker tocilizumab "
                   "(and manage neurotoxicity). This opened the era of engineered cell therapy.")},
    {"id": "checkpoint-melanoma-2010", "cluster": "targeted_onco", "era": "recent", "year": 2011,
     "title": "Checkpoint blockade in metastatic melanoma — unleash the immune system (2011)",
     "case": ("Ipilimumab (anti-CTLA-4) was the first therapy to improve overall survival in "
              "metastatic melanoma (approved 2011), launching immune-checkpoint inhibition; anti-PD-1 "
              "agents soon followed with greater benefit."),
     "question": ("A patient has metastatic melanoma, historically resistant to chemotherapy. What "
                  "class of therapy improves survival, and what distinctive toxicities must be "
                  "watched for?"),
     "reference": ("IMMUNE-CHECKPOINT INHIBITION (anti-CTLA-4 and/or anti-PD-1) — release the brakes "
                   "on T cells against the tumour. Watch for and treat IMMUNE-RELATED ADVERSE EVENTS "
                   "(colitis, hepatitis, pneumonitis, endocrinopathies) with prompt corticosteroids/ "
                   "immunosuppression. It made durable responses possible in a previously fatal "
                   "disease.")},

    # ---- Reperfusion & time-critical intervention ----
    {"id": "angioplasty-gruntzig-1977", "cluster": "reperfusion", "era": "recent", "year": 1977,
     "title": "Andreas Grüntzig — the first coronary balloon angioplasty (1977)",
     "case": ("Zurich, 1977. Andreas Grüntzig performed the first percutaneous coronary balloon "
              "angioplasty on an awake patient, opening a narrowed coronary artery without surgery — "
              "founding interventional cardiology."),
     "question": ("A patient has a flow-limiting coronary artery stenosis causing ischaemia. Besides "
                  "medication and bypass surgery, what catheter-based option can restore flow?"),
     "reference": ("PERCUTANEOUS CORONARY INTERVENTION (balloon angioplasty, now with stents) — "
                   "catheter-based revascularisation of the stenosis. For acute ST-elevation MI, "
                   "primary PCI is the preferred, time-critical reperfusion strategy (shortest "
                   "door-to-balloon time).")},
    {"id": "tpa-stroke-ninds-1995", "cluster": "reperfusion", "era": "recent", "year": 1995,
     "title": "Thrombolysis for acute ischaemic stroke — the NINDS trial (1995)",
     "case": ("1995. The NINDS trial showed that IV tissue plasminogen activator (tPA) given within "
              "3 hours of ischaemic-stroke onset improved outcomes — establishing that 'time is "
              "brain' and acute stroke is treatable."),
     "question": ("A patient presents with acute focal neurological deficits (suspected ischaemic "
                  "stroke) within a few hours of onset. What is the correct time-critical pathway?"),
     "reference": ("Emergent NON-CONTRAST CT to exclude haemorrhage, then IV THROMBOLYSIS (tPA/"
                   "tenecteplase) for eligible patients within the time window — the faster the "
                   "better ('time is brain'). For large-vessel occlusion, add mechanical "
                   "THROMBECTOMY (benefit out to 24 h with imaging selection). Do not delay.")},

    # ---- Patient safety & human factors ----
    {"id": "bromiley-2005", "cluster": "human_factors", "era": "recent", "year": 2005,
     "title": "Elaine Bromiley — 'can't intubate, can't oxygenate' and human factors (2005)",
     "case": ("2005, UK. During routine anaesthesia for elective surgery, Elaine Bromiley could not "
              "be intubated or oxygenated; experienced clinicians became fixated on repeated "
              "intubation attempts and never declared the emergency or secured a surgical airway. "
              "She died of hypoxic brain injury. Her husband, an airline pilot, drove human-factors "
              "reform in medicine."),
     "question": ("Under anaesthesia a patient cannot be intubated AND cannot be oxygenated by mask, "
                  "and repeated intubation attempts are failing while oxygen saturation falls. What "
                  "is the correct decision, and what human-factors trap must be avoided?"),
     "reference": ("Declare a 'CAN'T INTUBATE, CAN'T OXYGENATE' emergency and follow the failed-airway "
                   "drill — limit intubation attempts and move to FRONT-OF-NECK ACCESS (surgical/"
                   "cricothyroidotomy) to restore oxygenation. Avoid the fixation-error trap: someone "
                   "must step back, name the emergency, and escalate; team communication and "
                   "checklists are decisive.")},
    {"id": "josie-king-2001", "cluster": "human_factors", "era": "recent", "year": 2001,
     "title": "Josie King — listen to the family, escalate, prevent error (2001)",
     "case": ("2001, Johns Hopkins. Josie King, 18 months old and recovering from burns, deteriorated "
              "from dehydration and a subsequent narcotic error; her mother's repeated concerns were "
              "not acted on. She died. The case catalysed rapid-response systems and family-activated "
              "escalation."),
     "question": ("A recovering paediatric inpatient is deteriorating, and the parent repeatedly "
                  "raises concerns that the child is 'not right' and thirsty, but the team is "
                  "reassured. What are the correct decisions?"),
     "reference": ("TAKE THE FAMILY'S CONCERN SERIOUSLY and reassess: correct dehydration, and use "
                   "RAPID-RESPONSE / escalation pathways (including family-activated escalation) "
                   "rather than false reassurance. Enforce MEDICATION SAFETY (independent checks for "
                   "opioids). Systems that empower escalation and heed families prevent these deaths.")},

    # ---- Transplant, gene & reproductive frontiers ----
    {"id": "gene-therapy-desilva-1990", "cluster": "frontier_recent", "era": "recent", "year": 1990,
     "title": "Ashanti DeSilva — the first approved human gene therapy (1990)",
     "case": ("1990. Ashanti DeSilva, a girl with ADA-deficiency severe combined immunodeficiency "
              "(ADA-SCID), received the first federally approved human gene therapy — her own T cells "
              "engineered to carry a functional ADA gene."),
     "question": ("A child has a monogenic severe combined immunodeficiency (ADA deficiency). Beyond "
                  "enzyme replacement and transplant, what disease-modifying approach targets the "
                  "root cause?"),
     "reference": ("GENE THERAPY — deliver a functional copy of the defective gene (ex vivo into the "
                   "patient's own haematopoietic/T cells) to correct the enzyme deficiency at its "
                   "source. It proved the concept of correcting a monogenic disease genetically; HLA-"
                   "matched stem-cell transplant and enzyme replacement remain alternatives.")},
    {"id": "gelsinger-1999", "cluster": "frontier_recent", "era": "recent", "year": 1999,
     "title": "Jesse Gelsinger — eligibility and consent in a research death (1999)",
     "case": ("1999. Jesse Gelsinger, 18, with a partial ornithine transcarbamylase (OTC) deficiency, "
              "died of a fatal immune reaction to the viral vector in a gene-therapy trial. His "
              "baseline metabolic derangement arguably should have excluded him; the death forced "
              "reform of human-research oversight and conflict-of-interest rules."),
     "question": ("A young adult with a partly-controlled metabolic disorder is a candidate for an "
                  "early-phase experimental therapy, but his baseline labs are borderline against the "
                  "protocol's safety criteria. What is the correct decision?"),
     "reference": ("Apply the ELIGIBILITY / EXCLUSION criteria strictly and obtain genuine INFORMED "
                   "CONSENT free of conflicts of interest — do not enrol a patient whose baseline "
                   "makes the experimental risk unacceptable. Patient safety and honest disclosure of "
                   "risk override enthusiasm to proceed; this case reshaped research ethics oversight.")},
    {"id": "ivf-louise-brown-1978", "cluster": "frontier_recent", "era": "recent", "year": 1978,
     "title": "Louise Brown — the first baby born by IVF (1978)",
     "case": ("1978, UK. Patrick Steptoe and Robert Edwards achieved the first live birth from in "
              "vitro fertilisation — Louise Brown — for a couple with tubal-factor infertility, "
              "opening assisted reproduction to millions."),
     "question": ("A couple cannot conceive because of blocked/absent fallopian tubes (tubal-factor "
                  "infertility). What definitive option can achieve pregnancy?"),
     "reference": ("IN VITRO FERTILISATION (IVF): retrieve oocytes, fertilise outside the body, and "
                   "transfer an embryo to the uterus — bypassing the tubal blockage. It established "
                   "assisted reproductive technology as the treatment for tubal-factor (and many "
                   "other causes of) infertility.")},

    # ---- Critical care & ventilation ----
    {"id": "ardsnet-2000", "cluster": "critical_care", "era": "recent", "year": 2000,
     "title": "ARDSNet — lung-protective ventilation saves lives (2000)",
     "case": ("2000. The ARDS Network trial showed that ventilating ARDS patients with LOW tidal "
              "volumes (~6 mL/kg predicted body weight) and limited plateau pressures reduced "
              "mortality compared with traditional larger tidal volumes — a landmark in critical "
              "care."),
     "question": ("A patient with acute respiratory distress syndrome (ARDS) needs mechanical "
                  "ventilation. How should the ventilator be set to improve survival?"),
     "reference": ("LUNG-PROTECTIVE VENTILATION: low tidal volume (~6 mL/kg predicted body weight), "
                   "plateau pressure ≤ ~30 cmH₂O, appropriate PEEP, tolerating permissive "
                   "hypercapnia. Larger tidal volumes cause ventilator-induced lung injury; prone "
                   "positioning further reduces mortality in severe ARDS.")},

    # ============================ RECENT ERA (1975-2025), tranche 2 ============================
    # ---- Turning fatal or chronic disease treatable ----
    {"id": "hiv-haart-1996", "cluster": "chronic_cure", "era": "recent", "year": 1996,
     "title": "Combination antiretroviral therapy for HIV (1996)",
     "case": ("1996. The advent of combination ('triple') antiretroviral therapy (HAART) — typically "
              "two nucleoside analogues plus a protease inhibitor — collapsed HIV viral loads and "
              "transformed AIDS from a near-uniformly fatal disease into a manageable chronic "
              "condition."),
     "question": ("A patient with HIV needs treatment to prevent progression to AIDS. Why is "
                  "single-drug therapy the wrong approach, and what is correct?"),
     "reference": ("COMBINATION antiretroviral therapy (≥3 active agents) to suppress viral load below "
                   "detection — monotherapy rapidly selects resistance and fails. Start ART for "
                   "essentially all people with HIV, monitor viral load/CD4, and support adherence; "
                   "sustained suppression restores immunity and prevents transmission (U=U).")},
    {"id": "hiv-prep-iprex-2010", "cluster": "chronic_cure", "era": "recent", "year": 2010,
     "title": "Pre-exposure prophylaxis for HIV — iPrEx (2010)",
     "case": ("2010. The iPrEx trial showed that a daily oral antiretroviral (tenofovir/"
              "emtricitabine) taken by HIV-negative people at substantial risk markedly reduced HIV "
              "acquisition — establishing pre-exposure prophylaxis (PrEP)."),
     "question": ("An HIV-negative person at substantial ongoing risk of HIV asks how to protect "
                  "themselves beyond condoms. What biomedical prevention is correct?"),
     "reference": ("Offer PRE-EXPOSURE PROPHYLAXIS (PrEP) — daily oral tenofovir-based therapy (or a "
                   "long-acting injectable) — to HIV-negative people at substantial risk, with "
                   "baseline/periodic HIV and renal testing and adherence support. Efficacy tracks "
                   "adherence; combine with STI screening and risk-reduction counselling.")},
    {"id": "hcv-daa-2013", "cluster": "chronic_cure", "era": "recent", "year": 2013,
     "title": "Direct-acting antivirals cure hepatitis C (2013)",
     "case": ("2013 onward. Oral direct-acting antivirals (starting with sofosbuvir) replaced "
              "interferon and achieved cure (sustained virologic response) in over 95% of patients "
              "with chronic hepatitis C, in 8-12 weeks with few side effects."),
     "question": ("A patient has chronic hepatitis C infection. What is the correct modern treatment, "
                  "and what outcome is achievable?"),
     "reference": ("A short oral course of DIRECT-ACTING ANTIVIRALS (interferon-free) achieves CURE "
                   "(SVR) in >95% — treat essentially all chronic HCV. Choose the regimen by genotype/"
                   "resistance and cirrhosis status, confirm cure at 12 weeks post-treatment, and "
                   "still surveil for hepatocellular carcinoma in those with cirrhosis.")},
    {"id": "berlin-patient-2008", "cluster": "chronic_cure", "era": "recent", "year": 2008,
     "title": "The Berlin Patient — the first HIV cure (2008)",
     "case": ("Timothy Ray Brown, HIV-positive, developed acute leukaemia and received an allogeneic "
              "stem-cell transplant from a donor homozygous for the CCR5-Δ32 mutation (which blocks "
              "HIV entry). He remained free of HIV without antiretrovirals — the first documented "
              "cure of HIV."),
     "question": ("Is a true cure of HIV (not just viral suppression) biologically possible, and what "
                  "did the first cured patient demonstrate about the mechanism?"),
     "reference": ("Yes — the Berlin Patient proved cure is possible: replacing the immune system with "
                   "CCR5-Δ32 donor cells removed HIV's entry co-receptor, eliminating the reservoir. "
                   "This is a proof-of-concept (transplant is far too toxic for routine use), and it "
                   "focused cure research on CCR5 and reservoir elimination — routine care remains "
                   "lifelong ART.")},

    # ---- Neuromodulation & sensory restoration ----
    {"id": "dbs-parkinsons-1990s", "cluster": "neuromodulation", "era": "recent", "year": 1993,
     "title": "Deep brain stimulation for Parkinson's disease (1990s)",
     "case": ("Alim-Louis Benabid and colleagues showed that high-frequency electrical stimulation of "
              "deep brain targets (subthalamic nucleus / globus pallidus) via implanted electrodes "
              "reversibly relieves the motor symptoms of advanced Parkinson's disease."),
     "question": ("A patient with advanced Parkinson's disease has disabling motor fluctuations and "
                  "dyskinesias despite optimised medication. What intervention can help, and who is a "
                  "candidate?"),
     "reference": ("DEEP BRAIN STIMULATION (typically of the subthalamic nucleus) for appropriately "
                   "selected patients — good levodopa responsiveness, refractory motor fluctuations/"
                   "tremor, without significant dementia or unstable psychiatric disease. It is "
                   "adjustable and reversible, reducing off-time and dyskinesia; not a cure and it "
                   "does not halt progression.")},
    {"id": "cochlear-implant", "cluster": "neuromodulation", "era": "recent", "year": 1984,
     "title": "The cochlear implant for profound deafness",
     "case": ("Multichannel cochlear implants (approved for adults in the 1980s, children from 1990) "
              "restore functional hearing by directly stimulating the auditory nerve, bypassing "
              "non-functioning hair cells — the first device to substantially restore a human sense."),
     "question": ("A patient with profound bilateral sensorineural hearing loss gets no useful benefit "
                  "from hearing aids. What is the correct option, and why do hearing aids fail here?"),
     "reference": ("A COCHLEAR IMPLANT — it bypasses the damaged cochlear hair cells and directly "
                   "stimulates the auditory nerve, whereas hearing aids only amplify sound that "
                   "non-functioning hair cells still cannot transduce. Early implantation (especially "
                   "in children, within the critical period) plus auditory rehabilitation gives the "
                   "best speech outcomes.")},

    # ---- Perinatal & neonatal ----
    {"id": "surfactant-rds-1980", "cluster": "perinatal", "era": "recent", "year": 1980,
     "title": "Surfactant replacement for neonatal respiratory distress syndrome (1980)",
     "case": ("1980. Tetsuro Fujiwara reported that instilling exogenous surfactant into the lungs of "
              "premature infants with respiratory distress syndrome (hyaline membrane disease, caused "
              "by surfactant deficiency) rapidly improved oxygenation — transforming neonatal "
              "survival."),
     "question": ("A premature newborn has respiratory distress syndrome from surfactant deficiency, "
                  "with stiff lungs and hypoxaemia. What is the specific corrective treatment?"),
     "reference": ("EXOGENOUS SURFACTANT REPLACEMENT (intratracheal) plus respiratory support (CPAP/"
                   "gentle ventilation, oxygen) — it directly replaces the missing surfactant that "
                   "keeps alveoli open. Combine with antenatal steroids (given to the mother "
                   "beforehand) and lung-protective, minimally invasive respiratory support.")},
    {"id": "antenatal-steroids-1972", "cluster": "perinatal", "era": "recent", "year": 1972,
     "title": "Antenatal corticosteroids for threatened preterm birth (1972)",
     "case": ("1972. Liggins and Howie showed that giving corticosteroids to mothers before preterm "
              "delivery accelerates fetal lung maturation and dramatically reduces neonatal "
              "respiratory distress syndrome and death."),
     "question": ("A pregnant woman is in threatened preterm labour at, say, 30 weeks. What "
                  "intervention given to the MOTHER improves the newborn's outcome, and why?"),
     "reference": ("A course of ANTENATAL CORTICOSTEROIDS (betamethasone or dexamethasone) to the "
                   "mother — it matures the fetal lungs (surfactant production), cutting neonatal RDS, "
                   "intraventricular haemorrhage and death. Give when preterm birth is anticipated in "
                   "the recommended gestational window; a decisive, low-cost intervention.")},

    # ---- Minimally invasive & endovascular surgery ----
    {"id": "lap-chole-1987", "cluster": "minimally_invasive", "era": "recent", "year": 1987,
     "title": "Laparoscopic cholecystectomy — the minimally invasive revolution (1987)",
     "case": ("1985-1987 (Mühe, then Mouret). Removing the gallbladder through small ports with a "
              "laparoscope, rather than a large open incision, cut pain, hospital stay and recovery "
              "time — and launched minimally invasive surgery across specialties."),
     "question": ("A patient needs cholecystectomy for symptomatic gallstones. What approach is "
                  "preferred over open surgery, and what is the main intra-operative safety concern?"),
     "reference": ("LAPAROSCOPIC (minimally invasive) cholecystectomy is the standard of care — less "
                   "pain, faster recovery. The key safety principle is achieving the CRITICAL VIEW OF "
                   "SAFETY to avoid bile-duct injury, and converting to open surgery when anatomy is "
                   "unclear. It generalised minimally invasive surgery broadly.")},
    {"id": "evar-parodi-1991", "cluster": "minimally_invasive", "era": "recent", "year": 1991,
     "title": "Endovascular aneurysm repair (EVAR) for aortic aneurysm (1991)",
     "case": ("1991. Juan Parodi placed the first endovascular stent-graft to exclude an abdominal "
              "aortic aneurysm from within the vessel, via the femoral arteries — avoiding a major "
              "open operation in suitable patients."),
     "question": ("A patient has an abdominal aortic aneurysm meeting size threshold for repair but is "
                  "high-risk for open surgery. What less-invasive option exists, and what is its "
                  "trade-off?"),
     "reference": ("ENDOVASCULAR ANEURYSM REPAIR (EVAR) — a catheter-delivered stent-graft excludes "
                   "the aneurysm, with lower peri-operative mortality and faster recovery than open "
                   "repair. Trade-off: it requires suitable anatomy and lifelong imaging "
                   "SURVEILLANCE for endoleak/re-intervention; open repair is more durable. Choose by "
                   "anatomy, risk and life expectancy.")},

    # ---- Prevention, screening & genomic risk ----
    {"id": "statins-4s-1994", "cluster": "prevention_screening", "era": "recent", "year": 1994,
     "title": "Statins for cardiovascular prevention — the 4S trial (1994)",
     "case": ("1994. The Scandinavian Simvastatin Survival Study (4S) showed that lowering cholesterol "
              "with a statin reduced death and cardiovascular events in patients with coronary heart "
              "disease — proving that treating cholesterol saves lives."),
     "question": ("A patient with established coronary heart disease and elevated cholesterol needs "
                  "long-term risk reduction. What therapy reduces mortality, and how is intensity "
                  "chosen?"),
     "reference": ("A STATIN (high-intensity for established ASCVD) to lower LDL cholesterol reduces "
                   "mortality and recurrent events — the foundation of secondary prevention, alongside "
                   "antiplatelet therapy, blood-pressure control and lifestyle. For primary "
                   "prevention, base the decision on estimated cardiovascular risk, not the lipid "
                   "level alone.")},
    {"id": "icd-madit-1996", "cluster": "prevention_screening", "era": "recent", "year": 1996,
     "title": "Implantable defibrillator for sudden-death prevention — MADIT (1996)",
     "case": ("1996. The MADIT trial showed that an implantable cardioverter-defibrillator (ICD) "
              "reduced mortality in high-risk patients with prior myocardial infarction and low "
              "ejection fraction — establishing device prevention of sudden cardiac death."),
     "question": ("A patient with a prior myocardial infarction and a severely reduced ejection "
                  "fraction is at risk of sudden cardiac death from ventricular arrhythmia. What "
                  "intervention reduces mortality?"),
     "reference": ("An IMPLANTABLE CARDIOVERTER-DEFIBRILLATOR (ICD) for primary prevention in eligible "
                   "patients (e.g. LVEF ≤35% despite optimal therapy, adequate life expectancy) — it "
                   "terminates lethal ventricular arrhythmias. Ensure guideline-directed medical "
                   "therapy first and appropriate waiting periods after MI/revascularisation.")},
    {"id": "hpv-vaccine-2006", "cluster": "prevention_screening", "era": "recent", "year": 2006,
     "title": "HPV vaccination to prevent cancer (2006)",
     "case": ("Harald zur Hausen established that human papillomavirus causes cervical cancer; the "
              "first HPV vaccine was approved in 2006. Vaccinating before exposure prevents the "
              "infections that cause cervical and other HPV-driven cancers."),
     "question": ("How can HPV-driven cancers (cervical and others) be prevented at the population "
                  "level, and when is the intervention most effective?"),
     "reference": ("HPV VACCINATION of adolescents (ideally before sexual debut, routinely ~ages "
                   "9-12, with catch-up) prevents the oncogenic HPV infections that cause cervical, "
                   "anal, and oropharyngeal cancers — primary cancer prevention by vaccine. It "
                   "complements, not replaces, cervical SCREENING.")},
    {"id": "brca-risk-1994", "cluster": "prevention_screening", "era": "recent", "year": 1994,
     "title": "BRCA1/2 and risk-reducing management of hereditary cancer (1994)",
     "case": ("1994-95. Cloning of the BRCA1 and BRCA2 genes made it possible to identify people with "
              "a very high inherited risk of breast and ovarian cancer — enabling genetic testing and "
              "risk-reducing decisions."),
     "question": ("A woman has a strong family history of early breast and ovarian cancer and tests "
                  "positive for a pathogenic BRCA1 mutation. How should her markedly elevated risk be "
                  "managed?"),
     "reference": ("Manage the high inherited risk with an individualised plan: enhanced SURVEILLANCE "
                   "(e.g. breast MRI + mammography), consideration of RISK-REDUCING surgery "
                   "(mastectomy; and salpingo-oophorectomy, which also lowers mortality) at "
                   "appropriate ages, chemoprevention options, and CASCADE genetic testing/counselling "
                   "of relatives. Shared decision-making is central.")},

    # ---- Critical care & ventilation (existing cluster) ----
    {"id": "hypothermia-haca-2002", "cluster": "critical_care", "era": "recent", "year": 2002,
     "title": "Therapeutic hypothermia after cardiac arrest (2002)",
     "case": ("2002. Two trials (HACA and Bernard) showed that cooling comatose survivors of "
              "out-of-hospital ventricular-fibrillation cardiac arrest improved neurological outcome "
              "and survival — establishing targeted temperature management."),
     "question": ("A patient is resuscitated from an out-of-hospital cardiac arrest but remains "
                  "comatose after return of spontaneous circulation. What intervention improves "
                  "neurological outcome?"),
     "reference": ("TARGETED TEMPERATURE MANAGEMENT — controlled cooling (avoiding fever) of comatose "
                   "post-arrest patients — as part of a bundled post-resuscitation care package "
                   "(treat the cause, e.g. urgent coronary angiography for a cardiac cause; maintain "
                   "oxygenation/perfusion; delay firm neuro-prognostication). It protects the brain "
                   "after global ischaemia.")},
    {"id": "sepsis-egdt-rivers-2001", "cluster": "critical_care", "era": "recent", "year": 2001,
     "title": "Early recognition and resuscitation of sepsis — Rivers (2001)",
     "case": ("2001. Emanuel Rivers' early goal-directed therapy trial showed that recognising severe "
              "sepsis/septic shock early and resuscitating aggressively in the first hours improved "
              "survival — catalysing the sepsis-bundle era (later refined by the Surviving Sepsis "
              "Campaign)."),
     "question": ("A patient presents with infection plus hypotension and a raised lactate (septic "
                  "shock). What are the correct decisions in the first hour(s)?"),
     "reference": ("Recognise sepsis EARLY and act fast: obtain cultures/lactate, give broad-spectrum "
                   "ANTIBIOTICS within the first hour, and RESUSCITATE with IV fluids (≈30 mL/kg) then "
                   "reassess, adding norepinephrine for persistent hypotension (target MAP ≥65) — plus "
                   "source control. The decisive lesson is timeliness; later evidence de-emphasised "
                   "rigid protocolised targets in favour of the early bundle.")},

    # ---- Transplant frontiers (existing cluster) ----
    {"id": "ciclosporin-1983", "cluster": "frontier_recent", "era": "recent", "year": 1983,
     "title": "Ciclosporin — immunosuppression that made transplantation routine (1983)",
     "case": ("Roy Calne and others introduced ciclosporin (approved 1983), a calcineurin inhibitor "
              "that selectively suppressed graft rejection — turning organ transplantation from a "
              "rare, high-mortality gamble (as in the Herrick identical-twin era) into routine "
              "therapy across organs from non-identical donors."),
     "question": ("After a solid-organ transplant from a non-identical donor, the recipient's immune "
                  "system will reject the graft. What made routine transplantation possible, and what "
                  "must be balanced?"),
     "reference": ("Ongoing IMMUNOSUPPRESSION — a calcineurin inhibitor (ciclosporin/tacrolimus)-based "
                   "regimen — prevents rejection and made non-identical-donor transplantation routine. "
                   "It must be BALANCED against its costs: infection, malignancy, nephrotoxicity, and "
                   "drug interactions/levels — lifelong monitoring and prophylaxis. Overcoming "
                   "rejection is the problem the Herrick twin case first framed.")},
    {"id": "lung-transplant-1983", "cluster": "frontier_recent", "era": "recent", "year": 1983,
     "title": "The first successful lung transplant (1983)",
     "case": ("1983. Joel Cooper performed the first single-lung transplant with long-term survival, "
              "made feasible by better immunosuppression and surgical technique — extending "
              "transplantation to end-stage lung disease."),
     "question": ("A patient has end-stage lung disease (e.g. pulmonary fibrosis) refractory to "
                  "medical therapy, with a poor prognosis. What definitive option exists, and what "
                  "gates it?"),
     "reference": ("LUNG TRANSPLANTATION is the definitive option for selected end-stage lung disease. "
                   "It is gated by candidacy (severity/prognosis, absence of prohibitive comorbidity), "
                   "donor availability, and the lifelong burden of immunosuppression and chronic "
                   "rejection (bronchiolitis obliterans). Referral and evaluation should be timely, "
                   "before the patient is too ill.")},

    # ---- Targeted oncology (existing cluster) ----
    {"id": "atra-apl-1988", "cluster": "targeted_onco", "era": "recent", "year": 1988,
     "title": "ATRA turns acute promyelocytic leukaemia curable (1988)",
     "case": ("1988 (Shanghai; Wang Zhen-yi and colleagues). All-trans retinoic acid (ATRA) was shown "
              "to induce the malignant promyelocytes of acute promyelocytic leukaemia (APL) to mature "
              "rather than be killed — a differentiation therapy that, with arsenic trioxide, made "
              "this once rapidly-fatal leukaemia highly curable, largely without chemotherapy."),
     "question": ("A patient has acute promyelocytic leukaemia (APL, with the PML-RARA fusion), which "
                  "presents with dangerous coagulopathy. What is the correct, distinctive treatment "
                  "approach?"),
     "reference": ("Start ALL-TRANS RETINOIC ACID (ATRA) urgently — even before genetic confirmation — "
                   "combined with ARSENIC TRIOXIDE (± anthracycline in high-risk): differentiation "
                   "therapy targeting PML-RARA, not standard cytotoxic chemotherapy. Aggressively "
                   "manage the coagulopathy/DIC and watch for differentiation (ATRA) syndrome. APL is "
                   "now among the most curable acute leukaemias.")},
    {"id": "rituximab-lymphoma-1997", "cluster": "targeted_onco", "era": "recent", "year": 1997,
     "title": "Rituximab — the first therapeutic monoclonal antibody in cancer (1997)",
     "case": ("1997. Rituximab, a monoclonal antibody against CD20 on B cells, became the first "
              "therapeutic anticancer antibody — added to chemotherapy (R-CHOP), it substantially "
              "improved survival in CD20-positive B-cell lymphomas."),
     "question": ("A patient has a CD20-positive B-cell non-Hodgkin lymphoma. How should targeted "
                  "biology be added to chemotherapy, and what pre-treatment risk must be checked?"),
     "reference": ("Add the anti-CD20 monoclonal antibody RITUXIMAB to chemotherapy (e.g. R-CHOP) — "
                   "immunochemotherapy improves response and survival in CD20+ B-cell lymphoma. Screen "
                   "for HEPATITIS B before treatment (risk of reactivation) and give prophylaxis if "
                   "positive; watch for infusion reactions. It opened the era of therapeutic antibodies "
                   "in oncology.")},

    # ============================ RECENT ERA (1975-2025), tranche 3 ============================
    # ---- Vaccines, eradication & global health ----
    {"id": "smallpox-eradication-1980", "cluster": "global_health", "era": "recent", "year": 1980,
     "title": "Smallpox eradication — the first disease eliminated (1980)",
     "case": ("1980. WHO certified the global eradication of smallpox after a campaign of surveillance "
              "and ring vaccination; the last natural case was in 1977. It remains the only human "
              "disease ever eradicated."),
     "question": ("A highly contagious, often-fatal viral disease has an effective vaccine and no "
                  "animal reservoir, yet still causes outbreaks. What strategy can eliminate it "
                  "entirely?"),
     "reference": ("Global ERADICATION by SURVEILLANCE and RING VACCINATION (containment): find every "
                   "case, isolate it, and vaccinate contacts and their contacts to break chains of "
                   "transmission — feasible here because of an effective vaccine, no animal reservoir, "
                   "and a recognisable disease. Mass blanket vaccination alone is less efficient than "
                   "targeted surveillance-containment.")},
    {"id": "polio-eradication-1988", "cluster": "global_health", "era": "recent", "year": 1988,
     "title": "Polio — the eradication endgame (1988→)",
     "case": ("Launched in 1988, the Global Polio Eradication Initiative cut wild poliovirus cases by "
              "over 99% through mass vaccination and surveillance; wild types 2 and 3 are certified "
              "eradicated, with type 1 confined to a few areas."),
     "question": ("A vaccine-preventable paralytic virus persists in a few regions. What is the "
                  "correct strategy to finish eliminating it, and what nuance complicates the "
                  "endgame?"),
     "reference": ("Sustained mass VACCINATION (oral and inactivated) with intensive acute-flaccid-"
                   "paralysis SURVEILLANCE and rapid outbreak response. Endgame nuance: the live oral "
                   "vaccine can rarely seed vaccine-derived poliovirus, so as wild virus disappears "
                   "the strategy shifts toward inactivated and novel oral vaccines — the last mile is "
                   "the hardest.")},
    {"id": "malaria-vaccine-rtss-2021", "cluster": "global_health", "era": "recent", "year": 2021,
     "title": "The first malaria vaccine — RTS,S (2021)",
     "case": ("2021. After large pilot programmes, WHO recommended RTS,S/AS01 (the first vaccine "
              "against a human parasite) for children in areas of moderate-to-high malaria "
              "transmission; the R21 vaccine followed."),
     "question": ("Malaria still kills hundreds of thousands of children a year despite bed nets and "
                  "drugs. What new tool adds protection, and how should it be positioned?"),
     "reference": ("Add the MALARIA VACCINE (RTS,S/AS01 or R21) for children in moderate-to-high "
                   "transmission settings, LAYERED WITH existing measures — insecticide-treated nets, "
                   "seasonal chemoprevention, and prompt diagnosis and treatment. It is only partially "
                   "protective, so it COMPLEMENTS rather than replaces vector control and case "
                   "management.")},

    # ---- Structural / endovascular & lipid (existing clusters) ----
    {"id": "tavr-aortic-stenosis-2011", "cluster": "minimally_invasive", "era": "recent", "year": 2011,
     "title": "TAVR for severe aortic stenosis — PARTNER (2011)",
     "case": ("2011. The PARTNER trial showed transcatheter aortic valve replacement (TAVR) — "
              "implanting a valve via catheter — helped patients with severe symptomatic aortic "
              "stenosis who were inoperable or high-risk; it was later extended to lower-risk "
              "patients."),
     "question": ("A patient has severe symptomatic aortic stenosis but is high-risk or inoperable for "
                  "open surgical valve replacement. What option can relieve the obstruction?"),
     "reference": ("TRANSCATHETER AORTIC VALVE REPLACEMENT (TAVR/TAVI) — a catheter-delivered "
                   "prosthetic valve — for inoperable/high-risk (and now selected lower-risk) "
                   "patients, chosen by a HEART TEAM weighing anatomy, surgical risk and life "
                   "expectancy versus surgical AVR. Severe symptomatic AS has a poor prognosis "
                   "untreated, so intervene once symptomatic.")},
    {"id": "thrombectomy-stroke-2015", "cluster": "reperfusion", "era": "recent", "year": 2015,
     "title": "Endovascular thrombectomy for large-vessel-occlusion stroke (2015)",
     "case": ("2015. A series of trials (MR CLEAN and others) proved that mechanical thrombectomy — "
              "catheter clot removal — dramatically improved outcomes in acute ischaemic stroke from "
              "large-vessel occlusion, beyond IV thrombolysis alone."),
     "question": ("A patient has an acute ischaemic stroke from a large-vessel occlusion, which IV "
                  "thrombolysis alone often fails to reopen. What intervention improves outcome, and "
                  "in what window?"),
     "reference": ("ENDOVASCULAR THROMBECTOMY for large-vessel occlusion — mechanical clot retrieval — "
                   "added to IV thrombolysis when eligible. It benefits within ~6 hours, and out to "
                   "24 hours in patients selected by perfusion/core imaging (DAWN/DEFUSE-3). Organised "
                   "stroke systems and speed are decisive — 'time is brain'.")},
    {"id": "pcsk9-inhibitors-2017", "cluster": "prevention_screening", "era": "recent", "year": 2017,
     "title": "PCSK9 inhibitors — driving LDL lower still (2017)",
     "case": ("PCSK9-inhibitor antibodies (evolocumab, alirocumab) lower LDL cholesterol far below "
              "statin levels; the FOURIER trial (2017) showed added cardiovascular event reduction in "
              "high-risk patients already on statins."),
     "question": ("A very-high-risk patient with atherosclerotic disease still has elevated LDL "
                  "cholesterol despite a maximally tolerated statin (± ezetimibe). What is the next "
                  "step?"),
     "reference": ("Add a PCSK9 INHIBITOR (evolocumab/alirocumab, or the siRNA inclisiran) to further "
                   "lower LDL and reduce events in high-risk patients not at goal on statin ± "
                   "ezetimibe. It reinforced 'lower LDL is better' for very-high-risk secondary "
                   "prevention; weigh cost/access.")},

    # ---- Targeted & immuno-oncology (existing cluster) ----
    {"id": "anti-pd1-lung-2015", "cluster": "targeted_onco", "era": "recent", "year": 2015,
     "title": "Immunotherapy in lung cancer — anti-PD-1 (2015)",
     "case": ("~2015. Anti-PD-1 checkpoint inhibitors (nivolumab, pembrolizumab) improved survival in "
              "advanced non-small-cell lung cancer; pembrolizumab became first-line for high-PD-L1 "
              "tumours — immunotherapy in the leading cause of cancer death."),
     "question": ("A patient has advanced non-small-cell lung cancer without a targetable driver "
                  "mutation. Beyond chemotherapy, what improves survival, and what biomarker guides "
                  "it?"),
     "reference": ("IMMUNE CHECKPOINT INHIBITION (anti-PD-1/PD-L1, e.g. pembrolizumab) — as "
                   "monotherapy for high PD-L1 expression or combined with chemotherapy otherwise. "
                   "First EXCLUDE a targetable driver (EGFR/ALK/etc., which redirects to targeted "
                   "therapy) and TEST PD-L1; watch for immune-related adverse events.")},
    {"id": "braf-melanoma-2011", "cluster": "targeted_onco", "era": "recent", "year": 2011,
     "title": "BRAF-targeted therapy for melanoma — match the mutation (2011)",
     "case": ("2011. Vemurafenib targeted the BRAF V600E mutation in metastatic melanoma with rapid "
              "responses; adding a MEK inhibitor improved durability — precision therapy matched to a "
              "tumour mutation."),
     "question": ("A patient has metastatic melanoma harbouring a BRAF V600E mutation. What targeted "
                  "approach is correct, and why combine two drugs?"),
     "reference": ("BRAF-TARGETED therapy — a BRAF inhibitor COMBINED WITH a MEK inhibitor (e.g. "
                   "dabrafenib+trametinib) for BRAF V600-mutant melanoma; the combination delays "
                   "resistance and reduces paradoxical toxicity versus a BRAF inhibitor alone. TEST "
                   "for the BRAF mutation to select therapy — immunotherapy is the complementary/"
                   "alternative path.")},
    {"id": "mrd-leukemia-guided", "cluster": "targeted_onco", "era": "recent", "year": 2010,
     "title": "Measurable residual disease — guiding leukaemia therapy",
     "case": ("Sensitive detection of measurable (minimal) residual disease (MRD) — by "
              "multiparameter flow cytometry, PCR or next-generation sequencing — became a routine "
              "way to quantify leukaemia below the microscope and predict relapse, reshaping how "
              "acute leukaemias are treated."),
     "question": ("After inducing a morphologic remission in acute leukaemia, how can you tell who is "
                  "likely to relapse and tailor further therapy beyond what the microscope shows?"),
     "reference": ("Measure MEASURABLE RESIDUAL DISEASE (MRD) with sensitive methods (flow cytometry, "
                   "PCR, NGS): MRD status after therapy is a powerful prognostic marker used to "
                   "INTENSIFY or de-escalate treatment, decide on stem-cell transplant, and monitor "
                   "for relapse — individualising therapy beyond morphologic remission.")},

    # ---- Gene & cell therapy frontiers (existing cluster) ----
    {"id": "zolgensma-sma-2019", "cluster": "frontier_recent", "era": "recent", "year": 2019,
     "title": "Gene therapy for spinal muscular atrophy — treat before symptoms (2019)",
     "case": ("2019. Onasemnogene abeparvovec (Zolgensma), a one-time gene-replacement therapy "
              "delivering a functional SMN1 gene, transformed spinal muscular atrophy — a leading "
              "genetic cause of infant death — especially when given before symptoms via newborn "
              "screening."),
     "question": ("An infant is diagnosed (ideally by newborn screening) with spinal muscular atrophy "
                  "type 1 from SMN1 loss. What disease-modifying options exist, and why is timing "
                  "critical?"),
     "reference": ("Disease-modifying therapy — one-time GENE REPLACEMENT (onasemnogene) or SMN-"
                   "augmenting drugs (nusinersen, risdiplam) — started as EARLY as possible, ideally "
                   "pre-symptomatically via newborn screening, BEFORE motor neurons are lost. Early "
                   "treatment preserves motor function; timing is the decisive factor.")},
    {"id": "cftr-modulators-cf-2019", "cluster": "frontier_recent", "era": "recent", "year": 2019,
     "title": "CFTR modulators for cystic fibrosis — fix the protein (2019)",
     "case": ("CFTR-modulator drugs (ivacaftor from 2012; the triple combination "
              "elexacaftor/tezacaftor/ivacaftor from 2019) correct the underlying protein defect in "
              "cystic fibrosis for most patients, markedly improving lung function — treating the "
              "cause, not only symptoms."),
     "question": ("A patient with cystic fibrosis is on airway clearance, antibiotics and nutritional "
                  "support. What newer therapy addresses the root molecular defect, and how is it "
                  "selected?"),
     "reference": ("A CFTR MODULATOR (e.g. elexacaftor/tezacaftor/ivacaftor) chosen by the patient's "
                   "CFTR GENOTYPE — it corrects or potentiates the defective chloride channel for "
                   "eligible mutations, improving lung function and survival — used ALONGSIDE (not "
                   "instead of) airway clearance, antimicrobials and nutrition.")},
    {"id": "sickle-cell-gene-therapy-2023", "cluster": "frontier_recent", "era": "recent", "year": 2023,
     "title": "Gene editing for sickle cell disease (2023)",
     "case": ("2023. The first CRISPR gene-editing therapy (exagamglogene autotemcel) — alongside a "
              "lentiviral gene therapy — was approved for severe sickle cell disease, editing a "
              "patient's own stem cells to switch on fetal haemoglobin and prevent vaso-occlusive "
              "crises."),
     "question": ("A patient with severe sickle cell disease has recurrent vaso-occlusive crises "
                  "despite hydroxyurea and transfusions and has no matched transplant donor. What "
                  "curative-intent option now exists?"),
     "reference": ("Autologous GENE THERAPY / GENE EDITING (e.g. CRISPR exa-cel to induce fetal "
                   "haemoglobin) uses the patient's OWN edited stem cells — avoiding donor matching "
                   "and graft-versus-host disease — as a one-time, potentially curative option for "
                   "severe disease. It requires myeloablative conditioning (counsel on fertility and "
                   "toxicity); matched allogeneic transplant is the alternative curative route.")},

    # ---- Resistance, stewardship & the microbiome ----
    {"id": "fmt-cdiff-2013", "cluster": "amr_microbiome", "era": "recent", "year": 2013,
     "title": "Faecal microbiota transplant for recurrent C. difficile (2013)",
     "case": ("2013. A randomised trial showed faecal microbiota transplantation (FMT) cured "
              "recurrent Clostridioides difficile infection far better than vancomycin — restoring a "
              "healthy gut microbiome to resist C. difficile."),
     "question": ("A patient has multiply-recurrent C. difficile infection despite repeated courses of "
                  "oral antibiotics. What is the correct next step, and by what mechanism does it "
                  "work?"),
     "reference": ("FAECAL MICROBIOTA TRANSPLANTATION (screened donor stool, now also standardised "
                   "microbiome products) for recurrent C. difficile — it restores the colonic "
                   "microbiome that resists C. difficile colonisation, curing most patients where "
                   "repeated antibiotics fail. Treat the acute episode first with fidaxomicin or "
                   "vancomycin, and screen donors carefully.")},
    {"id": "mdr-tb-bpal-2019", "cluster": "amr_microbiome", "era": "recent", "year": 2019,
     "title": "All-oral regimens for drug-resistant tuberculosis (2019)",
     "case": ("New all-oral, shorter regimens built around bedaquiline (with pretomanid and "
              "linezolid — the BPaL regimen, ~2019) transformed multidrug-resistant tuberculosis from "
              "long, toxic injectable-based therapy into more effective, tolerable oral courses."),
     "question": ("A patient has multidrug-resistant tuberculosis (resistant to isoniazid and "
                  "rifampicin). How should treatment be approached, beyond the older injectable "
                  "regimens?"),
     "reference": ("Use a modern ALL-ORAL regimen guided by drug-susceptibility testing — bedaquiline-"
                   "based (e.g. BPaL/BPaLM: bedaquiline, pretomanid, linezolid ± moxifloxacin) — "
                   "which is shorter, more effective and less toxic than legacy injectables. Confirm "
                   "resistance by rapid molecular testing, support adherence, and monitor for QT "
                   "prolongation and linezolid toxicity.")},
    {"id": "mrsa-stewardship-2007", "cluster": "amr_microbiome", "era": "recent", "year": 2007,
     "title": "MRSA and antimicrobial stewardship (2000s)",
     "case": ("The spread of methicillin-resistant Staphylococcus aureus (MRSA), including "
              "community-associated strains in the 2000s, drove antimicrobial stewardship, infection-"
              "control bundles, and evidence-based empiric antibiotic choices."),
     "question": ("A patient has a serious skin/soft-tissue or bloodstream infection where MRSA is "
                  "prevalent. How should empiric therapy — and broader practice — be handled?"),
     "reference": ("Cover MRSA empirically when local risk/prevalence warrants (e.g. vancomycin or an "
                   "alternative), then DE-ESCALATE by culture — the core of ANTIMICROBIAL STEWARDSHIP "
                   "(right drug, dose, duration, prompt narrowing) — combined with infection control "
                   "(hand hygiene, contact precautions, decolonisation where indicated) to curb "
                   "resistance.")},

    # ---- Maternal, neonatal & critical care ----
    {"id": "txa-pph-woman-2017", "cluster": "perinatal", "era": "recent", "year": 2017,
     "title": "Tranexamic acid for postpartum haemorrhage — WOMAN trial (2017)",
     "case": ("2017. The WOMAN trial showed that early tranexamic acid reduces death from bleeding in "
              "women with postpartum haemorrhage — a leading cause of maternal death — when given "
              "promptly."),
     "question": ("A woman develops postpartum haemorrhage. Alongside uterotonics and resuscitation, "
                  "what drug given EARLY reduces death, and what is the key to its benefit?"),
     "reference": ("Give TRANEXAMIC ACID EARLY (as soon as possible, ideally within 3 hours of onset) "
                   "IN ADDITION to standard management — uterotonics (oxytocin), uterine massage, "
                   "fluid/blood resuscitation and source control. Timeliness is decisive: the "
                   "mortality benefit falls sharply with delay.")},
    {"id": "neonatal-cooling-hie-2010", "cluster": "perinatal", "era": "recent", "year": 2010,
     "title": "Cooling for neonatal hypoxic-ischaemic encephalopathy (2010)",
     "case": ("Trials through the 2000s showed that therapeutic hypothermia (whole-body or head "
              "cooling) for term newborns with moderate-to-severe hypoxic-ischaemic encephalopathy "
              "reduces death and disability."),
     "question": ("A term newborn suffers perinatal asphyxia and develops moderate hypoxic-ischaemic "
                  "encephalopathy. What neuroprotective intervention improves outcome, and when must "
                  "it start?"),
     "reference": ("THERAPEUTIC HYPOTHERMIA (controlled cooling to ~33.5°C for 72 hours) started "
                   "WITHIN 6 HOURS of birth for term/near-term infants with moderate-severe HIE — it "
                   "reduces death and neurodevelopmental disability. Deliver it in a unit able to cool "
                   "with monitoring and full supportive intensive care; the early window is critical.")},
    {"id": "dexamethasone-covid-recovery-2020", "cluster": "critical_care", "era": "recent", "year": 2020,
     "title": "Dexamethasone for severe COVID-19 — RECOVERY (2020)",
     "case": ("2020. The RECOVERY platform trial found that dexamethasone reduced mortality in "
              "COVID-19 patients requiring oxygen or ventilation — the first drug shown to save lives "
              "in severe COVID — with no benefit (and possible harm) in those not needing oxygen."),
     "question": ("A patient hospitalised with COVID-19 needs supplemental oxygen or ventilation. What "
                  "inexpensive therapy reduces mortality, and in whom should it NOT be used?"),
     "reference": ("DEXAMETHASONE (a corticosteroid) reduces mortality in COVID-19 patients requiring "
                   "OXYGEN or ventilatory support — give it to that group. Do NOT give it to patients "
                   "who do not need oxygen (no benefit, possible harm). A landmark that a cheap, "
                   "targeted anti-inflammatory helps only the right subgroup — match therapy to "
                   "disease stage.")},
)

_CASE_BY_ID = {c["id"]: c for c in CASES}


def all_cases() -> list[dict]:
    return [{**c, "era": c.get("era", "historical")} for c in CASES]


def all_clusters() -> list[dict]:
    return [{**c, "era": c.get("era", "historical")} for c in CLUSTERS]


def get_case(case_id: str) -> dict | None:
    c = _CASE_BY_ID.get(case_id)
    return dict(c) if c else None
