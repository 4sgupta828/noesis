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
)

_CASE_BY_ID = {c["id"]: c for c in CASES}


def all_cases() -> list[dict]:
    return [{**c, "era": c.get("era", "historical")} for c in CASES]


def all_clusters() -> list[dict]:
    return [{**c, "era": c.get("era", "historical")} for c in CLUSTERS]


def get_case(case_id: str) -> dict | None:
    c = _CASE_BY_ID.get(case_id)
    return dict(c) if c else None
