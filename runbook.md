# Runbook: Post-Pipeline Audit Summary (Phase 1)

## 1. Purpose

After the 9-node triage pipeline (ingest → sanitize → retrieve → extract →
classify → validate → route → acknowledge → trace) finishes for a record, the
raw trace JSON is technically complete but requires manual cross-referencing
to understand "what happened and why" in plain language. This is fine for
machine consumption but weak for demos, regulator walkthroughs, and quick
human audit review.

This phase adds a **post-decision audit summary**: one additional Gemini call
per record (with a deterministic fallback, consistent with every other
LLM-backed node in this pipeline) that reads the completed trace and produces
a short human-readable narrative connecting extraction → classification →
validation → routing → acknowledgement into one paragraph.

This is explicitly **not** a new decision-making node. It does not affect
tier, route, or acknowledgement outcomes in any way. It runs strictly after
Node 9 (trace) and only *narrates* the decision that was already made and
already persisted to `traces/`.

Phase 1 scope is the summary paragraph only. Mermaid diagram generation and
any UI rendering are explicitly out of scope for this phase (see Section 8).

## 2. Design Principles (must follow existing conventions)

1. **LLM + deterministic fallback pairing.** Every existing LLM-backed node
   (`extract.py`, `classify.py`, `acknowledge.py`) tries Gemini via
   `LLMClient.generate_json()` and falls back to a deterministic heuristic
   if `llm.available` is `False` or the call returns `None`. The new audit
   summary node must follow the exact same pattern — never raise, never block
   the pipeline, always produce a result.
2. **Source attribution.** Every model in `src/models.py` that can be
   AI-generated carries a `source: str` field (`"gemini"` or
   `"heuristic_fallback"`/`"deterministic"`). The new `AuditSummary` model
   must do the same.
3. **No effect on the decision path.** The audit summary must be generated
   from data that is already final (i.e., call it after `build_trace()` /
   `write_trace()`, using the same variables already in scope in
   `process_all()`). It must never be consulted by validator/router/
   acknowledge logic.
4. **Per-record, not batch.** Like every other node, this runs once per
   record inside the existing `for record in records:` loop in
   `run.py::process_all()`.
5. **Never crash the run.** Wrap the summary call the same way the rest of
   the loop body is wrapped — a failure here should be caught and logged,
   not allowed to fail the whole record (the existing `except Exception as e`
   per-record error handling in `process_all()` already covers this if the
   call is placed inside the try block, but the summary generation itself
   should also internally guard against `None`/exceptions from the LLM
   client, exactly like `acknowledge.py` does).

## 3. New Files to Create

### 3.1 `src/audit.py` (new module — the "audit summary" node)

Responsibilities:
- Define `generate_audit_summary(...)` — builds a Gemini prompt from the
  already-computed trace fields, calls `llm.generate_json(...)`, and returns
  an `AuditSummary` object either from Gemini or from a deterministic
  fallback string built with plain string formatting (no Jinja2 template
  needed for Phase 1 — the fallback is simple enough to build inline, but a
  template file may be used instead if it better matches the pattern in
  `acknowledge.py`; either approach is acceptable as long as it degrades
  gracefully).

