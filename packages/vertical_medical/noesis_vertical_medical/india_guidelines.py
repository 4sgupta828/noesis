"""India clinical-guidelines connector — ICMR + national-programme + society guidance.

This is the TOP-TIER evidence source for India (national guidelines outrank journals). It is a CURATED
REGISTRY, not a crawler: each entry is an authoritative Indian guideline (issuer, condition tags, and a
source `url` and/or `text`). Ingested with `source_country=IN` + guideline-tier facets so India-scoped
queries rank on Indian guidance. Mirrors the ClinicalTrials/EuropePMC connector shape
(`discover_entities → list_documents → fetch_artifact`).

PROVENANCE / HONESTY: inline `text` fields are **curated key-recommendation summaries** attributed to the
issuing body — a bootstrap so the India eval is exercisable and the highest-yield facts are grounded. They
are NOT the authoritative full text and each says so. A production ingest should `fetch_artifact` the real
`url` (PDF/HTML → parser) once the URLs are verified (gov URLs move). Registry content must be reviewed by
an Indian clinical specialist before this source is trusted as a quality benchmark.
"""
from __future__ import annotations


def _summary(body: str, issuer: str) -> str:
    return (f"_Curated key recommendations attributed to **{issuer}** (India) — a guideline-tier summary; "
            f"verify against the full published document._\n\n{body}")


