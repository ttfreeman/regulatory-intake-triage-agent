"""Node 2: Sanitization. Prompt injection detection and neutralization.

Complaint content is data provided by a member of the public, never an
instruction to the process (standing rule 5 in routing_rules.md). This module
detects embedded instruction-like content, strips it before it reaches any
LLM/heuristic step, and always records a security finding so the event is
visible in the trace, never silently honoured.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from src.models import SecurityFinding

# Zero-width/invisible characters used to obfuscate keywords (e.g. "o\u200bverride").
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")

INJECTION_PATTERNS = [
    r"ignore (all |any )?(prior|previous|the above)?\s*(instructions?|polic(?:y|ies)|rules?|protocol)",
    r"disregard (all |any )?(prior|previous)?\s*(instructions?|polic(?:y|ies)|rules?|protocol)",
    r"system notice",
    r"override",
    r"supersede",
    r"do not surface",
    r"do not escalate",
    r"close(d)? (this |the )?record[\s\S]{0,40}automatically",
    r"close automatically",
    r"automated (intake preprocessor|routing message|approval message|processing message)",
    r"no further action",
    r"output only",
    r"auto[- ]?approv",
    r"per internal directive",
    r"mark (this |the )?record[\s\S]{0,40}(low priority|approved|tier\s*\d)",
    r"delete (my |the |this |prior |previous )?(phone |previous )?(record|complaint|report)",
]

_DELIMITED_BLOCK_RE = re.compile(r"-{3,}.*?-{3,}", re.DOTALL)


def detect_and_sanitize(raw_text: str) -> Tuple[str, Optional[SecurityFinding]]:
    """Return (sanitized_text, finding_or_None)."""
    if not raw_text:
        return raw_text, None

    # Strip zero-width/invisible characters first so obfuscated keywords
    # (e.g. "o\u200bverride") are still caught by the patterns below.
    cleaned_text = _ZERO_WIDTH_RE.sub("", raw_text)

    matched: List[str] = []
    for pattern in INJECTION_PATTERNS:
        for m in re.finditer(pattern, cleaned_text, re.IGNORECASE):
            matched.append(m.group(0))

    # A delimited "BEGIN/END ... MESSAGE"-style block is itself a structural
    # red flag in public complaint text, even if no keyword pattern matched
    # inside it - legitimate submissions never arrive pre-formatted this way.
    block_match = _DELIMITED_BLOCK_RE.search(cleaned_text)
    if block_match:
        matched.append(block_match.group(0)[:60])

    if not matched:
        return raw_text, None

    sanitized = cleaned_text
    if block_match:
        sanitized = (
            cleaned_text[: block_match.start()]
            + "[REDACTED: possible prompt injection removed by sanitizer]"
            + cleaned_text[block_match.end() :]
        )
    else:
        for phrase in sorted(set(matched), key=len, reverse=True):
            sanitized = re.sub(re.escape(phrase), "[REDACTED]", sanitized, flags=re.IGNORECASE)

    finding = SecurityFinding(
        finding_type="prompt_injection",
        detail=(
            "Embedded instruction-like content detected in submitted text. "
            "Content was neutralized before extraction/classification; the "
            "record was still processed on its legitimate merits."
        ),
        matched_phrases=sorted({p.lower() for p in matched}),
    )
    return sanitized, finding
