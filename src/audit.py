"""Post-pipeline audit summary. Not a decision node — runs after the pipeline's
9 decision nodes complete, but before the trace is written, so the summary is
persisted as part of the trace itself (and surfaced in the dashboard).

Reads the already-finalized outputs of the 9-node pipeline and produces a
short human-readable narrative connecting extraction -> classification ->
validation -> routing -> acknowledgement. Never consulted by validator/router/
acknowledge logic and never affects tier, route, or acknowledgement outcomes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.llm import LLMClient
from src.models import (
    AuditSummary,
    ClassificationResult,
    ExtractionResult,
    RoutingResult,
    ValidatorResult,
)
from src.models import Acknowledgement


def generate_audit_summary(
    record_id: str,
    extraction: ExtractionResult,
    classification: ClassificationResult,
    validator_result: ValidatorResult,
    routing_result: RoutingResult,
    acknowledgement: Acknowledgement,
    llm: LLMClient,
) -> AuditSummary:
    generated_at = datetime.now(timezone.utc).isoformat()
    override_rules = [o.rule for o in validator_result.overrides]

    if llm.available:
        prompt = (
            "You are an audit summarizer for a regulatory intake triage pipeline. "
            f"Record: {record_id}.\n"
            f"Extraction facts: location={extraction.location}, operator={extraction.operator}, "
            f"hazard={extraction.hazard}, symptoms={extraction.symptoms}, "
            f"potential_water_impact={extraction.potential_water_impact}, "
            f"potential_wildlife_impact={extraction.potential_wildlife_impact}, "
            f"potential_h2s={extraction.potential_h2s}, "
            f"insufficient_information={extraction.insufficient_information}.\n"
            f"Classification: proposed_tier={classification.tier.value}, "
            f"rationale={classification.rationale}, "
            f"contravention_suspected={classification.contravention_suspected}.\n"
            f"Validator: final_tier={validator_result.final_tier.value}, "
            f"overrides={override_rules}, reclassified={validator_result.reclassified}.\n"
            f"Routing: route={routing_result.route.value}, "
            f"human_approval_required={routing_result.human_gate.human_approval_required}, "
            f"reasons={routing_result.human_gate.reasons}.\n"
            f"Acknowledgement: send_acknowledgement={acknowledgement.send_acknowledgement}, "
            f"source={acknowledgement.source}.\n"
            "Write 3-5 sentences in plain English explaining what was reported, how it "
            "was classified, whether/why it was escalated for human approval, and where "
            "it was routed. Do not invent facts not present in the trace. Do not promise "
            "a specific outcome or regulatory finding. "
            'Return ONLY a JSON object: {"summary": string}'
        )
        data = llm.generate_json(prompt)
        if data and data.get("summary"):
            return AuditSummary(
                record_id=record_id,
                summary_text=data["summary"],
                source="gemini",
                generated_at=generated_at,
            )

    if override_rules:
        overrides_sentence = (
            f"Validator override(s) applied: {', '.join(override_rules)}."
        )
    else:
        overrides_sentence = "No validator overrides were applied."

    if routing_result.human_gate.human_approval_required:
        approval_sentence = (
            f", and requires human approval because: "
            f"{', '.join(routing_result.human_gate.reasons)}"
        )
    else:
        approval_sentence = ""

    if acknowledgement.send_acknowledgement:
        ack_sentence = "An acknowledgement was sent to the reporter."
    else:
        ack_sentence = f"No acknowledgement was sent: {acknowledgement.skip_reason}"

    summary_text = (
        f"Record {record_id} was reported with the following details: "
        f"location {extraction.location}, operator {extraction.operator}, "
        f"hazard {extraction.hazard}. It was classified as "
        f"{validator_result.final_tier.value} ({classification.rationale}). "
        f"{overrides_sentence} It was routed to "
        f"{routing_result.route.value}{approval_sentence}. {ack_sentence}"
    )
    return AuditSummary(
        record_id=record_id,
        summary_text=summary_text,
        source="heuristic_fallback",
        generated_at=generated_at,
    )