# Curated starter registry. `conditions` drives discovery matching; `url` is the authoritative source
# (verify before a live fetch); `text` is the curated summary used until the full document is ingested.
INDIA_GUIDELINES: tuple[dict, ...] = (
    {"id": "ntep-tb", "issuer": "NTEP / Central TB Division, MoHFW",
     "title": "NTEP Guidelines — Programmatic Management of TB (India)",
     "conditions": ["tuberculosis", "tb", "pulmonary tuberculosis", "mdr-tb", "drug-resistant tb"],
     "url": "https://tbcindia.gov.in/", "year": 2023,
     "text": _summary(
         "- New drug-sensitive pulmonary TB: 4-drug intensive phase — **isoniazid, rifampicin, "
         "pyrazinamide, ethambutol (HRZE)** for 2 months, then **HR** continuation for 4 months (daily "
         "fixed-dose combinations, weight-banded).\n"
         "- Never treat active TB with mono- or dual therapy (drives resistance); rifampicin is essential.\n"
         "- MDR-TB (rifampicin/isoniazid resistant): treat under programmatic DR-TB pathways with newer "
         "regimens built around **bedaquiline** (per current WHO/NTEP guidance) — first-line drugs alone fail.",
         "NTEP / Central TB Division")},
    {"id": "naco-art", "issuer": "NACO, MoHFW",
     "title": "NACO National Guidelines for HIV Care and Antiretroviral Therapy (India)",
     "conditions": ["hiv", "art", "antiretroviral", "aids"],
     "url": "https://naco.gov.in/", "year": 2021,
     "text": _summary(
         "- First-line ART for treatment-naive adults is a **three-drug** regimen; current programmes "
         "favour a **dolutegravir (DTG)-based** regimen (e.g. tenofovir + lamivudine + dolutegravir, TLD).\n"
         "- Monotherapy or two-drug therapy is never adequate for first-line treatment.",
         "NACO")},
    {"id": "nvbdcp-dengue", "issuer": "NVBDCP / NCVBDC, MoHFW",
     "title": "National Guidelines for Clinical Management of Dengue Fever (India)",
     "conditions": ["dengue", "dengue fever", "dengue haemorrhagic fever"],
     "url": "https://ncvbdc.mohfw.gov.in/", "year": 2015,
     "text": _summary(
         "- Antipyretic/analgesic of choice is **paracetamol**. **Avoid NSAIDs and aspirin** "
         "(ibuprofen, diclofenac, aspirin) — they increase bleeding/gastritis risk.\n"
         "- Management is supportive with careful **fluid** therapy guided by warning signs/haematocrit.\n"
         "- **Do NOT** give prophylactic platelet transfusion based on platelet count alone in a "
         "haemodynamically stable patient without significant bleeding.\n"
         "- Corticosteroids are not recommended for routine dengue management.",
         "NVBDCP")},
    {"id": "nvbdcp-malaria", "issuer": "NVBDCP / NCVBDC, MoHFW",
     "title": "National Drug Policy on Malaria (India)",
     "conditions": ["malaria", "falciparum", "plasmodium", "vivax"],
     "url": "https://ncvbdc.mohfw.gov.in/", "year": 2013,
     "text": _summary(
         "- Uncomplicated **P. falciparum**: treat with **artemisinin-based combination therapy (ACT)** "
         "per regional policy (falciparum is chloroquine-resistant across India — chloroquine monotherapy "
         "is inadequate), plus a single dose of **primaquine** as gametocytocidal.\n"
         "- **P. vivax**: chloroquine for the acute attack + primaquine (14 days) for radical cure "
         "(after G6PD consideration).",
         "NVBDCP")},
    {"id": "icmr-amr-enteric", "issuer": "ICMR",
     "title": "ICMR Treatment Guidelines for Antimicrobial Use — Enteric Fever (India)",
     "conditions": ["typhoid", "enteric fever", "salmonella typhi"],
     "url": "https://main.icmr.nic.in/", "year": 2019,
     "text": _summary(
         "- Empirical therapy for uncomplicated enteric fever should account for **widespread "
         "fluoroquinolone resistance** in Indian S. Typhi — fluoroquinolones (ciprofloxacin) are no longer "
         "reliably first-line. **Azithromycin** (uncomplicated) or **ceftriaxone** (severe/complicated) are "
         "preferred; de-escalate on susceptibility.",
         "ICMR")},
    {"id": "icmr-rssdi-t2d", "issuer": "ICMR / RSSDI",
     "title": "ICMR–RSSDI Guidelines for Management of Type 2 Diabetes (India)",
     "conditions": ["diabetes", "type 2 diabetes", "t2dm", "hyperglycaemia"],
     "url": "https://main.icmr.nic.in/", "year": 2018,
     "text": _summary(
         "- **Metformin** is first-line pharmacotherapy for type 2 diabetes unless contraindicated.\n"
         "- Individualise glycaemic targets; add second agents based on comorbidity/cost; insulin is not "
         "first-line for most.",
         "ICMR / RSSDI")},
    {"id": "diPSI-gdm", "issuer": "DIPSI / MoHFW-ICMR",
     "title": "Diagnosis & Management of Gestational Diabetes Mellitus (India, DIPSI)",
     "conditions": ["gestational diabetes", "gdm", "diabetes in pregnancy"],
     "url": "https://main.icmr.nic.in/", "year": 2018,
     "text": _summary(
         "- **Universal screening** for GDM is recommended in India (high prevalence). The DIPSI approach "
         "uses a non-fasting 75 g oral glucose load with a 2-hour plasma glucose threshold; a single "
         "fasting value does not exclude GDM.",
         "DIPSI / ICMR")},
    {"id": "nrcp-rabies", "issuer": "National Rabies Control Programme, NCDC",
     "title": "National Guidelines on Rabies Prophylaxis (India)",
     "conditions": ["rabies", "dog bite", "animal bite", "post-exposure prophylaxis"],
     "url": "https://ncdc.mohfw.gov.in/", "year": 2019,
     "text": _summary(
         "- **Category III** exposure (transdermal bites/scratches, mucous-membrane contact) in an "
         "unvaccinated person requires **both rabies vaccine (full PEP course) AND rabies immunoglobulin "
         "(RIG)** infiltrated into/around the wound, plus thorough wound washing.\n"
         "- Category II requires vaccine; Category III always adds RIG.",
         "NRCP / NCDC")},
    {"id": "snakebite-nsmp", "issuer": "MoHFW National Snakebite Management Protocol",
     "title": "National Snakebite Management Protocol (India)",
     "conditions": ["snakebite", "snake bite", "envenomation", "anti-snake venom"],
     "url": "https://mohfw.gov.in/", "year": 2017,
     "text": _summary(
         "- Definitive treatment of systemic envenomation is **polyvalent anti-snake venom (ASV)** with "
         "monitoring for anaphylaxis; neostigmine/atropine for neurotoxic bites as indicated.\n"
         "- **Do NOT** apply arterial tourniquets, incise, or attempt suction — these are harmful; use "
         "reassurance, immobilisation, and rapid transfer.",
         "MoHFW")},
    {"id": "nvbdcp-kala-azar", "issuer": "NVBDCP / NCVBDC — Kala-azar Elimination",
     "title": "National Guidelines for Diagnosis & Treatment of Visceral Leishmaniasis (India)",
     "conditions": ["kala-azar", "visceral leishmaniasis", "leishmania"],
     "url": "https://ncvbdc.mohfw.gov.in/", "year": 2019,
     "text": _summary(
         "- In the Indian focus, **single-dose liposomal amphotericin B** is the preferred first-line "
         "treatment; **antimonials are not recommended** owing to high resistance.",
         "NVBDCP")},
)


