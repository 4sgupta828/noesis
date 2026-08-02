"""Vision pre-step — turn user-uploaded image(s) into a LABELED visual observation.

Epistemic contract (why this is safe): the observation is a DESCRIPTIVE reading of a
user's image (color, shape, borders, texture, distribution) produced by the vertical's
`vision_prompt`. It is NEVER corpus-grounded and NEVER a verified claim — it only frames
what the research agent should search for and how to interpret findings. The kernel keeps
it strictly separate from the compose step (which sees only span-verified findings), so it
can never leak into the answer as if it were evidence.

The domain wording (what to describe, and the "do not diagnose" guardrail) lives in the
vertical's `vision_prompt`; the kernel owns only the mechanics.
"""
from __future__ import annotations

from pydantic import BaseModel

from noesis_kernel.providers.llm import LLMClient
from noesis_kernel.research.budget import BudgetState


class VisualObservation(BaseModel):
    """A descriptive reading of the uploaded image(s). NOT a diagnosis, NOT evidence."""
    observation: str


# A kernel-side guardrail appended to every vision system prompt, independent of vertical.
_GUARD = (
    "\n\nYou are describing a user-provided image to help a downstream search over an "
    "evidence corpus. Describe ONLY what is visually present (colors, shapes, borders, "
    "texture, distribution, counts, measurable features). Do NOT name a diagnosis, disease, "
    "or condition, and do NOT recommend treatment. If the image is unclear or not "
    "interpretable, say so plainly. This description is an automated aid, not a clinical "
    "finding."
)


async def observe_images(
    *,
    llm: LLMClient,
    vision_prompt: str,
    images: list[dict],
    budget: BudgetState,
    max_images: int = 4,
) -> str:
    """Return a labeled descriptive observation of `images`, or "" if none/failed.

    `images` are dicts {media_type, data} where data is base64 (already normalized to a
    vision-capable image type by the caller). The call rides as Anthropic content blocks
    (text + image), which the LLM port passes straight through.
    """
    imgs = [im for im in (images or []) if im.get("data") and im.get("media_type")][:max_images]
    if not imgs:
        return ""
    content: list[dict] = [{
        "type": "text",
        "text": "Describe the following image(s) per your instructions.",
    }]
    for im in imgs:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": im["media_type"], "data": im["data"]},
        })
    res = await llm.complete(
        system=vision_prompt + _GUARD,
        messages=[{"role": "user", "content": content}],
        response_format=VisualObservation,
        max_tokens=1024,
    )
    budget.charge(calls=1, tokens=res.output_tokens)
    return (res.parsed.observation or "").strip()
