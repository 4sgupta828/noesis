"""Held-out eval set for the ambient CDS — 20 diverse encounters with clinician-authored gold.

Gold encodes the CLINICALLY-CORRECT expectation (not merely current engine output), so the scorer
surfaces both regressions and genuine engine errors. Diversity is deliberate: GDMT gaps, each
contraindication (hyperkalemia/bradycardia/hypotension/low-eGFR/pregnancy), negation traps (conditions
and meds), drug-safety interactions/allergy, fully-optimized patients, low-signal visits, and India mode.

gold keys: conditions / forbid_conditions / gaps / forbid_gaps / actions / cautions{id:level} /
safety_categories / codes / coverage(bool).
"""
from __future__ import annotations

CASES = [
    # 1 — flagship: HF + diabetes + tobacco, partial GDMT
    {"id": "hf_dm_tobacco", "mode": "US", "recent_hosp": True,
     "transcript": "Since your heart failure hospitalization you've been on furosemide and lisinopril, "
                   "and we're continuing metformin for your diabetes. You're still smoking about half a pack a day.",
     "patient": {"age": 64, "sex": "female"},
     "gold": {"conditions": ["heart_failure", "diabetes", "tobacco_use"],
              "gaps": ["hf_bb", "hf_mra", "hf_sglt2", "dm_statin", "dm_sglt2_organ"],
              "forbid_gaps": ["hf_renin"], "actions": ["tob_cessation", "toc_medrec", "toc_followup"],
              "codes": ["I50.22", "E11.9", "Z72.0"], "coverage": True}},

    # 2 — HF + hyperkalemia -> MRA hold
    {"id": "hf_hyperkalemia", "mode": "US",
     "transcript": "Chronic systolic heart failure, on lisinopril. Labs today: potassium 5.6.",
     "patient": {"age": 70, "sex": "male"},
     "gold": {"conditions": ["heart_failure"], "gaps": ["hf_bb", "hf_mra", "hf_sglt2"],
              "forbid_gaps": ["hf_renin"], "cautions": {"hf_mra": "hold"}}},

    # 3 — HF + bradycardia -> beta-blocker hold; SGLT2 already on board
    {"id": "hf_bradycardia", "mode": "US",
     "transcript": "Heart failure, on lisinopril and empagliflozin. Heart rate today is 42.",
     "patient": {"age": 66, "sex": "male"},
     "gold": {"conditions": ["heart_failure"], "gaps": ["hf_bb", "hf_mra"],
              "forbid_gaps": ["hf_renin", "hf_sglt2"], "cautions": {"hf_bb": "hold"}}},

    # 4 — HF fully optimized on all four pillars
    {"id": "hf_full_gdmt", "mode": "US",
     "transcript": "Heart failure, doing well on carvedilol, lisinopril, spironolactone and dapagliflozin.",
     "patient": {"age": 60, "sex": "female", "egfr": 70},
     "gold": {"conditions": ["heart_failure"],
              "forbid_gaps": ["hf_renin", "hf_bb", "hf_mra", "hf_sglt2"]}},

    # 5 — diabetes + CKD, low eGFR -> metformin renal safety; statin gap; SGLT2 indicated
    {"id": "dm_ckd_low_egfr", "mode": "US",
     "transcript": "Type 2 diabetes and chronic kidney disease, on metformin. eGFR is 24.",
     "patient": {"age": 68, "sex": "male"},
     "gold": {"conditions": ["diabetes", "ckd"], "gaps": ["dm_statin", "dm_sglt2_organ"],
              "safety_categories": ["renal-dosing"], "codes": ["E11.9", "N18.9"]}},

    # 6 — negation trap on conditions
    {"id": "negation_conditions", "mode": "US",
     "transcript": "He has heart failure but no diabetes. He quit smoking last year.",
     "patient": {},
     "gold": {"conditions": ["heart_failure"], "forbid_conditions": ["diabetes", "tobacco_use"]}},

    # 7 — negation trap on meds (stopped/discontinued)
    {"id": "negation_meds", "mode": "US",
     "transcript": "Heart failure. He is not on a beta-blocker, and we discontinued spironolactone last month.",
     "patient": {"age": 72, "sex": "male"},
     "gold": {"conditions": ["heart_failure"], "gaps": ["hf_bb", "hf_mra"]}},

    # 8 — drug-drug safety during the visit
    {"id": "warfarin_interaction", "mode": "US",
     "transcript": "You take warfarin. For this infection I'll start clarithromycin, and take ibuprofen for pain.",
     "patient": {"age": 74, "sex": "female"},
     "gold": {"safety_categories": ["drug-drug-interaction"]}},

    # 9 — pregnancy contraindications (ACEi + statin)
    {"id": "pregnancy_contra", "mode": "US",
     "transcript": "She is pregnant. Currently on ramipril and atorvastatin.",
     "patient": {"age": 31, "sex": "female", "pregnant": True},
     "gold": {"safety_categories": ["pregnancy"]}},

    # 10 — controlled hypertension, minimal gaps
    {"id": "htn_controlled", "mode": "US",
     "transcript": "Hypertension, well controlled on lisinopril. Blood pressure 122/78 today.",
     "patient": {"age": 55, "sex": "female"},
     "gold": {"conditions": ["hypertension"], "forbid_gaps": ["hf_bb", "hf_mra", "dm_statin"],
              "codes": ["I10"]}},

    # 11 — diabetes + hyperlipidemia, statin gap
    {"id": "dm_hyperlipidemia", "mode": "US",
     "transcript": "Type 2 diabetes and hyperlipidemia. Not on a statin currently.",
     "patient": {"age": 58, "sex": "male"},
     "gold": {"conditions": ["diabetes", "hyperlipidemia"], "gaps": ["dm_statin"],
              "codes": ["E11.9", "E78.5"]}},

    # 12 — drug-allergy safety (penicillin)
    {"id": "penicillin_allergy", "mode": "US",
     "transcript": "For the sinus infection I'll start Augmentin.",
     "patient": {"age": 40, "sex": "female", "allergies": ["penicillin"]},
     "gold": {"safety_categories": ["drug-allergy"]}},

    # 13 — HF + hypotension -> confirm cautions on BB and RAS
    {"id": "hf_hypotension", "mode": "US",
     "transcript": "New diagnosis of heart failure with reduced EF. Blood pressure 85/54 today.",
     "patient": {"age": 63, "sex": "male"},
     "gold": {"conditions": ["heart_failure"], "gaps": ["hf_renin", "hf_bb", "hf_mra", "hf_sglt2"],
              "cautions": {"hf_bb": "confirm", "hf_renin": "confirm"}}},

    # 14 — HF + very low eGFR -> SGLT2 confirm-threshold
    {"id": "hf_sglt2_threshold", "mode": "US",
     "transcript": "Heart failure, on lisinopril. eGFR is 18.",
     "patient": {"age": 77, "sex": "female"},
     "gold": {"conditions": ["heart_failure"], "gaps": ["hf_bb", "hf_mra", "hf_sglt2"],
              "cautions": {"hf_sglt2": "confirm"}}},

    # 15 — tobacco only
    {"id": "tobacco_only", "mode": "US",
     "transcript": "Here for a check-up. Still a heavy smoker, about a pack a day.",
     "patient": {"age": 45, "sex": "male"},
     "gold": {"conditions": ["tobacco_use"], "actions": ["tob_cessation"], "codes": ["Z72.0"]}},

    # 16 — diabetes with high A1c (labs)
    {"id": "dm_high_a1c", "mode": "US",
     "transcript": "Type 2 diabetes on metformin. A1c came back at 10.2.",
     "patient": {"age": 52, "sex": "female", "egfr": 80},
     "gold": {"conditions": ["diabetes"], "gaps": ["dm_statin"], "actions": ["dm_a1c"],
              "codes": ["E11.9"]}},

    # 17 — multimorbid, ACEi + MRA present -> hyperkalemia interaction + partial GDMT
    {"id": "multimorbid_ddi", "mode": "US",
     "transcript": "Heart failure and diabetes. On lisinopril and spironolactone and metformin.",
     "patient": {"age": 80, "sex": "male", "egfr": 55},
     "gold": {"conditions": ["heart_failure", "diabetes"], "gaps": ["hf_bb", "hf_sglt2", "dm_statin"],
              "forbid_gaps": ["hf_renin", "hf_mra"], "safety_categories": ["drug-drug-interaction"]}},

    # 18 — low-signal routine visit -> honest coverage gap, no fabricated problems
    {"id": "routine_well", "mode": "US",
     "transcript": "Routine annual visit. Feeling well, no complaints, no chronic conditions.",
     "patient": {"age": 34, "sex": "female"},
     "gold": {"forbid_conditions": ["heart_failure", "diabetes"], "coverage": True}},

    # 19 — India mode: brands + CKD, NSAID drug-disease safety, summary output
    {"id": "india_brands_ckd", "mode": "IN",
     "transcript": "Continue Glycomet for the diabetes and Cardace for blood pressure. For the knee pain start Hifenac. He has chronic kidney disease.",
     "patient": {"age": 62, "sex": "male"},
     "gold": {"conditions": ["diabetes", "ckd"], "safety_categories": ["drug-disease"]}},

    # 20 — India mode: warfarin brand + NSAID interaction
    {"id": "india_warfarin", "mode": "IN",
     "transcript": "On Warf for the clot. Starting Hifenac for back pain.",
     "patient": {"age": 66, "sex": "male", "current_meds": ["Warf 5"]},
     "gold": {"safety_categories": ["drug-drug-interaction"]}},
]
