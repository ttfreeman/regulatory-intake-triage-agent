# Observability Plan - Regulatory Intake Triage Agent

## What is captured

Every record produces a single JSON trace at `traces/<record_id>.json`
containing, in order of the pipeline:

0. `execution_log` - ordered, timestamped stage events for ingest, sanitizing,
   directive retrieval, extraction, classification, validation, routing, and
   acknowledgement. Events include engine choice, counts, and decision
   transitions without copying raw submissions or contact details.

1. `retrieved_directives` - which directives were retrieved and their
   similarity distance, before classification ran.
2. `extraction` - the full structured extraction (hazard, substance,
   symptoms, water/wildlife/H2S flags, volume/containment, sensitive/minor
   flags, and whether extraction used Gemini or the offline heuristic).
3. `classification` - proposed tier, rationale, contravention assessment,
   and which directives were actually considered.
4. `validator_overrides` - every rule that fired during validation, each
   with a machine-readable `rule` name, a human-readable `detail`, and the
   tier transition it caused (if any). Empty if the classifier's proposal
   already satisfied every hard rule.
5. `reclassified` / `final_tier` - whether the validator changed the tier,
   and what it ended up as.
6. `route` - the final routing destination.
7. `human_gate` - whether human approval is required and the full list of
   reasons (never just a boolean).
8. `acknowledgement` - the drafted text, or the reason it was skipped
   (anonymous/no contact, or linked to a prior record).
9. `security_findings` - any prompt injection or other security-relevant
   finding, independent of what tier the record ended up at.

Aggregated views:
- `artifacts/sample_run.json` - every trace from the most recent run, in one
  file, for bulk analysis.
- `artifacts/dashboard.html` - a static, single-file HTML summary (record,
  tier, directives, route, human flag, injection flag, link to the full
  trace) - no server required, safe to open directly or attach to an email.
- `artifacts/evaluation_report.json` - the full evaluation harness output
  for the run (per-dataset pass/fail detail plus the five hard rule tests).

The preflight manifest/report also contains an `execution_log` covering schema
validation, profiling, duplicate detection, injection and PII scans,
clustering, and narrative generation. These logs explain what ran and in what
order; the detailed result fields remain the audit evidence for each decision.

## What is deliberately *not* captured in the dashboard

Raw submission text, reporter contact details, and extracted PII fields are
never rendered in `dashboard.html` - only in the individual trace files,
which are treated as the audit record, not a public-facing view.

## Alerting posture (prototype stage)

This prototype does not ship a live alerting integration. In a pilot,
`human_gate.human_approval_required == true` combined with `final_tier ==
"Tier1"` would page the duty officer channel directly instead of relying on
someone reading the dashboard; `security_findings` non-empty would notify
the security/governance channel separately from the operational routing
queue.

## Retention

Traces and the aggregated run/eval artifacts are local files
(`traces/`, `artifacts/`) and are gitignored by default (see `.gitignore`)
since they may contain reporter PII from real intake in a future
non-synthetic deployment. A production deployment would need a defined
retention window and access control on this directory, not just
`.gitignore`.
