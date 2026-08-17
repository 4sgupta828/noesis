"""Alternative-modality directive + retrieval hint — the compose/query layer for the "Alternative"
therapy MODE (flag NOESIS_MODALITY_MODE; the app layer supplies the modality=alternative corpus scope).

Unlike the integrative opt-in (a small "complementary options" section on an otherwise-conventional
answer), this is the directive for an answer that is CENTERED on complementary & alternative medicine
(CAM) evidence — acupuncture, acupressure, and related therapies — while keeping conventional context
and enforcing responsible, per-indication evidence labeling (design research, 2026-08-14: rank by
evidence tier not journal prestige; label per source x per indication; flag contested modalities).
"""

MEDICAL_ALTERNATIVE_DIRECTIVE = """ANSWERING IN ALTERNATIVE-THERAPY MODE.
This answer is centered on complementary & alternative medicine (CAM) — acupuncture, acupressure,
moxibustion, cupping, traditional systems, mind-body and manual therapies, herbal medicine — but you
must present it responsibly, with conventional context, from the verified findings only (add no facts).

LABEL EVIDENCE PER THERAPY x PER INDICATION — never as a whole modality:
- Evidence tier: systematic review / meta-analysis > RCT > observational > mechanistic/preclinical >
  narrative/opinion. State the tier of the evidence you cite.
- Certainty: carry the source's own GRADE/quality rating VERBATIM when present (high/moderate/low/very
  low); never invent one.
- Direction: say plainly whether the evidence is SUPPORTIVE, INCONCLUSIVE, shows NO EFFECT (vs sham/
  placebo), or is HARMFUL for that specific use. Where benefit is attributed to placebo/expectation
  (e.g. some acupuncture-vs-sham findings), say so.
- Source authority: an independent evidence body (Cochrane, NCCIH, WHO) outranks any CAM journal, which
  outranks an advocacy-commissioned review. When sources conflict, defer to the most authoritative and
  most recent.

SAFETY, always and independently of efficacy: note real risks (e.g. acupuncture — infection/pneumothorax
with poor technique; herbal products — drug interactions, contamination). A CAM therapy is a COMPLEMENT
to, not a replacement for, indicated conventional care — say so when a serious condition is involved.

BE HONEST ABOUT WHAT ISN'T SUPPORTED: if the findings show a therapy lacks rigorous support or is
contested (e.g. homeopathy, energy therapies for most uses), state that clearly rather than implying
efficacy. Do not oversell. A truthful "the evidence is weak/mixed here" is the correct answer when that
is what the evidence says.
"""

# Appended (bracketed) to the research question to steer retrieval toward the CAM corpus + high-tier
# secondary evidence. Opaque to the kernel.
MEDICAL_ALTERNATIVE_QUERY_HINT = (
    "Focus on complementary & alternative medicine evidence (acupuncture, acupressure and related "
    "therapies): prioritize systematic reviews, meta-analyses, and Cochrane/NCCIH/WHO assessments, "
    "and note evidence strength and safety for the specific indication."
)

# CAM-intent router (flag NOESIS_CAM_AUTOSCOPE): ONE small LLM call on the main Q&A path decides whether
# a question is PRIMARILY about a CAM modality, so the answer auto-scopes to the CAM corpus (modality=
# alternative) instead of the default Allopathic view that EXCLUDES it — no mode toggle needed. Rule 18:
# the model owns the "is this a CAM question" judgment; code only reads the boolean. Conservative by
# design (prefer false) so a conventional question that merely mentions a supplement is NOT rerouted.
MEDICAL_CAM_INTENT_SYSTEM = (
    "You route a user's medical question. Decide whether it is PRIMARILY about complementary & "
    "alternative medicine (CAM): the user is asking FROM, ABOUT, or FOR a non-conventional modality — "
    "acupuncture / acupressure / moxibustion / cupping, Ayurveda, traditional Chinese medicine, herbal "
    "& botanical medicine, homeopathy, naturopathy, mind-body practices (yoga, meditation, tai chi, "
    "qigong), or energy therapies (Reiki, therapeutic touch).\n"
    "Set is_cam=true ONLY when a CAM modality is the SUBJECT of the question — e.g. 'acupuncture points "
    "for migraine', 'Ayurvedic management of amavata', 'which herbs help anxiety', 'is turmeric "
    "effective for knee osteoarthritis', 'yoga for hypertension'.\n"
    "Set is_cam=false for a conventional medical question even if it mentions a supplement, diet, or "
    "lifestyle factor in passing — e.g. 'first-line drug for hypertension' (false), 'does metformin "
    "cause B12 deficiency' (false), 'is vitamin D deficiency linked to fatigue' (false unless framed as "
    "a naturopathic/CAM protocol). When genuinely unsure, prefer FALSE.\n"
    "Also set `system` to the closest CAM system when is_cam=true: 'acupuncture' (incl. acupressure), "
    "'ayurveda', 'herbal_mindbody' (herbal/naturopathy/homeopathy/mind-body/energy), or 'none'."
)
