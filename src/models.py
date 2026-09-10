"""Pydantic data models shared across the pipeline nodes."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Tier(str, Enum):
    TIER1 = "Tier1"
    TIER2 = "Tier2"
    TIER3 = "Tier3"
    TIER4 = "Tier4"
    INSUFFICIENT = "InsufficientInformation"


class Route(str, Enum):
    DUTY_OFFICER = "DutyOfficer"
    FIELD_INSPECTION = "FieldInspection"
    OPERATOR_LIAISON = "OperatorLiaison"
    INTAKE_CLOSE = "IntakeClose"
    RECORDS_ONLY = "RecordsOnly"
    CALLBACK_QUEUE = "CallbackQueue"


class Reporter(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    anonymous: bool = False
    has_contact_route: bool = False


class ExtractionResult(BaseModel):
    record_id: str
    reporter: Reporter
    location: Optional[str] = None
    operator: Optional[str] = None
    hazard: Optional[str] = None
    substance: Optional[str] = None
    symptoms: List[str] = Field(default_factory=list)
    time_reference: Optional[str] = None
    potential_water_impact: bool = False
    potential_wildlife_impact: bool = False
    potential_h2s: bool = False
    volume_cubic_metres: Optional[float] = None
    fully_contained: Optional[bool] = None
    insufficient_information: bool = False
    sensitive_personal_info: bool = False
    minor_involved: bool = False
    extraction_notes: Optional[str] = None
    source: str = "unset"  # "gemini" or "heuristic_fallback"


class SecurityFinding(BaseModel):
    finding_type: str
    detail: str
    matched_phrases: List[str] = Field(default_factory=list)


class DirectiveMatch(BaseModel):
    directive: str
    category: str
    text: str
    distance: float


class ClassificationResult(BaseModel):
    tier: Tier
    rationale: str
    contravention_suspected: bool = False
    contravention_assessment: str = ""
    directive_cited: str = "NoneApplicable"
    directives_considered: List[str] = Field(default_factory=list)
    source: str = "unset"


class ValidatorOverride(BaseModel):
    rule: str
    detail: str
    previous_tier: Optional[str] = None
    new_tier: Optional[str] = None


class ValidatorResult(BaseModel):
    final_tier: Tier
    overrides: List[ValidatorOverride] = Field(default_factory=list)
    reclassified: bool = False
    is_records_only: bool = False
    linked_record_id: Optional[str] = None


class HumanGate(BaseModel):
    human_approval_required: bool = False
    reasons: List[str] = Field(default_factory=list)


class RoutingResult(BaseModel):
    route: Route
    human_gate: HumanGate


class Acknowledgement(BaseModel):
    send_acknowledgement: bool
    text: Optional[str] = None
    skip_reason: Optional[str] = None
    linked_record_id: Optional[str] = None
    source: str = "deterministic"


class AuditSummary(BaseModel):
    record_id: str
    summary_text: str
    source: str = "unset"  # "gemini" or "heuristic_fallback"
    generated_at: str
