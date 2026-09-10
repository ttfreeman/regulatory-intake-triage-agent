#!/usr/bin/env python3
"""Entry point: python run.py [command] [path/to/intake_records.json]

Commands:
  (none) / triage   Run the full pipeline (Ingest -> Sanitize -> Directive
                    Retrieval -> Extraction -> Classification -> Validation
                    -> Routing -> Acknowledgement -> Trace), write per-record
                    traces, build the static dashboard, then run the
                    evaluation harness and print a report.
  preflight         Run only the preflight intake analysis assistant and
                    write artifacts/preflight_report.html +
                    artifacts/preflight_manifest.json.
  all               Run preflight, then the full triage pipeline.
  serve             Serve the artifacts/ directory over http://localhost:8000.

Flags:
  --fresh           Purge traces/*.json before running (any command except
                    serve). Prevents a stale trace from a previous rehearsal
                    or dataset being mistaken for output of the current run.

Backward compatible: `python run.py data/intake_records.json` (no command)
still runs triage-only, as before.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.acknowledge import draft_acknowledgement
from src.audit import generate_audit_summary
from src.classify import classify_record
from src.dashboard import build_dashboard, write_dashboard
from src.extract import extract_record
from src.ingest import load_records
from src.llm import LLMClient
from src.preflight.html_dashboard import build_preflight_html, write_preflight_html
from src.preflight.report_builder import build_preflight_report
from src.retrieval import DirectiveRetriever
from src.router import route_record
from src.sanitize import detect_and_sanitize
from src.trace import build_trace, execution_event, write_trace
from src.validator import validate_and_correct

console = Console()

COMMANDS = {"preflight", "triage", "all", "serve"}


def run_preflight(records_path: str) -> dict:
    load_dotenv(ROOT / ".env")
    llm = LLMClient()

    console.print(
        f"[bold]Preflight Intake Analysis[/bold] - analyzing {records_path}\n"
    )
    console.print(
        "[dim]Stages: ingest -> profile -> duplicates -> injection scan -> PII scan -> cluster -> analyze[/dim]"
    )
    stage_number = 0
    preflight_errors: list[dict] = []

    def print_preflight_stage(event: dict) -> None:
        nonlocal stage_number
        stage_number += 1
        details = ", ".join(
            f"{key}: {value}"
            for key, value in event.items()
            if key not in {"timestamp", "stage", "status", "summary"}
        )
        suffix = f"; {details}" if details else ""
        console.print(
            f"  [green]OK[/green] [bold]{stage_number}/7 {event['stage']:<20}[/bold] "
            f"[dim]{event['summary']}{suffix}[/dim]"
        )

    try:
        report = build_preflight_report(records_path, llm, print_preflight_stage)
    except Exception as e:
        error_detail = {
            "stage": "preflight_analysis",
            "error_type": type(e).__name__,
            "error_message": str(e),
        }
        preflight_errors.append(error_detail)
        console.print(
            f"[red]ERROR[/red] Preflight analysis failed: {type(e).__name__}: {str(e)}"
        )
        print(
            f"ERROR Preflight analysis failed: {type(e).__name__}: {str(e)}",
            file=sys.stderr,
        )
        # Return empty report structure to prevent downstream crashes
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schema_results": [],
            "profile": {},
            "duplicates": [],
            "security_findings": [],
            "pii_findings": [],
            "clusters": [],
            "narrative": {},
            "manifest": {"records": 0, "warnings": 0, "holds": 0, "processable": 0},
            "human_attention_forecast": {"high_attention": []},
            "execution_log": [],
        }

    # Analyze data quality for go/no-go recommendation
    schema_results = report.get("schema_results", [])
    hold_records = [r for r in schema_results if r.get("status") == "HOLD"]
    warn_records = [r for r in schema_results if r.get("status") == "WARN"]
    ok_records = [r for r in schema_results if r.get("status") == "OK"]

    # Build go/no-go recommendation
    go_recommendation = "GO"
    go_reasons: list[str] = []
    no_go_reasons: list[str] = []

    if preflight_errors:
        go_recommendation = "NO-GO"
        no_go_reasons.append(
            f"Preflight analysis crashed: {preflight_errors[0]['error_type']}"
        )

    if hold_records:
        go_recommendation = "NO-GO"
        hold_issues = set()
        for r in hold_records:
            hold_issues.update(r.get("issues", []))
        no_go_reasons.append(
            f"{len(hold_records)} record(s) cannot be processed: {', '.join(sorted(hold_issues))}"
        )

    if go_recommendation == "GO":
        if warn_records:
            go_reasons.append(
                f"{len(warn_records)} record(s) have warnings but are processable"
            )
        if len(ok_records) == len(schema_results):
            go_reasons.append(f"All {len(ok_records)} records pass schema validation")

    # Write artifacts
    try:
        manifest_path = ROOT / "artifacts" / "preflight_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(report["manifest"], indent=2), encoding="utf-8"
        )

        html = build_preflight_html(report)
        html_path = write_preflight_html(
            html, ROOT / "artifacts" / "preflight_report.html"
        )

        console.print(f"Preflight report written to [cyan]{html_path}[/cyan]")
        console.print(f"Preflight manifest written to [cyan]{manifest_path}[/cyan]")
    except Exception as e:
        console.print(
            f"[yellow]WARNING[/yellow] Could not write artifacts: {type(e).__name__}: {str(e)}"
        )

    console.print(
        f"High attention records: {report['human_attention_forecast']['high_attention']}"
    )

    # Print go/no-go recommendation
    console.print("\n[bold]Preflight Decision[/bold]")
    if go_recommendation == "GO":
        console.print(f"[bold green]✓ GO[/bold green] - Safe to proceed to triage")
        for reason in go_reasons:
            console.print(f"  [green]✓[/green] {reason}")
        print(f"\n✓ GO - Safe to proceed to triage", file=sys.stderr)
        for reason in go_reasons:
            print(f"  ✓ {reason}", file=sys.stderr)
    else:
        console.print(
            f"[bold red]✗ NO-GO[/bold red] - Fix data quality issues before triage"
        )
        for reason in no_go_reasons:
            console.print(f"  [red]✗[/red] {reason}")
        if hold_records:
            console.print(
                "\n[bold]Records with blocking issues (cannot process):[/bold]"
            )
            for r in hold_records:
                issue_list = ", ".join(r.get("issues", []))
                console.print(f"  [red]✗[/red] {r['record_id']}: {issue_list}")
        print(f"\n✗ NO-GO - Fix data quality issues before triage", file=sys.stderr)
        for reason in no_go_reasons:
            print(f"  ✗ {reason}", file=sys.stderr)
        if hold_records:
            print("\nRecords with blocking issues (cannot process):", file=sys.stderr)
            for r in hold_records:
                issue_list = ", ".join(r.get("issues", []))
                print(f"  ✗ {r['record_id']}: {issue_list}", file=sys.stderr)

    console.print()
    # Add go_recommendation to report for downstream decision-making
    report["go_recommendation"] = go_recommendation
    return report


def purge_traces() -> None:
    traces_dir = ROOT / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    removed = sorted(f.name for f in traces_dir.glob("*.json"))
    for name in removed:
        (traces_dir / name).unlink()
    console.print(
        f"[dim]--fresh: removed {len(removed)} old trace file(s) from {traces_dir}[/dim]"
    )


def serve_artifacts(port: int = 8000) -> int:
    import functools
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    artifacts_dir = ROOT / "artifacts"

    class ArtifactHandler(SimpleHTTPRequestHandler):
        def translate_path(self, request_path: str) -> str:
            # Keep artifacts at the server root while exposing linked traces.
            path = request_path.split("?", 1)[0].rstrip("/")
            if path == "/traces" or path.startswith("/traces/"):
                self.directory = str(ROOT)
            else:
                self.directory = str(artifacts_dir)
            return super().translate_path(request_path)

    handler = functools.partial(ArtifactHandler, directory=str(artifacts_dir))
    console.print(
        f"Serving [cyan]{artifacts_dir}[/cyan] at http://localhost:{port} (Ctrl+C to stop)"
    )
    HTTPServer(("", port), handler).serve_forever()
    return 0


def process_all(records_path: str) -> list[dict]:
    load_dotenv(ROOT / ".env")

    llm = LLMClient()
    retriever = DirectiveRetriever(ROOT / "data" / "directives_extract.md")
    records = load_records(records_path)
    records = sorted(records, key=lambda r: r.get("received_utc", ""))

    duplicate_index: dict[str, str] = {}
    traces: list[dict] = []
    errors: list[dict] = []

    mode = "Gemini" if llm.available else "offline heuristic fallback"
    console.print(
        f"[bold]Regulatory Intake Triage Agent[/bold] - running in {mode} mode, {len(records)} records"
    )
    console.print(
        "[dim]Stages: ingest -> sanitize -> retrieve -> extract -> classify -> validate -> route -> acknowledge -> trace[/dim]\n"
    )

    def print_stage(
        record_id: str,
        number: int,
        stage: str,
        summary: str,
        decision_source: str = "deterministic",
    ) -> None:
        console.print(
            f"  [green]OK[/green] [bold]{number}/9 {stage:<14}[/bold] "
            f"[cyan][{decision_source}][/cyan] [dim]{summary}[/dim]"
        )

    for record in records:
        record_id = record.get("record_id", "UNKNOWN")
        try:
            console.rule(f"[bold cyan]Record {record_id}[/bold cyan]")
            execution_log = [
                execution_event(
                    "ingest", "Record loaded for triage.", record_id=record_id
                )
            ]
            print_stage(record_id, 1, "ingest", "record loaded")

            sanitized_text, security_finding = detect_and_sanitize(
                record.get("raw_text", "")
            )
            security_findings = [security_finding] if security_finding else []
            execution_log.append(
                execution_event(
                    "sanitize",
                    "Submission sanitized before downstream processing.",
                    security_findings=len(security_findings),
                )
            )
            print_stage(
                record_id,
                2,
                "sanitize",
                f"security findings: {len(security_findings)}",
            )

            directive_matches = retriever.retrieve(sanitized_text, k=3)
            execution_log.append(
                execution_event(
                    "directive_retrieval",
                    "Relevant directives retrieved before classification.",
                    matches=len(directive_matches),
                )
            )
            print_stage(
                record_id, 3, "retrieve", f"directives: {len(directive_matches)}"
            )
            extraction = extract_record(record, sanitized_text, llm)
            execution_log.append(
                execution_event(
                    "extraction",
                    "Structured fields extracted.",
                    decision_source=extraction.source,
                    source=extraction.source,
                    insufficient_information=extraction.insufficient_information,
                )
            )
            print_stage(
                record_id,
                4,
                "extract",
                f"source: {extraction.source}",
                extraction.source,
            )
            classification = classify_record(
                sanitized_text, extraction, directive_matches, llm
            )
            execution_log.append(
                execution_event(
                    "classification",
                    "Initial tier and contravention assessment produced.",
                    decision_source=classification.source,
                    source=classification.source,
                    proposed_tier=classification.tier.value,
                    contravention_suspected=classification.contravention_suspected,
                )
            )
            print_stage(
                record_id,
                5,
                "classify",
                f"proposed tier: {classification.tier.value} ({classification.source})",
                classification.source,
            )
            validator_result = validate_and_correct(
                sanitized_text,
                extraction,
                classification,
                directive_matches,
                security_findings,
                duplicate_index,
                record_id,
            )
            validation_checks = {
                "insufficient_information": (
                    "PASS"
                    if not extraction.insufficient_information
                    or validator_result.final_tier.value == "InsufficientInformation"
                    else "FAIL"
                ),
                "under_tiering_guard": (
                    "CORRECTED"
                    if any(
                        override.rule == "under_tiering_guard"
                        for override in validator_result.overrides
                    )
                    else "PASS"
                ),
                "records_only_rule": (
                    "APPLIED" if validator_result.is_records_only else "NOT_APPLICABLE"
                ),
                "prompt_injection_handling": (
                    "FLAGGED" if security_findings else "PASS"
                ),
                "repeat_contact_linkage": (
                    "LINKED" if validator_result.linked_record_id else "NONE_FOUND"
                ),
            }
            execution_log.append(
                execution_event(
                    "validation",
                    "Hard rules and correction loop completed.",
                    decision_source=(
                        "deterministic_correction"
                        if validator_result.reclassified or validator_result.overrides
                        else "deterministic_check"
                    ),
                    final_tier=validator_result.final_tier.value,
                    reclassified=validator_result.reclassified,
                    overrides=len(validator_result.overrides),
                    checks=validation_checks,
                )
            )
            print_stage(
                record_id,
                6,
                "validate",
                f"final tier: {validator_result.final_tier.value}; overrides: {len(validator_result.overrides)}",
                (
                    "deterministic_correction"
                    if validator_result.reclassified or validator_result.overrides
                    else "deterministic_check"
                ),
            )
            for check_name, check_status in validation_checks.items():
                console.print(f"      [dim]- {check_name}: {check_status}[/dim]")
            routing_result = route_record(
                extraction, classification, validator_result, security_findings
            )
            execution_log.append(
                execution_event(
                    "routing",
                    "Destination and human approval gate determined.",
                    route=routing_result.route.value,
                    human_approval_required=routing_result.human_gate.human_approval_required,
                )
            )
            print_stage(
                record_id,
                7,
                "route",
                f"destination: {routing_result.route.value}; human gate: {routing_result.human_gate.human_approval_required}",
            )
            acknowledgement = draft_acknowledgement(
                record, extraction, routing_result, validator_result, llm
            )
            execution_log.append(
                execution_event(
                    "acknowledgement",
                    "Acknowledgement decision and draft completed.",
                    decision_source=acknowledgement.source,
                    send_acknowledgement=acknowledgement.send_acknowledgement,
                    skip_reason=acknowledgement.skip_reason,
                )
            )
            print_stage(
                record_id,
                8,
                "acknowledge",
                "draft ready" if acknowledgement.send_acknowledgement else "skipped",
                acknowledgement.source,
            )
            execution_log.append(
                execution_event(
                    "trace_persistence", "Execution trace ready to be written."
                )
            )

            audit_summary = generate_audit_summary(
                record_id,
                extraction,
                classification,
                validator_result,
                routing_result,
                acknowledgement,
                llm,
            )
            console.print(
                f"      [dim]- audit summary ({audit_summary.source}): "
                f"{audit_summary.summary_text[:120]}...[/dim]"
            )

            trace = build_trace(
                record_id,
                directive_matches,
                extraction,
                classification,
                validator_result,
                routing_result,
                acknowledgement,
                security_findings,
                execution_log,
                audit_summary,
            )
            write_trace(trace, ROOT / "traces")
            print_stage(record_id, 9, "trace", "execution trace written")

            traces.append(trace)
        except Exception as e:
            error_detail = {
                "record_id": record_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "line_number": e.__traceback__.tb_lineno if e.__traceback__ else None,
            }
            errors.append(error_detail)
            console.print(
                f"[red]ERROR[/red] Record {record_id} failed: {type(e).__name__}: {str(e)}"
            )
            print(
                f"ERROR Record {record_id} failed: {type(e).__name__}: {str(e)}",
                file=sys.stderr,
            )
            continue

    # Report error summary
    if errors:
        console.print(
            f"\n[bold red]⚠️  {len(errors)} record(s) failed processing[/bold red]"
        )
        for error in errors:
            console.print(
                f"  [red]✗[/red] {error['record_id']}: {error['error_type']} - {error['error_message']}"
            )
        console.print(
            f"\n[yellow]Summary: {len(traces)} successful, {len(errors)} failed out of {len(records)} total[/yellow]"
        )
        print(f"\n⚠️  {len(errors)} record(s) failed processing", file=sys.stderr)
        for error in errors:
            print(
                f"  ✗ {error['record_id']}: {error['error_type']} - {error['error_message']}",
                file=sys.stderr,
            )
        print(
            f"\nSummary: {len(traces)} successful, {len(errors)} failed out of {len(records)} total",
            file=sys.stderr,
        )
    else:
        console.print(
            f"\n[bold green]✓ All {len(records)} records processed successfully[/bold green]"
        )
        print(f"\n✓ All {len(records)} records processed successfully", file=sys.stderr)

    return traces


def render_summary_table(traces: list[dict]) -> None:
    table = Table(title="Triage Results")
    table.add_column("Record", style="bold cyan")
    table.add_column("Tier")
    table.add_column("Route")
    table.add_column("Human Gate")
    table.add_column("Injection")
    table.add_column("Validator Overrides", style="yellow")
    for t in traces:
        ov_strs = []
        for ov in t.get("validator_overrides", []):
            rule = ov.get("rule")
            if rule == "under_tiering_guard":
                ov_strs.append(
                    f"{ov.get('previous_tier')}→{ov.get('new_tier')} [guard]"
                )
            elif rule == "repeat_contact_linkage":
                ov_strs.append("linked_contact")
            elif rule == "prompt_injection_ignored":
                ov_strs.append("injection_stripped")
            elif rule == "compliant_self_report":
                ov_strs.append("self_report_floor")
            elif rule == "insufficient_information_floor":
                ov_strs.append("insufficient_info_floor")
            else:
                ov_strs.append(rule)
        table.add_row(
            t["record_id"],
            t["final_tier"],
            t["route"],
            "YES" if t["human_gate"]["human_approval_required"] else "-",
            "YES" if t["security_findings"] else "-",
            ", ".join(ov_strs) if ov_strs else "-",
        )
    console.print(table)


def main() -> int:
    args = sys.argv[1:]
    fresh = "--fresh" in args
    if fresh:
        args = [a for a in args if a != "--fresh"]
    command = args[0] if args and args[0] in COMMANDS else None

    if command == "serve":
        return serve_artifacts()

    if fresh:
        purge_traces()

    records_path = (
        args[1]
        if command and len(args) > 1
        else (args[0] if not command and args else None)
    ) or str(ROOT / "data" / "intake_records.json")

    if command == "preflight":
        run_preflight(records_path)
        return 0

    if command == "all":
        preflight_report = run_preflight(records_path)
        if preflight_report.get("go_recommendation") == "NO-GO":
            console.print(
                "[bold red]✗ Triage skipped[/bold red] - Preflight detected blocking data issues. "
                "Fix data quality and run preflight again."
            )
            print(
                "✗ Triage skipped - Preflight detected blocking data issues. "
                "Fix data quality and run preflight again.",
                file=sys.stderr,
            )
            return 0

    traces = process_all(records_path)
    render_summary_table(traces)

    generated_at = datetime.now(timezone.utc).isoformat()
    dashboard_html = build_dashboard(traces, generated_at)
    dashboard_path = write_dashboard(
        dashboard_html, ROOT / "artifacts" / "dashboard.html"
    )
    console.print(f"\nDashboard written to [cyan]{dashboard_path}[/cyan]")

    sample_run_path = ROOT / "artifacts" / "sample_run.json"
    sample_run_path.write_text(json.dumps(traces, indent=2), encoding="utf-8")
    console.print(f"Aggregated run output written to [cyan]{sample_run_path}[/cyan]")

    # Run the evaluation harness against the traces we just produced.
    from evals.run_eval import run_evaluation

    report = run_evaluation(traces)
    report_path = ROOT / "artifacts" / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    console.print(
        "\n[bold cyan]═══════════════════════════════════════════════════════════════[/bold cyan]"
    )
    console.print(
        "[bold cyan]                 EVALUATION & ASSURANCE REPORT                 [/bold cyan]"
    )
    console.print(
        "[bold cyan]═══════════════════════════════════════════════════════════════[/bold cyan]"
    )

    # 1. Critical Control Suite (Binary Invariants: Release Standard = 100%)
    hard_rules_ok = report["hard_rule_tests"]["all_passed"]
    console.print(
        "\n[bold]1. Critical Control Suite[/bold] [dim](Release Standard: 100% zero-regression on known invariants)[/dim]"
    )

    crit_table = Table(box=None, padding=(0, 2))
    crit_table.add_column("Invariant / Check", style="dim")
    crit_table.add_column("Result")
    crit_table.add_column("Status")

    for r in report["hard_rule_tests"]["results"]:
        status = (
            "[green]PASS[/green]"
            if r["status"] == "passed"
            else "[yellow]NOT EVALUATED (skipped)[/yellow]"
            if r["status"] == "skipped"
            else "[red]FAIL[/red]"
        )
        crit_table.add_row(
            f"Hard Rule: {r['name']}", f"Record {r['record_id']}", status
        )

    for ds_name in (
        "safety_human_gates",
        "injection_resistance",
        "under_informed",
        "grounding",
        "contravention_consistency",
    ):
        if ds_name in report["datasets"]:
            res = report["datasets"][ds_name]
            skipped = len(res.get("skipped", []))
            status = (
                "[green]100% PASS[/green]"
                if res["pass_rate"] == 100.0 and res["total"] > 0
                else (
                    "[yellow]NOT EVALUATED[/yellow]"
                    if res["total"] == 0
                    else f"[red]{res['pass_rate']:.1f}%[/red]"
                )
            )
            crit_table.add_row(
                f"Invariant: {ds_name}",
                f"{res['passed']}/{res['total']} passed ({skipped} skipped)",
                status,
            )

    console.print(crit_table)

    # 2. Probabilistic Quality Reference (Target >= 90.0%)
    console.print(
        "\n[bold]2. Probabilistic Quality Reference[/bold] [dim](Target: ≥ 90.0% against candidate golden baseline)[/dim]"
    )
    golden_res = report["datasets"].get("golden_tiering", {})
    golden_skipped = len(golden_res.get("skipped", []))
    console.print(
        f"  • Golden reference tiering: [bold]{golden_res.get('passed', 0)}/{golden_res.get('total', 0)}[/bold] applicable ({golden_res.get('pass_rate', 100.0):.1f}%, {golden_skipped} skipped)"
    )
    console.print(
        f"  • Overall combined pass rate: [bold]{report['overall_pass_rate']:.1f}%[/bold] (Threshold: {report['required_overall_pass_rate']:.1f}%)"
    )

    if (
        not hard_rules_ok
        or report["overall_pass_rate"] < report["required_overall_pass_rate"]
    ):
        console.print(
            "\n[bold red]BUILD FAILED[/bold red]: acceptance criteria not met on statistical reference set."
        )
        if hard_rules_ok:
            console.print(
                "  [dim green]✓ All Critical Control safety invariants passed (100.0%).[/dim green]"
            )
        return 1

    console.print("\n[bold green]Acceptance criteria met.[/bold green]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
