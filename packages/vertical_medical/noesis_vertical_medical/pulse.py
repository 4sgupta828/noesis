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

CHANGE_BRIEF_PROMPT = """\
An item in the evidence corpus has changed (a paper retracted, a guideline replaced by a newer
edition, or a drug label amended). Write a short brief for a clinician explaining the change,
grounded ENTIRELY in the numbered SOURCE BLOCKS provided.

Produce two things:
- `brief_md`: the brief as short markdown, using up to three LABELLED parts (omit any that don't
  apply):
    • **What changed** — the concrete change (e.g. this paper was retracted; this guideline was
      replaced by a newer edition).
    • **What it means for practice** — the practical consequence for a clinician.
    • **What it replaced** — for a replacement, the prior source and what it said.
- `claims`: one entry per factual sentence in the brief, each carrying the `block_id` it came from
  and a `quote` copied VERBATIM — character for character — from THAT block.

HARD RULES:
- Every factual sentence in `brief_md` MUST be backed by a claim whose `quote` is an exact,
  verbatim span from one of the numbered blocks. No paraphrasing inside a quote.
- State nothing the blocks don't directly support. If the blocks only show THAT something changed
  and not why, say only that — a partial brief is correct.
- No dosing advice or recommendations beyond what a block literally states.
- If the blocks support no grounded statement, return an empty `brief_md` and an empty `claims`.
"""
