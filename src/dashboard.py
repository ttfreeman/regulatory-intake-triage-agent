"""Node 10 (supporting): Dashboard. Renders a single static HTML file summarizing
every processed record. No web server required.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Regulatory Intake Triage - Run Dashboard</title>
<style>
  body { font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 2rem; background: #f7f7f9; color: #1a1a1a; }
  h1 { margin-bottom: 0.25rem; }
  .meta { color: #555; margin-bottom: 1.5rem; }
  table { border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  th, td { border: 1px solid #ddd; padding: 0.5rem 0.7rem; font-size: 0.85rem; text-align: left; vertical-align: top; }
  th { background: #24304a; color: white; position: sticky; top: 0; }
  tr:nth-child(even) { background: #fafafa; }
  .tier1 { background: #ffe0e0; font-weight: bold; }
  .tier2 { background: #fff3d6; }
  .tier3 { background: #eaf3ff; }
  .tier4 { background: #eafaea; }
  .insufficient { background: #eee; }
  .flag-yes { color: #b00020; font-weight: bold; }
  .flag-no { color: #888; }
  a { color: #1a4dbf; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .summary { display: flex; gap: 1.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
  .card { background: white; padding: 0.75rem 1rem; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-width: 140px; }
  .card .num { font-size: 1.6rem; font-weight: bold; }
</style>
</head>
<body>
<h1>Regulatory Intake Triage Agent</h1>
<div class="meta">Run generated {{ generated_at }} &middot; {{ rows|length }} records processed</div>

<div class="summary">
  {% for tier, count in tier_counts.items() %}
  <div class="card"><div class="num">{{ count }}</div><div>{{ tier }}</div></div>
  {% endfor %}
  <div class="card"><div class="num">{{ human_gate_count }}</div><div>Human Approval Required</div></div>
  <div class="card"><div class="num">{{ injection_count }}</div><div>Injection Detected</div></div>
</div>

<table>
<thead>
<tr>
  <th>Record</th>
  <th>Tier</th>
  <th>Directives</th>
  <th>Route</th>
  <th>Human Flag</th>
  <th>Injection Detected</th>
  <th>Trace</th>
</tr>
</thead>
<tbody>
{% for row in rows %}
<tr class="{{ row.tier_class }}">
  <td>{{ row.record_id }}</td>
  <td>{{ row.tier }}</td>
  <td>{{ row.directives }}</td>
  <td>{{ row.route }}</td>
  <td class="{{ 'flag-yes' if row.human_flag else 'flag-no' }}">{{ 'YES: ' + row.human_reasons if row.human_flag else 'no' }}</td>
  <td class="{{ 'flag-yes' if row.injection else 'flag-no' }}">{{ 'YES' if row.injection else 'no' }}</td>
  <td><a href="../traces/{{ row.record_id }}.json">trace</a></td>
</tr>
{% endfor %}
</tbody>
</table>
</body>
</html>
"""


def build_dashboard(traces: List[Dict[str, Any]], generated_at: str) -> str:
    rows = []
    tier_counts: Dict[str, int] = {}
    human_gate_count = 0
    injection_count = 0

    for t in traces:
        tier = t["final_tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        human_flag = t["human_gate"]["human_approval_required"]
        injection = bool(t["security_findings"])
        if human_flag:
            human_gate_count += 1
        if injection:
            injection_count += 1
        rows.append(
            {
                "record_id": t["record_id"],
                "tier": tier,
                "tier_class": tier.lower().replace("insufficientinformation", "insufficient"),
                "directives": ", ".join(d["directive"] for d in t["retrieved_directives"][:2]) or "-",
                "route": t["route"],
                "human_flag": human_flag,
                "human_reasons": ", ".join(t["human_gate"]["reasons"]),
                "injection": injection,
            }
        )

    return Template(_TEMPLATE).render(
        generated_at=generated_at,
        rows=rows,
        tier_counts=tier_counts,
        human_gate_count=human_gate_count,
        injection_count=injection_count,
    )


def write_dashboard(html: str, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
