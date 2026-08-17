"""Deterministic block splitter — domain-free.

Splits parsed text into Blocks on blank-line paragraph boundaries, tracking char
offsets and a heading-derived section_path (markdown `#` headings). Deterministic
and versioned so re-splitting the same text yields identical blocks (stable
content_key → cross-document dedup of identical passages).
"""
from __future__ import annotations

from noesis_kernel.corpus.models import Block
from noesis_kernel.ingestion.storage import content_key

# v2 (2026-08-17): sub-split any paragraph over MAX_BLOCK_CHARS. A single unsplit paragraph
# (a flattened table, a wall of text) could exceed the embedder's 8192-token hard limit and
# 400 the whole batch (the atrial-fibrillation ingest). This is the SOURCE fix; the embedder
# token clamp remains the safety net. Blocks under the cap are byte-identical to v1, so their
# content_key (sha256 of text) is unchanged and cross-document dedup is preserved — only
# pathologically-large blocks (which failed to embed before) change.
SPLITTER_VERSION = "para.v2"

# ~8000 chars ≈ 2000-2700 tokens even for dense medical text — comfortably under the 8192-token
# embed limit, and only pathologically-large paragraphs ever hit it (normal prose paragraphs are
# far smaller and pass through untouched, preserving their v1 content_key).
MAX_BLOCK_CHARS = 8000


def _slice_oversized(text: str, max_chars: int = MAX_BLOCK_CHARS) -> list[tuple[int, str]]:
    """Split an over-long block into <= max_chars slices at the best nearby boundary.

    Returns (offset_within_text, slice_text) pairs. Deterministic (same input → same slices)
    so the dedup contract holds. Prefers to break at a newline > sentence end > whitespace found
    in the back half of the window; falls back to a hard cut only if no boundary exists. Pure
    structural chunking, no semantic decision (Rule 18)."""
    if len(text) <= max_chars:
        return [(0, text)]
    out: list[tuple[int, str]] = []
    i, n = 0, len(text)
    while i < n:
        end = min(i + max_chars, n)
        if end < n:
            window = text[i:end]
            cut = max(window.rfind("\n"), window.rfind(". "), window.rfind(" "))
            if cut > max_chars * 0.5:        # only honor a boundary past the halfway point
                end = i + cut + 1
        piece = text[i:end]
        stripped = piece.strip()
        if stripped:
            out.append((i + piece.find(stripped), stripped))
        i = end
    return out


def _heading_level(line: str) -> int | None:
    s = line.lstrip()
    if s.startswith("#"):
        n = len(s) - len(s.lstrip("#"))
        if 1 <= n <= 6 and (len(s) == n or s[n] == " "):
            return n
    return None


def split(document_id: str, text: str, *, min_chars: int = 1) -> list[Block]:
    blocks: list[Block] = []
    section: list[str] = []          # current heading stack (titles)
    index = 0
    pos = 0
    n = len(text)

    # Walk paragraph chunks separated by blank lines, preserving offsets.
    while pos < n:
        # skip leading blank lines
        while pos < n and text[pos] == "\n":
            pos += 1
        if pos >= n:
            break
        start = pos
        # extend to the next blank line (\n\n) or EOF
        nl = text.find("\n\n", pos)
        end = n if nl == -1 else nl
        chunk = text[start:end]
        pos = end

        stripped = chunk.strip()
        if not stripped:
            continue

        # A chunk may be a heading, OR a heading immediately followed by body text
        # on the next line (well-formed markdown without a blank line between). Peel
        # any leading heading line off as a section marker; keep the body as a block.
        first_nl = stripped.find("\n")
        first_line = stripped if first_nl == -1 else stripped[:first_nl]
        lvl = _heading_level(first_line)
        if lvl is not None:
            title = first_line.lstrip("#").strip()
            section = section[: lvl - 1] + [title]   # update heading stack
            if first_nl == -1:
                continue                              # heading only, no body
            stripped = stripped[first_nl + 1:].strip()
            if not stripped:
                continue

        if len(stripped) < min_chars:
            continue

        # locate the (post-heading) block text within the original document
        block_pos = text.find(stripped, start)
        # sub-split pathologically-large paragraphs so no single block exceeds the embed limit;
        # normal paragraphs yield exactly one slice with identical text (stable content_key).
        for sub_off, sub_text in _slice_oversized(stripped):
            char_start = block_pos + sub_off
            char_end = char_start + len(sub_text)
            blocks.append(Block(
                document_id=document_id,
                index=index,
                content_key=content_key(sub_text.encode("utf-8")),
                text=sub_text,
                char_start=char_start,
                char_end=char_end,
                section_path=tuple(section),
            ))
            index += 1
    return blocks
