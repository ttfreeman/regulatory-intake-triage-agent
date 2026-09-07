"""Preflight Component 7: Gemini analysis layer.

Tries Gemini first (if configured and enabled) to narrate the deterministic
findings above; falls back to a deterministic templated narrative
otherwise. Same fallback contract as the triage LLM nodes (src/llm.py):
`generate_json` returning None means "use the heuristic path", never an
error the caller has to special-case.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

from src.llm import LLMClient

_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "preflight_analysis.md"


def generate_narrative(
    profile: Dict[str, Any],
    duplicates: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]],
    security_findings: List[Dict[str, Any]],
    pii_findings: List[Dict[str, Any]],
    llm: LLMClient,
) -> Dict[str, Any]:
    if llm.available:
        prompt = Template(_PROMPT_PATH.read_text(encoding="utf-8")).render(
            profile_json=json.dumps(profile, indent=2),
            duplicates_json=json.dumps(duplicates, indent=2),
            clusters_json=json.dumps(clusters, indent=2),
            security_json=json.dumps(security_findings, indent=2),
        )
        data = llm.generate_json(prompt)
        if data:
            return {"source": "gemini", **data}

    return _heuristic_narrative(profile, duplicates, clusters, security_findings, pii_findings)


def _heuristic_narrative(
    profile: Dict[str, Any],
    duplicates: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]],
    security_findings: List[Dict[str, Any]],
    pii_findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    summary = (
        f"{profile['records']} records analyzed across "
        f"{len(profile['channel_distribution'])} channel(s) and {profile['operators']} named operator(s)."
    )
    if duplicates:
        summary += f" {len(duplicates)} potential repeat-contact/duplicate chain(s) identified."
    if security_findings:
        summary += f" {len(security_findings)} record(s) contain embedded instruction-like content."
    if pii_findings:
        summary += f" {len(pii_findings)} record(s) carry sensitive personal or health information."

    return {
        "source": "heuristic_fallback",
        "executive_summary": summary,
        "emerging_themes": [c["cluster"] for c in clusters if c["cluster"] != "Other"],
        "risk_signals": [
            f"{f['record_id']}: possible prompt injection" for f in security_findings
        ]
        or ["No security findings detected."],
        "potential_repeat_incidents": [
            f"{d['record_a']} <-> {d['record_b']} (score {d['score']}: {', '.join(d['reasons'])})"
            for d in duplicates
        ]
        or ["No duplicate/repeat-contact candidates above threshold."],
        "data_quality_issues": [
            f"{profile['missing_fields']['location_text']} record(s) missing location",
            f"{profile['missing_fields']['operator_named']} record(s) missing operator",
            f"{profile['contactability']['anonymous']} record(s) with no contact route",
        ],
        "interesting_patterns": [f"{c['cluster']}: {len(c['members'])} record(s)" for c in clusters],
        "suggested_human_attention_areas": sorted(
            {f["record_id"] for f in security_findings} | {f["record_id"] for f in pii_findings}
        ),
        "limitations": [
            "Heuristic narrative generated without Gemini; set USE_GEMINI=true for AI-assisted synthesis.",
            "Clustering and duplicate detection are keyword/rule-based, not semantic.",
        ],
    }
