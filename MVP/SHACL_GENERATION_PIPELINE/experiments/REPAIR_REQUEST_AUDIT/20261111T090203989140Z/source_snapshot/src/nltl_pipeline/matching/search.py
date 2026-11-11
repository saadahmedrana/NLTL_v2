from __future__ import annotations

import difflib
import re
from typing import Any

from ..retrieval.context import NLTL, VocabularyRepository


TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalized_tokens(value: str) -> set[str]:
    return set(TOKEN_RE.findall(value.lower().replace("_", " ").replace("-", " ")))


class CandidateSearcher:
    def __init__(self, vocabulary: VocabularyRepository) -> None:
        self.vocabulary = vocabulary

    @staticmethod
    def _score(query: str, term: dict[str, Any]) -> tuple[float, list[str]]:
        query_lower = query.lower()
        query_tokens = normalized_tokens(query)
        names = [
            str(term.get("localName", "")),
            str(term.get("label", "")),
            *[str(item) for item in term.get("aliases", [])],
        ]
        best_sequence = max(
            (difflib.SequenceMatcher(None, query_lower, name.lower()).ratio() for name in names if name),
            default=0.0,
        )
        term_tokens = set().union(*(normalized_tokens(name) for name in names if name))
        overlap = sorted(query_tokens & term_tokens)
        token_score = len(overlap) / len(query_tokens | term_tokens) if (query_tokens | term_tokens) else 0.0
        exact_bonus = 0.25 if any(name.lower() in query_lower for name in names if len(name) >= 4) else 0.0
        return min(1.0, 0.55 * best_sequence + 0.45 * token_score + exact_bonus), overlap

    def search(
        self,
        feedback: str,
        suspicious_iris: list[str],
        *,
        limit: int,
        minimum_score: float,
    ) -> list[dict[str, Any]]:
        unknown_names = [iri[len(NLTL):] for iri in suspicious_iris if iri.startswith(NLTL)]
        query = " ".join([feedback, *unknown_names])
        scored: list[tuple[float, str, dict[str, Any], list[str]]] = []
        for local_name, term in self.vocabulary.all_terms.items():
            score, overlap = self._score(query, term)
            if score >= minimum_score:
                scored.append((score, local_name, term, overlap))
        scored.sort(key=lambda item: (-item[0], item[1]))
        result: list[dict[str, Any]] = []
        for score, local_name, term, overlap in scored[:limit]:
            result.append({
                "localName": local_name,
                "iri": term["iri"],
                "label": term.get("label", local_name),
                "kind": term.get("kind", ""),
                "range": term.get("parentOrRange", ""),
                "datatype": term.get("datatype") or None,
                "recommendedUnit": term.get("unitIri") or None,
                "aliases": list(term.get("aliases") or []),
                "definition": term.get("normalizedDefinition", ""),
                "sourceReferences": term.get("sourceRefs", ""),
                "score": round(score, 6),
                "matchedTokens": overlap,
            })
        return result

