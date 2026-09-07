"""Node 3: Directive Retrieval. Loads the six synthetic directives into
memory and retrieves the most relevant ones for a given record.

Embeddings are produced by a small deterministic, dependency-free hashing
bag-of-words function (see HashingEmbeddingFunction) instead of downloading a
sentence-transformer model from the internet. This keeps retrieval fully
offline, which matters because everything except the Gemini call itself must
work with no network access.

Retrieval must occur before classification, and directive text/ids returned
here are the *only* directive references classification is allowed to cite -
nothing is ever hardcoded into the classification prompt or heuristic engine.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Sequence

from src.models import DirectiveMatch

_HEADING_RE = re.compile(r"^##\s+(RD-\d+)\s+(.+)$", re.MULTILINE)

_CATEGORY_BY_DIRECTIVE = {
    "RD-101": "release_reporting",
    "RD-114": "public_complaint_response",
    "RD-127": "proximity_and_setback",
    "RD-133": "flaring_and_venting",
    "RD-146": "site_access_and_landowner_notification",
    "RD-158": "noise_control",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def parse_directives(path: str | Path) -> List[Dict[str, str]]:
    """Parse directives_extract.md into a list of {directive, title, text, category}."""
    text = Path(path).read_text(encoding="utf-8")
    headings = list(_HEADING_RE.finditer(text))
    directives: List[Dict[str, str]] = []
    for i, m in enumerate(headings):
        directive_id, title = m.group(1), m.group(2).strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end].strip()
        directives.append(
            {
                "directive": directive_id,
                "title": title,
                "text": f"{title}\n{body}",
                "category": _CATEGORY_BY_DIRECTIVE.get(directive_id, "uncategorized"),
            }
        )
    return directives


class HashingEmbeddingFunction:
    """Deterministic, offline bag-of-words embedding (no model download)."""

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def _embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = _TOKEN_RE.findall(text.lower())
        for tok in tokens:
            idx = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[idx] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def __call__(self, texts: Sequence[str]) -> List[List[float]]:
        return [self._embed_one(text) for text in texts]


class DirectiveRetriever:
    def __init__(self, directives_path: str | Path):
        self.directives = parse_directives(directives_path)
        self._embed_fn = HashingEmbeddingFunction()
        self._directive_vectors = self._embed_fn([d["text"] for d in self.directives])

    def retrieve(self, query_text: str, k: int = 3) -> List[DirectiveMatch]:
        if not query_text.strip():
            return []
        query_vector = self._embed_fn([query_text])[0]
        scored = []
        for directive, vector in zip(self.directives, self._directive_vectors):
            similarity = sum(
                query_value * directive_value
                for query_value, directive_value in zip(query_vector, vector)
            )
            scored.append((1.0 - similarity, directive))

        scored.sort(key=lambda item: (item[0], item[1]["directive"]))
        return [
            DirectiveMatch(
                directive=directive["directive"],
                category=directive["category"],
                text=directive["text"],
                distance=distance,
            )
            for distance, directive in scored[: max(0, k)]
        ]
