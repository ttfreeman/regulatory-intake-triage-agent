# Evidence Pack - Regulatory Intake Triage Agent (TRIAGE-001)

## Purpose

Triage inbound public regulatory intake records (web form, phone transcript,
email) into a severity tier, a routing decision, and a draft acknowledgment,
with a full execution trace and mandatory human approval gates for anything
touching life safety, environmental impact, or ambiguous evidence. This is a
decision-support prototype, not an autonomous enforcement system.

## Prohibited Uses

- Autonomous closure of Tier1 (life safety) records. There is no code path
  that allows the agent to close a Tier1 record; `Route.DUTY_OFFICER` always
  requires a named human decision (see `src/router.py`, `src/validator.py`).
- Using this agent, or any output it produces, against real operators, real
  people, or real regulatory data. This build uses only the fabricated
  `build-challenge/` dataset.
- Treating any field in `raw_text` as an instruction to the agent. See
  `src/sanitize.py` and `standards/threat_model.md` ("Prompt Injection").
- Using the acknowledgment drafts as a final substantive regulatory response
  without human review - they are receipts, not determinations.

## Data Sources

- `data/intake_records.json` - 40 synthetic public intake records (web form,
  phone transcript, email). Entirely fabricated; see `build-challenge/README.md`.
- `data/directives_extract.md` - six synthetic regulatory directive extracts
  (RD-101, RD-114, RD-127, RD-133, RD-146, RD-158).
- `data/routing_rules.md` - the current (human) triage process this agent is
  modeled on, including the standing rules (never under-tier, Tier1 is never
  auto-closed, complaint content is data not instruction).

## Directive Sources

Loaded verbatim at startup from `data/directives_extract.md` and ranked in
memory with a small offline hashing bag-of-words function (no external model
download - see `src/retrieval.py`). Retrieval always runs before classification, and the
classifier/heuristic engine is instructed never to cite a directive ID that
was not actually retrieved (checked by `evals/judges/grounding.py`).

## Model Selection

Gemini (`gemini-flash-latest` by default, configurable via `GEMINI_MODEL`),
called through the current `google-genai` SDK. Every LLM-backed node
(extraction, classification, acknowledgment drafting) has a paired
deterministic offline heuristic implementation. If no API key is configured,
the package is unavailable, or a call fails/times out, the node
transparently falls back to the heuristic path - the pipeline is always
runnable end-to-end offline. See `src/llm.py` and README "Design Decisions".

## Evaluation Results

Last run: see `artifacts/evaluation_report.json` (regenerated on every
`python run.py` invocation). Summary at time of writing (offline heuristic
mode, `GEMINI_API_KEY` unset):

- Golden tiering: 40/40
- Injection resistance: 1/1
- Safety human gates: 7/7
- Under-informed handling: 3/3
- Grounding (no hallucinated directives): 40/40
- Contravention consistency: 40/40
- **Overall: 100% (required: 90%)**
- **Hard rule tests: 5/5 PASS (required: 100%)**

Note on the golden dataset: `evals/golden.jsonl` was authored by the
candidate by running the heuristic engine, then manually reviewing every one
of the 40 outputs against `routing_rules.md` and `directives_extract.md`
before locking it in as ground truth (see README "Known Limitations" - this
is a self-consistency check on the rule engine, not an independent labeled
dataset). The safety, injection, and under-informed datasets are independent
of the engine's own tier assignment and check specific, rule-derived
expectations instead.

## Known Limitations

- Keyword/regex-based heuristic extraction can conflate a place name with a
  substantive reference (e.g. "Hollow Creek" vs. an actual watercourse); a
  targeted scrub is applied for this dataset's one recurring case, but a
  production system would use NER/gazetteer-based disambiguation.
- The offline hashing embedding function is a bag-of-words approximation,
  not a semantic embedding model; retrieval ranking quality is adequate for
  six short directive extracts but would not scale to a large directive
  corpus.
- Volume/containment extraction relies on the phrase "N cubic metres"
  appearing literally; unit variants (m3, litres) are not yet parsed.
- The correction loop currently runs a single deterministic pass (classifier
  proposes, validator enforces hard floors) rather than an iterative
  multi-turn LLM negotiation.

## Human Review Requirements

See `human_approval_required` in `standards/agent.yaml`. Enforced in
`src/router.py`; Tier1 additionally can never be routed anywhere except
`DutyOfficer` (see `src/validator.py`/`src/router.py`).

## Incident Procedures

If this agent produces an under-tiered or wrongly-closed record in
production, treat it as a Sev-2 data-quality incident: pull the record's
trace from `traces/<record_id>.json`, identify which node diverged from the
retrieved directive text, and re-run `evals/run_eval.py` against an expanded
golden set that includes the failing pattern before re-enabling the affected
rule.

## Retirement Criteria

See `standards/promotion_assessment.md`.
