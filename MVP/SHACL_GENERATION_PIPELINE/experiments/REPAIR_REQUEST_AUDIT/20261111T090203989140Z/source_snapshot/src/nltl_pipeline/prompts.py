from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import PIPELINE_ROOT
from .models import ContextPack, StaticValidationReport, ValidatorIssue


class PromptFactory:
    CANONICAL_VOCABULARY_NAMESPACE = "https://w3id.org/nltl/vocab#"

    def __init__(self, prompt_directory: Path | None = None) -> None:
        self.directory = prompt_directory or PIPELINE_ROOT / "prompts"
        default_directory = PIPELINE_ROOT / "prompts"

        def read_prompt(name: str) -> str:
            selected = self.directory / name
            source = selected if selected.is_file() else default_directory / name
            return source.read_text(encoding="utf-8")

        self.generator_instructions = read_prompt("generator.txt")
        # FULL_REPAIR_V2 owns these contracts centrally. A historical prompt
        # directory may still override attempt-1 generation, syntax, and matcher.
        self.validator_instructions = (default_directory / "validator.txt").read_text(encoding="utf-8")
        self.semantic_repair_instructions = (default_directory / "semantic_repair.txt").read_text(encoding="utf-8")
        self.escape_hatch_instructions = self.generator_instructions + (
            "\n\nFULL_REPAIR_V2 ESCAPE HATCH: Generate a fresh complete candidate because targeted "
            "repair was deterministically detected as stalled or oscillating. Correct all currentIssues, "
            "honor pastMistakesToAvoid as non-authoritative regression guards, and use no behavioral evidence."
        )
        self.matcher_instructions = read_prompt("vocabulary_matcher.txt")
        self.syntax_repair_instructions = read_prompt("syntax_repair.txt")

    @staticmethod
    def _json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True)

    def generator_user(
        self,
        context: ContextPack,
        few_shots: list[dict[str, Any]],
        repair_feedback: str,
        generated_shape_namespace: str,
    ) -> str:
        return self._json({
            "task": "Generate one candidate SHACL graph",
            "canonicalVocabularyNamespace": self.CANONICAL_VOCABULARY_NAMESPACE,
            "requirement": context.requirement,
            "allowedVocabulary": context.terms,
            "nodePatterns": context.node_patterns,
            "selection": context.selection,
            "usagePolicy": context.usage_policy,
            "fewShotExamples": few_shots,
            "repairFeedback": repair_feedback or "NONE",
            "generatedShapeNamespace": generated_shape_namespace,
        })

    def validator_user(
        self,
        context: ContextPack,
        candidate_shacl: str,
        report: StaticValidationReport,
        used_canonical_terms: list[dict[str, Any]],
        mismatch_candidates: list[dict[str, Any]],
        past_mistakes_to_avoid: list[str] | None = None,
    ) -> str:
        return self._json({
            "task": "Review one candidate SHACL graph for freezing before later RDF evaluation",
            "canonicalVocabularyNamespace": self.CANONICAL_VOCABULARY_NAMESPACE,
            "requirement": context.requirement,
            "selection": context.selection,
            "retrievedRelevantVocabulary": context.terms,
            "candidateUsedCanonicalTerms": used_canonical_terms,
            "candidateShacl": candidate_shacl,
            "deterministicValidation": report.to_dict(),
            "mismatchCandidates": mismatch_candidates,
            "pastMistakesToAvoid": past_mistakes_to_avoid or [],
            "registryBoundary": (
                "The complete locked registry was checked deterministically but is intentionally not embedded. "
                "Treat unknown/out-of-scope findings as authoritative. Activate the vocabulary matcher whenever "
                "a repair requires locating a canonical term or controlled value absent from the scoped context, "
                "even when no deterministic candidate was supplied yet."
            ),
            "importantBoundary": "No ship graph or expected RDF outcome is part of this review.",
        })

    def semantic_repair_user(
        self, context: ContextPack, previous_candidate_shacl: str,
        current_issues: list[ValidatorIssue], past_mistakes_to_avoid: list[str],
        generated_shape_namespace: str,
    ) -> str:
        return self._json({
            "task": "Repair the supplied current SHACL candidate",
            "canonicalVocabularyNamespace": self.CANONICAL_VOCABULARY_NAMESPACE,
            "requirement": context.requirement, "allowedVocabulary": context.terms,
            "nodePatterns": context.node_patterns, "selection": context.selection,
            "usagePolicy": context.usage_policy,
            "previousCandidateShacl": previous_candidate_shacl,
            "currentIssues": [issue.to_dict() for issue in current_issues],
            "pastMistakesToAvoid": past_mistakes_to_avoid,
            "generatedShapeNamespace": generated_shape_namespace,
        })

    def escape_hatch_user(
        self, context: ContextPack, few_shots: list[dict[str, Any]],
        current_issues: list[ValidatorIssue], past_mistakes_to_avoid: list[str],
        generated_shape_namespace: str,
    ) -> str:
        payload = json.loads(self.generator_user(context, few_shots, "", generated_shape_namespace))
        payload["task"] = "Fresh regeneration escape hatch after targeted repair became stuck"
        payload.pop("repairFeedback", None)
        payload["currentIssues"] = [issue.to_dict() for issue in current_issues]
        payload["pastMistakesToAvoid"] = past_mistakes_to_avoid
        return self._json(payload)

    def syntax_repair_user(
        self,
        candidate_response: str,
        syntax_diagnostics: dict[str, Any],
        generated_shape_namespace: str,
    ) -> str:
        return self._json({
            "task": "Repair syntax only; preserve the candidate's semantic constraints",
            "canonicalVocabularyNamespace": self.CANONICAL_VOCABULARY_NAMESPACE,
            "generatedShapeNamespace": generated_shape_namespace,
            "syntaxDiagnostics": syntax_diagnostics,
            "candidateResponse": candidate_response,
        })

    def matcher_user(
        self,
        context: ContextPack,
        current_issues: list[ValidatorIssue],
        suspicious_iris: list[str],
        candidates: list[dict[str, Any]],
    ) -> str:
        return self._json({
            "task": "Resolve one canonical vocabulary mismatch",
            "canonicalVocabularyNamespace": self.CANONICAL_VOCABULARY_NAMESPACE,
            "requirement": context.requirement,
            "selection": context.selection,
            "currentVocabularyIssues": [issue.to_dict() for issue in current_issues],
            "suspiciousIris": suspicious_iris,
            "candidates": candidates,
        })
