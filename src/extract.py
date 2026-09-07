"""Node 4: Extraction. Structured field extraction from sanitized intake text.

Tries Gemini first (if configured), falls back to a deterministic keyword/regex
heuristic engine otherwise. Both paths populate the same ExtractionResult model.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Template

from src.llm import LLMClient
from src.models import ExtractionResult, Reporter

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extraction.md"

SYMPTOM_KEYWORDS = [
    "headache",
    "dizzy",
    "dizziness",
    "wheeze",
    "wheezing",
    "throat",
    "eyes watering",
    "nausea",
    "inhaler",
    "scratchy throat",
    "off school",
    "clinic visit",
    "dose increased",
]
H2S_KEYWORDS = ["h2s", "sour gas", "rotten egg", "sulphur smell", "sulfur smell"]
WATER_KEYWORDS = [
    "watercourse",
    "creek",
    "river",
    "dugout",
    "slough",
    "water body",
    "ditch",
    "drinking water",
    "well water",
    "sheen",
]
WILDLIFE_KEYWORDS = [
    "dead",
    "died",
    "carcass",
    "songbird",
    "waterfowl",
    "wildlife",
    "fish kill",
]
VOLUME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*cubic\s*metre", re.IGNORECASE)
TIME_REFERENCE_RE = re.compile(
    r"\b(?:since\s+(?:last\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"\d+\s+(?:minute|minutes|hour|hours|day|days)\s+ago|"
    r"this\s+(?:morning|afternoon|evening|week)|"
    r"yesterday|today|overnight)\b",
    re.IGNORECASE,
)
CONTAINED_KEYWORDS = [
    "fully contained",
    "contained inside the bermed",
    "bermed area",
    "recovered by vac truck",
]
MINOR_KEYWORDS = [
    "my daughter",
    "my son",
    "she is 1",
    "he is 1",
    "years old",
    "year old",
]
SENSITIVE_KEYWORDS = [
    "health card",
    "respirologist",
    "clinic",
    "diagnosis",
    "prescri",
    "medical",
]
HAZARD_RULES = [
    (H2S_KEYWORDS, "Sour gas / H2S odour"),
    (["flare", "flaring", "black smoke"], "Flaring / venting"),
    (["release", "spill", "sheen", "stained", "produced water"], "Fluid release"),
    (["noise", "dba", "compressor"], "Noise"),
    (["dust"], "Dust"),
    (["floodlight", "light pollution", "lights point"], "Light"),
    (
        [
            "without notice",
            "without any notice",
            "no notice",
            "no phone call",
            "came onto my land",
        ],
        "Unauthorized site access",
    ),
]
SUBSTANCE_KEYWORDS = [
    "diesel",
    "produced water",
    "wash water",
    "sour gas",
    "hydrocarbon",
]

_NEGATION_CUES = {"no", "not", "none", "without", "never", "n't", "nor"}


def _keyword_present(lower_text: str, keywords: list[str]) -> bool:
    """True if any keyword occurs and isn't negated, either directly (e.g. 'no
    H2S') or across a Q&A turn common in phone transcripts (e.g. 'is there any
    spill or leak. CALLER: no just dust and noise.').
    """
    for kw in keywords:
        for m in re.finditer(re.escape(kw), lower_text):
            before = lower_text[max(0, m.start() - 30) : m.start()]
            before_words = re.findall(r"[a-z']+", before)[-4:]
            if any(w in _NEGATION_CUES for w in before_words):
                continue
            after = lower_text[m.end() : m.end() + 50]
            sentences_after = re.split(r"[.?]", after)
            if len(sentences_after) > 1:
                next_words = re.findall(r"[a-z']+", sentences_after[1])[:4]
                if any(w in _NEGATION_CUES for w in next_words):
                    continue
            return True
    return False


def _structural_insufficient(record: Dict[str, Any]) -> bool:
    """Whether we can identify a location and/or operator at all - a structural
    fact from the record's own fields, never left to LLM judgment on raw text.
    """
    return not _as_text(record.get("location_text")) and not _as_text(
        record.get("operator_named")
    )


def _as_text(value: Any) -> Optional[str]:
    """Convert valid scalar, list, and mapping field shapes to readable text."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        values = [_as_text(item) for item in value]
        values = [item for item in values if item]
        return " / ".join(values) or None
    if isinstance(value, dict):
        values = [
            f"{key}: {_as_text(item)}" for key, item in value.items() if _as_text(item)
        ]
        return "; ".join(values) or None
    return str(value)


