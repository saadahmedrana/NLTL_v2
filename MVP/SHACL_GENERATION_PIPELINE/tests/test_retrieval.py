from __future__ import annotations

import unittest

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
        self.assertEqual(len(self.vocabulary.registry), 1625)
        eligible = sum(
            1 for item in self.vocabulary.requirements.values()
            if self.vocabulary.is_generation_eligible(item)
        )
        self.assertEqual(eligible, 238)

    def test_imo_057_r2_relationship_and_targets(self) -> None:
        context = self.vocabulary.build_context_pack("IMO-057")
        by_name = {term["localName"]: term for term in context.terms}
        self.assertNotIn("containingCompartment", by_name)
        self.assertEqual(by_name["hasContainingCompartment"]["kind"], "ObjectProperty")
        self.assertEqual(
            by_name["hasContainingCompartment"]["range"],
            "https://w3id.org/nltl/vocab#compartment",
        )
        self.assertTrue({
            "firePump", "emergencyFirePump", "waterMistPump", "waterSprayPump",
            "compartment", "hasComponent", "hasContainingCompartment", "maintainedTemperature",
        } <= set(by_name))
        self.assertEqual(by_name["hasComponent"]["requiredOwner"], "ship")
        self.assertEqual(by_name["hasContainingCompartment"]["requiredOwner"], "firePump")
        self.assertEqual(by_name["maintainedTemperature"]["requiredOwner"], "compartment")
        self.assertEqual(
            by_name["maintainedTemperature"]["domains"],
            ["https://w3id.org/nltl/vocab#compartment"],
        )
        contract = context.selection["dependencyContract"]
        self.assertEqual(contract["schemaVersion"], 2)
        self.assertEqual(
            contract["relationshipTerms"],
            ["hasComponent", "hasContainingCompartment"],
        )

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
            "https://w3id.org/nltl/vocab#evidenceStateApproved",
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
            ["https://w3id.org/nltl/vocab#visualIceDetectionLightCount"],
            limit=12,
            minimum_score=0.24,
        )
        self.assertIn(
            "visualIceDetectionIlluminationMeansCount",
            {item["localName"] for item in candidates},
        )

    def test_active_context_exposes_authoritative_ownership_and_obligations(self) -> None:
        vocabulary = VocabularyRepository(self.config)

        formula_context = vocabulary.build_context_pack("TRF-059")
        by_name = {term["localName"]: term for term in formula_context.terms}
        self.assertEqual(formula_context.selection["requiredTargetOwner"], "webFrame")
        self.assertEqual(by_name["requiredShearArea"]["requiredOwner"], "webFrame")

        envelope_context = vocabulary.build_context_pack("TRF-011")
        self.assertTrue(
            any(
                "bidirectional pointwise equality" in obligation
                for obligation in envelope_context.selection["semanticObligations"]
            )
        )

        resistance_context = vocabulary.build_context_pack("TRF-020")
        resistance_terms = {term["localName"]: term for term in resistance_context.terms}
        self.assertEqual(
            resistance_terms["upperIceWaterlineBreadth"]["requiredOwner"],
            "iceWaterline",
        )

        pressure_context = vocabulary.build_context_pack("TRF-025")
        self.assertIn(
            "newtonPerMetreToPowerOnePointFiveUnit",
            {term["localName"] for term in pressure_context.terms},
        )

        patch_context = vocabulary.build_context_pack("TRF-030")
        patch_terms = {term["localName"]: term for term in patch_context.terms}
        self.assertEqual(patch_terms["loadPatchLength"]["requiredOwner"], "directAnalysisCase")

        salinity_context = vocabulary.build_context_pack("TRF-015")
        self.assertIn(
            "gramPerKilogramSalinityUnit",
            {term["localName"] for term in salinity_context.terms},
        )

        pressure_context = vocabulary.build_context_pack("TRF-037")
        pressure_terms = {term["localName"] for term in pressure_context.terms}
        self.assertIn("hasDirectAnalysisCase", pressure_terms)
        self.assertEqual(
            {term["localName"]: term for term in pressure_context.terms}["iceLoadAreaFactorCa"]["requiredOwner"],
            "directAnalysisCase",
        )

        plating_context = vocabulary.build_context_pack("TRF-042")
        self.assertIn("plating", {term["localName"] for term in plating_context.terms})
        self.assertEqual(plating_context.selection["requiredTargetOwner"], "plating")

        self.assertEqual(patch_context.selection["exclusivePropertyGroups"], [])

    def test_complete_dependency_contract_rejects_absent_terms(self) -> None:
        vocabulary = VocabularyRepository(self.config)
        vocabulary.dependency_contracts["TRF-001"] = {
            "status": "COMPLETE",
            "ownerClasses": ["ship"],
            "operandTerms": ["termThatDoesNotExist"],
            "requiredModelFields": ["operandTerms"],
        }
        with self.assertRaisesRegex(Exception, "absent canonical terms"):
            vocabulary.build_context_pack("TRF-001")

    def test_complete_dependency_contract_rejects_unindexed_terms(self) -> None:
        vocabulary = VocabularyRepository(self.config)
        vocabulary.dependency_contracts["TRF-001"] = {
            "status": "COMPLETE",
            "ownerClasses": ["ship"],
            "operandTerms": ["upperIceWaterlineBreadth"],
            "requiredModelFields": ["operandTerms"],
        }
        with self.assertRaisesRegex(Exception, "not in the requirement index"):
            vocabulary.build_context_pack("TRF-001")

    def test_unique_canonical_domain_is_used_when_owner_override_is_absent(self) -> None:
        vocabulary = VocabularyRepository(self.config)
        context = vocabulary.build_context_pack("TRF-082")
        by_name = {term["localName"]: term for term in context.terms}
        self.assertEqual(by_name["tableLookupApplied"]["requiredOwner"], "tableLookupCase")

    def test_explicit_owner_override_cannot_contradict_canonical_domain(self) -> None:
        vocabulary = VocabularyRepository(self.config)
        vocabulary.term_owners.setdefault("TRF-082", {})["tableLookupApplied"] = "ship"
        with self.assertRaisesRegex(Exception, "ownership/domain mismatch"):
            vocabulary.build_context_pack("TRF-082")

    def test_schema_v2_contract_rejects_non_object_model_path(self) -> None:
        vocabulary = VocabularyRepository(self.config)
        vocabulary.dependency_contracts["TRF-001"] = {
            "status": "COMPLETE",
            "schemaVersion": 2,
            "ownerClasses": ["ship"],
            "relationshipTerms": ["constructionContractDate"],
            "modelPaths": [{
                "fromOwner": "ship", "via": "constructionContractDate", "toOwner": "ship",
            }],
            "requiredModelFields": ["comparisonModel"],
            "comparisonModel": "test",
        }
        with self.assertRaisesRegex(Exception, "does not use an object property"):
            vocabulary.build_context_pack("TRF-001")


if __name__ == "__main__":
    unittest.main()
