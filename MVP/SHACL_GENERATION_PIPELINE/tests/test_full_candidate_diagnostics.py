from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from rdflib import Graph


EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
if str(EVALUATION) not in sys.path:
    sys.path.insert(0, str(EVALUATION))

from experiment_runner.candidate_diagnostics import (
    _load_case_ledger,
    evaluate_candidate_case,
    repair_transition,
    unavailable_attempts,
    validator_confusion,
)
from experiment_runner.core import BenchmarkCase, PreflightError, sha256


class FullCandidateDiagnosticTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[BenchmarkCase, dict, Graph]:
        rdf = root / "MVP/SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13/rdf/I2/I2-001/C1.ttl"
        rdf.parent.mkdir(parents=True)
        rdf.write_text("@prefix ex:<urn:test:>. ex:s a ex:Ship; ex:ok true.\n", encoding="utf-8")
        case = BenchmarkCase("I2", "SRC-IACS-I2-R4", "1", "I2-001", "DIRECT_STATIC", "benchmark_manifest", "C1", "rdf/I2/I2-001/C1.ttl", sha256(rdf), "PASS", "oracle", "")
        shape = Graph().parse(data="@prefix sh:<http://www.w3.org/ns/shacl#>. @prefix ex:<urn:test:>. ex:S a sh:NodeShape; sh:targetClass ex:Ship; sh:property[sh:path ex:ok; sh:minCount 1].", format="turtle")
        candidate = {
            "candidate_manifest_id":"M", "generation_run":"RUN_01", "requirement_id":"I2-001",
            "attempt_number":1,
            "source_id":"SRC-IACS-I2-R4", "candidate_path":"candidate.ttl", "candidate_sha256":"0"*64,
            "deterministic_parse_status":"PASS", "deterministic_validation_status":"PASS",
            "deterministic_turtle_valid":True, "deterministic_meta_shacl_valid":True,
            "deterministic_validation_path":None, "reached_semantic_validator":True,
            "semantic_validator_decision":"ACCEPT", "semantic_validator_pipeline_decision":"ACCEPT",
            "semantic_validator_feedback":"ok", "became_official_accepted_output":True,
            "overall_requirement_eventually_aborted":False, "iteration_limit_abort":False,
            "overall_final_status":"GENERATION_ACCEPTED",
        }
        return case, candidate, shape

    def test_validator_confusion_classes(self) -> None:
        expected = {
            (True, True): "TRUE_ACCEPT",
            (True, False): "FALSE_ACCEPT",
            (False, False): "TRUE_REJECT",
            (False, True): "FALSE_REJECT",
        }
        for inputs, outcome in expected.items():
            with self.subTest(inputs=inputs):
                self.assertEqual(validator_confusion(*inputs), outcome)

    def test_repair_transition_classes(self) -> None:
        expected = {
            (False, True): "IMPROVED",
            (True, True): "STABLE_CORRECT",
            (False, False): "STABLE_WRONG",
            (True, False): "REPAIR_DRIFT",
        }
        for inputs, outcome in expected.items():
            with self.subTest(inputs=inputs):
                self.assertEqual(repair_transition(*inputs), outcome)

    def test_unavailable_attempts_are_not_invented(self) -> None:
        self.assertEqual(unavailable_attempts([1, 3, 4]), [2])
        self.assertEqual(unavailable_attempts([1, 2, 3]), [])
        self.assertEqual(unavailable_attempts([]), [])

    def test_candidate_ledger_key_includes_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "ledger.jsonl"
            rows = [
                {"generation_run": "RUN_01", "requirement_id": "I2-001", "attempt_number": 1, "case_id": "C1"},
                {"generation_run": "RUN_01", "requirement_id": "I2-001", "attempt_number": 2, "case_id": "C1"},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            loaded, keys = _load_case_ledger(path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(len(keys), 2)

    def test_candidate_ledger_key_includes_generation_run(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "ledger.jsonl"
            rows = [
                {"generation_run": "RUN_01", "requirement_id": "I2-001", "attempt_number": 1, "case_id": "C1"},
                {"generation_run": "RUN_02", "requirement_id": "I2-001", "attempt_number": 1, "case_id": "C1"},
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            _, keys = _load_case_ledger(path)
            self.assertEqual(len(keys), 2)

    def test_duplicate_candidate_case_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "ledger.jsonl"
            row = {"generation_run": "RUN_01", "requirement_id": "I2-001", "attempt_number": 1, "case_id": "C1"}
            path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaises(PreflightError):
                _load_case_ledger(path)

    def test_candidate_evaluation_captures_report(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); case, candidate, shape = self._fixture(root)
            row = evaluate_candidate_case(repo=root, output_dir=root / "out", diagnostic_id="D", candidate=candidate, case=case, shape_graph=shape, shape_error=None, ontology_graph=Graph())
            self.assertEqual(row["execution_status"], "EXECUTED")
            self.assertTrue(row["behavioral_match"])
            self.assertTrue((root / "out" / row["report_graph_path"]).is_file())

    def test_candidate_cannot_cross_requirement_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); case, candidate, shape = self._fixture(root)
            candidate["requirement_id"] = "I2-999"
            row = evaluate_candidate_case(repo=root, output_dir=root / "out", diagnostic_id="D", candidate=candidate, case=case, shape_graph=shape, shape_error=None, ontology_graph=Graph())
            self.assertEqual(row["execution_status"], "IDENTITY_MISMATCH")
            self.assertIsNone(row["actual_conforms"])


if __name__ == "__main__":
    unittest.main()
