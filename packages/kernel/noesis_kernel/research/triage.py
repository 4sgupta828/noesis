"""Guided intake / triage — a short clarifying conversation that converges on a crisp, answerable
question, then RECOMMENDS a route (Quick Q&A vs Specialist Panel).

The triage agent is a QUERY-FORMULATION CLARIFIER, not an advisor: it asks the minimum questions
needed to make the eventual grounded answer high-quality, then hands off. It never diagnoses,
recommends treatment, or gives medical advice — it only narrows intent and routes.

Domain framing (what a "material" clarification is, the medical routing boundary, the safety
guardrails) lives in the vertical's `triage_prompt`; the kernel owns only the turn mechanics and the
structural convergence cap (code owns structure, the LLM owns meaning — Rule 18):
  - the LLM decides, each turn, whether it needs one more clarification (`status="ask"`) or has
    enough to route (`status="ready"`);
  - the CALLER counts turns and passes `force_ready=True` once the hard cap is reached, so the
    conversation can never become an interrogation.

Nothing here answers the medical question — a `ready` turn only produces a refined question + a route;
running it goes through the normal grounded loop, so the grounding invariant is untouched.
"""
from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from noesis_kernel.providers.llm import LLMClient

_log = logging.getLogger(__name__)


class TriageTurn(BaseModel):
    # "ask" → keep clarifying (message = the ONE next question); "ready" → route (refined_question set).
    status: Literal["ask", "ready"] = "ask"
    message: str = ""                        # the clarifying question, or a brief handoff note
    understood_problem: str = ""             # cumulative crisp restatement of the case / intent
    refined_question: str = ""               # standalone question to run (required when ready)
    recommended_mode: Literal["qa", "panel"] = "qa"
    rationale: str = ""                      # one line: why this route
    # Generic, non-diagnostic urgency flag — the FE can surface a "seek urgent evaluation" notice.
    # NOT a diagnosis; the model is told to set this only for plainly emergent presentations.
    safety: Literal["ok", "urgent"] = "ok"


def _last_user(transcript: list[dict]) -> str:
    for t in reversed(transcript or []):
        if (t.get("role") or "") == "user" and (t.get("text") or "").strip():
            return t["text"].strip()
    return ""


async def run_triage_turn(
    *, llm: LLMClient, triage_prompt: str, transcript: list[dict],
    roster_summary: str = "", force_ready: bool = False, max_tokens: int = 700,
) -> TriageTurn:
    """Run ONE triage turn over the running transcript ([{role:"user"|"assistant", text}]) and return a
    validated TriageTurn. Fail-safe: any error → route the last user message straight to Quick Q&A so the
    user is never stuck. `force_ready` (caller-enforced turn cap) coerces a route this turn."""
    msgs: list[dict] = []
    for t in (transcript or []):
        role = "assistant" if (t.get("role") == "assistant") else "user"
        text = (t.get("text") or "").strip()
        if text:
            msgs.append({"role": role, "content": text})
    if not msgs:
        return TriageTurn(status="ask", message="What clinical question can I help you narrow down?")
    if msgs[-1]["role"] != "user":
        # the conversation must end on the user's turn for the model to respond to
        msgs.append({"role": "user", "content": "(continue)"})
    if roster_summary:
        msgs.insert(0, {"role": "user", "content":
                        f"[Available specialist lenses for a panel: {roster_summary}]"})
    if force_ready:
        msgs.append({"role": "user", "content":
                     "[You have enough context. Return status=\"ready\" now with your best "
                     "refined_question and recommended_mode — do NOT ask another question.]"})
    try:
        comp = await llm.complete(
            system=triage_prompt, messages=msgs, response_format=TriageTurn, max_tokens=max_tokens)
        turn = comp.parsed
    except Exception as e:   # noqa: BLE001 — triage must never block the user
        _log.warning("triage turn failed: %r", e)
        return TriageTurn(status="ready", recommended_mode="qa", refined_question=_last_user(transcript),
                          understood_problem=_last_user(transcript),
                          message="Let me search the evidence for that.", rationale="fallback")
    if force_ready:
        turn.status = "ready"
    if turn.status == "ready" and not (turn.refined_question or "").strip():
        turn.refined_question = turn.understood_problem.strip() or _last_user(transcript)
    return turn
