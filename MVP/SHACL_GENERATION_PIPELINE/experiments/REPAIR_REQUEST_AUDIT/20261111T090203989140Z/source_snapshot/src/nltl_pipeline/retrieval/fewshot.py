from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..errors import ConfigurationError
from ..models import ContextPack


TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(value: str) -> set[str]:
    return set(TOKEN_RE.findall(value.lower().replace("_", " ").replace("-", " ")))


class FewShotSelector:
    def __init__(self, jsonl_path: Path) -> None:
        self.examples: list[dict[str, Any]] = []
        try:
            for line in jsonl_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.examples.append(json.loads(line))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Cannot load few-shot JSONL: {jsonl_path}") from exc
        if not self.examples:
            raise ConfigurationError("Few-shot library is empty")

    @staticmethod
    def _query_tags(context: ContextPack) -> set[str]:
        requirement = context.requirement
        tags = tokens(" ".join(str(requirement.get(key, "")) for key in (
            "category", "encodingPattern", "normalizedRequirement", "sourceText"
        )))
        kinds = {term["kind"] for term in context.terms}
        datatypes = {str(term.get("datatype") or "") for term in context.terms}
        if "QuantityProperty" in kinds:
            tags.update({"quantity", "qudt", "numeric"})
        if "xsd:boolean" in datatypes:
            tags.update({"boolean", "required", "value"})
        if "ObjectProperty" in kinds:
            tags.update({"entity", "relation"})
        category = str(requirement.get("category", "")).lower()
        verification_mode = str(
            context.selection.get("dependencyContract", {}).get("verificationMode", "")
        )
        for value in context.selection.get("retrievalTags", []):
            tags.update(tokens(str(value)))
        if verification_mode == "COMPLEX_READINESS" or category == "complex":
            tags.update({
                "complex", "readiness", "external", "calculation", "inputs",
                "results", "engineering", "evidence",
            })
        elif "calculation" in category:
            tags.update({"comparison", "calculation", "sparql"})
        if "physical" in category:
            tags.update({"physical", "test", "evidence"})
        if "dynamic" in category:
            tags.update({"observation", "history", "readiness"})
        return tags

    def select(self, context: ContextPack, count: int = 2) -> list[dict[str, Any]]:
        query = self._query_tags(context)
        scored: list[tuple[float, str, dict[str, Any], list[str]]] = []
        for example in self.examples:
            example_tags = set()
            for value in example.get("retrievalTags", []):
                example_tags.update(tokens(str(value)))
            example_tags.update(tokens(str(example.get("caseId", ""))))
            overlap = sorted(query & example_tags)
            union = query | example_tags
            score = len(overlap) / len(union) if union else 0.0
            # Category routing is deliberately stronger than lexical overlap:
            # an equation in a Complex source must not select a formula/SPARQL
            # teaching example instead of the readiness boundary.
            mode = str(context.selection.get("dependencyContract", {}).get("verificationMode", ""))
            if mode == "COMPLEX_READINESS" and {"complex", "readiness"}.issubset(example_tags):
                score += 2.0
            scored.append((score, str(example.get("exampleId", "")), example, overlap))
        scored.sort(key=lambda item: (-item[0], item[1]))
        selected: list[dict[str, Any]] = []
        for score, _example_id, example, overlap in scored[:count]:
            selected.append({
                "exampleId": example.get("exampleId"),
                "caseId": example.get("caseId"),
                "retrievalTags": example.get("retrievalTags", []),
                "selectionScore": round(score, 6),
                "selectionReasons": overlap,
                "status": example.get("status"),
                "inputRequirement": example.get("inputRequirement"),
                "generatorVocabulary": example.get("generatorVocabulary", []),
                "expectedShapeTurtle": example.get("expectedShapeTurtle"),
            })
        return selected
