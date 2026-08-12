from __future__ import annotations

import unittest
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.matching.search import CandidateSearcher
from nltl_pipeline.retrieval.context import VocabularyRepository
from nltl_pipeline.retrieval.fewshot import FewShotSelector


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = PipelineConfig.load()
        cls.vocabulary = VocabularyRepository(cls.config)

    def test_locked_counts_and_eligibility(self) -> None:
        self.assertEqual(len(self.vocabulary.requirements), 313)
        self.assertEqual(len(self.vocabulary.registry), 825)
        eligible = sum(
            1 for item in self.vocabulary.requirements.values()
            if self.vocabulary.is_generation_eligible(item)
        )
        self.assertEqual(eligible, 240)

    def test_imo_057_r2_relationship_and_targets(self) -> None:
        context = self.vocabulary.build_context_pack("IMO-057")
        by_name = {term["localName"]: term for term in context.terms}
        self.assertNotIn("containingCompartment", by_name)
        self.assertEqual(by_name["hasContainingCompartment"]["kind"], "ObjectProperty")
        self.assertEqual(
            by_name["hasContainingCompartment"]["range"],
            "https://w3id.org/nltl-benchmark/vocab#compartment",
        )
        self.assertTrue({
            "firePump", "emergencyFirePump", "waterMistPump", "waterSprayPump",
            "compartment", "hasContainingCompartment", "maintainedTemperature",
        } <= set(by_name))

    def test_context_has_indexed_and_target_dependencies(self) -> None:
        context = self.vocabulary.build_context_pack("IMO26-014")
        names = {term["localName"] for term in context.terms}
        self.assertTrue({
            "operatesOnlyInContinuousDaylight",
            "visualIceDetectionIlluminationMeansCount",
            "ship",
            "benchmarkEntity",
        } <= names)
        self.assertTrue(context.selection["eligibleForGeneration"])

    def test_controlled_range_values_are_available_to_generator(self) -> None:
        context = self.vocabulary.build_context_pack("IMO-088")
        by_name = {term["localName"]: term for term in context.terms}
        self.assertEqual(by_name["evidenceStateApproved"]["kind"], "NamedIndividual")
        self.assertEqual(
            by_name["evidenceStateApproved"]["iri"],
            "https://w3id.org/nltl-benchmark/vocab#evidenceStateApproved",
        )

    def test_few_shot_selection_is_deterministic(self) -> None:
        context = self.vocabulary.build_context_pack("IMO26-014")
        selector = FewShotSelector(self.config.path("few_shot_jsonl"))
        first = selector.select(context, 2)
        second = selector.select(context, 2)
        self.assertEqual([item["exampleId"] for item in first], [item["exampleId"] for item in second])
        self.assertEqual(len(first), 2)

    def test_candidate_search_finds_canonical_illumination_count(self) -> None:
        searcher = CandidateSearcher(self.vocabulary)
        candidates = searcher.search(
            "Replace the visual ice detection light count with the illumination means count.",
            ["https://w3id.org/nltl-benchmark/vocab#visualIceDetectionLightCount"],
            limit=12,
            minimum_score=0.24,
        )
        self.assertIn(
            "visualIceDetectionIlluminationMeansCount",
            {item["localName"] for item in candidates},
        )

    def test_r6_context_exposes_authoritative_ownership_and_obligations(self) -> None:
        config_path = Path(__file__).resolve().parents[1] / "config" / "pipeline.dev-batch01.json"
        vocabulary = VocabularyRepository(PipelineConfig.load(config_path))

        formula_context = vocabulary.build_context_pack("TRF-059")
        by_name = {term["localName"]: term for term in formula_context.terms}
        self.assertEqual(formula_context.selection["requiredTargetOwner"], "webFrame")
        self.assertEqual(by_name["requiredShearArea"]["requiredOwner"], "webFrame")

        envelope_context = vocabulary.build_context_pack("TRF-011")
        self.assertIn(
            "Validate that the UIWL is the pointwise upper envelope of all intended ice-operating waterlines; presence alone is insufficient.",
            envelope_context.selection["semanticObligations"],
        )

        salinity_context = vocabulary.build_context_pack("TRF-015")
        self.assertIn(
            "gramPerKilogramSalinityUnit",
            {term["localName"] for term in salinity_context.terms},
        )


if __name__ == "__main__":
    unittest.main()
