"""Node 1: Ingest. Load and normalize raw intake records from JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _normalize_received_utc(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        value = value.strip()
        if value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc).isoformat()
            except ValueError:
                pass
    return ""


def _normalize_raw_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


def load_records(path: str | Path) -> List[Dict[str, Any]]:
    """Load intake records and normalize inconsistent field shapes.

    Accepts either the repository shape ({"records": [...]}) or a bare JSON
    list of records for convenient use with unseen interview inputs.

    Normalizes three common variabilities:
    - reporter: dict, string, or null → always dict
    - operator_named: string, list, or null → always string or None
    - location_text: string or null → always string or None
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
    normalized: List[Dict[str, Any]] = []
    for index, raw in enumerate(raw_records, start=1):
        record = dict(raw)

        record_id = record.get("record_id")
        if record_id is None or not str(record_id).strip():
            record["record_id"] = f"generated-{index}"
        else:
            record["record_id"] = str(record_id).strip()

        # Normalize reporter: dict | string | null → dict
        reporter = record.get("reporter")
        if isinstance(reporter, dict):
            record["reporter"] = reporter
        elif isinstance(reporter, str) and reporter.strip():
            record["reporter"] = {"name": reporter.strip()}
        else:
            record["reporter"] = {}

        # Normalize operator_named: string | list | null → string or None
        operator = record.get("operator_named")
        if isinstance(operator, list):
            # Take first operator if list; prefer named over others
            record["operator_named"] = next(
                (o for o in operator if isinstance(o, str) and o.strip()), None
            )
        elif isinstance(operator, str) and not operator.strip():
            record["operator_named"] = None
        # else: keep as-is (string or None)

        # Normalize location_text: always string or None
        location = record.get("location_text")
        if isinstance(location, str) and location.strip():
            record["location_text"] = location.strip()
        else:
            record["location_text"] = None

        record["raw_text"] = _normalize_raw_text(record.get("raw_text"))
        record["received_utc"] = _normalize_received_utc(record.get("received_utc"))
        normalized.append(record)
    return normalized
