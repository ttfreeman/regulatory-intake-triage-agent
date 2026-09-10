"""Node 9: Trace Generation. Builds and persists the execution trace for a record."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.models import (
    Acknowledgement,
    AuditSummary,
    ClassificationResult,
    DirectiveMatch,
    ExtractionResult,
    RoutingResult,
    SecurityFinding,
    ValidatorResult,
)


def execution_event(
    stage: str,
    summary: str,
    decision_source: str = "deterministic",
    **details: Any,
) -> Dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "status": "completed",
        "summary": summary,
        "decision_source": decision_source,
        **details,
    }


def build_trace(
    record_id: str,
    directive_matches: List[DirectiveMatch],
    extraction: ExtractionResult,
    classification: ClassificationResult,
    validator_result: ValidatorResult,
    routing_result: RoutingResult,
    acknowledgement: Acknowledgement,
    security_findings: List[SecurityFinding],
    execution_log: List[Dict[str, Any]],
    audit_summary: AuditSummary,
) -> Dict[str, Any]:
    return {
        "record_id": record_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "retrieved_directives": [m.model_dump() for m in directive_matches],
        "extraction": extraction.model_dump(),
        "classification": classification.model_dump(),
        "validator_overrides": [o.model_dump() for o in validator_result.overrides],
        "reclassified": validator_result.reclassified,
        "final_tier": validator_result.final_tier.value,
        "route": routing_result.route.value,
        "human_gate": routing_result.human_gate.model_dump(),
        "acknowledgement": acknowledgement.model_dump(),
        "security_findings": [f.model_dump() for f in security_findings],
        "execution_log": execution_log,
        "audit_summary": audit_summary.model_dump(),
    }


def write_trace(trace: Dict[str, Any], traces_dir: str | Path) -> Path:
    traces_dir = Path(traces_dir)
    traces_dir.mkdir(parents=True, exist_ok=True)
    path = traces_dir / f"{trace['record_id']}.json"
    suffix = 2
    while path.exists():
        path = traces_dir / f"{trace['record_id']}-{suffix}.json"
        suffix += 1
    path.write_text(json.dumps(trace, indent=2), encoding="utf-8")
    return path
