"""Shared duplicate record detection and scoring logic.

Used by both preflight (batch scoring for review priority) and triage
(exact-match linkage for procedural purposes). Centralizes the scoring
algorithm to ensure preflight and triage never disagree about what
constitutes a duplicate candidate.
"""

from __future__ import annotations

import re
from itertools import combinations
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from src.models import Reporter

# Scoring weights
SAME_PHONE = 40
SAME_EMAIL = 40
SAME_ADDRESS = 40
SAME_OPERATOR = 10
SIMILAR_TEXT = 20
DUPLICATE_THRESHOLD = 60

_WORD_RE = re.compile(r"[a-z']{4,}")
_STOPWORDS = {"this", "that", "with", "have", "there", "been", "will", "just"}


def _tokens(text: str) -> set[str]:
    """Extract significant words from text (4+ chars, excluding stopwords)."""
    words = _WORD_RE.findall((text or "").lower())
    return {w for w in words if w not in _STOPWORDS}


def _phone_digits(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[1:] if len(digits) == 11 and digits.startswith("1") else digits


def text_similarity(a: str, b: str) -> float:
    """Jaccard similarity of tokens between two text strings.

    Returns 0.0 if either text is empty or has no significant words.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def score_pair(
    record_a: Dict[str, Any], record_b: Dict[str, Any]
) -> tuple[int, List[str]]:
    """Score a pair of records for duplicate likelihood.

    Returns (score, reasons) where reasons is a list of matching criteria.
    """
    score = 0
    reasons: List[str] = []
    rep_a = record_a.get("reporter") or {}
    rep_b = record_b.get("reporter") or {}

    phone_a, phone_b = (
        _phone_digits(rep_a.get("phone")),
        _phone_digits(rep_b.get("phone")),
    )
    if phone_a and phone_b and phone_a == phone_b:
        score += SAME_PHONE
        reasons.append("same_phone")

    email_a, email_b = rep_a.get("email"), rep_b.get("email")
    if email_a and email_b and email_a == email_b:
        score += SAME_EMAIL
        reasons.append("same_email")

    addr_a, addr_b = rep_a.get("address"), rep_b.get("address")
    if addr_a and addr_b and addr_a == addr_b:
        score += SAME_ADDRESS
        reasons.append("same_address")

    op_a, op_b = record_a.get("operator_named"), record_b.get("operator_named")
    if op_a and op_b and op_a == op_b:
        score += SAME_OPERATOR
        reasons.append("same_operator")

    if (
        text_similarity(record_a.get("raw_text", ""), record_b.get("raw_text", ""))
        >= 0.2
    ):
        score += SIMILAR_TEXT
        reasons.append("similar_text")

    return score, reasons


def find_duplicate_candidates(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find all record pairs scoring >= DUPLICATE_THRESHOLD.

    Used by preflight for batch analysis and review prioritization.
    Sorted by score descending.
    """
    candidates: List[Dict[str, Any]] = []

    for r1, r2 in combinations(records, 2):
        score, reasons = score_pair(r1, r2)
        if score >= DUPLICATE_THRESHOLD:
            candidates.append(
                {
                    "record_a": r1["record_id"],
                    "record_b": r2["record_id"],
                    "score": score,
                    "reasons": reasons,
                }
            )

    return sorted(candidates, key=lambda c: c["score"], reverse=True)


def find_repeat_contact_exact(
    record: Dict[str, Any], duplicate_index: Dict[str, str]
) -> tuple[str | None, List[str]]:
    """Find exact reporter contact match in duplicate_index (within-run linkage).

    Used by triage validator for procedural repeat-contact linking.
    Returns (prior_record_id, reasons) or (None, []) if no match found.

    A record is considered a repeat contact if its reporter's phone, email,
    or address exactly matches a prior record in the same run.
    """
    reporter = record.get("reporter") or {}
    key = (
        reporter.get("address")
        or reporter.get("email")
        or _phone_digits(reporter.get("phone"))
    )

    if not key:
        return None, []

    prior = duplicate_index.get(key)
    if prior and prior != record.get("record_id"):
        return prior, ["exact_contact_match"]

    return None, []


def find_repeat_contact_from_extraction(
    record_id: str, reporter: Reporter, duplicate_index: Dict[str, str]
) -> tuple[str | None, List[str]]:
    """Find exact reporter contact match using extraction Reporter object.

    Used by triage validator for procedural repeat-contact linking.
    Returns (prior_record_id, reasons) or (None, []) if no match found.

    A record is considered a repeat contact if its reporter's phone, email,
    or address exactly matches a prior record in the same run.
    """
    key = (
        reporter.address
        or reporter.contact_email
        or _phone_digits(reporter.contact_phone)
    )

    if not key:
        return None, []

    prior = duplicate_index.get(key)
    if prior and prior != record_id:
        return prior, ["exact_contact_match"]

    return None, []
