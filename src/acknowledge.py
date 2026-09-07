"""Node 8: Acknowledgement. Drafts (or skips) an acknowledgment to the reporter.

Standing rule: every reporter gets an acknowledgment, except where they are
anonymous with no contact route, or where a duplicate has already been
acknowledged for the same incident (linked by the validator).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from jinja2 import Template

from src.llm import LLMClient
from src.models import Acknowledgement, ExtractionResult, RoutingResult, ValidatorResult

_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "acknowledgement.md"
)


def draft_acknowledgement(
    record: Dict[str, Any],
    extraction: ExtractionResult,
    routing_result: RoutingResult,
    validator_result: ValidatorResult,
    llm: LLMClient,
) -> Acknowledgement:
    reporter = extraction.reporter

    if not reporter.has_contact_route:
        return Acknowledgement(
            send_acknowledgement=False,
            skip_reason="Anonymous submission with no email or phone contact route provided.",
            source="deterministic",
        )

    if validator_result.linked_record_id:
        return Acknowledgement(
            send_acknowledgement=False,
            skip_reason=f"Repeat contact already linked to {validator_result.linked_record_id}; original acknowledgment stands.",
            linked_record_id=validator_result.linked_record_id,
            source="deterministic",
        )

    reporter_name = (
        reporter.name if (reporter.name and not reporter.anonymous) else "there"
    )
    route_value = routing_result.route.value

    if llm.available:
        prompt = (
            "You are the acknowledgement node of a regulatory intake triage pipeline. "
            "Draft a brief, professional acknowledgment email (3-4 sentences) to the "
            f"reporter named '{reporter_name}' for record {record['record_id']}, which has "
            f"been routed to '{route_value}'. Do not promise a specific outcome. "
            'Return ONLY a JSON object: {"text": string}'
        )
        data = llm.generate_json(prompt)
        if data and data.get("text"):
            return Acknowledgement(
                send_acknowledgement=True,
                text=data["text"],
                source="gemini",
            )

    text = Template(_TEMPLATE_PATH.read_text(encoding="utf-8")).render(
        reporter_name=reporter_name, record_id=record["record_id"], route=route_value
    )
    return Acknowledgement(
        send_acknowledgement=True,
        text=text.strip(),
        source="heuristic_fallback",
    )