Suggested signature (mirrors `draft_acknowledgement`'s parameter style):

```python
def generate_audit_summary(
    record_id: str,
    extraction: ExtractionResult,
    classification: ClassificationResult,
    validator_result: ValidatorResult,
    routing_result: RoutingResult,
    acknowledgement: Acknowledgement,
    llm: LLMClient,
) -> AuditSummary:
    ...
```

Gemini prompt content (adapt freely, but must include):
- Role framing: "You are an audit summarizer for a regulatory intake triage
  pipeline."
- The record id.
- Key extraction facts: location, operator, hazard/substance, symptoms,
  potential_water_impact, potential_wildlife_impact, potential_h2s,
  insufficient_information.
- Classification: proposed tier, rationale (short), contravention_suspected.
- Validator: final_tier, list of override rule names applied (if any),
  reclassified flag.
- Router: route destination, human_approval_required, reasons list.
- Acknowledgement: send_acknowledgement, source.
- Explicit instructions:
  - "Write 3-5 sentences in plain English explaining what was reported, how
    it was classified, whether/why it was escalated for human approval, and
    where it was routed."
  - "Do not invent facts not present in the trace."
  - "Do not promise a specific outcome or regulatory finding."
  - 'Return ONLY a JSON object: {"summary": string}'
- Call `llm.generate_json(prompt)` exactly like `acknowledge.py` does; check
  `data and data.get("summary")` before trusting it.

Deterministic fallback (when `llm.available` is `False` or Gemini returns
nothing usable): build a summary string via plain Python f-string
concatenation, e.g.:

```
"Record {record_id} was reported with the following details: location
{location}, operator {operator}, hazard {hazard}. It was classified as
{final_tier} ({rationale_short}). {overrides_sentence} It was routed to
{route}{approval_sentence}. {ack_sentence}"
```

Where:
- `overrides_sentence` is `"No validator overrides were applied."` or
  `"Validator override(s) applied: {rule names}."` (join
  `validator_result.overrides[i].rule`).
- `approval_sentence` is `""` if no approval required, or
  `", and requires human approval because: {', '.join(reasons)}"` if
  `routing_result.human_gate.human_approval_required` is `True`.
- `ack_sentence` is `"An acknowledgement was sent to the reporter."` or
  `f"No acknowledgement was sent: {acknowledgement.skip_reason}"`.

This keeps the fallback fully deterministic and traceable, consistent with
every other fallback in the codebase.

### 3.2 `prompts/audit_summary.md` (optional, only if you choose the template
route for the fallback instead of inline f-strings)

If you prefer to mirror `acknowledge.py`'s Jinja2-template fallback pattern
exactly (recommended for consistency), create this file following the same
structure as `prompts/acknowledgement.md` (route-conditional Jinja2 blocks
are not needed here — a single template with variables is sufficient since
this is a narrative, not a route-specific message). Either approach
(inline f-string vs. Jinja2 template file) is acceptable; pick one and note
the choice in the PR description.

## 4. Model Changes

### 4.1 Add `AuditSummary` to `src/models.py`

Add near the bottom of the file, after `Acknowledgement`:

```python
class AuditSummary(BaseModel):
    record_id: str
    summary_text: str
    source: str = "unset"  # "gemini" or "heuristic_fallback"
    generated_at: str
```

`generated_at` should be an ISO-8601 UTC timestamp
(`datetime.now(timezone.utc).isoformat()`), consistent with timestamps
elsewhere in `trace.py`.

## 5. Output Storage — New `audits/` Folder

Create a new top-level folder `audits/` (sibling to `traces/`), created at
runtime the same way `traces/` is (via `Path.mkdir(parents=True,
exist_ok=True)`), not committed with pre-existing content.

Add a `write_audit_summary()` helper, either in `src/audit.py` itself or in
`src/trace.py` alongside `write_trace()` (placing it in `src/audit.py` next
to `generate_audit_summary()` is preferred for cohesion). Mirror
`write_trace()`'s behavior exactly, including the collision-avoidance suffix
loop:

```python
def write_audit_summary(summary: AuditSummary, audits_dir: str | Path) -> Path:
    audits_dir = Path(audits_dir)
    audits_dir.mkdir(parents=True, exist_ok=True)
    path = audits_dir / f"{summary.record_id}.json"
    suffix = 2
    while path.exists():
        path = audits_dir / f"{summary.record_id}-{suffix}.json"
        suffix += 1
    path.write_text(json.dumps(summary.model_dump(), indent=2), encoding="utf-8")
    return path
```

Each file: `audits/{record_id}.json`, containing the serialized
`AuditSummary` (i.e., `record_id`, `summary_text`, `source`,
`generated_at`).

## 6. Wiring into `run.py`

### 6.1 Imports

Add to the existing import block near the top of `run.py` (alongside the
other `src.*` imports):

```python
from src.audit import generate_audit_summary, write_audit_summary
```

### 6.2 Call site in `process_all()`

Insert the call **after** `write_trace(trace, ROOT / "traces")` and its
`print_stage(record_id, 9, "trace", "execution trace written")` line, but
still **inside** the existing per-record `try` block (so a failure here is
caught by the existing `except Exception as e:` and reported as a per-record
error rather than crashing the whole batch — though internally
`generate_audit_summary` should already guard against exceptions the same
way `LLMClient.generate_json` does, so this should only ever fail on a truly
unexpected bug).

