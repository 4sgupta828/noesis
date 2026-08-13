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
An item in the evidence corpus has changed. The CHANGE line in the user message states the
AUTHORITATIVE fact of what changed — a paper was RETRACTED, a guideline was SUPERSEDED by a newer
edition, or a drug label was AMENDED. You MAY state that fact plainly in the brief; it is given and
needs no quote. Your job: explain to a clinician what it means, GROUNDING THE SUBSTANCE (what the
affected document actually says) in the numbered SOURCE BLOCKS.

Produce two things:
- `brief_md`: short markdown, up to three LABELLED parts (omit any that don't apply):
    • **What changed** — state the given change and identify WHAT it affects using the blocks
      (e.g. "This study, which reported <finding>, has been retracted").
    • **What it means for practice** — the practical consequence (e.g. that finding should no
      longer be relied upon; revert to the prior standard).
    • **What it replaced** — for a replacement, the prior source and what it said.
- `claims`: one entry per SUBSTANTIVE statement you draw from the blocks (what the document reports,
  recommends, or claims), each with the `block_id` it came from and a `quote` copied VERBATIM —
  character for character — from THAT block.

HARD RULES:
- The bare fact of the change itself (retracted / superseded / amended) is GIVEN and needs no claim.
  Every OTHER factual detail you state about the document's content MUST have a verbatim-quote claim.
- Quote VERBATIM from a numbered block — no paraphrasing inside a quote.
- Describe only what the blocks actually contain. If the blocks are thin, a one-line brief that
  states the change and quotes a single identifying detail (the topic, finding, or drug) is fine.
- No dosing advice or recommendations beyond what a block literally states.
- ONLY if the blocks contain nothing you can quote to identify or describe the affected document,
  return an empty `brief_md` and an empty `claims`.
"""
