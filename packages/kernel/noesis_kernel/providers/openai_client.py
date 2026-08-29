"""OpenAILLMClient — an OpenAI-protocol `LLMClient` (providers/llm.py) usable against ANY
OpenAI-compatible endpoint, notably **DeepSeek** (https://api.deepseek.com is OpenAI-compatible via
`base_url`). This is the provider seam that lets noesis swap its drafting/judging model family away
from Anthropic — mirrors eigen's provider swap.

Structured output: Anthropic's client (anthropic_llm.py) forces a tool-call `emit`; OpenAI/DeepSeek
instead use `response_format`. We try OpenAI's `json_schema` mode first (strict=False so a partial/
defaulted object still parses), then fall back ONCE to plain `json_object` mode with the schema
described in the system prompt — because DeepSeek's OpenAI-compat surface supports `json_object` but
not (reliably) `json_schema`. This makes the same client work for both OpenAI and DeepSeek.

Conventions matched from anthropic_llm.py so the rest of the system is unchanged:
  * appends to LLM_CALL_LOG (the diagnostics-trace contextvar) per call,
  * returns the same `LLMResult` shape (parsed + token counts + latency + model),
  * reuses `_recover_stringified` to salvage the model-stringified-a-container quirk.
"""
from __future__ import annotations

import json
import os
import time
from decimal import Decimal

from pydantic import BaseModel, ValidationError

from .anthropic_llm import LLM_CALL_LOG, _recover_stringified
from .llm import LLMResult

# Default model when the provider is OpenAI-compatible. DeepSeek's chat model is "deepseek-chat"
# (V3); its reasoning model is "deepseek-reasoner" (R1). NOESIS_LLM_MODEL overrides.
DEFAULT_MODEL = "deepseek-chat"


class OpenAILLMClient:
    def __init__(self, *, model: str | None = None, api_key: str | None = None,
                 base_url: str | None = None):
        self._model = model or os.environ.get("NOESIS_LLM_MODEL", DEFAULT_MODEL)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        # base_url targets any OpenAI-compatible endpoint (DeepSeek). None → OpenAI's default.
        self._base_url = base_url or os.environ.get("NOESIS_OPENAI_BASE_URL") or None
        self._client = None

    def _ensure(self) -> None:
        if self._client is None:
            from openai import AsyncOpenAI   # lazy, optional dep (already used for embeddings)
            kw: dict = {}
            if self._api_key:
                kw["api_key"] = self._api_key
            if self._base_url:
                kw["base_url"] = self._base_url
            self._client = AsyncOpenAI(**kw)

    def _parse(self, content: str | None, response_format: type[BaseModel]) -> BaseModel:
        obj = json.loads(content or "")
        try:
            return response_format.model_validate(obj)
        except ValidationError:
            # same quirk anthropic_llm handles: a container field (or the whole object) came back as a
            # JSON *string* — recover rather than fail-safe an otherwise-correct answer.
            recovered = _recover_stringified(obj, response_format)
            if recovered is None:
                raise
            return recovered

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
        assert self._client is not None
        # OpenAI keeps `system` as a role in the messages list; fold any system-role turns into it
        # (mirror anthropic_llm) and keep only user/assistant turns as the conversation.
        sys_parts = [system] + [m["content"] for m in messages if m.get("role") == "system"]
        system_text = "\n\n".join(p for p in sys_parts if p)
        convo = [{"role": m["role"], "content": m["content"]}
                 for m in messages if m.get("role") in ("user", "assistant")]

        schema = response_format.model_json_schema()
        base_messages = ([{"role": "system", "content": system_text}] if system_text else []) + convo
        common: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            **({"temperature": temperature} if temperature is not None else {}),
        }

        _t0 = time.perf_counter()
        resp = None
        try:
            # Primary: OpenAI structured output via json_schema (non-strict → defaulted/partial parses).
            resp = await self._client.chat.completions.create(
                messages=base_messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": response_format.__name__, "schema": schema, "strict": False},
                },
                **common,
            )
            parsed = self._parse(resp.choices[0].message.content, response_format)
        except Exception:
            # Fallback: DeepSeek (and older models) reject json_schema — retry ONCE in plain json_object
            # mode with the schema DESCRIBED in the system prompt.
            fallback_system = (system_text
                               + "\n\nReturn ONLY a single JSON object that conforms to this JSON Schema:\n"
                               + json.dumps(schema))
            fb_messages = [{"role": "system", "content": fallback_system}] + convo
            resp = await self._client.chat.completions.create(
                messages=fb_messages,
                response_format={"type": "json_object"},
                **common,
            )
            parsed = self._parse(resp.choices[0].message.content, response_format)

        _ms = int((time.perf_counter() - _t0) * 1000)
        usage = getattr(resp, "usage", None)
        in_tok = (getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        out_tok = (getattr(usage, "completion_tokens", 0) or 0) if usage else 0
        _log = LLM_CALL_LOG.get()
        if _log is not None:
            _log.append({"model": self._model, "max_tokens": max_tokens, "ms": _ms,
                         "in": in_tok, "out": out_tok})
        return LLMResult(
            parsed=parsed,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=Decimal(0),   # priced by the caller's cost governor if needed
            latency_ms=_ms,
            model=self._model,
        )
