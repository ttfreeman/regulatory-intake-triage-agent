"""Judge: is every classification grounded in retrieved, real directives?

Checks that (a) retrieval actually ran and returned at least one directive for
every tiered record, and (b) no directive ID appears anywhere in the output
that isn't one of the six real directives loaded into the vector store -
i.e. nothing was hallucinated.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

_KNOWN_DIRECTIVES = {"RD-101", "RD-114", "RD-127", "RD-133", "RD-146", "RD-158"}


def evaluate(traces_by_id: Dict[str, Any]) -> Tuple[int, int, List[Dict[str, Any]]]:
    passed = 0
    total = 0
    details: List[Dict[str, Any]] = []
    for record_id, trace in traces_by_id.items():
        total += 1
        ok = True
        reasons = []

        retrieved = [d["directive"] for d in trace["retrieved_directives"]]
        considered = trace["classification"]["directives_considered"]

        if trace["final_tier"] != "InsufficientInformation" and not retrieved:
            ok = False
            reasons.append("No directives retrieved before classification")

        hallucinated = [d for d in considered if d not in _KNOWN_DIRECTIVES]
        if hallucinated:
            ok = False
            reasons.append(f"Cited unknown directive(s): {hallucinated}")

        if ok:
            passed += 1
        details.append({"record_id": record_id, "passed": ok, "reasons": reasons})
    return passed, total, details
