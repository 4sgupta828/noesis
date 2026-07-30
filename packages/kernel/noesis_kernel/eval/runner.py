"""Eval runner — run the vertical's held-out gold through the agent and score it.

Ties the (generic) qa scorer to a vertical's eval_gold. Decoupled from the runtime
(takes an `ask` callable) so it doesn't drag in providers. Run it in `replay` for
free (against captured cassettes) as a CI gate; the one-time baseline is a `record`
run — the single budgeted-credit action.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from noesis_kernel.eval.qa_scoring import QaAnswer, QaCase, QaClaim, QaScore, score_qa
from noesis_kernel.research.react import AnswerResult

AskFn = Callable[..., Awaitable[AnswerResult]]


def _answer_from_result(res: AnswerResult) -> QaAnswer:
    return QaAnswer(
        prose=" ".join(f"{c.text} {c.quote}" for c in res.verified_claims),
        refused=not res.grounded,
        claims=tuple(
            QaClaim(text=c.text, verified=True,
                    citation_facets={"source_class": c.source_key} if c.source_key else {})
            for c in res.verified_claims
        ),
    )


def _case_from_gold(case_id: str, spec: dict) -> QaCase:
    return QaCase(
        id=case_id,
        expect_kind=spec.get("expect", "value"),
        expected_values=tuple(spec.get("expected_values", ())),
        forbidden_values=tuple(spec.get("forbidden_values", ())),
        required_phrases=tuple(spec.get("required_phrases", ())),
    )


async def run_qa_eval(ask: AskFn, gold: dict, *, tenant_id: str,
                      source_keys: list[str] | None = None) -> dict[str, QaScore]:
    scores: dict[str, QaScore] = {}
    for case_id, spec in gold.items():
        res = await ask(question=spec["question"], tenant_id=tenant_id, source_keys=source_keys)
        scores[case_id] = score_qa(_case_from_gold(case_id, spec), _answer_from_result(res))
    return scores


def summarize(scores: dict[str, QaScore]) -> dict:
    total = len(scores) or 1
    passed = sum(1 for s in scores.values() if s.fully_correct)
    return {"passed": passed, "total": len(scores), "pass_rate": passed / total,
            "failing": [cid for cid, s in scores.items() if not s.fully_correct]}