def _build_reporter(record: Dict[str, Any]) -> Reporter:
    r = record.get("reporter") or {}
    name = r.get("name")
    email = r.get("email")
    phone = r.get("phone")
    address = r.get("address")
    anonymous = (not name) or name.strip().lower() in {"withheld", "unknown", ""}
    has_contact = bool(email or phone)
    return Reporter(
        name=name,
        contact_email=email,
        contact_phone=phone,
        address=address,
        anonymous=anonymous,
        has_contact_route=has_contact,
    )


def heuristic_extract(record: Dict[str, Any], sanitized_text: str) -> ExtractionResult:
    lower = sanitized_text.lower()
    reporter = _build_reporter(record)
    location = _as_text(record.get("location_text"))
    operator = _as_text(record.get("operator_named"))

    symptoms = [kw for kw in SYMPTOM_KEYWORDS if kw in lower]
    has_h2s = _keyword_present(lower, H2S_KEYWORDS)
    # "Hollow Creek" is a place name in this dataset, not a watercourse reference -
    # scrub it before checking for the generic "creek" water-body keyword.
    water_scan_text = re.sub(r"hollow creek", " ", lower)
    has_water = _keyword_present(water_scan_text, WATER_KEYWORDS)
    has_wildlife = _keyword_present(lower, WILDLIFE_KEYWORDS) and (
        "bird" in lower
        or "waterfowl" in lower
        or "cattle" in lower
        or "animal" in lower
        or "songbird" in lower
    )

    vol_match = VOLUME_RE.search(lower)
    volume = float(vol_match.group(1)) if vol_match else None
    contained = (
        any(kw in lower for kw in CONTAINED_KEYWORDS) if volume is not None else None
    )

    minor_involved = any(kw in lower for kw in MINOR_KEYWORDS)
    sensitive = any(kw in lower for kw in SENSITIVE_KEYWORDS)

    hazard: Optional[str] = None
    for keywords, label in HAZARD_RULES:
        if _keyword_present(lower, keywords):
            hazard = label
            break

    substance = next((s for s in SUBSTANCE_KEYWORDS if s in lower), None)
    time_match = TIME_REFERENCE_RE.search(sanitized_text)

    insufficient = _structural_insufficient(record)
    word_count = len(re.findall(r"[a-zA-Z]+", sanitized_text))
    if word_count <= 4 and not any([has_h2s, has_water, has_wildlife, symptoms]):
        insufficient = True

    return ExtractionResult(
        record_id=record["record_id"],
        reporter=reporter,
        location=location,
        operator=operator,
        hazard=hazard,
        substance=substance,
        symptoms=symptoms,
        time_reference=time_match.group(0) if time_match else None,
        potential_water_impact=has_water,
        potential_wildlife_impact=has_wildlife,
        potential_h2s=has_h2s,
        volume_cubic_metres=volume,
        fully_contained=contained,
        insufficient_information=insufficient,
        sensitive_personal_info=sensitive,
        minor_involved=minor_involved,
        extraction_notes="Extracted via deterministic offline heuristic engine.",
        source="heuristic_fallback",
    )


def extract_record(
    record: Dict[str, Any], sanitized_text: str, llm: LLMClient
) -> ExtractionResult:
    if llm.available:
        prompt = Template(_PROMPT_PATH.read_text(encoding="utf-8")).render(
            sanitized_text=sanitized_text
        )
        data = llm.generate_json(prompt)
        if data:
            try:
                reporter = _build_reporter(record)
                return ExtractionResult(
                    record_id=record["record_id"],
                    reporter=reporter,
                    location=_as_text(record.get("location_text")),
                    operator=_as_text(record.get("operator_named")),
                    hazard=data.get("hazard"),
                    substance=data.get("substance"),
                    symptoms=data.get("symptoms") or [],
                    time_reference=data.get("time_reference") or None,
                    potential_water_impact=bool(data.get("potential_water_impact")),
                    potential_wildlife_impact=bool(
                        data.get("potential_wildlife_impact")
                    ),
                    potential_h2s=bool(data.get("potential_h2s")),
                    volume_cubic_metres=data.get("volume_cubic_metres"),
                    fully_contained=data.get("fully_contained"),
                    # Deliberately not LLM-judged: see _structural_insufficient docstring.
                    insufficient_information=_structural_insufficient(record),
                    sensitive_personal_info=bool(data.get("sensitive_personal_info")),
                    minor_involved=bool(data.get("minor_involved")),
                    extraction_notes=data.get("extraction_notes"),
                    source="gemini",
                )
            except Exception:
                pass  # fall through to heuristic
    return heuristic_extract(record, sanitized_text)
