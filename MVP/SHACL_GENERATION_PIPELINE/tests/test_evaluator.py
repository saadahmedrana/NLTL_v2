from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.evaluator.bulk import BulkRdfEvaluator, EvaluationManifest


class EvaluatorTests(unittest.TestCase):
    def test_separate_bulk_evaluator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            shape = root / "shape.ttl"
            shape.write_text(
                "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
                "@prefix ex: <urn:test:> .\n"
                "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
                "ex:S a sh:NodeShape; sh:targetClass ex:Ship; sh:property [sh:path ex:ok; sh:datatype xsd:boolean; sh:hasValue true] .\n",
                encoding="utf-8",
            )
            passing = root / "pass.ttl"
            passing.write_text(
                "@prefix ex: <urn:test:> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
                "ex:ship a ex:Ship; ex:ok true .\n",
                encoding="utf-8",
            )
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps({
                "evaluation_id": "UNIT",
                "items": [{
                    "case_id": "C1", "variant_id": "PASS", "case_level": "requirement",
                    "requirement_ids": ["R1"], "shape_file": "shape.ttl", "data_file": "pass.ttl",
                    "expected_conforms": True,
                }],
            }), encoding="utf-8")
            base = PipelineConfig.load()
            raw = copy.deepcopy(base.raw)
            raw["reporting"]["excel_enabled"] = False
            config = PipelineConfig(raw=raw, config_path=base.config_path)
            output = BulkRdfEvaluator(config).evaluate(EvaluationManifest.load(manifest_path), root / "out")
            summary = json.loads((output / "evaluation_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["items"], 1)
            self.assertEqual(summary["expected_matches"], 1)

    def test_manifest_hash_mismatch_blocks_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            shape = root / "shape.ttl"
            shape.write_text(
                "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
                "@prefix ex: <urn:test:> .\n"
                "ex:S a sh:NodeShape; sh:targetClass ex:Ship .\n",
                encoding="utf-8",
            )
            data = root / "data.ttl"
            data.write_text("@prefix ex: <urn:test:> .\nex:ship a ex:Ship .\n", encoding="utf-8")
            shape_hash = hashlib.sha256(shape.read_bytes()).hexdigest()
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps({
                "evaluation_id": "HASH",
                "items": [{
                    "case_id": "C1", "variant_id": "PASS", "case_level": "requirement",
                    "requirement_ids": ["R1"], "shape_file": "shape.ttl", "data_file": "data.ttl",
                    "shape_sha256": shape_hash, "data_sha256": "0" * 64,
                    "expected_conforms": True,
                }],
            }), encoding="utf-8")
            base = PipelineConfig.load()
            raw = copy.deepcopy(base.raw)
            raw["reporting"]["excel_enabled"] = False
            output = BulkRdfEvaluator(
                PipelineConfig(raw=raw, config_path=base.config_path)
            ).evaluate(EvaluationManifest.load(manifest_path), root / "out")
            result = json.loads((output / "evaluation_results.jsonl").read_text(encoding="utf-8"))
            self.assertFalse(result["execution_ok"])
            self.assertFalse(result["file_integrity_ok"])
            self.assertIn("SHA-256", result["error"])


if __name__ == "__main__":
    unittest.main()
