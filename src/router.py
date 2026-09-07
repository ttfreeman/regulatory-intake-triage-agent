"""Node 7: Routing. Maps the validated tier onto a routing destination and
determines whether a human approval gate is triggered.
"""
from __future__ import annotations

from src.models import (
    ClassificationResult,
    ExtractionResult,
    HumanGate,
    Route,
    RoutingResult,
    SecurityFinding,
    Tier,
    ValidatorResult,
)
from typing import List

_ROUTE_BY_TIER = {
    Tier.TIER1: Route.DUTY_OFFICER,
    Tier.TIER2: Route.FIELD_INSPECTION,
    Tier.TIER3: Route.OPERATOR_LIAISON,
    Tier.TIER4: Route.INTAKE_CLOSE,
    Tier.INSUFFICIENT: Route.CALLBACK_QUEUE,
}


def route_record(
    extraction: ExtractionResult,
    classification: ClassificationResult,
    validator_result: ValidatorResult,
    security_findings: List[SecurityFinding],
) -> RoutingResult:
    tier = validator_result.final_tier
    route = Route.RECORDS_ONLY if validator_result.is_records_only else _ROUTE_BY_TIER[tier]

    reasons: List[str] = []
    if tier == Tier.TIER1:
        reasons.append("Tier1")
        reasons.append("Life Safety")
    elif extraction.symptoms:
        reasons.append("Life Safety")

    if extraction.potential_h2s:
        reasons.append("Potential H2S")
    if extraction.potential_water_impact and tier in (Tier.TIER1, Tier.TIER2):
        reasons.append("Watercourse Impact")
    if extraction.potential_wildlife_impact:
        reasons.append("Wildlife Mortality")
    if security_findings:
        reasons.append("Prompt Injection")
    if extraction.minor_involved and extraction.symptoms:
        reasons.append("Minor Health Information")
    if extraction.sensitive_personal_info:
        reasons.append("Sensitive Personal Information")
    if any(o.rule == "under_tiering_guard" for o in validator_result.overrides):
        reasons.append("Uncertain Classification")

    # de-duplicate while preserving order
    seen = set()
    deduped = [r for r in reasons if not (r in seen or seen.add(r))]

    human_gate = HumanGate(human_approval_required=bool(deduped), reasons=deduped)
    return RoutingResult(route=route, human_gate=human_gate)
