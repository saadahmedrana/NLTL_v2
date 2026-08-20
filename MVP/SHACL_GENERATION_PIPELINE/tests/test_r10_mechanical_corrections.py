from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from rdflib import Graph, Namespace, RDFS
from rdflib.compare import isomorphic

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.retrieval.context import VocabularyRepository


NLTL = Namespace("https://w3id.org/nltl/vocab#")
EXPECTED = {"Static": 194, "Static Calculation": 43, "Complex": 42,
            "Dynamic": 19, "Physical Test": 15}


class R10MechanicalCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = Path(__file__).resolve().parents[1]
        cls.mvp = cls.pipeline.parent
        cls.r10 = cls.mvp / "BENCHMARK_VOCABULARY/FINAL_LOCK_R10"
        cls.r9 = cls.mvp / "BENCHMARK_VOCABULARY/FINAL_LOCK_R9"
        cls.config = PipelineConfig.load(cls.pipeline / "config/pipeline.r10-prelock-offline.json")
        cls.vocabulary = VocabularyRepository(cls.config)
        cls.evidence = json.loads((cls.r10 / "evidence/stage1_approved.json").read_text())
        cls.r9_evidence = json.loads((cls.r9 / "evidence/stage1_approved.json").read_text())
        cls.index = json.loads((cls.r10 / "requirement_term_index.json").read_text())
        cls.r9_index = json.loads((cls.r9 / "requirement_term_index.json").read_text())
        cls.by_id = {row["id"]: row for row in cls.evidence["requirements"]}

    def test_exact_category_delta_and_counts(self) -> None:
        before = {row["id"]: row for row in self.r9_evidence["requirements"]}
        changed = {rid for rid in self.by_id if self.by_id[rid]["category"] != before[rid]["category"]}
        self.assertEqual({"TRF-056", "TRF-128"}, changed)
        self.assertEqual(EXPECTED, dict(Counter(row["category"] for row in self.evidence["requirements"])))
        for rid in changed:
            self.assertEqual("Static", self.by_id[rid]["category"])
            self.assertEqual("DIRECT_STATIC", self.index["dependencyContracts"][rid]["verificationMode"])

    def test_exact_ontology_and_registry_delta(self) -> None:
        before = {t["localName"]: t for t in json.loads((self.r9 / "registry/term_registry.json").read_text())}
        after = {t["localName"]: t for t in json.loads((self.r10 / "registry/term_registry.json").read_text())}
        self.assertEqual({"tableLookupPropellerLocation"}, set(after) - set(before))
        graph = Graph().parse(self.r10 / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
        self.assertIn((NLTL.sectionCalculationCaseStructuralMember, RDFS.domain, NLTL.calculationCase), graph)
        self.assertNotIn((NLTL.sectionCalculationCaseStructuralMember, RDFS.domain,
                          NLTL.localFrameSectionCalculationCase), graph)
        self.assertIn((NLTL.tableLookupPropellerLocation, RDFS.domain, NLTL.tableLookupCase), graph)
        self.assertIn((NLTL.tableLookupPropellerLocation, RDFS.range, NLTL.propellerLocationValue), graph)
        rdf = Graph().parse(self.r10 / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
        self.assertTrue(isomorphic(graph, rdf))

    def test_i2_029_uses_only_case_linked_member_path(self) -> None:
        contract = self.index["dependencyContracts"]["I2-029"]
        self.assertEqual(["hasCalculationCase", "sectionCalculationCaseStructuralMember"],
                         contract["relationshipTerms"])
        self.assertNotIn("hasStructuralMember", self.index["requirements"]["I2-029"])
        self.assertEqual([
            {"fromOwner": "ship", "via": "hasCalculationCase", "toOwner": "calculationCase"},
            {"fromOwner": "calculationCase", "via": "sectionCalculationCaseStructuralMember",
             "toOwner": "structuralMember"},
        ], contract["modelPaths"])
        self.assertIn("flangeMaterialIncludedInShearArea = true", contract["conditionalRules"][0]["if"])
        self.assertIn("flangeFitted = true", contract["conditionalRules"][0]["then"])

    def test_trf_078_has_exact_two_table_selection_keys(self) -> None:
        contract = self.index["dependencyContracts"]["TRF-078"]
        self.assertEqual("N_ice = k1 * k2 * k3 * N_class * n_n", contract["formulaExpression"])
        self.assertIn("iceClass", contract["relationshipTerms"])
        self.assertIn("tableLookupPropellerLocation", contract["relationshipTerms"])
        self.assertNotIn("propellerLocation", contract["relationshipTerms"])
        self.assertEqual(1, contract["cardinalityPolicies"][0]["minCount"])
        self.assertEqual(1, contract["cardinalityPolicies"][0]["maxCount"])

    def test_trf_128_is_direct_time_limit_without_capacity_formula(self) -> None:
        contract = self.index["dependencyContracts"]["TRF-128"]
        terms = set(self.index["requirements"]["TRF-128"])
        self.assertEqual("DIRECT_STATIC", contract["verificationMode"])
        self.assertEqual("", contract["formulaExpression"])
        self.assertNotIn("airReceiverCapacity", terms)
        self.assertNotIn("airCompressorCapacity", self.vocabulary.all_terms)
        self.assertIn("compressorChargeTime <= 0.5 hour", contract["conditionalRules"][0]["then"])
        self.assertIn("compressorChargeTime <= 1 hour", contract["conditionalRules"][1]["else"])

    def test_trf_028_removes_only_mandatory_performance_experience(self) -> None:
        self.assertEqual([
            "alternativeCalculationEvidence", "modelTestEvidence", "approvalStatus",
            "approvalRevocationStatus",
        ], self.index["dependencyContracts"]["TRF-028"]["evidenceTerms"])
        self.assertIn("shipPerformanceExperienceEvidence", self.index["requirements"]["TRF-028"])
        self.assertIn("shipPerformanceExperienceEvidence", self.vocabulary.all_terms)

    def test_trf_056_is_direct_static_and_trf_048_is_unchanged(self) -> None:
        contract = self.index["dependencyContracts"]["TRF-056"]
        self.assertEqual("DIRECT_STATIC", contract["verificationMode"])
        self.assertEqual("", contract["formulaExpression"])
        self.assertIn("hatchOpeningLength > shipBreadth / 2", contract["conditionalRules"][0]["if"])
        for key in ("requirements", "termOwners", "requirementTargetOwner", "semanticObligations"):
            self.assertEqual(self.r9_index[key].get("TRF-048"), self.index[key].get("TRF-048"), key)
        self.assertEqual(self.r9_index["dependencyContracts"]["TRF-048"],
                         self.index["dependencyContracts"]["TRF-048"])

    def test_all_contexts_resolve_and_r9_is_immutable(self) -> None:
        for rid in sorted(self.vocabulary.requirements):
            self.assertEqual(rid, self.vocabulary.build_context_pack(rid).selection["requirementId"])
        provenance = json.loads((self.r10 / "provenance/r9_immutable_source_hashes.json").read_text())
        for relative, expected in provenance["files"].items():
            path = self.mvp / relative
            self.assertTrue(path.exists(), relative)
            self.assertEqual(expected, hashlib.sha256(path.read_bytes()).hexdigest(), relative)


if __name__ == "__main__":
    unittest.main()
