"""AnthropicLLM — a real LLMClient (structured output via forced tool-use).

Anthropic has no JSON mode; the robust pattern is a single tool whose input_schema
IS the response_format, with tool_choice forcing it — so the model must return a
schema-valid object. Lazy-imports the SDK (optional dep). Wrap in CassetteLLM so
dev/CI/eval replay for free; this only spends credits in record/live mode.
"""
from __future__ import annotations

import os
from decimal import Decimal

from pydantic import BaseModel

from .llm import LLMResult

DEFAULT_MODEL = os.environ.get("NOESIS_LLM_MODEL", "claude-sonnet-5")


class AnthropicLLM:
    def __init__(self, *, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self._model = model
        self._api_key = api_key
        self._client = None

    def _ensure(self) -> None:
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key) if self._api_key \
                else anthropic.Anthropic()

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        response_format: type[BaseModel],
        max_tokens: int = 2048,
        temperature: float | None = None,
    ) -> LLMResult:
        self._ensure()
        # Anthropic keeps `system` separate; fold any system-role turns into it.
        sys_parts = [system] + [m["content"] for m in messages if m.get("role") == "system"]
        convo = [{"role": m["role"], "content": m["content"]}
                 for m in messages if m.get("role") in ("user", "assistant")]

        tool = {
            "name": "emit",
            "description": "Emit the structured result for this step.",
            "input_schema": response_format.model_json_schema(),
        }
        import asyncio
        # The Anthropic SDK client here is SYNCHRONOUS; run it off the event loop so a research
        # request's LLM round-trip doesn't block the whole API (and SSE heartbeats can flush).
        resp = await asyncio.to_thread(
            lambda: self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system="\n\n".join(p for p in sys_parts if p),
                messages=convo,
                tools=[tool],
                tool_choice={"type": "tool", "name": "emit"},
                **({"temperature": temperature} if temperature is not None else {}),
            ))
        # A max_tokens cutoff truncates the emit tool-call mid-JSON, so block.input is a partial dict
        # that fails schema validation with an opaque pydantic error. Surface the REAL cause instead
        # (Rule 13) so the fix is "raise max_tokens", not a wild goose chase.
        if getattr(resp, "stop_reason", None) == "max_tokens":
            raise RuntimeError(
                f"Anthropic structured output truncated: hit max_tokens={max_tokens} before the "
                f"'{response_format.__name__}' emit call completed — raise max_tokens for this call.")
        parsed = None
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "emit":
                parsed = response_format.model_validate(block.input)
                break
        if parsed is None:
            raise RuntimeError("Anthropic response contained no 'emit' tool_use block")

        return LLMResult(
            parsed=parsed,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cost_usd=Decimal(0),   # priced by the caller's cost governor if needed
            model=self._model,
        )
