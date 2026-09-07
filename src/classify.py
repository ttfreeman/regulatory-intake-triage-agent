"""Node 5: Classification. Assigns a severity tier and contravention
assessment, grounded in the directives retrieved for this record.

Tries Gemini first (if configured), falls back to a deterministic rule engine
derived from routing_rules.md and directives_extract.md.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

from src.llm import LLMClient
from src.models import ClassificationResult, DirectiveMatch, ExtractionResult, Tier

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "classification.md"

LIFE_SAFETY_TERMS = [
    "dizzy",
    "dizziness",
    "headache",
    "throat",
    "eyes watering",
    "wheeze",
    "scratchy throat",
    "symptom",
    "off school",
    "clinic",
]
ACUTE_TERMS = [
    "bang",
    "just happened",
    "minutes ago",
    "half an hour ago",
    "fifteen minutes ago",
    "loud bang",
]
SENSITIVE_RECEPTOR_TERMS = ["school", "hospital", "care facility", "elementary"]
NO_NOTICE_TERMS = ["without notice", "without any notice", "no notice", "no phone call"]
STRUCTURE_TERMS = ["fence", "gate", "signage", "cattle guard", "snow fence"]
DAMAGE_STATE_TERMS = ["down", "damaged", "left open", "fallen over", "broken"]
NUISANCE_TERMS = [
    "noise",
    "dba",
    "dust",
    "light pollution",
    "floodlight",
    "vent stack noise",
    "odour",
    "smell",
]
INFO_FEEDBACK_TERMS = [
    "positive feedback",
    "professional and cleaned",
    "not a complaint",
    "reclamation status",
    "copy of the emergency response plan",
    "requesting information",
    "not a complaint",
]
OUT_OF_JURISDICTION_TERMS = [
    "subdivision development",
    "not associated with an energy facility",
]
EXPOSED_INFRASTRUCTURE_TERMS = ["exposed", "erosion"]


def _directive_cited(
    assessment: str, directives: List[str], contravention: bool
) -> str:
    if not contravention:
        return "NoneApplicable"
    cited = re.findall(r"RD-\d+", assessment)
    for directive in cited:
        if directive in directives:
            return directive
    return "NoneApplicable"


def heuristic_classify(
    sanitized_text: str,
    extraction: ExtractionResult,
    directive_matches: List[DirectiveMatch],
) -> ClassificationResult:
    lower = sanitized_text.lower()
    directives = [m.directive for m in directive_matches]
    contravention_suspected = False
    assessment = ""

    if extraction.insufficient_information:
        tier = Tier.INSUFFICIENT
        assessment = "Insufficient information to identify location and/or responsible operator; cannot be tiered as-is."
        return ClassificationResult(
            tier=tier,
            rationale="No location and no operator identified in the submission.",
            contravention_suspected=False,
            contravention_assessment=assessment,
            directive_cited="NoneApplicable",
            directives_considered=directives,
            source="heuristic_fallback",
        )

    has_symptom = bool(extraction.symptoms) or any(
        t in lower for t in LIFE_SAFETY_TERMS
    )
    acute_incident = any(t in lower for t in ACUTE_TERMS)
    near_sensitive_receptor = any(t in lower for t in SENSITIVE_RECEPTOR_TERMS)

    if extraction.potential_h2s and (
        has_symptom or near_sensitive_receptor or acute_incident
    ):
        tier = Tier.TIER1
        assessment = "Potential H2S / sour gas exposure with life-safety indicators; immediately reportable (RD-101.1) and escalable under RD-114.3."
        contravention_suspected = True
    elif has_symptom:
        tier = Tier.TIER1
        assessment = "Complaint describes a potential risk to human health (reported symptoms); RD-114.3 requires duty-officer escalation and a human decision before closure, regardless of the suspected source."
        contravention_suspected = extraction.hazard in {
            "Flaring / venting",
            "Sour gas / H2S odour",
        }
    elif (
        extraction.potential_water_impact
        and any(t in lower for t in EXPOSED_INFRASTRUCTURE_TERMS)
        and ("creek" in lower or "watercourse" in lower or "water" in lower)
    ):
        tier = Tier.TIER1
        assessment = "Exposed infrastructure threatening a watercourse; treated as an uncontrolled release risk under RD-101.1."
        contravention_suspected = True
    elif (
        extraction.fully_contained
        and extraction.volume_cubic_metres is not None
        and extraction.volume_cubic_metres <= 2.0
        and not extraction.potential_water_impact
        and not extraction.potential_h2s
        and not extraction.potential_wildlife_impact
    ):
        tier = Tier.TIER4
        assessment = "Self-reported release fully contained on site, at or below the 2.0 m3 threshold, no water/H2S/wildlife impact: compliant record-only report, not a contravention (RD-101.3)."
        contravention_suspected = False
    elif extraction.potential_wildlife_impact:
        tier = Tier.TIER2
        assessment = "Wildlife mortality associated with facility activity is reportable within 24 hours irrespective of volume (RD-101.4)."
        contravention_suspected = True
    elif extraction.potential_water_impact:
        tier = Tier.TIER2
        assessment = "Possible watercourse/water body impact; requires field assessment to confirm extent and source (RD-101.1/RD-101.2)."
        contravention_suspected = True
    elif any(t in lower for t in NO_NOTICE_TERMS):
        tier = Tier.TIER2
        assessment = "Entry to private land without prior notice is a contravention on its face (RD-146.2)."
        contravention_suspected = True
    elif any(s in lower for s in STRUCTURE_TERMS) and any(
        d in lower for d in DAMAGE_STATE_TERMS
    ):
        tier = Tier.TIER2
        assessment = "Property impact: site access controls (fence/gate/signage) reported down or compromised. RD-146.3 requires these be restored to prior condition; property impact is Tier 2 by default."
        contravention_suspected = True
    elif (
        extraction.volume_cubic_metres is not None
        and extraction.volume_cubic_metres > 2.0
    ):
        tier = Tier.TIER2
        assessment = "Reported release volume exceeds the 2.0 m3 contained-release threshold; immediately reportable (RD-101.2)."
        contravention_suspected = True
    elif extraction.hazard == "Flaring / venting" and (
        "black smoke" in lower
        or "outside permitted hours" in lower
        or "after hours" in lower
        or "after-hours" in lower
    ):
        tier = Tier.TIER2
        assessment = "Flaring producing visible black smoke, or occurring outside permitted hours, is reportable within 24 hours (RD-133.2) - not routine/permitted flaring."
        contravention_suspected = True
    elif extraction.hazard == "Fluid release" and extraction.substance is not None:
        tier = Tier.TIER2
        assessment = "Third-party-observed fluid release with an identified substance and no confirmed compliant self-report; requires field verification of volume/containment before this can be treated as record-only (RD-101.2/101.3)."
        contravention_suspected = True
    elif any(t in lower for t in NUISANCE_TERMS):
        tier = Tier.TIER3
        assessment = "Nuisance/amenity-level impact (noise, dust, light, or odour without symptoms) requiring operator liaison follow-up."
        contravention_suspected = "measure" in lower or "dba" in lower
    elif any(t in lower for t in INFO_FEEDBACK_TERMS) or any(
        t in lower for t in OUT_OF_JURISDICTION_TERMS
    ):
        tier = Tier.TIER4
        assessment = "Information request, positive feedback, or matter outside regulatory jurisdiction; acknowledge and close."
        contravention_suspected = False
    else:
        tier = Tier.TIER3
        assessment = "No immediate safety, environmental, or contravention indicators found; treated conservatively as an ongoing nuisance/amenity matter pending liaison follow-up rather than auto-closed."
        contravention_suspected = False

    return ClassificationResult(
        tier=tier,
        rationale=assessment,
        contravention_suspected=contravention_suspected,
        contravention_assessment=assessment,
        directive_cited=_directive_cited(
            assessment, directives, contravention_suspected
        ),
        directives_considered=directives,
        source="heuristic_fallback",
    )


def classify_record(
    sanitized_text: str,
    extraction: ExtractionResult,
    directive_matches: List[DirectiveMatch],
    llm: LLMClient,
) -> ClassificationResult:
    if llm.available:
        directive_context = "\n\n".join(
            f"[{m.directive}] {m.text}" for m in directive_matches
        )
        prompt = Template(_PROMPT_PATH.read_text(encoding="utf-8")).render(
            extraction_json=extraction.model_dump_json(indent=2),
            directive_context=directive_context,
            sanitized_text=sanitized_text,
        )
        data = llm.generate_json(prompt)
        if data:
            try:
                return ClassificationResult(
                    tier=Tier(data["tier"]),
                    rationale=data.get("rationale", ""),
                    contravention_suspected=bool(data.get("contravention_suspected")),
                    directive_cited=(
                        data.get("directive_cited")
                        if data.get("directive_cited")
                        in [m.directive for m in directive_matches]
                        else "NoneApplicable"
                    ),
                    contravention_assessment=data.get("contravention_assessment", ""),
                    directives_considered=[m.directive for m in directive_matches],
                    source="gemini",
                )
            except Exception:
                pass  # fall through to heuristic
    return heuristic_classify(sanitized_text, extraction, directive_matches)
