"""Node 6: Validation. The correction loop.

Initial Classification -> Validator Review -> Conflict Detected? -> Reclassify
-> Final Decision.

The validator independently derives a rule-based "floor" tier from the same
extracted fields (via the deterministic heuristic engine) and never allows the
final tier to be *less* severe than that floor - this is the under-tiering
guard the standing rules call out as the failure the team fears most. It also
enforces record shape rules (insufficient information, compliant self-reports)
that must hold no matter what the classifier (Gemini or heuristic) proposed.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.classify import heuristic_classify
from src.models import (
    ClassificationResult,
    DirectiveMatch,
    ExtractionResult,
    SecurityFinding,
    Tier,
    ValidatorOverride,
    ValidatorResult,
)
from src.util.duplicate_scoring import find_repeat_contact_from_extraction

_SEVERITY_RANK = {Tier.TIER1: 0, Tier.TIER2: 1, Tier.TIER3: 2, Tier.TIER4: 3}


def _is_records_only(extraction: ExtractionResult) -> bool:
    # A reporter describing symptoms is a life-safety signal that a compliant
    # containment/volume reading must never suppress - see standing rule on
    # RD-114.3 duty-officer escalation regardless of suspected source.
    return bool(
        extraction.fully_contained
        and extraction.volume_cubic_metres is not None
        and extraction.volume_cubic_metres <= 2.0
        and not extraction.potential_water_impact
        and not extraction.potential_h2s
        and not extraction.potential_wildlife_impact
        and not extraction.symptoms
    )


def validate_and_correct(
    sanitized_text: str,
    extraction: ExtractionResult,
    classification: ClassificationResult,
    directive_matches: List[DirectiveMatch],
    security_findings: List[SecurityFinding],
    duplicate_index: Dict[str, str],
    record_id: str,
) -> ValidatorResult:
    overrides: List[ValidatorOverride] = []
    tier = classification.tier
    reclassified = False
    is_records_only = False

    # Hard rule: insufficient information is never overridden by a classifier's guess.
    # A classifier may identify insufficiency even when the structural extractor
    # found location/operator fields, so preserve either signal and send it to
    # the callback queue rather than allowing the floor comparison to turn it
    # into an auto-close tier.
    if extraction.insufficient_information or tier == Tier.INSUFFICIENT:
        if tier != Tier.INSUFFICIENT:
            overrides.append(
                ValidatorOverride(
                    rule="insufficient_information_floor",
                    detail="No location and no operator identified; forced to InsufficientInformation regardless of classifier output.",
                    previous_tier=tier.value,
                    new_tier=Tier.INSUFFICIENT.value,
                )
            )
            reclassified = True
        tier = Tier.INSUFFICIENT

    else:
        # Under-tiering guard: cross-check against an independently rule-derived floor.
        floor_result = heuristic_classify(sanitized_text, extraction, directive_matches)
        floor_tier = floor_result.tier
        if floor_tier != Tier.INSUFFICIENT and _SEVERITY_RANK[
            floor_tier
        ] < _SEVERITY_RANK.get(tier, 99):
            overrides.append(
                ValidatorOverride(
                    rule="under_tiering_guard",
                    detail=(
                        f"Rule-derived floor tier is {floor_tier.value} "
                        f"({floor_result.contravention_assessment}); classifier proposed {tier.value}. "
                        "Escalated to the floor - under-tiering is never permitted."
                    ),
                    previous_tier=tier.value,
                    new_tier=floor_tier.value,
                )
            )
            tier = floor_tier
            reclassified = True

        # Hard rule: compliant, fully-contained self-report is RecordsOnly, never auto-escalated
        # into a contravention and never silently downgraded below record-keeping either.
        if _is_records_only(extraction):
            is_records_only = True
            if tier != Tier.TIER4:
                overrides.append(
                    ValidatorOverride(
                        rule="compliant_self_report",
                        detail="Contained release at or below 2.0 m3 with no water/H2S/wildlife impact is compliant record-keeping, not a contravention.",
                        previous_tier=tier.value,
                        new_tier=Tier.TIER4.value,
                    )
                )
                tier = Tier.TIER4
                reclassified = True

    # Prompt injection never changes the outcome the attacker demanded; it only adds visibility.
    if security_findings:
        overrides.append(
            ValidatorOverride(
                rule="prompt_injection_ignored",
                detail="Embedded instructions detected in submission were ignored; record processed on its legitimate content only.",
            )
        )

    # Repeat-contact linkage: same reporter contact/address seen before in this run.
    linked_record_id: Optional[str] = None
    prior, reasons = find_repeat_contact_from_extraction(
        record_id, extraction.reporter, duplicate_index
    )
    if prior:
        linked_record_id = prior
        overrides.append(
            ValidatorOverride(
                rule="repeat_contact_linkage",
                detail=f"Same reporter contact as {prior}; linked, response clock does not restart.",
            )
        )
    else:
        # Index this record's contact for future comparison in this run.
        key = (
            extraction.reporter.address
            or extraction.reporter.contact_email
            or extraction.reporter.contact_phone
        )
        if key:
            duplicate_index[key] = record_id

    return ValidatorResult(
        final_tier=tier,
        overrides=overrides,
        reclassified=reclassified,
        is_records_only=is_records_only,
        linked_record_id=linked_record_id,
    )
