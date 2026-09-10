# Demo prep — talk track (12 min + live run)

**Setup:** venv active, repo root, `USE_GEMINI=true`. Backup screen-recording of a clean run open in a tab.

## The 30-second version (for when they stop you)

> "Two people can't keep up with 200 contacts a week, and life-safety cases slip. So I built decision support, not an autonomous decider. Gemini interprets the messy text and proposes a tier; deterministic code owns the control plane. A validator floor can only escalate, never lower a tier — under-tiering is the failure the team fears most. A router gate forces human approval on anything life-safety, and a Tier1 can never be auto-closed. It recommends and cites; a human decides."

**Spine:** This is decision support. It extracts, proposes a tier, cites a directive, drafts an acknowledgment, and logs how it got there — and two deterministic layers the model cannot touch guarantee it never closes a file, never makes a final contravention finding, and never owns a regulatory outcome.

---

## 1. Frame (1 min)

Two people triage ~200 contacts/week; the queue runs days behind, and life-safety matters that must escalate within an hour sometimes don't. That's the only reason this exists.

Decision support: recommend, don't decide; draft, don't send; escalate, don't silently close. Design references — EU AI Act high-risk provisions and Canada's federal agentic-AI guidance — as inspiration, not a compliance claim.

---

## 2. The one design decision (4 min — the centre)

The model interprets the text. **It does not own the control plane.**

```
Gemini recommendation → validator.py (rule-derived floor) → max(model tier, floor) → router.py (human gate) → route
```

**Layer 1 — `validator.py`, the floor.** The validator independently re-derives a tier from the extracted fields and holds the final tier to that floor. `under_tiering_guard` can **escalate**; nothing lowers a tier below the floor. Under-tiering is the failure the duty team fears most, so it's the one thing I refused to leave to a model. The only downgrade is `compliant_self_report` — contained, ≤2.0 m³, no water/H2S/wildlife, **and no symptoms** — a lawful self-report to RecordsOnly under RD-101.3.

**Layer 2 — `router.py`, the human gate.** Once the tier is locked, the router decides whether a human must approve before anything executes. Nine deterministic triggers — Tier1, Life Safety, Potential H2S, Watercourse Impact, Wildlife Mortality, Prompt Injection, Minor Health Information, Sensitive Personal Information, Uncertain Classification — each add a named reason to `human_gate.reasons`. The route table has **no path from Tier1 to IntakeClose**.

> Neither layer can be overridden by model output or by complaint text.

---

## 3. Enforcement in code, not persuasion (2 min)

**Injection is a boundary, not a request.** `sanitize.py` strips embedded instructions **before Gemini is ever called**, always records a `SecurityFinding`, and forces a human gate.

> Prompt instruction is persuasion. The boundary is enforcement.

**Every decision is reconstructable.** Each trace logs retrieved directives, full extraction, proposed tier + rationale + citation, every validator override (rule, previous/new tier), route, full `human_gate.reasons`, and a `source` tag per node. Maps to EU AI Act Art. 12 / TBS DADM audit trails.

**Audit summary (`audit.py`).** A post-decision node narrates the *completed* decision in plain English for a duty officer — **zero influence** on tier, route, or acknowledgment; it only explains a decision already made.

---

## 4. What I cut, and what I know is wrong (2 min)

**Cut, deliberately:** no vector DB (in-memory hashing — first to break at volume); static HTML only; no multi-agent architecture (one bounded task — agents only where they earn it); no auto-learning; no writes to a system of record.

**Two things I'll tell you before you find them:**

- **The floor is a keyword engine, and that's its limit.** With the model off, that same engine *is* the floor — so on novel phrasing, where a model is most likely to slip, the floor is blind the same way. The fix isn't more keywords; it's deriving critical controls from structured extraction facts so the validator reasons over facts, not English. This is the argument *for* the model layer, not against it — and why evaluation (can this version promote?) and the runtime validator (can this recommendation proceed?) are separate controls.
- **My acceptance gate treats an unevaluated control as PASS.** Records outside the known set report `skipped`, and the gate reads `skipped` as "not failed." A control that wasn't evaluated is **UNKNOWN, not PASS** — first thing I'd fix.

---

## 5. The live run

```shell
python run.py preflight <panel_file>.json    # situational awareness only, no tier
python run.py all <panel_file>.json --fresh  # --fresh purges old traces
python diff_modes.py <panel_file>.json       # concordance, guard hits, overrides
```

Set expectations up front: most eval lines will read `skipped` — that means *not evaluated*, not PASS; only grounding and contravention-consistency judge unseen records.

Read in triage order: Tier1 first, then injection flags, then `InsufficientInformation`, then any `under_tiering_guard` override, then anything surprising. Per record watch `human_gate.reasons`, any `Tier→Tier [guard]`, `injection_stripped`, `linked_contact`, and the Audit Summary. **When something looks wrong, open the trace rather than defend it** — check `source` to see whether the model or the fallback produced it. If a non-English or novel-phrasing record under-tiers with the model off, that's the keyword-floor limit I described — the model layer is exactly what covers it.

Close: "*N* records, *N* flagged for human review, *N* reconstructable traces with plain-English summaries showing what was proposed, what was enforced, and where a human is required. I wouldn't add these to the golden set — the duty team adjudicates first."

---

## 6. Fast answers to pushback

- **Why keep `validator.py`?** Understanding and authority differ. Gemini can recommend above the floor; it can't authorize below it.
- **Why not learn from human decisions?** Wrong decisions become tomorrow's precedent. Approved outcomes enter a governed corpus first.
- **You showed the floor is wrong.** It under-binds, never over-relaxes — a missed escalation, not an active harm. Rebuild on structural signals, don't delete it.
- **Your labels or Gemini's?** Unknown — that's the gap; the duty team adjudicates.
- **What breaks at 200/week?** Retrieval first, then quota/cost, then human-review capacity.
- **How would you know it's failing in prod?** Shadow mode against real decisions; override rate by tier as the leading indicator.

---

## Before production

Duty-team-adjudicated reference cases; sign-off on every rule; privacy/security review; adversarial evaluation; shadow-mode evidence; monitoring; and a promotion gate independent of the person who built it — right now I'm developer, rule author, labeler, evaluator, and approver. That's not independent assurance.

> "I didn't design to a regulation by copying controls out of legislation. I used the regulatory outcomes as constraints — test before deployment, preserve evidence, bound authority, keep human oversight, fail safely. `validator.py`, the router's human gate, the critical-control suite, and the audit trail are my engineering implementations of those principles."