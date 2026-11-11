from __future__ import annotations

import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyshacl
from rdflib import Graph

from ..config import PipelineConfig
from ..reporting.tracker import build_excel_from_payload
from ..validation.sparql_extensions import register_math_functions


register_math_functions()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def file_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def concise_report(result: dict[str, Any]) -> str:
    """Summarize a report for Excel while raw JSONL/CSV retain full detail."""
    if not result.get("execution_ok"):
        return str(result.get("error", "Evaluation execution failed"))
    if result.get("actual_conforms") is True:
        return "Conforms: true"
    messages = [
        line.split("Message:", 1)[1].strip()
        for line in str(result.get("report_text", "")).splitlines()
        if "Message:" in line
    ]
    detail = messages[-1] if messages else "SHACL violation; see raw exports for full detail."
    return f"Conforms: false | {detail}"


class EvaluationManifest:
    def __init__(self, evaluation_id: str, items: list[dict[str, Any]], source: Path) -> None:
        self.evaluation_id = evaluation_id
        self.items = items
        self.source = source

    @classmethod
    def load(cls, path: Path) -> "EvaluationManifest":
        path = path.resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "items" in payload:
            items: list[dict[str, Any]] = []
            for item in payload["items"]:
                row = dict(item)
                for key in ("shape_file", "data_file"):
                    value = Path(str(row[key]))
                    row[key] = str(value if value.is_absolute() else (path.parent / value).resolve())
                items.append(row)
            return cls(str(payload["evaluation_id"]), items, path)
        if "cases" in payload:
            items = []
            for case_ref in payload["cases"]:
                case_dir = path.parent / str(case_ref["directory"])
                metadata_path = path.parent / str(case_ref["metadata"])
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                requirement_ids = [item["requirementId"] for item in metadata.get("requirements", [])]
                for variant in metadata.get("variants", []):
                    items.append({
                        "case_id": metadata["caseId"],
                        "variant_id": variant["variantId"],
                        "case_level": metadata.get("caseLevel", case_ref.get("caseLevel", "")),
                        "requirement_ids": requirement_ids,
                        "shape_file": str((case_dir / metadata["shapeFile"]).resolve()),
                        "data_file": str((case_dir / variant["dataFile"]).resolve()),
                        "expected_conforms": variant.get("expectedConforms"),
                    })
            return cls(str(payload.get("pilotId", path.stem)), items, path)
        raise ValueError("Evaluation manifest must contain either items or pilot cases")


