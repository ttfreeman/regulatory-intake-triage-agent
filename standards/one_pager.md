# Regulatory Intake Triage Agent — One-Page Reflection

Tony Freeman · AER Build Challenge

This prototype prioritises explainability, evaluation, and governance over sophistication. The mission is to help two people make better, faster, more consistent decisions — not to replace their judgment or move where accountability sits.

## What my build gets wrong today

- **The deterministic layer is English-only.** A French complaint describing a child coughing near a school extracts no symptom, no hazard, and falls through to Tier3 — operator liaison, ten business days. In offline mode the validator floor *is* that keyword engine, so the guard I describe as my safety net is what produced the miss. This is the strongest argument for the LLM layer, not against it.
- **Repeat-contact linkage suppresses the wrong thing.** A second report from the same address, correctly escalated to Tier1 because the reporter's daughter is now symptomatic, receives no acknowledgment — because linkage fires before the acknowledgment decision. RD-114.4 says the response clock doesn't restart; it doesn't say don't respond. I encoded the directive without asking what the reporter experiences.
- **My evaluation barely protects records it hasn't seen.** Four of six judges and all five hard-rule tests match on fixed record IDs. On new records they report `skipped`, and because `skipped` counts as not-failed, the acceptance gate reports `PASS` trivially. The under-tiering guard could be broken and a run of unseen records wouldn't catch it.
- **The golden set is self-authored.** I ran my own engine, reviewed all forty outputs against the routing rules, and locked that in as ground truth. It proves internal consistency, not correctness.
- **Keyword extraction is tuned to this dataset.** Volume parses only from the literal phrase "cubic metres"; a hardcoded scrub stops "Hollow Creek" reading as a watercourse. Both work here and neither generalises.

## What I would do differently with more time

**First:** an independently labelled evaluation set with inter-rater agreement against the duty team, and judges that assert rule-derived invariants on *any* record rather than matching known IDs. Everything else is worth less until the evaluation means something.

Then: real embeddings over the full directive corpus with a precedent library, so classification cites prior human-reviewed dispositions rather than reasoning from directives alone; a human override loop that logs every correction with a reason; structured geospatial analysis for proximity and setback; and continuous online evaluation comparing agent output to human decisions in production.

## What I would never let this system do

- **Autonomously close a Tier1, or find that no further action is needed** where people, wildlife, or the environment may be harmed. There is no code path from Tier1 to `IntakeClose`, regardless of model confidence.
- **Make a final contravention determination.** It recommends and cites; a human decides.
- **Treat complaint text as instructions,** under any framing. Injection is detected in code before any model call, always surfaced, never silently honoured or silently hidden.
- **Under-tier to reduce workload.** The validator floor can escalate a proposed tier and never downgrade it.
- **Ship a decision with no trace,** send external communications on material cases without approval, or write to a system of record without explicit authorisation.
- **Change its own rules from production decisions.** Every rule change goes through human review — never silent online retraining.

## What I would need from you before this ran on real submissions

- Sign-off from the duty team on every tiering rule. The engine currently encodes **my** reading of six extracts, not the regulator's.
- The real directive corpus, a representative set of historical cases with their actual outcomes, and formal acceptance criteria and SLAs from the operational team.
- Agreement on a staged rollout — shadow, then assisted, then supervised autonomy for the lowest-risk paths only, with Tier1 never autonomous.
- Access control, a defined retention window for traces, and a documented escalation path for pipeline failures before any real reporter PII is in scope.
- Agreement on the system's role: **decision support that improves triage quality, responsiveness, and transparency, while accountability for regulatory outcomes stays exactly where it is today.**
