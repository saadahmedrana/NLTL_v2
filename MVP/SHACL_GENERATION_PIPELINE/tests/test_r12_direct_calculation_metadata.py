from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.errors import ConfigurationError
from nltl_pipeline.retrieval.context import VocabularyRepository


EXPECTED_COUNTS = {"Static": 191, "Static Calculation": 43, "Complex": 45,
                   "Dynamic": 19, "Physical Test": 15}


class R12DirectCalculationMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = Path(__file__).resolve().parents[1]
        cls.mvp = cls.pipeline.parent
        cls.r12 = cls.mvp / "BENCHMARK_VOCABULARY/FINAL_LOCK_R12"
        cls.r11 = cls.mvp / "BENCHMARK_VOCABULARY/FINAL_LOCK_R11"
        cls.config = PipelineConfig.load(cls.pipeline / "config/pipeline.r12-prelock-offline.json")
        cls.repo = VocabularyRepository(cls.config)
        cls.evidence = json.loads((cls.r12 / "evidence/stage1_approved.json").read_text())
        cls.before = {row["id"]: row for row in json.loads(
            (cls.r11 / "evidence/stage1_approved.json").read_text())["requirements"]}
        cls.by_id = {row["id"]: row for row in cls.evidence["requirements"]}
        cls.index = json.loads((cls.r12 / "requirement_term_index.json").read_text())

    def test_exact_category_delta_counts_and_eligibility(self):
        changed = {rid for rid in self.by_id if self.by_id[rid]["category"] != self.before[rid]["category"]}
        self.assertEqual({"TRF-055"}, changed)
        self.assertEqual(EXPECTED_COUNTS, dict(Counter(row["category"] for row in self.evidence["requirements"])))
        self.assertEqual(268, sum(self.repo.is_generation_eligible(row) for row in self.by_id.values()))

    def test_vocabulary_and_ontology_are_byte_identical_to_r11(self):
        for relative in ("registry/term_registry.json", "registry/term_registry.csv",
                         "ontology/nltl_benchmark_vocabulary.ttl", "ontology/nltl_benchmark_vocabulary.rdf"):
            self.assertEqual((self.r11 / relative).read_bytes(), (self.r12 / relative).read_bytes(), relative)
        ttl = Graph().parse(self.r12 / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
        rdf = Graph().parse(self.r12 / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
        self.assertTrue(isomorphic(ttl, rdf))

    def test_trf055_and_trf059_exact_cleanup(self):
        c = self.index["dependencyContracts"]
        self.assertEqual("DIRECT_STATIC", c["TRF-055"]["verificationMode"])
        self.assertIn("actualSectionModulus >= requiredSectionModulus", c["TRF-055"]["comparisonModel"])
        self.assertIn("0.10 <= permittedReducedLineLoad < 0.15", c["TRF-055"]["comparisonModel"])
        self.assertNotIn("sectionModulus", self.index["requirements"]["TRF-059"])
        self.assertNotIn("sectionModulus", self.index["termOwners"]["TRF-059"])
        self.assertNotIn("sectionModulus", c["TRF-059"].get("legacyIndexedTerms", []))

    def test_all_complete_direct_calculations_are_complete(self):
        violations = []
        for rid, contract in self.index["dependencyContracts"].items():
            if contract.get("status") == "COMPLETE" and contract.get("verificationMode") == "DIRECT_CALCULATION":
                missing = [field for field in ("operandTerms", "resultTerms", "comparisonModel") if not contract.get(field)]
                if missing:
                    violations.append((rid, missing))
        self.assertEqual([], violations)

    def test_future_lock_completeness_rule_is_blocking(self):
        contract = self.repo.dependency_contracts["TRF-059"]
        original = list(contract["operandTerms"])
        original_required = list(contract["requiredModelFields"])
        try:
            contract["operandTerms"] = []
            contract["requiredModelFields"] = [field for field in original_required if field != "operandTerms"]
            with self.assertRaisesRegex(ConfigurationError, "lacks required calculation metadata"):
                self.repo.validate_dependency_contract("TRF-059")
        finally:
            contract["operandTerms"] = original
            contract["requiredModelFields"] = original_required

    def test_all_contexts_resolve_r11_immutable_and_api_client_unchanged(self):
        for rid in sorted(self.repo.requirements):
            self.assertEqual(rid, self.repo.build_context_pack(rid).selection["requirementId"])
        provenance = json.loads((self.r12 / "provenance/r11_immutable_source_hashes.json").read_text())
        for relative, expected in provenance["files"].items():
            path = self.mvp / relative
            self.assertTrue(path.exists(), relative)
            self.assertEqual(expected, hashlib.sha256(path.read_bytes()).hexdigest(), relative)
        r11_lock = json.loads((self.r11 / "benchmark_vocabulary_stage2_LOCK-2026-08-21-R11.lock.json").read_text())
        relative = "src/nltl_pipeline/api/client.py"
        self.assertEqual(r11_lock["pipelineSourceSha256"][relative],
                         hashlib.sha256((self.pipeline / relative).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
