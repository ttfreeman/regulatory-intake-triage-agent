"""Preflight Component 5: Sensitive data (PII) detection.

Flags records that likely contain health information, minors, or contact
details that need extra care in review - a signal for reviewers, not a
classification. Kept independent of src/extract.py's keyword lists so this
module stays usable standalone ahead of the full triage pipeline.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

MINOR_KEYWORDS = [
    "my daughter", "my son", "years old", "year old", "she is 1", "he is 1", "my child",
]
MEDICAL_KEYWORDS = [
    "respirologist", "clinic", "diagnosis", "prescri", "medical", "symptom log",
    "rescue inhaler", "health card",
]
_HEALTH_CARD_RE = re.compile(r"health card number", re.IGNORECASE)


def detect_pii(record: Dict[str, Any]) -> Dict[str, Any]:
    text = (record.get("raw_text") or "").lower()
    signals: List[str] = []

    if any(kw in text for kw in MINOR_KEYWORDS):
        signals.append("minor")
    if any(kw in text for kw in MEDICAL_KEYWORDS) or _HEALTH_CARD_RE.search(text):
        signals.append("medical_info")

    reporter = record.get("reporter") or {}
    if reporter.get("address"):
        signals.append("address")
    if reporter.get("phone"):
        signals.append("phone_number")

    return {
        "record_id": record["record_id"],
        "sensitive_data": bool(signals),
        "signals": signals,
    }


def scan_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [detect_pii(r) for r in records]
