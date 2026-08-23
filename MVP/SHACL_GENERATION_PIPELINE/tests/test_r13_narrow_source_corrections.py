from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, RDF, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import OWL, XSD

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.errors import ConfigurationError
from nltl_pipeline.retrieval.context import VocabularyRepository


MVP = Path(__file__).resolve().parents[2]
LOCK = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R13"
SOURCE = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R12"
CONFIG = MVP / "SHACL_GENERATION_PIPELINE/config/pipeline.r13-prelock-offline.json"
NS = "https://w3id.org/nltl/vocab#"
NEW = {"steelGradeB", "steelGradeD", "steelGradeE", "steelGradeAh", "steelGradeDh", "steelGradeEh", "steelGradeFh", "traficomTable6Dash14"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class R13CorrectionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = read(LOCK / "requirement_term_index.json")
        cls.evidence = read(LOCK / "evidence/stage1_approved.json")
        cls.registry = {x["localName"]: x for x in read(LOCK / "registry/term_registry.json")}
        cls.old_registry = {x["localName"]: x for x in read(SOURCE / "registry/term_registry.json")}
        cls.vocabulary = VocabularyRepository(PipelineConfig.load(CONFIG))

    def test_counts_and_exact_vocabulary_delta(self):
        self.assertEqual(Counter(x["category"] for x in self.evidence["requirements"]),
                         {"Static":191,"Static Calculation":43,"Complex":45,"Dynamic":19,"Physical Test":15})
        self.assertEqual(sum(c.get("status") == "COMPLETE" for c in self.index["dependencyContracts"].values()), 268)
        self.assertEqual(set(self.registry) - set(self.old_registry), NEW)
        self.assertFalse(set(self.old_registry) - set(self.registry))
        changed = {k for k in self.old_registry if self.old_registry[k] != self.registry[k]}
        self.assertEqual(changed, {"assessmentDate"})

    def test_ontology_serializations_and_grade_ranks(self):
        ttl = Graph().parse(LOCK / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
        rdfxml = Graph().parse(LOCK / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
        self.assertTrue(isomorphic(ttl, rdfxml))
        expected = {"steelGradeB":1,"steelGradeD":2,"steelGradeE":3,"steelGradeAh":1,"steelGradeDh":2,"steelGradeEh":3,"steelGradeFh":4}
        for local, rank in expected.items():
            iri = URIRef(NS + local)
            self.assertIn((iri, RDF.type, OWL.NamedIndividual), ttl)
            self.assertIn((iri, RDF.type, URIRef(NS + "steelGradeValue")), ttl)
            self.assertIn((iri, URIRef(NS + "steelGradeOrderRank"), Literal(rank, datatype=XSD.integer)), ttl)

    def test_i2_048_exact_table_and_cleanup(self):
        contract = self.index["dependencyContracts"]["I2-048"]
        model = contract["tableModel"]
        self.assertEqual(model["canonicalTableReference"], "iacsUrI2Table8")
        self.assertEqual(model["selectors"], ["asBuiltPlateThickness","polarClass","steelMaterialClass","steelStrengthCategory"])
        self.assertEqual(len(model["rows"]), 9)
        self.assertEqual(sum(len(x["selections"]) for x in model["rows"]), 126)
        expected_pairs = [
            ["B/AH","B/AH","B/AH","B/AH","E/EH","E/EH","B/AH"],
            ["B/AH","B/AH","D/DH","B/AH","E/EH","E/EH","D/DH"],
            ["D/DH","B/AH","D/DH","B/AH","E/EH","E/EH","D/DH"],
            ["D/DH","B/AH","D/DH","B/AH","E/EH","E/EH","D/DH"],
            ["D/DH","B/AH","E/EH","D/DH","E/EH","E/EH","E/EH"],
            ["D/DH","B/AH","E/EH","D/DH","E/EH","E/EH","E/EH"],
            ["D/DH","D/DH","E/EH","D/DH","NOT_APPLICABLE/FH","E/EH","E/EH"],
            ["E/EH","D/DH","E/EH","D/DH","NOT_APPLICABLE/FH","E/EH","E/EH"],
            ["E/EH","D/DH","E/EH","D/DH","NOT_APPLICABLE/FH","NOT_APPLICABLE/FH","E/EH"],
        ]
        grade_label = {"steelGradeB":"B","steelGradeD":"D","steelGradeE":"E","steelGradeAh":"AH","steelGradeDh":"DH","steelGradeEh":"EH","steelGradeFh":"FH"}
        actual_pairs = []
        for row in model["rows"]:
            selections = row["selections"]
            actual_pairs.append([
                f"{grade_label.get(selections[i]['requiredGrade'], 'NOT_APPLICABLE')}/{grade_label[selections[i+1]['requiredGrade']]}"
                for i in range(0, 14, 2)
            ])
        self.assertEqual(actual_pairs, expected_pairs)
        self.assertEqual(contract["operandTerms"], ["polarClass","asBuiltPlateThickness","steelMaterialClass","steelStrengthCategory"])
        self.assertEqual(contract["resultTerms"], ["requiredHullStructuralSteelGrade"])
        text = json.dumps({"terms":self.index["requirements"]["I2-048"], "contract":contract})
        for stale in ("asBuiltThickness", "materialClass", "steelGrade", "hasTableLookupCase", "lookupSelectionEvidence"):
            self.assertNotIn(f'"{stale}"', text)
        self.assertFalse(any(s.get("requiredGrade") == "NOT_APPLICABLE" for r in model["rows"] for s in r["selections"]))

    def test_approval_policies(self):
        authority = ["Administration", "recognized organization accepted by the Administration"]
        ab = ["standard acceptable to the Organization", "another standard offering an equivalent level of safety"]
        for rid in ("IMO-031", "IMO-048"):
            policy = self.index["dependencyContracts"][rid]["stringValuePolicies"]
            self.assertEqual(policy, {"approvingAuthority":authority, "approvalStandard":ab})
        for rid in ("IMO-032", "IMO-049"):
            branches = self.index["dependencyContracts"][rid]["approvalBranchPolicies"]
            self.assertEqual(branches["categoryAOrB"]["approvalStandard"], ab)
            self.assertFalse(branches["iceStrengthenedCategoryC"]["equivalentSafetyAlternativeAllowed"])

    def test_readiness_date_and_table_reference(self):
        trf12 = self.index["dependencyContracts"]["TRF-012"]
        self.assertEqual(trf12["verificationMode"], "COMPLEX_READINESS")
        self.assertFalse(trf12["formulaExecutionRequired"])
        self.assertTrue(any("pointwise lower envelope" in x for x in trf12["prohibitedOperations"]))
        trf14 = self.index["dependencyContracts"]["TRF-014"]
        self.assertIn("assessmentDate", self.index["requirements"]["TRF-014"])
        self.assertEqual(trf14["literalConstants"]["regulatoryCutoffDate"]["lexicalForm"], "2007-07-01")
        self.assertNotRegex(json.dumps(trf14), r"NOW\(|YEAR\(|MONTH\(|DAY\(")
        trf109 = self.index["dependencyContracts"]["TRF-109"]
        self.assertEqual(trf109["tableModel"]["canonicalTableReference"], "traficomTable6Dash14")
        self.assertIn("traficomTable6Dash14", trf109["controlledValueTerms"])
        self.assertTrue(all(v == {"minCount":1,"maxCount":1} for v in trf109["tableModel"]["coefficientCardinality"].values()))

    def test_all_contexts_and_table_guard(self):
        for item in self.evidence["requirements"]:
            self.vocabulary.build_context_pack(item["id"])
        checked = []
        for rid, contract in self.index["dependencyContracts"].items():
            model = contract.get("tableModel")
            if contract.get("status") == "COMPLETE" and isinstance(model, dict) and model.get("structured") and model.get("canonicalTableReference"):
                checked.append(rid)
                self.vocabulary.validate_dependency_contract(rid)
        self.assertIn("I2-048", checked)
        self.assertIn("TRF-109", checked)
        contract = self.vocabulary.dependency_contracts["TRF-109"]
        original = list(contract["controlledValueTerms"])
        contract["controlledValueTerms"] = [x for x in original if x != "traficomTable6Dash14"]
        with self.assertRaises(ConfigurationError):
            self.vocabulary.validate_dependency_contract("TRF-109")
        contract["controlledValueTerms"] = original

    def test_r12_immutable(self):
        provenance = read(LOCK / "provenance/r12_immutable_source_hashes.json")
        for relative, expected in provenance["files"].items():
            path = MVP / relative
            self.assertTrue(path.exists(), relative)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected, relative)


if __name__ == "__main__":
    unittest.main()
