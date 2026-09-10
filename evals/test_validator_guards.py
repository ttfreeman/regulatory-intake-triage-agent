"""Standalone regression test for the compliant_self_report / symptom interaction.

Guards against a real bug found during interview prep: a compliant, fully
contained self-report (<=2.0 m3, no water/H2S/wildlife) must NOT be
downgraded below Tier1 when the reporter also describes symptoms. Run with
`python -m evals.test_validator_guards` or `python evals/test_validator_guards.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.models import ClassificationResult, ExtractionResult, Reporter, Tier
from src.validator import validate_and_correct

_REPORTER = Reporter(name="Test", contact_email="t@example.com", has_contact_route=True)


def _extraction(**overrides) -> ExtractionResult:
    base = dict(
        record_id="TEST-001",
        reporter=_REPORTER,
        fully_contained=True,
        volume_cubic_metres=1.5,
        potential_water_impact=False,
        potential_h2s=False,
        potential_wildlife_impact=False,
        symptoms=[],
    )
    base.update(overrides)
    return ExtractionResult(**base)


def _classification(tier: Tier) -> ClassificationResult:
    return ClassificationResult(
        tier=tier,
        rationale="test",
        contravention_suspected=False,
        source="heuristic_fallback",
    )


def test_compliant_self_report_without_symptoms_downgrades_to_tier4() -> None:
    result = validate_and_correct(
        "contained release, no symptoms",
        _extraction(),
        _classification(Tier.TIER2),
        [],
        [],
        {},
        "TEST-001",
    )
    assert result.final_tier == Tier.TIER4, result.final_tier
    assert result.is_records_only is True


def test_compliant_self_report_with_symptoms_is_never_downgraded() -> None:
    extraction = _extraction(symptoms=["headache"])
    result = validate_and_correct(
        "contained release, reporter felt nauseous",
        extraction,
        _classification(Tier.TIER1),
        [],
        [],
        {},
        "TEST-002",
    )
    assert result.final_tier == Tier.TIER1, result.final_tier
    assert result.is_records_only is False
    assert not any(o.rule == "compliant_self_report" for o in result.overrides)


def main() -> int:
    tests = [
        test_compliant_self_report_without_symptoms_downgrades_to_tier4,
        test_compliant_self_report_with_symptoms_is_never_downgraded,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
    if failures:
        print(f"\n{failures}/{len(tests)} test(s) failed")
        return 1
    print(f"\nAll {len(tests)} test(s) passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
