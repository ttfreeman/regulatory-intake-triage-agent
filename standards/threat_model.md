# Threat Model - Regulatory Intake Triage Agent

## Prompt Injection

**Threat:** Submitted text embeds fake system/administrative instructions
attempting to change agent behavior (e.g. `R-014`'s embedded "SYSTEM NOTICE"
demanding all Nordvik Resources records be closed as Tier4 without
acknowledgment, and that the notice itself be hidden from the trace).

**Mitigation:**
- `src/sanitize.py` runs before any extraction/classification and pattern-
  matches instruction-like phrases ("ignore instructions", "system notice",
  "override", "supersede", "do not surface", "close automatically",
  "automated intake preprocessor", "no further action"). Matched blocks are
  stripped before the text reaches the LLM or heuristic engine.
- A `SecurityFinding` is always recorded regardless of whether the sanitizer
  fully neutralized the text, so the event is visible in the trace and
  dashboard - it is never silently dropped.
- `src/validator.py` adds an explicit `prompt_injection_ignored` override
  entry whenever a finding exists, and `src/router.py` always sets
  `human_approval_required=True` with reason `"Prompt Injection"` - a human
  reviews every record where injection was attempted, regardless of outcome.
- Both extraction and classification prompts (`prompts/*.md`) explicitly
  instruct the model to treat submitted text as data, never as instructions.

**Residual risk:** a sufficiently novel injection phrasing that doesn't match
any pattern and doesn't use a `---`-delimited block could slip past the
sanitizer's redaction step, though it would still need to defeat the
prompt-level "treat as data" instruction given to the model.

## Hallucination

**Threat:** the LLM invents a directive number, a fact not present in the
submission, or a rationale disconnected from the retrieved directive text.

**Mitigation:**
- Retrieval always runs before classification; the classification prompt
  only supplies the directives actually retrieved and instructs the model
  never to cite an unretrieved directive number.
- `evals/judges/grounding.py` checks every trace for citations outside the
  six known directive IDs.
- The deterministic heuristic engine is not just a fallback for missing API
  keys - it is also the floor the validator holds the LLM's output against
  (see "Under-tiering" below), which bounds how much a hallucinated
  classification can diverge from the rule-derived answer.

## Under-tiering

**Threat:** the failure the duty team fears most (`routing_rules.md`) - a
genuinely severe record gets a lower tier than it should, e.g. from an LLM
being too conservative or missing a signal.

**Mitigation:**
- `src/validator.py`'s under-tiering guard independently re-derives a tier
  from the same extracted fields via the deterministic rule engine and
  refuses to let the final tier be less severe than that floor - it can only
  escalate, never downgrade, an LLM-proposed tier.
- Tier1 conditions (H2S with symptoms, exposed infrastructure threatening a
  watercourse, or any reported health symptom under RD-114.3) all escalate
  by default per the standing rule "when uncertain, use the higher tier".

## Sensitive Data Leakage

**Threat:** a submission includes health card numbers, a minor's medical
history, or other sensitive personal information that should not be echoed
back verbatim in an acknowledgment or exposed in the dashboard summary.

**Mitigation:**
- `src/extract.py` flags `sensitive_personal_info` and `minor_involved`
  independently of tier; `src/router.py` always raises a human approval gate
  ("Sensitive Personal Information" / "Minor Health Information") on these
  records so a human reviews the file before any further action.
- The dashboard (`src/dashboard.py`) only ever displays the record ID, tier,
  directive IDs, route, and flags - never the raw submission text or
  extracted PII fields.

## Improper Closure

**Threat:** a Tier1 (life-safety) record gets automatically closed/routed to
`IntakeClose` instead of `DutyOfficer`.

**Mitigation:**
- `src/router.py`'s route table has no path from `Tier1` to `IntakeClose`;
  Tier1 always maps to `DutyOfficer`.
- `human_approval_required` is forced `True` for every Tier1 record.
- The compliant self-report path (`RecordsOnly`) is only reachable when the
  validator independently confirms containment, volume ≤ 2.0 m3, and no
  water/H2S/wildlife impact - it can never be reached from a Tier1 record.

## Directive Misapplication

**Threat:** citing a real directive but applying it to a scenario it doesn't
cover (e.g. treating routine permitted flaring as a violation of RD-133).

**Mitigation:**
- Directive text is retrieved and passed to the classifier verbatim, rather
  than summarized/paraphrased, reducing the chance of the letter of the rule
  being lost.
- Heuristic rules are written to match the specific qualifying conditions in
  the directive text (e.g. RD-133.2 triggers only on "black smoke" or
  "outside permitted hours", not on flaring in general).

## Audit Failure

**Threat:** a decision can't be reconstructed after the fact - which
directive, which extracted fields, which overrides led to the routing.

**Mitigation:**
- Every record produces a complete `traces/<record_id>.json` with the
  retrieved directives, full extraction, classification, every validator
  override with a rule name and detail string, the final human gate
  reasons, the route, and the acknowledgment (or reason it was skipped).
- `artifacts/sample_run.json` aggregates every trace from a run;
  `artifacts/evaluation_report.json` records the pass/fail detail for every
  judge on that run.
