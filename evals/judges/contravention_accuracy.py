"""Judge: internal consistency of the contravention assessment.

There is no independently hand-labeled contravention dataset for this
synthetic exercise, so this judge checks structural invariants that must
always hold regardless of which record is being scored:
  - A compliant self-report (RecordsOnly) must never be marked as a
    suspected contravention (RD-101.3 explicitly frames it as compliant).
  - Any Tier1 or Tier2 record must carry a non-empty rationale explaining
    why (auditability requirement).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def evaluate(traces_by_id: Dict[str, Any]) -> Tuple[int, int, List[Dict[str, Any]]]:
    passed = 0
    total = 0
    details: List[Dict[str, Any]] = []
    for record_id, trace in traces_by_id.items():
        total += 1
        ok = True
        reasons = []

        if trace["route"] == "RecordsOnly" and trace["classification"]["contravention_suspected"]:
            ok = False
            reasons.append("RecordsOnly record incorrectly marked as a suspected contravention")

        if trace["final_tier"] in ("Tier1", "Tier2") and not trace["classification"]["contravention_assessment"].strip():
            ok = False
            reasons.append("Tier1/Tier2 record missing a contravention assessment rationale")

        if ok:
            passed += 1
        details.append({"record_id": record_id, "passed": ok, "reasons": reasons})
    return passed, total, details
