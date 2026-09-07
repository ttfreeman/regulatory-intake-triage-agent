# Promotion Assessment - Regulatory Intake Triage Agent

## Current State: Experiment

Built as a take-home/interview prototype against a fabricated 40-record
dataset and six fabricated directive extracts. Runs locally, offline-capable,
with an optional real Gemini integration. Not connected to any real intake
channel, case management system, or the actual AER directive corpus.

## Promotion Recommendation

**Do not promote directly to production.** Recommend a staged pilot:

1. **Shadow mode** (4-6 weeks): run alongside the existing two-person duty
   team on real (but access-controlled) intake volume. The agent's output is
   logged and reviewed but never routed or acknowledged automatically. Compare
   agent tier/route against the human team's actual decision on every record.
2. **Assisted mode**: agent output is shown to the duty team as a suggestion
   with rationale and directive citations; human makes the final call on
   every record, not just gated ones. Track override rate and reasons.
3. **Supervised autonomy**: only for the lowest-risk paths (`Tier4`
   info/feedback, `RecordsOnly` compliant self-reports) with 100% human
   spot-check for the first month and no autonomy at all for `Tier1`.

## Required Improvements Before Pilot

- Replace the offline hashing embedding function with a real embedding model
  once the actual (much larger) AER directive corpus is in scope - the
  bag-of-words approach here only works because there are six short extracts.
- Replace the self-reviewed golden dataset with an independently labeled set
  (see `standards/evaluation_plan.md` - "Golden dataset provenance") and
  measure inter-rater agreement between the agent and at least two human
  reviewers.
- Add real place-name/gazetteer disambiguation instead of the targeted
  "Hollow Creek" scrub (see `standards/evidence_pack.md` - "Known
  Limitations").
- Add authentication, access control, and a defined retention policy for
  `traces/` before any real reporter PII is processed (see
  `standards/observability_plan.md` - "Retention").
- Wire `Tier1` + `security_findings` into a real paging/alerting channel
  instead of a static dashboard.
- Expand the injection pattern list and add adversarial red-teaming beyond
  the single embedded-instruction pattern in this dataset.

## Known Risks

- Heuristic keyword matching is dataset-specific in places (see "Known
  Limitations" in the evidence pack); novel phrasing in real intake could
  evade both the heuristic engine and an under-resourced LLM prompt.
- Gemini API availability/quota is an external dependency; the offline
  fallback protects availability but produces a different (deterministic,
  non-LLM) decision path that has not been evaluated against as broad a set
  of adversarial inputs as the LLM path would need in production.
- No load testing has been done; 40 records process in well under a minute
  locally, but real intake volume and Gemini rate limits are unknown.

## Pilot Readiness Assessment

**Not pilot-ready as-is.** Suitable as a design/architecture reference and a
working demonstration of the governance pattern (retrieval-before-
classification, validator-enforced floors, mandatory human gates, full
tracing, prompt-injection resistance). Needs the improvements above, plus
sign-off from the actual duty team on the tiering rules, before touching
real intake.
