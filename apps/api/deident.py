"""De-identification for anonymous publication (Active Cases).

Removes DIRECT IDENTIFIERS from free text before a session is copied to a public, anonymous board:
explicit strings the caller knows (the attached patient name/ID, the asker's name and email), email
addresses, phone numbers, long identifier-like digit runs, labelled identifiers ("MRN 12345",
"ID: AB-9876"), full calendar dates (day-level; bare years and durations survive), and labelled
name/DOB lines. Ages, lab values, doses and years are clinical content and are kept.

This is a generic identifier scrubber — it knows nothing about any vertical's vocabulary. It cannot
recognise an unlabelled free-text name ("Mrs Smith came in…"); the UI says so and asks the publisher
to confirm the case text carries no names beyond what is removed here.
"""
from __future__ import annotations

import re
from typing import Any

REDACTED = "[redacted]"

_MONTH = (r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?")
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # e-mail addresses
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email]"),
    # labelled identifiers: MRN / ID / record number / account / NHS number / SSN …
    (re.compile(r"\b(?:mrn|medical record(?: number| no\.?)?|record(?: number| no\.?)|patient id|"
                r"chart(?: number| no\.?)|account(?: number| no\.?)|nhs(?: number| no\.?)?|ssn|"
                r"social security(?: number)?|passport(?: number| no\.?)?|id(?: number| no\.?)?)"
                r"\s*[:#]?\s*[A-Za-z0-9][A-Za-z0-9-]{2,}(?:\s\d{2,4}){0,3}", re.I), "[id]"),
    # long bare digit runs (identifiers), never short clinical values or years
    (re.compile(r"(?<![\d.,])\d{6,}(?![\d.,])"), "[id]"),
    # full calendar dates — numeric (dd/mm/yyyy, yyyy-mm-dd, mm/dd/yy)
    (re.compile(r"\b(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b"), "[date]"),
    # full calendar dates — worded ("March 5, 1962", "5 March 1962", "Mar 5th 2020")
    (re.compile(rf"\b(?:{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}|\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH},?\s+\d{{4}})\b",
                re.I), "[date]"),
    # labelled name / date-of-birth lines: "Name: John Smith", "Patient name — …", "DOB: …"
    (re.compile(r"(?im)^(\s*(?:patient(?:'s)?\s+)?(?:name|full name|surname|dob|date of birth|birth date)\s*[:\-—–]\s*).*$"),
     r"\g<1>" + REDACTED),
    (re.compile(r"\b(?:dob|date of birth)\s*[:\-—–]?\s*[^\s,;.]+(?:[\s/.-][^\s,;.]+){0,2}", re.I), "[date]"),
]

_STOP = {"the", "and", "for", "with", "from", "mr", "mrs", "ms", "dr", "miss", "patient", "case"}


def _identifier_tokens(identifiers: list[str] | None) -> list[str]:
    """The explicit identifier strings plus their individual tokens (≥ 3 chars, not stop words),
    longest first so whole strings are removed before their parts."""
    out: list[str] = []
    for ident in identifiers or []:
        s = (ident or "").strip()
        if not s:
            continue
        out.append(s)
        for tok in re.split(r"[\s/,;:|()#\-]+", s):
            tok = tok.strip()
            if len(tok) >= 3 and tok.lower() not in _STOP:
                out.append(tok)
    return sorted(set(out), key=lambda t: (-len(t), t))


# phone numbers: 2–5 groups of 2–4 digits joined by a separator (optional +country / (area)),
# 7–15 digits in all. Groups must be ≥ 2 digits, so a row of short clinical values ("140 4.0 100 24")
# never qualifies; a lone number is never a phone.
_PHONE = re.compile(r"(?<!\w)(?<!\d\.)\+?\(?\d{2,4}\)?(?:[\s.-]\(?\d{2,4}\)?){1,4}(?!\w|\.\d)")


def _phone_repl(m: re.Match[str]) -> str:
    digits = sum(c.isdigit() for c in m.group(0))
    return "[phone]" if 7 <= digits <= 15 else m.group(0)


def scrub_text(text: str, identifiers: list[str] | None = None) -> str:
    """Return `text` with direct identifiers replaced."""
    if not text:
        return text or ""
    s = text
    for tok in _identifier_tokens(identifiers):
        s = re.sub(r"(?<!\w)" + re.escape(tok) + r"(?!\w)", REDACTED, s, flags=re.I)
    for pat, repl in _PATTERNS:
        s = pat.sub(repl, s)
    s = _PHONE.sub(_phone_repl, s)
    return s


def scrub_value(value: Any, identifiers: list[str] | None = None) -> Any:
    """Recursively scrub every string inside a JSON-like value (dicts, lists, strings)."""
    if isinstance(value, str):
        return scrub_text(value, identifiers)
    if isinstance(value, list):
        return [scrub_value(v, identifiers) for v in value]
    if isinstance(value, dict):
        return {k: scrub_value(v, identifiers) for k, v in value.items()}
    return value


# Session fields that must never reach an anonymous copy: who asked, who owns it, what was attached,
# how it was routed. `thread` turns drop the same keys.
PRIVATE_KEYS = frozenset({
    "user_id", "user_name", "user_email", "tenant_id", "workspace_id", "share_token", "public",
    "published_at", "patient_ref", "real_patient", "attachments", "intake_transcript",
    "visual_observation", "video_filename", "video_title", "video_duration", "diagnostics",
})


def anonymous_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    """An identity-free, scrubbed copy of a stored session suitable for anonymous publication."""
    identifiers = [row.get("patient_ref") or "", row.get("user_name") or "", row.get("user_email") or ""]
    snap = {k: v for k, v in row.items() if k not in PRIVATE_KEYS and k not in ("id", "created_at")}
    snap["thread"] = [{k: v for k, v in (t or {}).items() if k not in PRIVATE_KEYS}
                      for t in (row.get("thread") or [])]
    return scrub_value(snap, identifiers)
