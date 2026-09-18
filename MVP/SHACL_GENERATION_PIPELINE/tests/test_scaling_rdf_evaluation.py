from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from rdf_evaluation_common import output_directory, summarize_cases
from run_rdf_evaluation import extract_first_generation, select_first_generator_artifact
from summarize_rdf_evaluations import write_workbook


class ScalingRdfEvaluationTests(unittest.TestCase):
    def test_first_generation_wrapper_extraction_preserves_candidate_bytes(self):
        turtle = "\n@prefix sh: <http://www.w3.org/ns/shacl#> .\n<#S> a sh:NodeShape .\n"
        raw = "reasoning\n<BEGIN_SHACL>\n" + turtle + "<END_SHACL>\nafter"
        extracted, method = extract_first_generation(raw)
        self.assertEqual(extracted, turtle)
        self.assertEqual(method, "SHACL_RESPONSE_WRAPPER")

    def test_first_generation_allows_one_markdown_fence_without_repair(self):
        body = "@prefix sh: <http://www.w3.org/ns/shacl#> .\nBROKEN ["
        extracted, method = extract_first_generation("prose\n```turtle\n" + body + "\n```\n")
        self.assertEqual(extracted, body)
        self.assertEqual(method, "MARKDOWN_CODE_FENCE")

    def test_fenced_response_wrapper_is_only_unwrapped(self):
        body = "@prefix sh: <http://www.w3.org/ns/shacl#> .\n<#S> a sh:NodeShape .\n"
        raw = "```turtle\n<BEGIN_SHACL>\n" + body + "<END_SHACL>\n```\n"
        extracted, method = extract_first_generation(raw)
        self.assertEqual(extracted, body)
        self.assertEqual(method, "SHACL_RESPONSE_WRAPPER")

    def test_ambiguous_markdown_candidates_are_rejected(self):
        raw = "```turtle\na .\n```\n```ttl\nb .\n```\n"
        with self.assertRaises(ValueError):
            extract_first_generation(raw)

    def test_iteration_one_selection_never_substitutes_later_candidate(self):
        later = {"ITERATION": "2", "ARTIFACT_TYPE": "generator_raw_response", "ARTIFACT_PATH": "later.txt"}
        self.assertIsNone(select_first_generator_artifact([later]))
        first = {"ITERATION": "1", "ARTIFACT_TYPE": "generator_raw_response", "ARTIFACT_PATH": "first.txt"}
        self.assertIs(select_first_generator_artifact([later, first]), first)

    def test_metrics_keep_no_verdicts_in_end_to_end_denominator(self):
        rows = [
            {"requirement_id": "A", "expected_outcome": "PASS", "actual_conforms": True, "execution_status": "EXECUTED", "behavioral_match": True, "generation_status": "GENERATED"},
            {"requirement_id": "A", "expected_outcome": "FAIL", "actual_conforms": False, "execution_status": "EXECUTED", "behavioral_match": True, "generation_status": "GENERATED"},
            {"requirement_id": "B", "expected_outcome": "FAIL", "actual_conforms": True, "execution_status": "EXECUTED", "behavioral_match": False, "generation_status": "GENERATED"},
            {"requirement_id": "B", "expected_outcome": "PASS", "actual_conforms": False, "execution_status": "EXECUTED", "behavioral_match": False, "generation_status": "GENERATED"},
            {"requirement_id": "C", "expected_outcome": "PASS", "actual_conforms": None, "execution_status": "INFRASTRUCTURE_FAILURE", "behavioral_match": None, "generation_status": "GENERATION_ERROR"},
        ]
        summary = summarize_cases(rows)
        self.assertEqual((summary["tp"], summary["tn"], summary["fp_false_accept"], summary["fn_false_reject"]), (1, 1, 1, 1))
        self.assertEqual(summary["correct_cases"], 2)
        self.assertEqual(summary["total_cases"], 5)
        self.assertEqual(summary["no_verdict_count"], 1)
        self.assertEqual(summary["end_to_end_accuracy"], 2 / 5)
        self.assertEqual(summary["executable_accuracy"], 2 / 4)
        self.assertEqual(summary["precision"], 1 / 2)
        self.assertEqual(summary["recall"], 1 / 2)
        self.assertEqual(summary["specificity"], 1 / 2)
        self.assertEqual(summary["f1"], 1 / 2)
        self.assertEqual(summary["artifact_coverage"], 2 / 3)
        self.assertEqual(summary["exact_requirement_success_count"], 1)

    def test_output_paths_are_mode_scope_and_model_isolated(self):
        experiment = Path("/experiment")
        self.assertEqual(
            output_directory(experiment, "final", "SELF_REPAIR_FINAL", "luna"),
            Path("/experiment/OUTPUTS/RDF_EVALUATION/SELF_REPAIR_FINAL/luna"),
        )
        self.assertEqual(
            output_directory(experiment, "smoke", "FIRST_GENERATION", "gpt_oss"),
            Path("/experiment/OUTPUTS/RDF_EVALUATION/SMOKE/FIRST_GENERATION/gpt_oss"),
        )

    def test_comparison_workbook_is_written_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "comparison.xlsx"
            write_workbook(path, [{
                "scope": "smoke",
                "evaluation_mode": "FIRST_GENERATION",
                "model": "luna",
                "model_id": "gpt-5.6-luna-2026-07-09",
                "total_cases": 9,
            }], "test")
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)

    def test_frozen_selection_has_50_requirements_381_cases_and_9_smoke_cases(self):
        experiment = ROOT / "experiments/MODEL_SCALING_FULL_REPAIR_V2_50"
        sample = json.loads((experiment / "MANIFESTS/sample_50.json").read_text())
        smoke = json.loads((experiment / "MANIFESTS/smoke_2.json").read_text())
        behavioral = [json.loads(line) for line in (experiment / "REFERENCE/LUNA/behavioral_subset.jsonl").read_text().splitlines() if line.strip()]
        self.assertEqual(len(sample["requirements"]), 50)
        self.assertEqual(len(behavioral), 381)
        self.assertEqual(set(row["requirement_id"] for row in behavioral), set(sample["requirements"]))
        self.assertEqual(smoke["requirements"], ["IMO-069", "TRF-116"])
        self.assertEqual(sum(record["frozen_case_count"] for record in smoke["records"]), 9)
        self.assertEqual({record["verification_mode"] for record in smoke["records"]}, {"DIRECT_STATIC", "COMPLEX_READINESS"})


if __name__ == "__main__":
    unittest.main()
