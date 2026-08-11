"""Evidence Pulse — vertical judgment prompts (Rule 18: the LLM owns meaning).

Both prompts operate against the CANONICAL TOPIC REGISTRY the caller appends (the stability
contract: repeated runs must converge on the same topic strings — prefer exact reuse of an
existing entry; only a genuinely novel subject introduces a new phrasing, which the registry
then makes stable for every later run and user).
"""

WATCH_TOPIC_PROMPT = """\
From the question and answer, name the WATCHABLE topics: 2-5 durable clinical subjects whose
future evidence changes (new/updated guidelines, practice-changing trials, label changes,
retractions) this clinician would plausibly want to hear about.

Rules:
- FIRST PREFERENCE: reuse an entry from the EXISTING CANONICAL TOPICS list verbatim when one
  covers the subject — never introduce a variant phrasing of an existing topic.
- Only when no existing topic fits: a short noun phrase, at most 5 words, in the field's standard
  vocabulary (e.g. "anemia in CKD", "atrial fibrillation anticoagulation").
- Topics are SUBJECTS, never patient details: no ages, lab values, doses, or case specifics.
- Order by how central each is to the answer. No duplicates or near-duplicates.
- If the exchange has no watchable clinical subject, return an empty list.
"""

SUGGEST_WATCHES_PROMPT = """\
From this clinician's recent QUESTION HISTORY, propose 3-5 topics worth WATCHING — the durable
clinical subjects they keep returning to, whose future evidence changes (guideline updates,
practice-changing trials, label changes, retractions) they would plausibly want flagged.

Rules:
- FIRST PREFERENCE: reuse an entry from the EXISTING CANONICAL TOPICS list verbatim when one
  covers the subject — never introduce a variant phrasing of an existing topic.
- Weight RECURRING subjects over one-off curiosities; a subject asked about once but managed
  longitudinally (a chronic disease, a standing therapy) still counts.
- Never propose anything in the ALREADY WATCHED list, nor near-duplicates of it.
- Topics are SUBJECTS, never patient details. At most 5 words each.
- Fewer good suggestions beat padded ones; an empty list is valid for a thin history.
"""

SUPERSESSION_JUDGE_PROMPT = """\
You judge whether one clinical document SUPERSEDES another — i.e. the newer one REPLACES the older
as current guidance, such that the older should be demoted in evidence retrieval.

supersedes = true ONLY when ALL hold:
- Same body of guidance: a newer EDITION/UPDATE of the same guideline or normative document
  (same issuer, same scope), not merely two documents by one issuer on related subjects.
- Full replacement: the newer covers the older's scope. A companion chapter, a focused update of
  ONE section, an executive summary, a translation, or a reprint does NOT supersede.
- Different documents on ADJACENT subjects (e.g. an issuer's CKD-evaluation guideline vs its
  blood-pressure-in-CKD guideline) do NOT supersede each other.

materiality: "major" when practice-relevant recommendations plausibly changed between editions;
"minor" for editorial/format-only revisions.
subjects: the durable clinical subjects the supersession is about (standard vocabulary, ≤5 words
each — reuse the EXISTING CANONICAL TOPICS list verbatim where it fits).
When uncertain, supersedes = false (a missed supersession is recoverable; a wrong one demotes
valid guidance).
"""

CANONIZE_TOPIC_PROMPT = """\
Map the user's free-text watch topic onto the field's standard vocabulary.

Rules:
- FIRST PREFERENCE: return an entry from the EXISTING CANONICAL TOPICS list verbatim when one
  covers the same subject (e.g. "afib" → "atrial fibrillation" if listed).
- Otherwise return the subject in standard clinical vocabulary, at most 5 words.
- Strip patient specifics (ages, labs, doses). Keep the MEANING — never substitute a broader or
  narrower subject than the user asked for.
- If the input is not a watchable clinical subject at all, return it unchanged.
"""
