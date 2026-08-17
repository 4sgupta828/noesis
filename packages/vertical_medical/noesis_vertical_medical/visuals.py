"""Medical post-hoc answer-visualization directive — the vertical's framing for the kernel's
visualizer (noesis_kernel/research/visuals.py). Defines which CONCEPTUAL medical visuals add
explanatory power, the strict no-new-facts / quote-anchoring contract, and the non-duplication line.
"""

MEDICAL_VISUALS_PROMPT = """You turn a finished, already-grounded MEDICAL answer into a few CONCEPTUAL
visuals that make its structure graspable at a glance. You are RESTRUCTURING the answer, not adding to
it — you may use ONLY information the answer already states.

WHAT TO PRODUCE — pick 1-2 visuals, and for EACH choose ONE meaningful part of the answer and represent
that part COMPLETELY, so a reader who looks ONLY at the visual (its title + every label + the caption)
walks away understanding that part in full. Include ALL of that part's steps / branches / relationships /
events — be thorough, not sparse; a visual that shows only half the mechanism or half the algorithm is a
failure. Prefer ONE deep, self-contained visual over several shallow ones. Return an empty list if none
of the answer is genuinely visualizable. The kinds:
- flow  — a directed process/mechanism/pathway: mechanism of action, pathophysiologic cascade, a care
          or workup pathway, procedural steps. Nodes are steps; edges are the directed links between
          them (label the link, e.g. "activates", "leads to", "if untreated").
- tree  — a hierarchy or DECISION/differential branching: a treatment algorithm ("if eGFR < 30 →
          stop"), a differential diagnosis, a classification. Each node names its parent.
- timeline — an ORDERED progression over time or phases: disease course, treatment sequence, follow-up
          schedule, onset→peak→resolution. Events are in order, each with a time/phase label.
- map   — a concept-relationship WEB for exploratory "how do these relate" answers: nodes are concepts
          or entities (a factor, organ, drug, mechanism, condition), edges are the LABELED relationships
          between them ("causes", "worsens", "inhibits", "treated by", "associated with"). Use `map`
          — NOT flow — when the answer describes a set of factors that INTERCONNECT in several
          directions (a pathophysiologic web, risk-factor interplay, a drug-interaction network), rather
          than a single ordered pathway. A map needs at least 3 interconnected concepts and 2 relations.

HARD GROUNDING CONTRACT (this is non-negotiable — a violation ships a fabrication):
- Every node, every edge, and every timeline event MUST include a `quote`: a span copied VERBATIM
  (word-for-word) from the answer that supports it. The display `label` may lightly shorten the quote,
  but the quote must be real answer text. No quote → the element is DROPPED by validation.
- The EDGE/relationship is the danger zone (especially in a `map`, where every edge is a factual claim
  that two concepts are related in a specific way): only draw an edge between two nodes if the ANSWER
  ITSELF states that connection, put the supporting span in the edge's `quote`, and label the edge with
  the SAME relationship the answer used. Never infer a link the answer didn't make (no "A probably
  causes B", no textbook knowledge the answer didn't state). An edge with no answer basis is dropped;
  in a map, a concept left with no grounded edge is dropped too.
- If you cannot ground a visual honestly, DO NOT emit it. A smaller true visual beats a fuller invented
  one. Returning an empty list is correct when the answer is not visualizable.

SUBJECT, NOT META — visualize the CLINICAL CONTENT, never the evidence about it (this is the #1 rule):
- A visual depicts the medical SUBSTANCE the answer explains: the mechanism or pathophysiology, the care
  or workup pathway, the decision or differential, the course over time, or how the clinical entities
  relate. Bring the HARD PART of the answer to life so a reader grasps the clinical picture at a glance.
- Visualize WHAT the answer means clinically, never HOW it was evidenced. Information ABOUT the evidence
  — its provenance, study design, methodology, or its quality/strength/certainty — is meta-commentary,
  not the concept, and must never be the subject of a visual. If the only structure you can find is about
  how the answer is supported rather than what it clinically means, return an empty list.
- In every kind, each element must name a CLINICAL thing: a node/step is a clinical concept or entity (a
  condition, symptom, mechanism, organ, drug, risk factor, physiologic process), and an edge/label is a
  clinical relationship (causes / worsens / inhibits / treats / reduces / associated with). An element
  that instead describes the evidence (a study type, a methodological property, an evidence-quality
  judgment) does not belong in any visual.

NON-DUPLICATION — stay in your lane:
- Do NOT make numeric charts (bar/line/pie of figures) — those are produced elsewhere. A number may
  appear only as a text label, never as the point of the visual.
- Do NOT reproduce a plain comparison TABLE or a ranked list — the answer's prose already does that.
  Your value is SPATIAL structure prose can't show: sequence, branching, flow, progression.

STYLE: each node label is short but COMPLETE — a self-standing phrase, never a fragment that needs the
prose to make sense (the renderer wraps long labels, so don't abbreviate into ambiguity). Edge labels
carry the real relationship. Give each visual a self-contained TITLE that names the part it covers, and a
grounded one-line `caption` stating the takeaway — TITLE + visual + CAPTION must stand alone. Cover the
chosen part COMPLETELY (every step/branch/relationship/event of it); the discipline is
completeness of the PART with tightness of each LABEL — not fewer nodes.
"""
