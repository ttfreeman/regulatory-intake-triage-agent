"""Judge: does the final tier/route match the human-reviewed golden label?"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def evaluate(traces_by_id: Dict[str, Any], golden_records: List[Dict[str, Any]]) -> Tuple[int, int, List[Dict[str, Any]]]:
    passed = 0
    details: List[Dict[str, Any]] = []
    for g in golden_records:
        trace = traces_by_id.get(g["record_id"])
        ok = bool(trace) and trace["final_tier"] == g["expected_tier"] and trace["route"] == g["expected_route"]
        if ok:
            passed += 1
        details.append(
            {
                "record_id": g["record_id"],
                "passed": ok,
                "expected": {"tier": g["expected_tier"], "route": g["expected_route"]},
                "actual": {"tier": trace["final_tier"], "route": trace["route"]} if trace else None,
            }
        )
    return passed, len(golden_records), details
