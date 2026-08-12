"""India brand→generic resolver (Noesis IN, spec D-3) — QUESTION-SIDE ONLY, ABSTAINING.

Curated from PUBLIC artifacts (CDSCO approved lists, NLEM annexures, Jan Aushadhi catalogue,
package inserts) — no commercial DB scraping. Rows carry STRENGTH and FDC COMPONENTS because
bare generic mapping is a clinical hazard (panel D-3: "Augmentin 625" must resolve to the
exact amox/clav split, never leave strength to the LLM). The resolver is STRUCTURAL (exact
normalized token match) and ABSTAINS on anything unknown or ambiguous — a wrong mapping is
worse than none. Output feeds a PLANNER-ONLY context line (never compose — grounding
untouched; answers still cite only span-verified evidence).

PENDING CLINICIAN REVIEW before launch (D-8 dependency) — entries are curator drafts.
"""
from __future__ import annotations

import re

# {brand_norm: (display, [components], strength, form)} — strength "" = brand family whose
# strength varies by suffix; the resolver reports the family and flags strength UNKNOWN.
_B = lambda display, comps, strength="", form="tablet": (display, comps, strength, form)  # noqa: E731

BRANDS: dict[str, tuple] = {
    # --- analgesic / antipyretic
    "dolo 650": _B("Dolo 650", ["paracetamol"], "650 mg"),
    "dolo": _B("Dolo (family)", ["paracetamol"], ""),
    "crocin": _B("Crocin (family)", ["paracetamol"], ""),
    "calpol": _B("Calpol (family)", ["paracetamol"], ""),
    "combiflam": _B("Combiflam", ["ibuprofen", "paracetamol"], "400 mg + 325 mg"),
    "zerodol": _B("Zerodol", ["aceclofenac"], "100 mg"),
    "zerodol p": _B("Zerodol-P", ["aceclofenac", "paracetamol"], "100 mg + 325 mg"),
    "zerodol sp": _B("Zerodol-SP", ["aceclofenac", "paracetamol", "serratiopeptidase"],
                     "100 mg + 325 mg + 15 mg"),
    "ultracet": _B("Ultracet", ["tramadol", "paracetamol"], "37.5 mg + 325 mg"),
    "voveran": _B("Voveran (family)", ["diclofenac"], ""),
    # --- antibiotics
    "augmentin 625": _B("Augmentin 625 Duo", ["amoxicillin", "clavulanic acid"], "500 mg + 125 mg"),
    "augmentin 1g": _B("Augmentin 1g", ["amoxicillin", "clavulanic acid"], "875 mg + 125 mg"),
    "augmentin": _B("Augmentin (family)", ["amoxicillin", "clavulanic acid"], ""),
    "moxikind cv": _B("Moxikind-CV (family)", ["amoxicillin", "clavulanic acid"], ""),
    "azee": _B("Azee (family)", ["azithromycin"], ""),
    "azithral": _B("Azithral (family)", ["azithromycin"], ""),
    "taxim o": _B("Taxim-O (family)", ["cefixime"], ""),
    "zifi": _B("Zifi (family)", ["cefixime"], ""),
    "monocef": _B("Monocef (family)", ["ceftriaxone"], "", "injection"),
    "cifran": _B("Cifran (family)", ["ciprofloxacin"], ""),
    "norflox": _B("Norflox (family)", ["norfloxacin"], ""),
    "oflox": _B("Oflox (family)", ["ofloxacin"], ""),
    "o2": _B("O2", ["ofloxacin", "ornidazole"], "200 mg + 500 mg"),
    "doxy 1": _B("Doxy-1", ["doxycycline"], "100 mg", "capsule"),
    "septran": _B("Septran", ["trimethoprim", "sulfamethoxazole"], "80 mg + 400 mg"),
    "metrogyl": _B("Metrogyl (family)", ["metronidazole"], ""),
    # --- GI
    "pan 40": _B("Pan 40", ["pantoprazole"], "40 mg"),
    "pan d": _B("Pan-D", ["pantoprazole", "domperidone"], "40 mg + 30 mg", "capsule"),
    "omez": _B("Omez (family)", ["omeprazole"], "", "capsule"),
    "rantac": _B("Rantac (family)", ["ranitidine"], ""),
    "aciloc": _B("Aciloc (family)", ["ranitidine"], ""),
    "digene": _B("Digene", ["antacid combination (aluminium/magnesium hydroxide, simethicone)"], ""),
    "cyclopam": _B("Cyclopam", ["dicyclomine", "paracetamol"], "20 mg + 500 mg"),
    "meftal spas": _B("Meftal-Spas", ["dicyclomine", "mefenamic acid"], "10 mg + 250 mg"),
    "eldoper": _B("Eldoper", ["loperamide"], "2 mg", "capsule"),
    "vomikind": _B("Vomikind (family)", ["ondansetron"], ""),
    "emeset": _B("Emeset (family)", ["ondansetron"], ""),
    "domstal": _B("Domstal (family)", ["domperidone"], ""),
    # --- cardio-metabolic
    "ecosprin": _B("Ecosprin (family)", ["aspirin"], ""),
    "ecosprin av": _B("Ecosprin-AV (family)", ["aspirin", "atorvastatin"], "", "capsule"),
    "telma": _B("Telma (family)", ["telmisartan"], ""),
    "telma h": _B("Telma-H (family)", ["telmisartan", "hydrochlorothiazide"], ""),
    "amlong": _B("Amlong (family)", ["amlodipine"], ""),
    "stamlo": _B("Stamlo (family)", ["amlodipine"], ""),
    "atorva": _B("Atorva (family)", ["atorvastatin"], ""),
    "rosuvas": _B("Rosuvas (family)", ["rosuvastatin"], ""),
    "clopitab": _B("Clopitab (family)", ["clopidogrel"], ""),
    "met xl": _B("Met-XL (family)", ["metoprolol succinate ER"], ""),
    "concor": _B("Concor (family)", ["bisoprolol"], ""),
    "dytor": _B("Dytor (family)", ["torsemide"], ""),
    "lasix": _B("Lasix (family)", ["furosemide"], ""),
    # --- diabetes
    "glycomet": _B("Glycomet (family)", ["metformin"], ""),
    "glycomet gp": _B("Glycomet-GP (family)", ["glimepiride", "metformin"], ""),
    "amaryl": _B("Amaryl (family)", ["glimepiride"], ""),
    "janumet": _B("Janumet (family)", ["sitagliptin", "metformin"], ""),
    "istamet": _B("Istamet (family)", ["sitagliptin", "metformin"], ""),
    "galvus met": _B("Galvus Met (family)", ["vildagliptin", "metformin"], ""),
    "jardiance": _B("Jardiance (family)", ["empagliflozin"], ""),
    "forxiga": _B("Forxiga (family)", ["dapagliflozin"], ""),
    "mixtard": _B("Human Mixtard (family)", ["biphasic isophane insulin 30/70"], "", "injection"),
    "lantus": _B("Lantus", ["insulin glargine"], "100 U/mL", "injection"),
    # --- respiratory / allergy
    "allegra": _B("Allegra (family)", ["fexofenadine"], ""),
    "cetzine": _B("Cetzine", ["cetirizine"], "10 mg"),
    "okacet": _B("Okacet", ["cetirizine"], "10 mg"),
    "montair lc": _B("Montair-LC", ["montelukast", "levocetirizine"], "10 mg + 5 mg"),
    "asthalin": _B("Asthalin (family)", ["salbutamol"], "", "inhaler"),
    "budecort": _B("Budecort (family)", ["budesonide"], "", "inhaler"),
    "foracort": _B("Foracort (family)", ["formoterol", "budesonide"], "", "inhaler"),
    "duolin": _B("Duolin", ["levosalbutamol", "ipratropium"], "", "respules"),
    "sinarest": _B("Sinarest", ["paracetamol", "phenylephrine", "chlorpheniramine"],
                   "500 mg + 10 mg + 2 mg"),
    "grilinctus": _B("Grilinctus (family)", ["dextromethorphan", "chlorpheniramine"], "", "syrup"),
    "ascoril": _B("Ascoril (family)", ["bromhexine", "terbutaline", "guaifenesin"], "", "syrup"),
    # --- thyroid / endocrine / supplements
    "thyronorm": _B("Thyronorm (family)", ["levothyroxine"], ""),
    "eltroxin": _B("Eltroxin (family)", ["levothyroxine"], ""),
    "shelcal": _B("Shelcal (family)", ["calcium carbonate", "vitamin D3"], ""),
    "uprise d3": _B("Uprise-D3", ["cholecalciferol"], "60,000 IU", "capsule"),
    "becosules": _B("Becosules", ["B-complex vitamins with vitamin C"], "", "capsule"),
    "livogen": _B("Livogen", ["ferrous fumarate", "folic acid"], "152 mg + 1.5 mg"),
    "orofer xt": _B("Orofer-XT", ["ferrous ascorbate", "folic acid"], "100 mg + 1.5 mg"),
    "zincovit": _B("Zincovit", ["multivitamin with zinc"], ""),
    # --- neuro / psych
    "gabapin": _B("Gabapin (family)", ["gabapentin"], ""),
    "pregabid": _B("Pregabid (family)", ["pregabalin"], ""),
    "nexito": _B("Nexito (family)", ["escitalopram"], ""),
    "prothiaden": _B("Prothiaden (family)", ["dosulepin"], ""),
    "alprax": _B("Alprax (family)", ["alprazolam"], ""),
    "restyl": _B("Restyl (family)", ["alprazolam"], ""),
    "vertin": _B("Vertin (family)", ["betahistine"], ""),
    "stugeron": _B("Stugeron (family)", ["cinnarizine"], ""),
    "naxdom": _B("Naxdom (family)", ["naproxen", "domperidone"], ""),
    # --- steroids / others
    "wysolone": _B("Wysolone (family)", ["prednisolone"], ""),
    "omnacortil": _B("Omnacortil (family)", ["prednisolone"], ""),
    "medrol": _B("Medrol (family)", ["methylprednisolone"], ""),
    "chymoral forte": _B("Chymoral Forte", ["trypsin-chymotrypsin"], "100,000 AU"),
    "limcee": _B("Limcee", ["vitamin C"], "500 mg", "chewable tablet"),
    "betnovate": _B("Betnovate (family)", ["betamethasone valerate"], "", "topical"),
    "quadriderm": _B("Quadriderm", ["betamethasone", "clotrimazole", "gentamicin", "iodochlorhydroxyquin"],
                     "", "topical"),
    "candid": _B("Candid (family)", ["clotrimazole"], "", "topical"),
    "surfaz sn": _B("Surfaz-SN", ["clotrimazole", "beclomethasone", "neomycin"], "", "topical"),
    "zandu balm": _B("Zandu Balm", ["counterirritant balm (menthol, oils)"], "", "topical"),
}


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (s or "").lower()).split())


