"""Preflight Component 6: Complaint clustering.

Deterministic keyword-based theme clustering by default so the report stays
reproducible with no network/model dependency. A record may land in more
than one cluster (e.g. odour + flaring); records matching nothing land in
"Other" so every record is accounted for in the report.
"""
from __future__ import annotations

from typing import Any, Dict, List

CLUSTER_KEYWORDS: Dict[str, List[str]] = {
    "Odour": ["odour", "odor", "smell", "sulphur", "sulfur", "rotten egg", "sour gas", "h2s"],
    "Noise": ["noise", "dba", "compressor", "loud"],
    "Flaring": ["flare", "flaring", "black smoke"],
    "Access": ["gate", "fence", "without notice", "no notice", "trespass", "access"],
    "Water": ["creek", "river", "watercourse", "dugout", "slough", "ditch", "water"],
    "Wildlife": ["dead", "carcass", "wildlife", "fish kill", "songbird", "waterfowl"],
}


def cluster_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    members: Dict[str, List[str]] = {name: [] for name in CLUSTER_KEYWORDS}
    unclustered: List[str] = []

    for record in records:
        text = (record.get("raw_text") or "").lower()
        matched = False
        for name, keywords in CLUSTER_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                members[name].append(record["record_id"])
                matched = True
        if not matched:
            unclustered.append(record["record_id"])

    clusters = [{"cluster": name, "members": ids} for name, ids in members.items() if ids]
    if unclustered:
        clusters.append({"cluster": "Other", "members": unclustered})
    return clusters
