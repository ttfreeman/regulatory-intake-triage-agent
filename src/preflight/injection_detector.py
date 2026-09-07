"""Preflight Component 4: Prompt injection detection.

Reuses the same sanitizer the triage pipeline uses (src/sanitize.py) so
preflight and triage never disagree about what counts as an injection
attempt - this component only reports the finding, it doesn't neutralize
anything (triage's sanitize step still runs its own pass later).
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.sanitize import detect_and_sanitize


def detect_injection(record: Dict[str, Any]) -> Dict[str, Any]:
    _, finding = detect_and_sanitize(record.get("raw_text", ""))
    return {
        "record_id": record["record_id"],
        "injection_detected": finding is not None,
        "detail": finding.detail if finding else None,
    }


def scan_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [detect_injection(r) for r in records]
