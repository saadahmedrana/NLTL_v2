from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from typing import Any

from rdflib import Graph, URIRef
from rdflib.compare import to_isomorphic
from rdflib.namespace import SH

from ..models import ValidatorIssue
from ..retrieval.context import NLTL


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def issue_key(issue: ValidatorIssue) -> str:
    return "|".join((_normalize(issue.category), _normalize(issue.location)))


def guard_key(value: str) -> str:
    words = re.findall(r"[a-z0-9]+", _normalize(value).replace("millimetre", "millimeter"))
    return " ".join(words)


def issues_payload(issues: list[ValidatorIssue]) -> list[dict[str, Any]]:
    return [asdict(issue) for issue in issues]


def format_issues(issues: list[ValidatorIssue]) -> str:
    blocking = [issue for issue in issues if issue.blocking]
    if not blocking:
        return "No concrete blocking defect detected in the current candidate."
    return " | ".join(
        f"[{issue.category}] {issue.location}: {issue.problem} Required change: {issue.required_change}"
        for issue in blocking
    )


class RepairMemory:
    def __init__(self) -> None:
        self.current_issues: list[ValidatorIssue] = []
        self._guards: dict[str, str] = {}

    @property
    def guards(self) -> list[str]:
        unique: dict[str, str] = {}
        for value in self._guards.values():
            unique.setdefault(guard_key(value), value)
        return [unique[key] for key in sorted(unique)]

    def transition(self, new_issues: list[ValidatorIssue]) -> None:
        new_by_key = {issue_key(issue): issue for issue in new_issues if issue.blocking}
        for old in self.current_issues:
            key = issue_key(old)
            if key not in new_by_key:
                guard = old.regression_guard.strip()
                self._guards[key] = guard
        open_keys = set(new_by_key)
        self._guards = {key: value for key, value in self._guards.items() if key not in open_keys}
        self.current_issues = list(new_issues)


def static_issues(errors: list[str]) -> list[ValidatorIssue]:
    issues: list[ValidatorIssue] = []
    for error in errors:
        lower = error.lower()
        vocabulary = any(token in lower for token in ("vocabulary", "canonical", "unknown", "out of scope"))
        issues.append(ValidatorIssue(
            category="CANONICAL_VOCABULARY" if vocabulary else "DETERMINISTIC_VALIDATION",
            location=f"deterministic validation: {error}",
            problem=error,
            required_change="Correct this deterministic error while preserving all unrelated candidate semantics.",
            regression_guard=f"Preserve the correction for deterministic finding: {error}",
            blocking=True,
            needs_vocabulary_resolution=vocabulary,
            source="STATIC",
        ))
    return issues


def packet_sha256(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def rdf_identity(turtle: str) -> str | None:
    try:
        graph = Graph().parse(data=turtle, format="turtle")
        return str(to_isomorphic(graph).graph_digest())
    except Exception:
        return None


def repair_diff(previous: str, current: str) -> dict[str, Any]:
    before = Graph().parse(data=previous, format="turtle")
    after = Graph().parse(data=current, format="turtle")
    before_iso, after_iso = to_isomorphic(before), to_isomorphic(after)
    added = after - before
    removed = before - after
    nltl = lambda graph: sorted({str(node) for triple in graph for node in triple if isinstance(node, URIRef) and str(node).startswith(NLTL)})
    paths = lambda graph: sorted({str(value) for value in graph.objects(None, SH.path)})
    targets = lambda graph: sorted({f"{predicate}|{value}" for predicate in (SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf, SH.target) for value in graph.objects(None, predicate)})
    before_paths, after_paths = set(paths(before)), set(paths(after))
    before_targets, after_targets = set(targets(before)), set(targets(after))
    before_terms, after_terms = set(nltl(before)), set(nltl(after))
    return {
        "previous_candidate_sha256": hashlib.sha256(previous.encode()).hexdigest(),
        "new_candidate_sha256": hashlib.sha256(current.encode()).hexdigest(),
        "normalized_rdf_equal": before_iso == after_iso,
        "triple_count_before": len(before), "triple_count_after": len(after),
        "triples_added": len(added), "triples_removed": len(removed),
        "canonical_nltl_terms_added": sorted(after_terms - before_terms),
        "canonical_nltl_terms_removed": sorted(before_terms - after_terms),
        "shacl_paths_added": sorted(after_paths - before_paths),
        "shacl_paths_removed": sorted(before_paths - after_paths),
        "shacl_targets_added": sorted(after_targets - before_targets),
        "shacl_targets_removed": sorted(before_targets - after_targets),
    }
