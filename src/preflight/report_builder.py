"""Preflight report assembly: manifest, human-attention forecast, and the
full report dict consumed by the HTML dashboard.

`human_attention_forecast` is deliberately NOT a severity/risk/tier signal -
it is only a review-priority pointer for a human, per the module's design
principles (it must never substitute for triage).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.llm import LLMClient
from src.preflight.analyzer import generate_narrative
from src.preflight.clustering import cluster_records
from src.preflight.duplicate_detector import find_duplicate_candidates
from src.preflight.injection_detector import scan_records as scan_injections
from src.preflight.loader import load_and_validate
from src.preflight.pii_detector import scan_records as scan_pii
from src.preflight.profiler import profile_records
from src.trace import execution_event


def build_human_attention_forecast(
    security_findings: List[Dict[str, Any]],
    pii_findings: List[Dict[str, Any]],
    duplicates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    high: set[str] = set()
    high.update(f["record_id"] for f in security_findings)
    high.update(f["record_id"] for f in pii_findings)
    for d in duplicates:
        high.add(d["record_a"])
        high.add(d["record_b"])
    return {"high_attention": sorted(high)}


def build_manifest(
    schema_results: List[Dict[str, Any]],
    duplicates: List[Dict[str, Any]],
    security_findings: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]],
) -> Dict[str, Any]:
    warnings = sum(1 for r in schema_results if r["status"] == "WARN")
    holds = sum(1 for r in schema_results if r["status"] == "HOLD")
    processable = sum(1 for r in schema_results if r["status"] != "HOLD")
    return {
        "records": len(schema_results),
        "processable": processable,
        "warnings": warnings,
        "holds": holds,
        "duplicate_candidates": len(duplicates),
        "security_findings": len(security_findings),
        "clusters": len(clusters),
    }


def build_preflight_report(
    records_path: str | Path,
    llm: LLMClient,
    stage_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    execution_log: List[Dict[str, Any]] = []

    def record_stage(stage: str, summary: str, **details: Any) -> None:
        event = execution_event(stage, summary, **details)
        execution_log.append(event)
        if stage_callback:
            stage_callback(event)

    records, schema_results = load_and_validate(records_path)
    record_stage("ingest", "Preflight records loaded and schema-checked.")

    profile = profile_records(records)
    record_stage(
        "profiling",
        "Record shape and distribution profile completed.",
        records=len(records),
    )
    duplicates = find_duplicate_candidates(records)
    record_stage(
        "duplicate_detection",
        "Potential repeat contacts identified.",
        candidates=len(duplicates),
    )

    all_security = scan_injections(records)
    security_findings = [f for f in all_security if f["injection_detected"]]
    record_stage(
        "injection_detection",
        "Submission instruction patterns scanned.",
        findings=len(security_findings),
    )

    all_pii = scan_pii(records)
    pii_findings = [f for f in all_pii if f["sensitive_data"]]
    record_stage(
        "pii_detection",
        "Sensitive-data indicators scanned.",
        findings=len(pii_findings),
    )

    clusters = cluster_records(records)
    record_stage(
        "clustering",
        "Records grouped into deterministic themes.",
        clusters=len(clusters),
    )
    narrative = generate_narrative(
        profile, duplicates, clusters, security_findings, pii_findings, llm
    )
    record_stage(
        "analysis",
        "Preflight narrative generated.",
        decision_source=narrative.get("source", "unknown"),
        source=narrative.get("source", "unknown"),
    )

    manifest = build_manifest(schema_results, duplicates, security_findings, clusters)
    manifest["execution_log"] = execution_log
    attention = build_human_attention_forecast(
        security_findings, pii_findings, duplicates
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_results": schema_results,
        "profile": profile,
        "duplicates": duplicates,
        "security_findings": security_findings,
        "pii_findings": pii_findings,
        "clusters": clusters,
        "narrative": narrative,
        "manifest": manifest,
        "human_attention_forecast": attention,
        "execution_log": execution_log,
    }
