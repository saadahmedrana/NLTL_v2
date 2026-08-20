from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.prompts import PromptFactory
from nltl_pipeline.retrieval.context import VocabularyRepository
from nltl_pipeline.validation.shacl import ShaclStaticValidator


RECLASSIFIED = {
    "I2-008", "I2-015", "I2-022", "I2-023", "I2-024", "I2-030", "I2-040",
    "I2-041", "I2-043", "I2-050", "I2-053", "I2-054", "I2-064", "I2-065",
    "TRF-020", "TRF-022", "TRF-025", "TRF-026", "TRF-030", "TRF-034",
    "TRF-041", "TRF-051", "TRF-060", "TRF-116",
}
EXPECTED_COUNTS = {
    "Static": 151, "Static Calculation": 65, "Complex": 64,
    "Dynamic": 17, "Physical Test": 16,
}


class R8VerificationPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = Path(__file__).resolve().parents[1]
        cls.mvp = cls.pipeline.parent
        cls.r8 = cls.mvp / "BENCHMARK_VOCABULARY/FINAL_LOCK_R8"
        cls.r7 = cls.mvp / "BENCHMARK_VOCABULARY/FINAL_LOCK_R7"
        cls.config = PipelineConfig.load(cls.pipeline / "config/pipeline.r8-prelock-offline.json")
        cls.vocabulary = VocabularyRepository(cls.config)
        cls.index = json.loads((cls.r8 / "requirement_term_index.json").read_text(encoding="utf-8"))
        cls.evidence = json.loads((cls.r8 / "evidence/stage1_approved.json").read_text(encoding="utf-8"))
        cls.by_id = {row["id"]: row for row in cls.evidence["requirements"]}

    def test_exact_reclassifications_and_category_counts(self) -> None:
        r7 = json.loads((self.r7 / "evidence/stage1_approved.json").read_text(encoding="utf-8"))
        r7_by_id = {row["id"]: row for row in r7["requirements"]}
        changed = {
            rid for rid in self.by_id
            if self.by_id[rid]["category"] != r7_by_id[rid]["category"]
        }
        self.assertEqual(RECLASSIFIED, changed)
        self.assertEqual(EXPECTED_COUNTS, dict(Counter(row["category"] for row in self.evidence["requirements"])))

    def test_complex_readiness_eligibility_is_contract_driven(self) -> None:
        complete = [
            rid for rid, row in self.by_id.items()
            if row["category"] == "Complex"
            and self.index["dependencyContracts"][rid].get("status") == "COMPLETE"
            and self.index["dependencyContracts"][rid].get("verificationMode") == "COMPLEX_READINESS"
        ]
        eligible = [rid for rid in complete if self.vocabulary.is_generation_eligible(self.by_id[rid])]
        self.assertEqual(23, len(complete))
        self.assertEqual(set(complete), set(eligible))
        self.assertTrue(self.vocabulary.is_generation_eligible(self.by_id["I2-008"]))
        self.assertFalse(self.vocabulary.is_generation_eligible(self.by_id["I2-053"]))

    def test_formula_is_informational_not_execution_obligation(self) -> None:
        contract = self.index["dependencyContracts"]["TRF-116"]
        self.assertEqual("COMPLEX_READINESS", contract["verificationMode"])
        self.assertFalse(contract["formulaExecutionRequired"])
        self.assertIn("sqrt", contract["informationalSourceFormula"])
        context = self.vocabulary.build_context_pack("TRF-116")
        raw = """<BEGIN_SHACL>
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix nltl: <https://w3id.org/nltl/vocab#> .
@prefix ex: <urn:nltl:generated-shape:> .
ex:TRF116 a sh:NodeShape ;
  sh:targetClass nltl:ship ;
  sh:property [ sh:path nltl:nonHemisphericalImpactContactArea ; sh:minCount 1 ] ;
  sh:property [ sh:path nltl:designIceThickness ; sh:minCount 1 ] ;
  sh:property [ sh:path nltl:propellerHubOrThrusterEndCapImpact ; sh:minCount 1 ] ;
  sh:property [ sh:path nltl:equivalentImpactSphereRadius ; sh:minCount 1 ] .
<END_SHACL>"""
        _, report = ShaclStaticValidator(self.vocabulary).validate_raw(raw, context)
        self.assertFalse(any("formula" in error.lower() for error in report.errors), report.errors)
        self.assertFalse(any("COMPLEX_READINESS" in error for error in report.errors), report.errors)

    def test_readiness_required_fields_and_direct_checks_are_enforced(self) -> None:
        contract = self.vocabulary.dependency_contracts["TRF-116"]
        original = list(contract["operandTerms"])
        try:
            contract["operandTerms"] = []
            with self.assertRaisesRegex(Exception, "lacks required model fields|lacks required inputs"):
                self.vocabulary.validate_dependency_contract("TRF-116")
        finally:
            contract["operandTerms"] = original
        context = self.vocabulary.build_context_pack("I2-064")
        raw = """<BEGIN_SHACL>
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix nltl: <https://w3id.org/nltl/vocab#> .
@prefix ex: <urn:nltl:generated-shape:> .
ex:I2064 a sh:NodeShape ; sh:targetClass nltl:ship ;
  sh:property [ sh:path nltl:calculationMethod ; sh:minCount 1 ] .
<END_SHACL>"""
        _, report = ShaclStaticValidator(self.vocabulary).validate_raw(raw, context)
        self.assertTrue(any("DIRECT_CHECK" in error for error in report.errors), report.errors)
        self.assertTrue(any("required input" in error for error in report.errors), report.errors)
        self.assertTrue(any("required result/output" in error for error in report.errors), report.errors)

    def test_generator_and_validator_readiness_routing(self) -> None:
        prompts = PromptFactory(self.config.path("prompt_directory") if "prompt_directory" in self.config.raw["paths"] else None)
        generator = prompts.generator_instructions
        validator = prompts.validator_instructions
        self.assertIn("do not reproduce the complete engineering numerical calculation", generator)
        self.assertIn("Generate readiness/result SHACL", generator)
        self.assertIn("do\nnot reject a candidate merely because it does not execute", validator)
        self.assertIn("only the subconstraints explicitly marked DIRECT_CHECK", validator)

    def test_static_and_static_calculation_behavior_remains_direct(self) -> None:
        static = self.by_id["TRF-001"]
        static_calc = self.by_id["TRF-016"]
        self.assertEqual("Static", static["category"])
        self.assertEqual("Static Calculation", static_calc["category"])
        self.assertTrue(self.vocabulary.is_generation_eligible(static))
        self.assertTrue(self.vocabulary.is_generation_eligible(static_calc))
        self.assertNotEqual("COMPLEX_READINESS", self.index["dependencyContracts"]["TRF-001"].get("verificationMode"))
        self.assertNotEqual("COMPLEX_READINESS", self.index["dependencyContracts"]["TRF-016"].get("verificationMode"))

    def test_r7_is_immutable_and_vocabulary_is_identical(self) -> None:
        provenance = json.loads((self.r8 / "provenance/r7_immutable_source_hashes.json").read_text(encoding="utf-8"))
        for relative, expected in provenance["files"].items():
            path = self.mvp / relative
            self.assertTrue(path.exists(), relative)
            self.assertEqual(expected, hashlib.sha256(path.read_bytes()).hexdigest(), relative)
        self.assertEqual(
            (self.r7 / "registry/term_registry.json").read_bytes(),
            (self.r8 / "registry/term_registry.json").read_bytes(),
        )
        self.assertEqual(
            (self.r7 / "ontology/nltl_benchmark_vocabulary.ttl").read_bytes(),
            (self.r8 / "ontology/nltl_benchmark_vocabulary.ttl").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
