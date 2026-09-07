"""Preflight visualization dashboard. Single static HTML file, no server or
JS framework required - matches src/dashboard.py's approach and visual style.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from jinja2 import Template

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Preflight Intake Analysis</title>
<style>
  body { font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 2rem; background: #f7f7f9; color: #1a1a1a; }
  h1 { margin-bottom: 0.25rem; }
  h2 { margin-top: 2.5rem; border-bottom: 2px solid #24304a; padding-bottom: 0.25rem; }
  .meta { color: #555; margin-bottom: 1.5rem; }
  table { border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 1rem; }
  th, td { border: 1px solid #ddd; padding: 0.5rem 0.7rem; font-size: 0.85rem; text-align: left; vertical-align: top; }
  th { background: #24304a; color: white; }
  tr:nth-child(even) { background: #fafafa; }
  a { color: #1a4dbf; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .summary { display: flex; gap: 1.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
  .card { background: white; padding: 0.75rem 1rem; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-width: 140px; }
  .card .num { font-size: 1.6rem; font-weight: bold; }
  .flag-yes { color: #b00020; font-weight: bold; }
  .flag-no { color: #888; }
  .bar-row { display: flex; align-items: center; gap: 0.5rem; margin: 0.3rem 0; font-size: 0.85rem; }
  .bar-label { width: 220px; flex-shrink: 0; }
  .bar-track { background: #eee; flex-grow: 1; border-radius: 3px; height: 14px; }
  .bar-fill { background: #464feb; height: 14px; border-radius: 3px; }
  .bar-count { width: 40px; text-align: right; }
  .narrative-box { background: white; padding: 1rem 1.25rem; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .narrative-box ul { margin: 0.4rem 0 1rem 1.2rem; }
  .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
  .badge-gemini { background: #e0e8ff; color: #1a4dbf; }
  .badge-heuristic { background: #eee; color: #555; }
  .status-OK { color: #1a7a1a; }
  .status-WARN { color: #b8860b; }
  .status-HOLD { color: #b00020; font-weight: bold; }
</style>
</head>
<body>
<h1>Preflight Intake Analysis</h1>
<div class="meta">Generated {{ report.generated_at }} &middot; {{ report.profile.records }} records &middot; preceding triage, not a substitute for it</div>

<div class="summary">
  <div class="card"><div class="num">{{ report.manifest.records }}</div><div>Records</div></div>
  <div class="card"><div class="num">{{ report.manifest.processable }}</div><div>Processable</div></div>
  <div class="card"><div class="num">{{ report.manifest.warnings }}</div><div>Warnings</div></div>
  <div class="card"><div class="num">{{ report.manifest.holds }}</div><div>Holds</div></div>
  <div class="card"><div class="num">{{ report.manifest.duplicate_candidates }}</div><div>Duplicate Candidates</div></div>
  <div class="card"><div class="num">{{ report.manifest.security_findings }}</div><div>Security Findings</div></div>
  <div class="card"><div class="num">{{ report.manifest.clusters }}</div><div>Clusters</div></div>
</div>

<h2>0. Execution Log</h2>
<table>
<thead><tr><th>Time</th><th>Stage</th><th>Status</th><th>Summary</th><th>Details</th></tr></thead>
<tbody>
{% for event in report.execution_log %}
<tr><td>{{ event.timestamp }}</td><td>{{ event.stage }}</td><td class="status-{{ event.status }}">{{ event.status }}</td>
<td>{{ event.summary }}</td><td>{% for key, value in event.items() if key not in ['timestamp', 'stage', 'status', 'summary'] %}{{ key }}={{ value }}{% if not loop.last %}; {% endif %}{% endfor %}</td></tr>
{% endfor %}
</tbody>
</table>

<h2>1. Executive Summary</h2>
<div class="narrative-box">
  <span class="badge {{ 'badge-gemini' if report.narrative.source == 'gemini' else 'badge-heuristic' }}">
    {{ 'Gemini-assisted' if report.narrative.source == 'gemini' else 'Heuristic (offline)' }}
  </span>
  <p>{{ report.narrative.executive_summary }}</p>
  <strong>Suggested human attention areas:</strong>
  <ul>{% for item in report.narrative.suggested_human_attention_areas %}<li>{{ item }}</li>{% endfor %}</ul>
</div>

<h2>2. Dataset Overview</h2>
<strong>Operator distribution</strong>
{% for op, count in report.profile.operator_distribution.items() %}
<div class="bar-row">
  <div class="bar-label">{{ op }}</div>
  <div class="bar-track"><div class="bar-fill" style="width: {{ (count / report.profile.records * 100)|round(1) }}%"></div></div>
  <div class="bar-count">{{ count }}</div>
</div>
{% endfor %}
<strong>Channel distribution</strong>
{% for ch, count in report.profile.channel_distribution.items() %}
<div class="bar-row">
  <div class="bar-label">{{ ch }}</div>
  <div class="bar-track"><div class="bar-fill" style="width: {{ (count / report.profile.records * 100)|round(1) }}%"></div></div>
  <div class="bar-count">{{ count }}</div>
</div>
{% endfor %}
<p>Average length: {{ report.profile.avg_length }} chars &middot; Median: {{ report.profile.median_length }} chars &middot;
Longest: {{ report.profile.longest_record.record_id }} ({{ report.profile.longest_record.length }}) &middot;
Shortest: {{ report.profile.shortest_record.record_id }} ({{ report.profile.shortest_record.length }})</p>

<h2>3. Quality Analysis</h2>
<table>
<thead><tr><th>Record</th><th>Status</th><th>Issues</th></tr></thead>
<tbody>
{% for r in report.schema_results if r.status != 'OK' %}
<tr><td>{{ r.record_id }}</td><td class="status-{{ r.status }}">{{ r.status }}</td><td>{{ r.issues|join(', ') }}</td></tr>
{% endfor %}
</tbody>
</table>

<h2>4. Potential Duplicate Chains</h2>
<table>
<thead><tr><th>Record A</th><th>Record B</th><th>Score</th><th>Reasons</th></tr></thead>
<tbody>
{% for d in report.duplicates %}
<tr><td>{{ d.record_a }}</td><td>{{ d.record_b }}</td><td>{{ d.score }}</td><td>{{ d.reasons|join(', ') }}</td></tr>
{% else %}
<tr><td colspan="4">No duplicate/repeat-contact candidates above threshold.</td></tr>
{% endfor %}
</tbody>
</table>

<h2>5. Security Findings</h2>
<table>
<thead><tr><th>Record</th><th>Injection Detected</th><th>Detail</th></tr></thead>
<tbody>
{% for f in report.security_findings %}
<tr><td>{{ f.record_id }}</td><td class="flag-yes">YES</td><td>{{ f.detail }}</td></tr>
{% else %}
<tr><td colspan="3">No prompt-injection signals detected.</td></tr>
{% endfor %}
</tbody>
</table>

<h2>6. Complaint Clusters</h2>
<table>
<thead><tr><th>Cluster</th><th>Members</th></tr></thead>
<tbody>
{% for c in report.clusters %}
<tr><td>{{ c.cluster }}</td><td>{{ c.members|join(', ') }}</td></tr>
{% endfor %}
</tbody>
</table>

<h2>7. Gemini Analysis</h2>
<div class="narrative-box">
  <strong>Emerging themes:</strong>
  <ul>{% for item in report.narrative.emerging_themes %}<li>{{ item }}</li>{% endfor %}</ul>
  <strong>Risk signals:</strong>
  <ul>{% for item in report.narrative.risk_signals %}<li>{{ item }}</li>{% endfor %}</ul>
  <strong>Potential repeat incidents:</strong>
  <ul>{% for item in report.narrative.potential_repeat_incidents %}<li>{{ item }}</li>{% endfor %}</ul>
  <strong>Data quality issues:</strong>
  <ul>{% for item in report.narrative.data_quality_issues %}<li>{{ item }}</li>{% endfor %}</ul>
  <strong>Interesting patterns:</strong>
  <ul>{% for item in report.narrative.interesting_patterns %}<li>{{ item }}</li>{% endfor %}</ul>
  <strong>Limitations:</strong>
  <ul>{% for item in report.narrative.limitations %}<li>{{ item }}</li>{% endfor %}</ul>
</div>

<h2>8. Appendix</h2>
<p>PII / sensitive-data signals: {{ report.pii_findings|length }} record(s) flagged.</p>
<table>
<thead><tr><th>Record</th><th>Signals</th></tr></thead>
<tbody>
{% for f in report.pii_findings %}
<tr><td>{{ f.record_id }}</td><td>{{ f.signals|join(', ') }}</td></tr>
{% else %}
<tr><td colspan="2">No sensitive-data signals detected.</td></tr>
{% endfor %}
</tbody>
</table>
<p style="color:#888; font-size: 0.8rem;">This report is a review-priority forecast only. It does not assign a
severity tier, contravention assessment, or routing decision - see the
triage dashboard (artifacts/dashboard.html) for those outcomes.</p>

</body>
</html>
"""


def build_preflight_html(report: Dict[str, Any]) -> str:
    return Template(_TEMPLATE).render(report=report)


def write_preflight_html(html: str, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
