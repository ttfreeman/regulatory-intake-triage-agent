"""Preflight Component 2: Data profiling."""

from __future__ import annotations

import statistics
from typing import Any, Dict, List


def profile_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    operator_counts: Dict[str, int] = {}
    channel_counts: Dict[str, int] = {}
    missing_location = 0
    missing_operator = 0
    missing_contact = 0
    lengths: List[int] = []
    longest = {"record_id": None, "length": 0}
    shortest = {"record_id": None, "length": None}

    for record in records:
        operator = record.get("operator_named")
        if isinstance(operator, list):
            operators = [
                name for name in operator if isinstance(name, str) and name.strip()
            ]
        elif isinstance(operator, str) and operator.strip():
            operators = [operator]
        else:
            operators = []

        if operators:
            for name in operators:
                operator_counts[name] = operator_counts.get(name, 0) + 1
        else:
            missing_operator += 1

        channel = record.get("channel") or "unknown"
        channel_counts[channel] = channel_counts.get(channel, 0) + 1

        if not record.get("location_text"):
            missing_location += 1

        reporter = record.get("reporter") or {}
        if not (reporter.get("email") or reporter.get("phone")):
            missing_contact += 1

        length = len(record.get("raw_text") or "")
        lengths.append(length)
        if length > longest["length"]:
            longest = {"record_id": record.get("record_id"), "length": length}
        if shortest["length"] is None or length < shortest["length"]:
            shortest = {"record_id": record.get("record_id"), "length": length}

    return {
        "records": len(records),
        "operators": len(operator_counts),
        "operator_distribution": operator_counts,
        "channel_distribution": channel_counts,
        "missing_fields": {
            "location_text": missing_location,
            "operator_named": missing_operator,
            "reporter_contact": missing_contact,
        },
        "contactability": {
            "with_contact": len(records) - missing_contact,
            "anonymous": missing_contact,
        },
        "avg_length": round(statistics.fmean(lengths), 1) if lengths else 0,
        "median_length": round(statistics.median(lengths), 1) if lengths else 0,
        "longest_record": longest,
        "shortest_record": shortest,
    }
