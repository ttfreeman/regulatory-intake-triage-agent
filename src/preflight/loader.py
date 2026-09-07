"""Preflight Component 1: Schema validation.

Loads records (reusing the same normalization as the triage pipeline) and
flags malformed records before any analysis runs. This never rejects a
record outright - it downgrades to WARN/HOLD status so the report stays
useful even against a messy, unseen dataset.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.ingest import load_records

VALID_CHANNELS = {"web_form", "phone_transcript", "email"}


def load_and_validate(
    path: str | Path,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (records, schema_results). Records are normalized as usual;
    schema_results is a per-record list of {record_id, status, issues}.

    Validation happens BEFORE normalization to catch malformed fields.
    """
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        raw_records = payload
    elif isinstance(payload, dict):
        raw_records = payload.get("records", [])
    else:
        raise ValueError(
            "Intake JSON must be a record list or an object with a 'records' list"
        )
    # Validate raw (pre-normalized) records
    schema_results = validate_schema_raw(raw_records)

    # Then normalize
    records = load_records(path)
    return records, schema_results


def validate_schema_raw(raw_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate raw records BEFORE normalization, catching malformed fields."""
    results: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for record in raw_records:
        issues: List[str] = []
        record_id = record.get("record_id")

        if not record_id:
            issues.append("missing_record_id")
        elif record_id in seen_ids:
            issues.append("duplicate_record_id")
        else:
            seen_ids.add(record_id)

        if not record.get("raw_text"):
            issues.append("missing_raw_text")
        if not record.get("received_utc"):
            issues.append("missing_received_date")
        if record.get("channel") not in VALID_CHANNELS:
            issues.append("invalid_channel")

        # Check reporter BEFORE normalization
        reporter = record.get("reporter")
        if not isinstance(reporter, dict):
            if reporter == "":
                issues.append("malformed_reporter_empty_string")
            elif reporter is None:
                issues.append("malformed_reporter_null")
            else:
                issues.append("malformed_reporter_unexpected_type")

        if not record.get("location_text"):
            issues.append("missing_location")

        # Check operator_named variability (before normalization)
        operator = record.get("operator_named")
        if operator and not isinstance(operator, (str, list)):
            issues.append("operator_named_unexpected_type")
        if isinstance(operator, list) and len(operator) > 1:
            issues.append("operator_named_is_list_multiple_operators")
        if isinstance(operator, str) and not operator.strip():
            issues.append("operator_named_empty_string")

        # Ingest generates IDs and trace persistence disambiguates duplicates.
        # Keep these visible as warnings without blocking the whole batch.
        if issues:
            status = "WARN"
        else:
            status = "OK"

        results.append(
            {"record_id": record_id or "UNKNOWN", "status": status, "issues": issues}
        )

    return results
