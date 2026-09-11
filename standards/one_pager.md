# Regulatory Intake Triage Agent — One-Page Reflection

Tony Freeman · AER Build Challenge

This prototype favours explainability, evaluation, and governance over sophistication. It's decision support for two people triaging ~200 contacts/week — not a replacement for their judgment, and it doesn't move where accountability sits.

## What my build gets wrong today

- **The deterministic floor is a keyword engine.** With the model off, that same engine *is* the validator floor — a French complaint about a coughing child extracts no symptom and falls through to Tier3. That's the strongest argument for the model layer, not against it.
- **Evaluation barely protects unseen records.** Most judges and hard-rule tests match fixed record IDs; new records report `skipped`, and the acceptance gate reads that as "not failed." Unevaluated is UNKNOWN, not PASS.
- **The golden set is self-authored** — I ran my own engine and locked my review in as ground truth. It proves internal consistency, not correctness; the duty team hasn't adjudicated a case yet.

## What I would do differently with more time

An independently labelled evaluation set with duty-team agreement, and judges that assert rule invariants on *any* record, not known IDs — everything else matters less until evaluation is trustworthy. Then: real embeddings with a precedent library, a logged human-override loop, geospatial proximity analysis, and continuous online evaluation against human decisions.

## What I would never let this system do

- Autonomously close a Tier1 — no route from Tier1 to `IntakeClose`.
- Make a final contravention determination — it recommends and cites; a human decides.
- Treat complaint text as instructions — injection is caught in code, always surfaced, never honoured.
- Under-tier to reduce workload — the validator floor only escalates, never downgrades.
- Ship a decision with no trace, or write to a system of record without authorisation.
- Change its own rules from production decisions — every change goes through human review.

## What I would need from you before this ran on real submissions

Duty-team sign-off on every tiering rule — this currently encodes my reading, not the regulator's. The real directive corpus, historical cases with actual outcomes, and formal SLAs. A staged rollout — shadow, then assisted, then supervised autonomy, Tier1 never autonomous. Access control, a trace retention window, and an escalation path before real PII is in scope.
