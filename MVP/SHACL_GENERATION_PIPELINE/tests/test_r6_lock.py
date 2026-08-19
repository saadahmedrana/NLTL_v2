from __future__ import annotations

import json
import unittest
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.retrieval.context import VocabularyRepository


class R6LockRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.config = PipelineConfig.load(root / "config/pipeline.r6-prelock-offline.json")
        cls.vocabulary = VocabularyRepository(cls.config)
        cls.index = json.loads(cls.config.path("requirement_term_index").read_text(encoding="utf-8"))

    def test_all_313_contexts_resolve(self) -> None:
        for requirement_id in self.vocabulary.requirements:
            self.vocabulary.build_context_pack(requirement_id)

    def test_complete_contracts_have_no_unresolved_diagnostic_flags(self) -> None:
        complete = [item for item in self.index["dependencyContracts"].values() if item.get("status") == "COMPLETE"]
        self.assertEqual(238, len(complete))
        self.assertTrue(all(not item.get("auditFlags") for item in complete))
        self.assertTrue(all(not item.get("observedFailureStatus") for item in complete))

    def test_r6_confirmed_models_are_bound(self) -> None:
        i2_030 = self.index["dependencyContracts"]["I2-030"]
        self.assertIn("netAttachedShellPlateThickness", i2_030["applicabilityTerms"])
        self.assertIn("1000*netAttachedShellPlateThickness*frameSpacing", i2_030["formulaExpression"])
        self.assertEqual("loadCase", self.index["termOwners"]["I2-031"]["combinedShearAndBendingDemand"])
        self.assertEqual("structuralMember", self.index["termOwners"]["I2-031"]["plasticStrength"])
        self.assertEqual("passengerShip", self.index["dependencyContracts"]["IMO-118"]["authoritativeApplicabilityRepresentations"][0]["class"])
        self.assertEqual(
            {"validityDateCategory", "surveyDateCategory", "endorsementDateCategory"},
            set(self.index["dependencyContracts"]["IMO-017"]["controlledValueTerms"]),
        )


if __name__ == "__main__":
    unittest.main()
