"""Per-run cost governor — domain-free.

Bounds a single research run's LLM spend (call count + optional token ceiling),
independent of the per-source WAF/rate breaker. The ReAct loop reserves before
each model call and charges after; a would-be over-budget call raises so a run
can't silently run away with credits (complements the provider-mode live guard).
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MAX_LLM_CALLS = 40


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class BudgetState:
    max_calls: int = DEFAULT_MAX_LLM_CALLS
    max_tokens: int | None = None
    spent_calls: int = 0
    spent_tokens: int = 0

    def remaining_calls(self) -> int:
        return max(0, self.max_calls - self.spent_calls)

    @property
    def exhausted(self) -> bool:
        if self.spent_calls >= self.max_calls:
            return True
        if self.max_tokens is not None and self.spent_tokens >= self.max_tokens:
            return True
        return False

    def reserve(self, calls: int = 1) -> None:
        """Raise BEFORE making a call that would breach the ceiling."""
        if self.spent_calls + calls > self.max_calls:
            raise BudgetExceeded(
                f"LLM call budget exhausted ({self.spent_calls}/{self.max_calls})")
        if self.max_tokens is not None and self.spent_tokens >= self.max_tokens:
            raise BudgetExceeded(
                f"LLM token budget exhausted ({self.spent_tokens}/{self.max_tokens})")

    def charge(self, *, calls: int = 1, tokens: int = 0) -> None:
        self.spent_calls += calls
        self.spent_tokens += tokens
