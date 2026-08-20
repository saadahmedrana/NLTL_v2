from __future__ import annotations

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from rdflib import Graph

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.prompts import PromptFactory
from nltl_pipeline.retrieval.context import VocabularyRepository
from nltl_pipeline.retrieval.fewshot import FewShotSelector


EXPECTED_COUNTS = {
    "Static": 192, "Static Calculation": 45, "Complex": 42,
    "Dynamic": 19, "Physical Test": 15,
}


class R9ClassificationAndFewShotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = Path(__file__).resolve().parents[1]
        cls.mvp = cls.pipeline.parent
        cls.r9 = cls.mvp / "BENCHMARK_VOCABULARY/FINAL_LOCK_R9"
        cls.r8 = cls.mvp / "BENCHMARK_VOCABULARY/FINAL_LOCK_R8"
        cls.config = PipelineConfig.load(cls.pipeline / "config/pipeline.r9-prelock-offline.json")
        cls.vocabulary = VocabularyRepository(cls.config)
        cls.evidence = json.loads((cls.r9 / "evidence/stage1_approved.json").read_text())
        cls.r8_evidence = json.loads((cls.r8 / "evidence/stage1_approved.json").read_text())
        cls.index = json.loads((cls.r9 / "requirement_term_index.json").read_text())
        cls.by_id = {row["id"]: row for row in cls.evidence["requirements"]}

    def test_exact_62_changes_and_counts(self) -> None:
        before = {row["id"]: row for row in self.r8_evidence["requirements"]}
        changed = {rid for rid in self.by_id if before[rid]["category"] != self.by_id[rid]["category"]}
        decisions = json.loads(
            (self.r9 / "registry/r9_classification_change_decisions.json").read_text()
        )
        approved = {row["requirementId"] for row in decisions["changes"]}
        self.assertEqual(62, len(changed))
        self.assertEqual(approved, changed)
        self.assertEqual(EXPECTED_COUNTS, dict(Counter(row["category"] for row in self.evidence["requirements"])))

    def test_category_verification_routing_and_context_resolution(self) -> None:
        expected = {
            "Static": "DIRECT_STATIC", "Static Calculation": "DIRECT_CALCULATION",
            "Complex": "COMPLEX_READINESS", "Dynamic": "DYNAMIC_DEFERRED",
            "Physical Test": "PHYSICAL_TEST_DEFERRED",
        }
        for rid, requirement in self.by_id.items():
            context = self.vocabulary.build_context_pack(rid)
            self.assertEqual(rid, context.selection["requirementId"])
            contract = self.index["dependencyContracts"][rid]
            if contract.get("status") == "COMPLETE" or requirement["category"] in {"Dynamic", "Physical Test"}:
                self.assertEqual(expected[requirement["category"]], contract.get("verificationMode"), rid)

    def test_changed_requirement_vocabulary_sufficiency_and_deferred_blockers(self) -> None:
        decisions = json.loads(
            (self.r9 / "registry/r9_classification_change_decisions.json").read_text()
        )
        insufficient = {row["requirementId"] for row in decisions["changes"] if not row["vocabularySufficient"]}
        self.assertEqual({"I2-003", "TRF-039"}, insufficient)
        for rid in insufficient:
            self.assertFalse(self.vocabulary.is_generation_eligible(self.by_id[rid]))
            self.assertTrue(self.index["dependencyContracts"][rid]["deferredReason"])
        for row in decisions["changes"]:
            rid = row["requirementId"]
            for term in self.index["requirements"][rid]:
                self.assertIn(term, self.vocabulary.all_terms, f"{rid}: {term}")

    def test_category_completion_and_eligibility_counts(self) -> None:
        expected = {
            "Static": (192, 192, 192, 0),
            "Static Calculation": (45, 43, 43, 2),
            "Complex": (42, 34, 34, 8),
        }
        for category, counts in expected.items():
            ids = [rid for rid, row in self.by_id.items() if row["category"] == category]
            complete = [rid for rid in ids if self.index["dependencyContracts"][rid].get("status") == "COMPLETE"]
            eligible = [rid for rid in ids if self.vocabulary.is_generation_eligible(self.by_id[rid])]
            self.assertEqual(counts, (len(ids), len(complete), len(eligible), len(ids) - len(eligible)))

    def test_complex_context_tags_and_readiness_selection(self) -> None:
        selector = FewShotSelector(self.config.path("few_shot_jsonl"))
        context = self.vocabulary.build_context_pack("I2-030")
        self.assertEqual(
            ["complex", "readiness", "external-calculation", "calculation-inputs",
             "calculation-results", "engineering-evidence"],
            context.selection["retrievalTags"],
        )
        selected = selector.select(context, 2)
        self.assertEqual(
            ["FS-COMPLEX-READINESS-01", "FS-COMPLEX-READINESS-02"],
            [row["exampleId"] for row in selected],
        )
        self.assertTrue(all("readiness" in row["retrievalTags"] for row in selected))

    def test_new_complex_fewshots_are_exactly_present_and_parse(self) -> None:
        root = self.mvp / "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES"
        records = [json.loads(line) for line in (root / "few_shot_pairs.jsonl").read_text().splitlines()]
        self.assertEqual(22, len(records))
        by_id = {row["exampleId"]: row for row in records}
        for example_id in ("FS-COMPLEX-READINESS-01", "FS-COMPLEX-READINESS-02"):
            self.assertEqual("synthetic-few-shot-not-benchmark-ground-truth", by_id[example_id]["status"])
            self.assertNotIn("sh:sparql", by_id[example_id]["expectedShapeTurtle"])
            Graph().parse(data=by_id[example_id]["expectedShapeTurtle"], format="turtle")
        report = json.loads((root / "validation_report.json").read_text())
        self.assertTrue(report["allChecksPassed"])
        self.assertEqual(22, report["actualPassGraphConformanceCount"])
        self.assertEqual(22, report["actualFailGraphNonConformanceCount"])

    def test_prompts_state_full_five_category_policy(self) -> None:
        prompts = PromptFactory(None)
        generator = prompts.generator_instructions
        validator = prompts.validator_instructions
        for token in ("DIRECT_STATIC", "DIRECT_CALCULATION", "COMPLEX_READINESS", "Dynamic", "Physical Test"):
            self.assertIn(token, generator)
            self.assertIn(token, validator)
        self.assertIn("never\nclassify or relabel", validator)
        self.assertIn("never reconstruct the\n    advanced formula", generator)

    def test_r8_immutable_and_vocabulary_unchanged(self) -> None:
        provenance = json.loads((self.r9 / "provenance/r8_immutable_source_hashes.json").read_text())
        for relative, expected in provenance["files"].items():
            path = self.mvp / relative
            self.assertTrue(path.exists(), relative)
            self.assertEqual(expected, hashlib.sha256(path.read_bytes()).hexdigest(), relative)
        for relative in (
            "registry/term_registry.json", "registry/term_registry.csv",
            "ontology/nltl_benchmark_vocabulary.ttl", "ontology/nltl_benchmark_vocabulary.rdf",
        ):
            self.assertEqual((self.r8 / relative).read_bytes(), (self.r9 / relative).read_bytes(), relative)


if __name__ == "__main__":
    unittest.main()
