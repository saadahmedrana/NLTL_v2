from __future__ import annotations

import json
import unittest
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.retrieval.context import VocabularyRepository


NEW_TERMS = {
    "calculationCaseAssessedHullStructure", "frameAttachmentRecord", "hasWeld",
    "iceConditionLessSevereThanCategoryAAndB", "linearCalculationMethodValue",
    "mediumFirstYearIceWithPossibleOldIceInclusions", "ownerRequested2008EngineOutputRequirements",
    "timberLoadLineMarkApplicable", "warningTriangleUpperEdgeVerticallyAboveIceMark", "weld",
}


class R7LockRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.root = root
        cls.config = PipelineConfig.load(root / "config/pipeline.r7-prelock-offline.json")
        cls.vocabulary = VocabularyRepository(cls.config)
        cls.index = json.loads(cls.config.path("requirement_term_index").read_text(encoding="utf-8"))
        cls.registry = json.loads(cls.config.path("term_registry").read_text(encoding="utf-8"))
        cls.r6_index = json.loads((root.parent / "BENCHMARK_VOCABULARY/FINAL_LOCK_R6/requirement_term_index.json").read_text(encoding="utf-8"))

    def test_all_313_contexts_resolve(self) -> None:
        for requirement_id in self.vocabulary.requirements:
            self.vocabulary.build_context_pack(requirement_id)

    def test_counts_and_term_delta(self) -> None:
        self.assertEqual(313, len(self.index["dependencyContracts"]))
        self.assertEqual(238, sum(c.get("status") == "COMPLETE" for c in self.index["dependencyContracts"].values()))
        r6_names = {row["localName"] for row in json.loads((self.root.parent / "BENCHMARK_VOCABULARY/FINAL_LOCK_R6/registry/term_registry.json").read_text(encoding="utf-8"))}
        self.assertEqual(NEW_TERMS, {row["localName"] for row in self.registry} - r6_names)

    def test_i2_009_is_intentionally_unchanged(self) -> None:
        self.assertEqual(self.r6_index["requirements"]["I2-009"], self.index["requirements"]["I2-009"])
        self.assertEqual(self.r6_index["dependencyContracts"]["I2-009"], self.index["dependencyContracts"]["I2-009"])
        self.assertEqual(self.r6_index["termOwners"].get("I2-009"), self.index["termOwners"].get("I2-009"))

    def test_existing_paths_are_reused(self) -> None:
        self.assertEqual("hullAreaValue", self.index["dependencyContracts"]["I2-019"]["modelPaths"][1]["toOwner"])
        self.assertIn("interpolationPointCoordinate", self.index["requirements"]["I2-024"])
        self.assertIn("hasStructuralMemberLoadCase", self.index["dependencyContracts"]["I2-037"]["relationshipTerms"])
        self.assertEqual("loadingConditionCase", self.index["termOwners"]["IMO-037"]["residualStabilityFactorSI"])
        self.assertIn("propellerBladeCount", self.index["dependencyContracts"]["TRF-102"]["operandTerms"])
        self.assertNotIn("hasPropellerShaftLineComponent", self.index["dependencyContracts"]["TRF-123"]["relationshipTerms"])
        self.assertIn("occasionalForceCaseAssessedComponent", self.index["dependencyContracts"]["TRF-123"]["relationshipTerms"])
        self.assertIn("inletChest", self.index["requirements"]["TRF-130"])
        self.assertIn("hasComponent", self.index["dependencyContracts"]["TRF-130"]["relationshipTerms"])

    def test_trf_127_has_no_starting_air_term_or_formula(self) -> None:
        names = {row["localName"] for row in self.registry}
        self.assertFalse(any("startingair" in name.lower() and "capacity" in name.lower() for name in names))
        contract = self.index["dependencyContracts"]["TRF-127"]
        self.assertEqual("", contract.get("formulaExpression"))
        self.assertIn("No starting-air baseline sum is stated or inferred", contract["comparisonModel"])

    def test_new_controlled_and_structural_models_are_bound(self) -> None:
        self.assertIn("linearCalculationMethodValue", self.index["dependencyContracts"]["I2-064"]["controlledValueTerms"])
        self.assertIn("doubleContinuousWeld", self.index["dependencyContracts"]["I2-066"]["controlledValueTerms"])
        self.assertIn("mediumFirstYearIceWithPossibleOldIceInclusions", self.index["dependencyContracts"]["IMO-001"]["controlledValueTerms"])
        self.assertIn("iceConditionLessSevereThanCategoryAAndB", self.index["dependencyContracts"]["IMO-003"]["controlledValueTerms"])
        self.assertEqual("frameAttachmentRecord", self.index["requirementTargetOwner"]["TRF-050"])
        self.assertIn("warningTriangleUpperEdgeVerticallyAboveIceMark", self.index["dependencyContracts"]["TRF-133"]["evidenceTerms"])


if __name__ == "__main__":
    unittest.main()