class BulkRdfEvaluator:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.lock_info = config.verify_locked_inputs()
        self.ontology_graph = Graph().parse(config.path("ontology"), format="turtle")

    def evaluate(self, manifest: EvaluationManifest, output_root: Path) -> Path:
        output_directory = output_root.resolve() / f"EVAL-{manifest.evaluation_id}-{utc_stamp()}"
        output_directory.mkdir(parents=True, exist_ok=False)
        jsonl_path = output_directory / "evaluation_results.jsonl"
        rows: list[dict[str, Any]] = []
        for item in manifest.items:
            started = time.monotonic()
            result: dict[str, Any] = {
                "evaluation_id": manifest.evaluation_id,
                "case_id": item["case_id"],
                "variant_id": item["variant_id"],
                "case_level": item.get("case_level", ""),
                "requirement_ids": item.get("requirement_ids", []),
                "shape_file": item["shape_file"],
                "data_file": item["data_file"],
                "expected_conforms": item.get("expected_conforms"),
            }
            try:
                shape_sha256 = file_sha256(item["shape_file"])
                data_sha256 = file_sha256(item["data_file"])
                expected_shape_sha256 = item.get("shape_sha256")
                expected_data_sha256 = item.get("data_sha256")
                checks = [
                    actual == expected
                    for actual, expected in (
                        (shape_sha256, expected_shape_sha256),
                        (data_sha256, expected_data_sha256),
                    )
                    if expected is not None
                ]
                integrity_ok = all(checks) if checks else None
                result.update({
                    "shape_sha256": shape_sha256,
                    "data_sha256": data_sha256,
                    "expected_shape_sha256": expected_shape_sha256 or "",
                    "expected_data_sha256": expected_data_sha256 or "",
                    "file_integrity_ok": integrity_ok,
                })
                if integrity_ok is False:
                    raise ValueError("Shape or RDF SHA-256 does not match the evaluation manifest")
                shapes = Graph().parse(item["shape_file"], format="turtle")
                data = Graph().parse(item["data_file"], format="turtle")
                conforms, report_graph, report_text = pyshacl.validate(
                    data,
                    shacl_graph=shapes,
                    ont_graph=self.ontology_graph,
                    inference="rdfs",
                    meta_shacl=True,
                    advanced=True,
                )
                if not isinstance(report_graph, Graph):
                    raise ValueError(f"SHACL engine rejected the shape or query: {report_text}")
                actual = bool(conforms)
                expected = item.get("expected_conforms")
                result.update({
                    "execution_ok": True,
                    "actual_conforms": actual,
                    "expected_match": actual == expected if isinstance(expected, bool) else None,
                    "report_triples": len(report_graph),
                    "report_text": str(report_text),
                    "error": "",
                })
            except Exception as exc:
                result.update({
                    "execution_ok": False,
                    "actual_conforms": None,
                    "expected_match": False if isinstance(item.get("expected_conforms"), bool) else None,
                    "report_triples": 0,
                    "report_text": "",
                    "error": f"{type(exc).__name__}: {exc}",
                })
            result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
            rows.append(result)
            with jsonl_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")) + "\n")

        csv_path = output_directory / "evaluation_results.csv"
        headers = [
            "evaluation_id", "case_id", "variant_id", "case_level", "requirement_ids",
            "shape_file", "data_file", "shape_sha256", "data_sha256", "expected_shape_sha256",
            "expected_data_sha256", "file_integrity_ok", "expected_conforms", "execution_ok", "actual_conforms",
            "expected_match", "report_triples", "elapsed_ms", "error", "report_text",
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                export = dict(row)
                export["requirement_ids"] = " | ".join(row["requirement_ids"])
                writer.writerow(export)
        summary = {
            "evaluation_id": manifest.evaluation_id,
            "manifest": str(manifest.source),
            "manifest_sha256": file_sha256(str(manifest.source)),
            "vocabulary_lock_id": self.lock_info["lock_id"],
            "ontology_sha256": self.lock_info["ontology_sha256"],
            "items": len(rows),
            "execution_ok": sum(1 for row in rows if row["execution_ok"]),
            "expected_matches": sum(1 for row in rows if row["expected_match"] is True),
            "expected_mismatches": sum(1 for row in rows if row["expected_match"] is False),
        }
        (output_directory / "evaluation_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        headers = [
            "EVALUATION_ID", "CASE_ID", "VARIANT_ID", "CASE_LEVEL", "REQUIREMENT_IDS",
            "SHAPE_FILE", "DATA_FILE", "SHAPE_SHA256", "DATA_SHA256", "FILE_INTEGRITY_OK",
            "EXPECTED_CONFORMS", "EXECUTION_OK", "ACTUAL_CONFORMS",
            "EXPECTED_MATCH", "REPORT_TRIPLES", "ELAPSED_MS", "ERROR", "REPORT_SUMMARY",
        ]
        excel_rows = [[
            row["evaluation_id"], row["case_id"], row["variant_id"], row["case_level"],
            " | ".join(row["requirement_ids"]), row["shape_file"], row["data_file"],
            row.get("shape_sha256", ""), row.get("data_sha256", ""), str(row.get("file_integrity_ok", "")).upper(),
            str(row["expected_conforms"]).upper(), str(row["execution_ok"]).upper(),
            str(row["actual_conforms"]).upper(), str(row["expected_match"]).upper(),
            row["report_triples"], row["elapsed_ms"], row["error"], concise_report(row),
        ] for row in rows]
        tracker_payload = {
            "kind": "evaluation",
            "title": "NLTL Bulk RDF Evaluation Tracker",
            "subtitle": f"Evaluation: {manifest.evaluation_id}",
            "sheets": [
                {
                    "name": "README",
                    "headers": ["SECTION", "DETAIL"],
                    "rows": [
                        ["PURPOSE", "Separate bulk RDF/ship-graph execution of frozen SHACL shapes."],
                        ["BOUNDARY", "This evaluator never calls an LLM and is not part of the generation repair loop."],
                        ["VOCABULARY_LOCK", self.lock_info["lock_id"]],
                        ["ONTOLOGY_SHA256", self.lock_info["ontology_sha256"]],
                        ["MANIFEST", str(manifest.source)],
                        ["MANIFEST_SHA256", file_sha256(str(manifest.source))],
                    ],
                },
                {"name": "EVALUATION_RESULTS", "headers": headers, "rows": excel_rows},
            ],
        }
        payload_path = output_directory / "tracker_payload.json"
        payload_path.write_text(json.dumps(tracker_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        build_excel_from_payload(
            self.config,
            payload_path,
            output_directory / "rdf_evaluation_tracker.xlsx",
        )
        return output_directory
