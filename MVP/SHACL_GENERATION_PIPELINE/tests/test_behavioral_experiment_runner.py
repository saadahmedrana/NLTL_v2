from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from rdflib import Graph


EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
if str(EVALUATION) not in sys.path:
    sys.path.insert(0, str(EVALUATION))

from experiment_runner.core import BenchmarkCase, PreflightError, load_generated_manifest, sha256
from experiment_runner.execution import (
    evaluate_case,
    extract_validation_results,
    load_ledger,
    parse_shape,
    semantic_outcome,
    validate_expected_keys,
)


SHAPE = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <urn:test:> .
ex:S a sh:NodeShape ; sh:targetClass ex:Ship ; sh:property [ sh:path ex:ok ; sh:minCount 1 ] .
"""


class BehavioralExperimentRunnerTests(unittest.TestCase):
    def test_01_expected_pass_conforms(self) -> None:
        self.assertEqual(semantic_outcome("PASS", True), ("CORRECT_BEHAVIOR", True))

    def test_02_expected_fail_nonconforms(self) -> None:
        self.assertEqual(semantic_outcome("FAIL", False), ("CORRECT_BEHAVIOR", True))

    def test_03_false_accept(self) -> None:
        self.assertEqual(semantic_outcome("FAIL", True), ("FALSE_ACCEPT", False))

    def test_04_false_reject(self) -> None:
        self.assertEqual(semantic_outcome("PASS", False), ("FALSE_REJECT", False))

    def _case(self, root: Path, expected: str = "PASS", requirement: str = "R-1") -> BenchmarkCase:
        rdf_dir = root / "MVP/SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13/rdf/X/R-1"
        rdf_dir.mkdir(parents=True, exist_ok=True)
        rdf = rdf_dir / "C-1.ttl"
        rdf.write_text("@prefix ex: <urn:test:> . ex:a a ex:Ship ; ex:ok true .\n", encoding="utf-8")
        return BenchmarkCase("I2", "SRC", "1", requirement, "DIRECT_STATIC", "benchmark_manifest", "C-1", "rdf/X/R-1/C-1.ttl", sha256(rdf), expected, "oracle", "")

    def _generated(self, root: Path, requirement: str = "R-1", status: str = "GENERATED") -> tuple[dict, Graph | None]:
        shape = root / "shape.ttl"
        shape.write_text(SHAPE, encoding="utf-8")
        generated = {
            "manifest_id": "M1", "configuration": "FULL", "requirement_id": requirement,
            "source_id": "SRC", "generated_shacl_path": "shape.ttl",
            "generated_shacl_sha256": sha256(shape), "generation_status": status,
            "pipeline_final_status": "OK", "run_id": "G1", "generation_config_identifier": "CFG",
            "r13_contract_identifier": "R13", "failure_stage": "GENERATION", "failure_detail": "failed",
        }
        return generated, Graph().parse(shape, format="turtle") if status == "GENERATED" else None

    def _context(self) -> dict:
        return {"run_id": "E1", "run_timestamp_utc": "2026-01-01T00:00:00Z", "git_commit": None, "repository_dirty_state": None, "benchmark_integrity_hash": "lock"}

    def test_05_missing_generated_shape(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); case = self._case(root); generated, _ = self._generated(root, status="NOT_GENERATED")
            row = evaluate_case(repo=root, output_dir=root / "out", run_context=self._context(), configuration="FULL", case=case, generated=generated, shape_graph=None, ontology_graph=Graph())
            self.assertEqual(row["outcome_class"], "SHAPE_MISSING")
            self.assertIsNone(row["actual_conforms"])

    def test_06_malformed_shacl_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); shape = root / "bad.ttl"; shape.write_text("this is not turtle", encoding="utf-8")
            generated = {"generation_status": "GENERATED", "generated_shacl_path": "bad.ttl", "generated_shacl_sha256": sha256(shape)}
            graph, error, _ = parse_shape(root, generated)
            self.assertIsNone(graph); self.assertEqual(error, "SHAPE_SYNTAX_ERROR")

    def test_07_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); case = self._case(root); generated, graph = self._generated(root, requirement="R-2")
            row = evaluate_case(repo=root, output_dir=root / "out", run_context=self._context(), configuration="FULL", case=case, generated=generated, shape_graph=graph, ontology_graph=Graph())
            self.assertEqual(row["outcome_class"], "IDENTITY_MISMATCH")

    def test_08_duplicate_generated_rule(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "manifest.jsonl"
            row = {"configuration": "FULL", "requirement_id": "R-1"}
            path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaises(PreflightError): load_generated_manifest(path, "FULL")

    def test_09_pyshacl_execution_exception(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); case = self._case(root); generated, graph = self._generated(root)
            def fail(*args, **kwargs): raise RuntimeError("synthetic execution failure")
            row = evaluate_case(repo=root, output_dir=root / "out", run_context=self._context(), configuration="FULL", case=case, generated=generated, shape_graph=graph, ontology_graph=Graph(), validate_fn=fail)
            self.assertEqual(row["outcome_class"], "PYSHACL_EXECUTION_ERROR")
            self.assertTrue((root / "out" / row["traceback_path"]).exists())

    def test_10_report_graph_capture(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); case = self._case(root); generated, graph = self._generated(root)
            row = evaluate_case(repo=root, output_dir=root / "out", run_context=self._context(), configuration="FULL", case=case, generated=generated, shape_graph=graph, ontology_graph=Graph())
            self.assertEqual(row["execution_status"], "EXECUTED")
            self.assertTrue((root / "out" / row["report_graph_path"]).exists())

    def test_11_multiple_validation_results(self) -> None:
        report = Graph().parse(data="""@prefix sh:<http://www.w3.org/ns/shacl#>. @prefix ex:<urn:x:>.
        ex:r1 a sh:ValidationResult; sh:focusNode ex:a. ex:r2 a sh:ValidationResult; sh:focusNode ex:b.
        """, format="turtle")
        self.assertEqual(len(extract_validation_results(report)), 2)

    def test_12_wrong_requirement_cannot_execute(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); case = self._case(root, requirement="R-9"); generated, graph = self._generated(root)
            called = False
            def validator(*args, **kwargs):
                nonlocal called; called = True; return True, Graph(), ""
            row = evaluate_case(repo=root, output_dir=root / "out", run_context=self._context(), configuration="FULL", case=case, generated=generated, shape_graph=graph, ontology_graph=Graph(), validate_fn=validator)
            self.assertFalse(called); self.assertEqual(row["failure_stage"], "IDENTITY_CHECK")

    def test_13_duplicate_result_row_detection(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "ledger.jsonl"; row = {"configuration":"FULL","requirement_id":"R-1","case_id":"C-1"}
            path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaises(PreflightError): load_ledger(path)

    def test_14_resume_behavior_reads_existing_key(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "ledger.jsonl"; row = {"configuration":"FULL","requirement_id":"R-1","case_id":"C-1"}
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            rows, keys = load_ledger(path)
            self.assertEqual(len(rows), 1); self.assertIn(("FULL", "R-1", "C-1"), keys)

    def test_15_final_expected_row_count_check(self) -> None:
        rows = [{"configuration":"FULL","requirement_id":"R-1","case_id":"C-1"}]
        validate_expected_keys(rows, {("FULL", "R-1", "C-1")})
        with self.assertRaises(PreflightError):
            validate_expected_keys(rows, {("FULL", "R-1", "C-1"), ("FULL", "R-1", "C-2")})


if __name__ == "__main__":
    unittest.main()

