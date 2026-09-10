# Demo prep — condensed talk track (12 min + live run)

Setup: venv active, repo root. `USE_GEMINI=true` unless noted. Have a terminal
tab ready with this morning's failed eval run, and one pre-typed but unrun:
`USE_GEMINI=false python run.py triage data/test_intake_records.json`.

---

## 1. Frame (1 min)

Two people triage ~200 contacts/week; the queue runs days behind. Life-safety
matters must escalate within an hour, and sometimes don't — that's the only
reason this exists.

This is **decision support**: it extracts, proposes a tier, cites a directive,
drafts an acknowledgment, and logs how it got there. It never closes a file,
never makes a final contravention finding, and never owns a regulatory
outcome. Design references: EU AI Act high-risk provisions (risk management,
testing, logging, human oversight) and Canada's federal agentic-AI guidance
(bounded authority, human intervention, traceability) — used as design
inspiration, not claimed as legal compliance.

Most of the time today goes to what this build gets wrong, including that it
currently fails its own acceptance gate.

## 2. The one design decision (2 min)

Gemini does semantic interpretation — reading messy, bilingual, ambiguous
text and proposing a tier. Deterministic code owns the control plane:
sanitization before any model call, directive retrieval before classification
(so citations are grounded), and two enforcement layers the model can't touch:

```
Gemini recommendation → validator.py (rule-derived regulatory floor) → max(model tier, floor)
```

The model can recommend **higher**, never **lower**. Then the router applies
nine deterministic triggers (Tier1, symptoms, H2S keywords, minor+symptoms,
injection detected, water impact at Tier1/2, wildlife mortality, sensitive
PII, under-tiering escalation) that mandate human approval before any route
executes. Neither layer can be overridden by model output or prompt text.

> The model interprets the text. It does not own the control plane.

## 3. What I cut