```python
            write_trace(trace, ROOT / "traces")
            print_stage(record_id, 9, "trace", "execution trace written")

            audit_summary = generate_audit_summary(
                record_id,
                extraction,
                classification,
                validator_result,
                routing_result,
                acknowledgement,
                llm,
            )
            write_audit_summary(audit_summary, ROOT / "audits")
            console.print(
                f"      [dim]- audit summary ({audit_summary.source}): "
                f"{audit_summary.summary_text[:120]}...[/dim]"
            )

            traces.append(trace)
```

Do not add this as a numbered stage in the `9/9` progress output (it is
explicitly post-pipeline, not part of the 9 decision nodes) — the indented
`console.print` line above (matching the style already used for the
per-check validation lines, e.g. `f"      [dim]- {check_name}: ..."`) is
sufficient and keeps the "9/9" framing intact.

### 6.3 `--fresh` flag behavior

`run.py` already purges `traces/*.json` when `--fresh` is passed (see the
existing purge logic around line 212-218 that targets `ROOT / "traces"`).
Extend the same purge logic to also clear `audits/*.json` so a fresh run
doesn't mix old and new audit summaries. Follow the exact same
glob-and-unlink pattern already used for `traces_dir`.

## 7. `.gitignore`

Check the existing `.gitignore` for how `traces/` is handled (it is
generated output). Add `audits/` alongside it so generated audit summaries
are not committed, consistent with how trace output is treated.

## 8. Explicitly Out of Scope for Phase 1

- Mermaid diagram generation (defer to Phase 2 — would extend the same
  Gemini prompt/JSON schema to add a `"mermaid_diagram"` key and a matching
  `mermaid_diagram: Optional[str]` field on `AuditSummary`).
- Any dashboard/HTML rendering of the summary (Phase 2/3 — would integrate
  with `src/dashboard.py`).
- Batch-level (all-records) roll-up summary — this phase is strictly
  per-record.
- Any change to tier, route, or acknowledgement decision logic.

## 9. Acceptance Criteria

1. Running `python run.py all data/intake_records.json` (or `triage`)
   produces one new file per processed record at
   `audits/{record_id}.json` containing valid JSON with keys `record_id`,
   `summary_text`, `source`, `generated_at`.
2. With no `GEMINI_API_KEY` / `USE_GEMINI` unset (offline mode, the default),
   every `audits/*.json` file has `"source": "heuristic_fallback"` and a
   non-empty, factually consistent `summary_text` built only from the
   record's own trace data (no hallucinated facts, since it's pure string
   formatting).
3. With a valid Gemini key and `USE_GEMINI=true`, `audits/*.json` files may
   have `"source": "gemini"` with a natural-language paragraph; if the
   Gemini call fails for any reason, the record must still get a
   `heuristic_fallback` summary — the run must never crash or skip writing
   an audit file for a record that otherwise completed the 9-node pipeline.
4. `--fresh` clears both `traces/*.json` and `audits/*.json` before the run.
5. No existing test, trace shape, or dashboard output changes — `traces/`
   content and `artifacts/dashboard.html` generation remain byte-for-byte
   unaffected by this change (the audit summary is purely additive, written
   to its own new folder).
6. `python -m py_compile src/audit.py src/models.py run.py` (or equivalent
   lint/import check) passes with no errors.

## 10. Suggested Test/Verification Steps

1. Run `python run.py triage build-challenge/intake_records.json` (or the
   project's existing sample dataset) with no `GEMINI_API_KEY` set — confirm
   `audits/` is created with one JSON file per record, all
   `source: "heuristic_fallback"`.
2. Spot-check 2-3 `audits/{record_id}.json` files against their
   corresponding `traces/{record_id}.json` to confirm the summary text
   accurately reflects `final_tier`, `route`, `human_gate.reasons`, and
   `acknowledgement.send_acknowledgement` with no invented details.
3. Re-run with `--fresh` and confirm old `audits/*.json` files are removed
   first.
4. If a Gemini key is available, set `GEMINI_API_KEY` and `USE_GEMINI=true`
   and re-run; confirm `source: "gemini"` appears and text still reads as a
   coherent 3-5 sentence paragraph with no promised outcomes.