def _facets(g: dict) -> dict:
    # `pub_type=guideline` → guideline tier in evidence_kind; source_country=IN scopes India queries.
    return {"pub_type": "guideline", "source_country": "IN",
            "issuer": g.get("issuer", ""), "year": g.get("year"),
            "source_country_label": "India"}


class IndiaGuidelinesConnector:
    """Curated Indian-guideline source. `documents=` injects/overrides registry entries (tests + verified
    full-text). Discovery matches `window['query']` against condition tags / titles; an empty query returns
    the whole registry (bulk ingest)."""
    key = "india_guidelines"

    class _Http:
        egress_class = "datacenter"; engine = "http"; proxy_enabled = False
        async def fetch(self, url: str, **o) -> bytes:  # noqa: ANN003
            import httpx
            async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as c:
                r = await c.get(url); r.raise_for_status(); return r.content

    def __init__(self, *, registry: tuple[dict, ...] = INDIA_GUIDELINES, documents: list[dict] | None = None):
        self.fetch_strategy = self._Http()
        self._reg: dict[str, dict] = {g["id"]: dict(g) for g in registry}
        for d in documents or []:                     # inject/override (tests, verified content)
            self._reg[d["id"]] = {**self._reg.get(d["id"], {}), **d}

    def _match(self, query: str) -> list[dict]:
        q = (query or "").strip().lower()
        if not q:
            return list(self._reg.values())
        hits = []
        for g in self._reg.values():
            conds = [c.lower() for c in g.get("conditions", [])]
            if any(c in q or q in c for c in conds) or q in g.get("title", "").lower():
                hits.append(g)
        return hits

    async def discover_entities(self, window: dict):
        from noesis_kernel.contract.dto import EntityRef
        return [EntityRef(source_key=self.key, native_id=g["id"], title=g.get("title", ""),
                          facets=_facets(g)) for g in self._match((window or {}).get("query", ""))]

    async def list_documents(self, entity):
        from noesis_kernel.contract.dto import DocumentRef
        g = self._reg.get(entity.native_id, {})
        url = g.get("url", "")
        ctype = "application/pdf" if url.lower().endswith(".pdf") else "text/markdown"
        return [DocumentRef(source_key=self.key, native_id=entity.native_id, title=entity.title,
                            content_type=ctype, facets=_facets(g), entity_ids=(entity.native_id,))]

    async def fetch_artifact(self, doc) -> bytes:
        g = self._reg[doc.native_id]
        if g.get("text"):                             # curated summary (or injected verified text)
            md = (f"# {g.get('title', '')}\n\n"
                  f"_Issuer: {g.get('issuer', '')} · India · guideline-tier_\n\n{g['text']}\n")
            return md.encode("utf-8")
        url = g.get("url")
        if not url:
            raise ValueError(f"india_guidelines: no text or url for {doc.native_id!r}")
        return await self.fetch_strategy.fetch(url)   # live fetch (PDF/HTML → parser)