No vector DB (in-memory hashing retrieval over six directive extracts — fine
at this scale, first thing to break at real volume). No interactive UI
(static HTML only). No multi-agent architecture (one bounded semantic task;
I'd add agents only where they create measurable value). No auto-learning
from production decisions (no provenance/change control yet). No direct
writes to a system of record.

## 4. My build fails its own gate (2 min)

This morning's eval: 88.55% against a 90% semantic-quality bar → red,
non-zero exit.

Two evaluation types, deliberately not treated the same:
- **Statistical** (tier accuracy, extraction quality, grounding,
  contravention consistency) — thresholds.
- **Critical Control Suite** (life-safety human gate 7/7, injection
  resistance 1/1, insufficient-information handling 3/3, directive grounding
  40/40, compliant self-report protection 1/1, all 5 hard-rule tests) —
  **100% required, zero tolerance.**

All critical controls pass. The only failure is golden tiering: 25/40
(62.5%) — and that's *my* self-authored reference set, not regulatory ground
truth. Of the 15 disagreements (see `diff_modes.py`): 10 are Gemini going
*higher* than my label (standing rule: uncertain → higher tier), 4 are Gemini
correctly refusing to guess (`InsufficientInformation`), 1 is a correct
proximity-notification up-tier. Gemini complied with the legal floor
unassisted on 35/40 (87.5%); the validator caught and corrected all 5 where
it proposed below the floor.

Two honest flaws in the gate itself: it pools raw counts across
differently-sized datasets, and — the bigger one — untested records report
`skipped`, which the gate currently treats as "not failed" and prints as
PASS. **A control that wasn't evaluated is UNKNOWN, not PASS.** First thing
I'd fix.

## 5. The problem with my guard (3 min — the centre of the talk)

Run the floor alone, model off:
```bash
USE_GEMINI=false python run.py triage data/test_intake_records.json
```
A record describes a rotten-egg smell (hyphenated) near a school, two kids
coughing — Tier1 on any reading. The floor derives **Tier2**: my H2S keyword
list has `rotten egg` as two words; the hyphen breaks the match, and only a
"creek" mention in the location field saves it from going lower. A French
complaint about a coughing child falls to Tier3 with no human gate at all —
every keyword list is English. An oily sheen on a pond with ducks doesn't
match "water" or "wildlife" vocabulary and auto-closes at Tier4.

With the model on, all three are read correctly. But here's the actual
finding: **the validator's floor is the same keyword engine that just failed.**
It only binds when keyword matching catches something the model missed — so
on exactly the novel-phrasing cases where a model is most likely to fail,
the floor is blind too, and blinder. **My safety floor is weakest precisely
where I need it most.**

The fix isn't more keywords — it's deriving critical controls from normalized
structural facts (`hazard`, `symptoms_present`, `sensitive_receptor`,
`water_impact`) extracted from the text, so the validator reasons over facts
rather than trying to parse English itself. That still depends on extraction
not missing the fact, so production needs independent critical-signal
detection, adversarial evaluation, and human escalation under uncertainty.

This is why evaluation and validation are separate controls: offline
evaluation asks "can this version be promoted?"; the runtime validator asks
"can this specific recommendation proceed?" Neither replaces the other.

## 6. Trace, injection, and the new audit layer (1.5 min)

Every trace logs: retrieved directives (pre-classification), full
extraction, proposed tier/rationale/citations, every validator override
(rule, previous tier, new tier), routing destination with a multi-factor
`human_gate.reasons` list, and a `source` tag per node (`gemini`,
`heuristic_fallback`, `deterministic_check`/`deterministic_correction`). Maps
to EU AI Act Art. 12 (logging/traceability) and TBS DADM 6.2 (audit trails).

Five validator override rules: `under_tiering_guard` (escalate below-floor
proposals), `insufficient_information_floor` (force callback rather than
guess), `compliant_self_report` (the one downgrade rule — 5 statutory
conditions must all hold), `prompt_injection_ignored` (audit-only, forces
human review), `repeat_contact_linkage` (links repeats without resetting the
SLA clock).

New this build: a 10th, **post-decision** node — an audit summary embedded
directly in each record's trace (`trace.audit_summary`) and surfaced as a
column in the dashboard. It's Gemini reading the *completed* decision and
narrating it in plain English (with a deterministic fallback, same pattern as
every other node) — it has zero influence on tier, route, or acknowledgement;
it only explains a decision already made. Example, generated live against
R-005:

> "A report was submitted concerning unauthorized access and surveying near a
> wellhead operated by Sablefield Energy at SW-12-56-3-W5. The incident was
> classified as Tier 2 because it involves a suspected regulatory
> contravention regarding unauthorized entry onto private land, though no
> immediate environmental or life safety hazards were identified. The
> classification was validated without overrides, and human approval was not
> required. The report was ultimately routed for a field inspection, and an
> acknowledgement notification was generated."

On the injection record (R-014): sanitization strips the embedded "SYSTEM
NOTICE" instruction at node 2, **before** Gemini ever sees it. Not the model
resisting injection — a security boundary the model never had to pass.

> Prompt instruction is persuasion. The boundary is enforcement.

## 7. Close (1 min)

Enforced, not aspirational: no autonomous close of a Tier1 or harm-adjacent
case; no final contravention determination; complaint text is never treated
as process instruction; no self-modifying rules or auto-learning from
production output. Recommend, don't decide. Draft, don't send. Propose,
don't write. Escalate, don't silently close.

One qualifier: the floor's only downgrade path is `compliant_self_report`
(contained, ≤2.0 m³, no water/H2S/wildlife) — I'd want the duty team to
confirm those five conditions before treating it as authoritative.

What's needed before production: duty-team-adjudicated reference cases,
sign-off on every hard rule, privacy/records/security review, adversarial
evaluation, human ownership of every consequential decision, shadow-mode
evidence, monitoring/incident controls, and a promotion gate independent of
the person who built the system — because right now I'm the developer, rule
author, labeler, evaluator, and approver. That's not independent assurance.

---

## 8. The live run

Save the provided file as `live.json`. Three expectations to set: needs
network for Gemini (fails gracefully to the rule engine if not); most eval
output will read `skipped` on unseen records — that means *not evaluated*,
not PASS; and my own adversarial set under-tiered all four cases against the
floor, so if something looks wrong here, it probably is.

```bash
python run.py preflight live.json      # situational awareness only, no tier assigned
python run.py all live.json --fresh    # --fresh purges old traces/ first
python diff_modes.py live.json         # executive diagnostic: concordance, guard hits, overrides
```

Per record, watch: `human_gate.reasons`, any `Tier3→Tier2 [guard]` override,
`injection_stripped`, `linked_contact`, and the new Audit Summary column in
`dashboard.html` (source `gemini` or `heuristic_fallback`, also printed
inline during the run) — the plain-English explanation to hand a duty
officer without opening the raw trace.

Read results in triage order: any Tier1 first, then injection flags, then
`InsufficientInformation`, then any `under_tiering_guard` override (the
weakest component — it only helps when keywords happen to catch what the
model missed), then anything surprising. When something looks wrong, open
the trace rather than defend it — check `source` on extraction and
classification to see whether the model or the fallback produced it.

| If you see | Say |
|---|---|
| `heuristic_fallback` on a node | Call failed/timed out; fell back to the rule engine — trace shows exactly which node. |
| Unparsed `m3`/litres volume | Fails conservatively toward Tier2, not Tier4. Right direction, wrong reason. |
| Place name with "creek" | Hardcoded scrub for one place name; needs a gazetteer. |
| `location_text` as an object | Ingest nulls non-string locations silently; should WARN, not drop. |
| `NoneApplicable` contravention | Retrieval recall miss; fails closed rather than cite something unseen. |

Close: "*N* records, *N* flagged for human review, *N* reconstructable
traces plus *N* plain-English audit summaries showing what was proposed, what
was enforced, and where a human is required. I wouldn't add these straight to
the golden set — the duty team adjudicates first; only approved outcomes
become regression evidence."

---

## 9. Fast answers to expected pushback

- **Why offline eval?** Repeatable pre-deployment regression, not "no
  network in prod." Proves a model/prompt/rule change against known cases
  before promotion.
- **Why 100% on hard-rule tests?** My release policy, not a statutory
  number — zero tolerance only for a finite set of known-unacceptable
  failures (bypassed Tier1 gate, accepted injection, invented citation,
  mishandled compliant self-report).
- **Why keep validator.py if the model understands cases better?**
  Understanding and authority are different things. Gemini can recommend
  above the floor; it can't authorize below it.
- **Why not learn from human decisions?** Wrong decisions would become
  tomorrow's precedent. Approved outcomes should enter a versioned,
  governed corpus first — retrieval before fine-tuning.
- **But you showed the floor is wrong.** It under-binds (fails to escalate),
  it never over-relaxes — a missed opportunity, not an active harm. Rebuild
  on structural signals rather than delete it.
- **Which is right, your labels or Gemini's?** Unknown — that's the actual
  gap. Duty-team adjudication decides, not me.
- **What breaks at 200/week?** Retrieval first (bag-of-words won't scale),
  then quota/cost, then human review capacity — the real constraint.
- **How would you know it's failing in production?** Not the golden set —
  shadow mode against real duty-team decisions, with override rate by tier
  as the leading indicator.

---

## The one sentence to remember

> "I didn't design to a regulation by copying controls out of legislation. I
> used the regulatory outcomes as constraints: test before deployment,
> preserve evidence, bound authority, maintain effective human oversight, and
> fail safely. Golden cases, the critical-control suite, `validator.py`, and
> the audit-summary trail are my engineering implementations of those
> principles."