def resolve_brands(text: str, *, limit: int = 3) -> list[dict]:
    """STRUCTURAL brand detection in question text — longest match first, word-boundary safe,
    ABSTAINS on anything not in the table (returns only exact-known rows; never guesses).
    Multi-word brands ("pan d", "augmentin 625") match before their family fallback."""
    hay = f" {_norm(text)} "
    out, seen_display = [], set()
    for key in sorted(BRANDS, key=len, reverse=True):
        if f" {key} " in hay:
            display, comps, strength, form = BRANDS[key]
            if display in seen_display or any(display.startswith(o["brand"].split(" (")[0])
                                              for o in out):
                continue
            seen_display.add(display)
            out.append({"brand": display, "components": comps,
                        "strength": strength or "UNKNOWN — do not assume",
                        "form": form})
            if len(out) >= limit:
                break
    return out


def brand_context(text: str) -> str:
    """Planner-only context line (fed via the kernel's question_context seam — NEVER compose):
    tells the engine what the brand IS so it searches generics; explicitly forbids treating
    the mapping as evidence. Empty string when nothing resolves (fail-safe)."""
    rows = resolve_brands(text)
    if not rows:
        return ""
    lines = []
    for r in rows:
        comp = " + ".join(r["components"])
        lines.append(f"- {r['brand']} = {comp}"
                     + (f" ({r['strength']}, {r['form']})" if r["strength"] else f" ({r['form']})"))
    return ("INDIAN BRAND MAPPING (structural lookup table, NOT evidence — use it only to "
            "form search queries with the generic names; never cite it, and never assume a "
            "strength marked UNKNOWN):\n" + "\n".join(lines))


# Noesis IN compose ADDENDUM (D-7 conflict protocol) — additive extra_directive; the validated
# base directive is untouched. Governs how India-specific vs global guidance is PRESENTED.
INDIA_CONFLICT_DIRECTIVE = (
    "PRACTICE CONTEXT: INDIA. Where Indian national guidance (ICMR, national programmes such as "
    "NTEP/NVBDCP, MoHFW standard treatment guidelines) is among the findings and governs the "
    "question, lead with it and label it as the guidance that applies for practice in India. "
    "When Indian and international guidance DISAGREE, present BOTH positions explicitly, label "
    "which applies where, and never suppress either. Regulatory status differs by country: an "
    "approval, combination, or ban may be India-specific — say so when the findings show it. "
    "Do not state Indian brand names unless they appear in the findings themselves.")
