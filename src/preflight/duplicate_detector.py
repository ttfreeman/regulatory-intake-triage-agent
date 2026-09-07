"""Preflight Component 3: Duplicate / repeat-contact detection.

Scores every record pair on shared contact details, shared operator, and
raw-text similarity. This is a review-priority signal, not a triage
decision - the validator's own repeat-contact linking (src/validator.py)
remains the source of truth for acknowledgment suppression during triage.

Uses shared scoring logic (src/util/duplicate_scoring.py) to ensure preflight
and triage never disagree about what constitutes a duplicate candidate.
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.util.duplicate_scoring import find_duplicate_candidates


def scan_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find all duplicate candidates in the batch. Returns sorted by score descending."""
    return find_duplicate_candidates(records)

