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
