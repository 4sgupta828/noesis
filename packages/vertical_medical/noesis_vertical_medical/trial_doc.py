"""Turn a ClinicalTrials.gov v2 study record into a citable document + facets.

A trial is structured JSON, not a PDF — so we synthesize ONE markdown "trial
document" per NCT from its text-bearing modules (title, summary, description,
conditions, interventions, outcomes, eligibility). The kernel then splits it into
section blocks and each block is span-verifiable. The narrowing facets
(condition/phase/status/study_type/intervention/country/year) are denormalized
onto every block so search filters like "phase 3 diabetes trials" work.
"""
from __future__ import annotations


def _ps(study: dict) -> dict:
    return study.get("protocolSection", {})


def nct_id(study: dict) -> str:
    return _ps(study).get("identificationModule", {}).get("nctId", "")


def title(study: dict) -> str:
    idm = _ps(study).get("identificationModule", {})
    return idm.get("officialTitle") or idm.get("briefTitle", "")


def facets(study: dict) -> dict:
    ps = _ps(study)
    cond = ps.get("conditionsModule", {}).get("conditions", []) or []
    des = ps.get("designModule", {})
    phases = des.get("phases", []) or []
    st = ps.get("statusModule", {})
    start = (st.get("startDateStruct") or {}).get("date", "")
    ivs = ps.get("armsInterventionsModule", {}).get("interventions", []) or []
    locs = ps.get("contactsLocationsModule", {}).get("locations", []) or []
    countries = sorted({l.get("country", "") for l in locs if l.get("country")})
    f = {
        "study_type": des.get("studyType", "").lower(),
        "status": st.get("overallStatus", "").lower(),
    }
    # single-valued facets (first / primary); lists kept in extra for display
    if cond:
        f["condition"] = cond[0].lower()
    if phases:
        f["phase"] = phases[0].lower()
    if start[:4].isdigit():
        f["year"] = start[:4]
    if ivs:
        f["intervention"] = (ivs[0].get("name") or "").lower()
    if countries:
        f["country"] = countries[0]
    return {k: v for k, v in f.items() if v}


def to_markdown(study: dict) -> str:
    ps = _ps(study)
    idm = ps.get("identificationModule", {})
    desc = ps.get("descriptionModule", {})
    cond = ps.get("conditionsModule", {}).get("conditions", []) or []
    ivs = [i.get("name", "") for i in ps.get("armsInterventionsModule", {}).get("interventions", [])]
    elig = ps.get("eligibilityModule", {})
    outcomes = ps.get("outcomesModule", {})

    parts: list[str] = [f"# {title(study)}", ""]
    if idm.get("nctId"):
        parts += [f"Registry ID: {idm['nctId']}", ""]
    if cond:
        parts += ["## Conditions",
                  "This study investigates the following conditions: " + ", ".join(cond) + ".", ""]
    if ivs:
        named = [x for x in ivs if x]
        if named:
            parts += ["## Interventions",
                      "The interventions studied are: " + ", ".join(named) + ".", ""]
    if desc.get("briefSummary"):
        parts += ["## Brief Summary", desc["briefSummary"].strip(), ""]
    if desc.get("detailedDescription"):
        parts += ["## Detailed Description", desc["detailedDescription"].strip(), ""]
    prim = outcomes.get("primaryOutcomes", []) or []
    if prim:
        parts += ["## Primary Outcomes"]
        for o in prim:
            m = o.get("measure", "")
            if m:
                parts.append(f"- {m}")
        parts.append("")
    if elig.get("eligibilityCriteria"):
        parts += ["## Eligibility", elig["eligibilityCriteria"].strip(), ""]
    return "\n".join(parts).strip() + "\n"
