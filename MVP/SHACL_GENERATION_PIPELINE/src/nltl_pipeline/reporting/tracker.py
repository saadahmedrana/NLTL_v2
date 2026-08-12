from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable

from ..config import PIPELINE_ROOT, PipelineConfig
from ..retrieval.context import VocabularyRepository


SHEET_HEADERS: dict[str, list[str]] = {
    "README": ["SECTION", "DETAIL"],
    "REGULATION_QUEUE": [
        "REQUIREMENT_ID", "SOURCE", "EDITION", "PAGE", "CLAUSE", "CATEGORY",
        "ACTIVE_STATUS", "CODABILITY", "FIGURE_DEPENDENT", "QUEUE_ELIGIBILITY", "RUN_STATUS",
    ],
    "RUNS": [
        "SESSION_ID", "RUN_ID", "REQUIREMENT_ID", "STARTED_UTC", "FINISHED_UTC",
        "PIPELINE_VERSION", "VOCABULARY_LOCK_ID", "ATTEMPTS", "FINAL_STATUS", "ACCEPTED",
        "FINAL_SHAPE", "FINAL_FEEDBACK",
    ],
    "ITERATIONS": [
        "RUN_ID", "REQUIREMENT_ID", "ITERATION", "STATIC_VALID", "VALIDATOR_ACCEPT",
        "MATCHER_ACTIVATED", "DECISION", "FEEDBACK", "GENERATOR_ELAPSED_MS", "VALIDATOR_ELAPSED_MS",
    ],
    "API_CALLS": [
        "EVENT_ID", "RUN_ID", "REQUIREMENT_ID", "TIMESTAMP_UTC", "ROLE", "MODEL",
        "TRANSPORT_ATTEMPT", "STATUS", "AUTH_HEADER_NAME", "RATE_LIMIT_WAIT_MS", "ELAPSED_MS",
        "RETRYING", "RESPONSE_ID", "INPUT_TOKENS", "OUTPUT_TOKENS", "TOTAL_TOKENS",
    ],
    "TERM_RETRIEVAL": [
        "RUN_ID", "REQUIREMENT_ID", "LOCAL_NAME", "IRI", "KIND", "DATATYPE", "RANGE",
        "RECOMMENDED_UNIT", "SELECTION_REASON", "ITERATION_ADDED",
    ],
    "FEW_SHOT_SELECTION": [
        "RUN_ID", "REQUIREMENT_ID", "EXAMPLE_ID", "CASE_ID", "SCORE", "MATCHED_TAGS", "STATUS",
    ],
    "VALIDATION": [
        "RUN_ID", "REQUIREMENT_ID", "ITERATION", "VALID", "EXTRACTION_VALID", "TURTLE_VALID",
        "SHACL_STRUCTURE_VALID", "META_SHACL_VALID", "VOCABULARY_VALID", "DATATYPE_UNIT_VALID",
        "TARGET_PATH_VALID", "ERRORS", "WARNINGS", "USED_CANONICAL_IRIS", "UNKNOWN_IRIS",
        "OUT_OF_SCOPE_IRIS", "SUSPICIOUS_EXTERNAL_IRIS",
    ],
    "VOCAB_MATCHES": [
        "RUN_ID", "REQUIREMENT_ID", "ITERATION", "EVENT", "QUERY_FEEDBACK", "CANDIDATE_COUNT",
        "MATCH_FOUND", "CANONICAL_LOCAL_NAME", "CANONICAL_IRI", "FEEDBACK_APPENDIX",
    ],
    "ARTIFACTS": [
        "RUN_ID", "REQUIREMENT_ID", "ITERATION", "ARTIFACT_TYPE", "ARTIFACT_PATH", "SHA256", "BYTES",
    ],
    "UNRESOLVED": [
        "RUN_ID", "REQUIREMENT_ID", "ITERATION", "ISSUE_TYPE", "DETAIL", "STATUS",
    ],
    "RDF_TEST_QUEUE": [
        "RUN_ID", "REQUIREMENT_ID", "FINAL_SHAPE", "GENERATION_STATUS", "RDF_EVALUATION_STATUS", "NOTES",
    ],
}


def _join(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value)


class TrackerExporter:
    def __init__(self, config: PipelineConfig, vocabulary: VocabularyRepository) -> None:
        self.config = config
        self.vocabulary = vocabulary

    @staticmethod
    def _events(run_directory: Path) -> list[dict[str, Any]]:
        path = run_directory / "events.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _build_tables(self, run_directory: Path) -> dict[str, list[list[Any]]]:
        events = self._events(run_directory)
        tables: dict[str, list[list[Any]]] = {name: [] for name in SHEET_HEADERS}
        tables["README"] = [
            ["PURPOSE", "Traceability view for one regulation-to-SHACL generation run."],
            ["BOUNDARY", "Generation is frozen before RDF execution; no ship graph or hidden expected outcome is used here."],
            ["SOURCE OF TRUTH", "events.jsonl is append-only; CSV and Excel sheets are derived views."],
            ["ACCEPTED", "Static validation passed and the semantic validator accepted the candidate."],
            ["VOCABULARY_GAP", "No verified canonical term was available; the generator was not allowed to invent one."],
            ["RDF TEST QUEUE", "Accepted shapes await the separate bulk evaluator."],
        ]
        run_status = next((event.get("status", "") for event in reversed(events) if event["event_type"] == "run_finished"), "NOT_RUN")
        for item in self.vocabulary.regulation_queue():
            current = run_status if item["requirement_id"] == events[0]["requirement_id"] else "NOT_RUN"
            tables["REGULATION_QUEUE"].append([
                item["requirement_id"], item["source"], item["edition"], item["page"], item["clause"],
                item["category"], item["active_status"], item["codability"], item["figure_dependent"],
                item["queue_eligibility"], current,
            ])

        started = next((event for event in events if event["event_type"] == "run_started"), {})
        finished = next((event for event in reversed(events) if event["event_type"] == "run_finished"), {})
        tables["RUNS"].append([
            started.get("session_id", ""), started.get("run_id", ""), started.get("requirement_id", ""),
            started.get("timestamp_utc", ""), finished.get("timestamp_utc", ""),
            started.get("pipeline_version", ""), started.get("vocabulary_lock_id", ""),
            finished.get("attempts", 0), finished.get("status", ""), finished.get("accepted", False),
            finished.get("final_shape", ""), finished.get("final_feedback", ""),
        ])

        for event in events:
            kind = event["event_type"]
            if kind == "iteration_completed":
                tables["ITERATIONS"].append([
                    event["run_id"], event["requirement_id"], event.get("iteration"),
                    event.get("static_valid"), event.get("validator_accept"), event.get("matcher_activated"),
                    event.get("decision", ""), event.get("feedback", ""),
                    event.get("generator_elapsed_ms", 0), event.get("validator_elapsed_ms", 0),
                ])
            elif kind == "api_attempt_finished":
                tables["API_CALLS"].append([
                    event["event_id"], event["run_id"], event["requirement_id"], event["timestamp_utc"],
                    event.get("role", ""), event.get("model", ""), event.get("transport_attempt", ""),
                    event.get("status", ""), event.get("auth_header_name", ""),
                    event.get("rate_limit_wait_ms", 0), event.get("elapsed_ms", 0), event.get("retrying", False),
                    "", "", "", "",
                ])
            elif kind == "api_call_completed":
                tables["API_CALLS"].append([
                    event["event_id"], event["run_id"], event["requirement_id"], event["timestamp_utc"],
                    event.get("role", ""), event.get("model", ""), event.get("transport_attempts", ""),
                    "COMPLETED", "", 0, event.get("elapsed_ms", 0), False,
                    event.get("response_id", ""), event.get("input_tokens", ""),
                    event.get("output_tokens", ""), event.get("total_tokens", ""),
                ])
            elif kind == "term_retrieved":
                tables["TERM_RETRIEVAL"].append([
                    event["run_id"], event["requirement_id"], event.get("local_name", ""), event.get("iri", ""),
                    event.get("kind", ""), event.get("datatype", ""), event.get("range", ""),
                    event.get("recommended_unit", ""), event.get("selection_reason", ""), event.get("iteration_added", 0),
                ])
            elif kind == "few_shot_selected":
                tables["FEW_SHOT_SELECTION"].append([
                    event["run_id"], event["requirement_id"], event.get("example_id", ""), event.get("case_id", ""),
                    event.get("score", 0), _join(event.get("matched_tags", [])), event.get("status", ""),
                ])
            elif kind == "validation_completed":
                tables["VALIDATION"].append([
                    event["run_id"], event["requirement_id"], event.get("iteration"), event.get("valid"),
                    event.get("extraction_valid"), event.get("turtle_valid"), event.get("shacl_structure_valid"),
                    event.get("meta_shacl_valid"), event.get("vocabulary_valid"), event.get("datatype_unit_valid"),
                    event.get("target_path_valid"), _join(event.get("errors", [])), _join(event.get("warnings", [])),
                    _join(event.get("used_canonical_iris", [])), _join(event.get("unknown_canonical_iris", [])),
                    _join(event.get("out_of_scope_canonical_iris", [])), _join(event.get("suspicious_external_iris", [])),
                ])
            elif kind in {"matcher_search", "matcher_decision"}:
                tables["VOCAB_MATCHES"].append([
                    event["run_id"], event["requirement_id"], event.get("iteration"), kind,
                    event.get("query_feedback", ""), event.get("candidate_count", ""), event.get("match_found", ""),
                    event.get("canonical_local_name", ""), event.get("canonical_iri", ""),
                    event.get("feedback_appendix", ""),
                ])
            elif kind == "artifact_written":
                tables["ARTIFACTS"].append([
                    event["run_id"], event["requirement_id"], event.get("iteration", ""),
                    event.get("artifact_type", ""), event.get("artifact_path", ""), event.get("sha256", ""),
                    event.get("bytes", 0),
                ])
            elif kind == "unresolved_issue":
                tables["UNRESOLVED"].append([
                    event["run_id"], event["requirement_id"], event.get("iteration", ""),
                    event.get("issue_type", ""), event.get("detail", ""), event.get("status", "OPEN"),
                ])

        if finished.get("accepted"):
            tables["RDF_TEST_QUEUE"].append([
                finished.get("run_id", ""), finished.get("requirement_id", ""), finished.get("final_shape", ""),
                finished.get("status", ""), "NOT_RUN", "Run later with the separate bulk RDF evaluator.",
            ])
        return tables

    @staticmethod
    def _write_csv_tables(run_directory: Path, tables: dict[str, list[list[Any]]]) -> None:
        table_dir = run_directory / "tables"
        table_dir.mkdir(exist_ok=True)
        for name, rows in tables.items():
            path = table_dir / f"{name.lower()}.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(SHEET_HEADERS[name])
                writer.writerows(rows)

    def export(self, run_directory: Path) -> tuple[Path | None, list[str]]:
        tables = self._build_tables(run_directory)
        self._write_csv_tables(run_directory, tables)
        payload = {
            "kind": "pipeline",
            "title": "NLTL SHACL Pipeline Run Tracker",
            "subtitle": f"Run folder: {run_directory.name}",
            "sheets": [
                {"name": name, "headers": SHEET_HEADERS[name], "rows": rows}
                for name, rows in tables.items()
            ],
        }
        payload_path = run_directory / "tables" / "tracker_payload.json"
        payload_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        output = run_directory / "pipeline_run_tracker.xlsx"
        return build_excel_from_payload(self.config, payload_path, output)


def build_excel_from_payload(
    config: PipelineConfig,
    payload_path: Path,
    output: Path,
) -> tuple[Path | None, list[str]]:
    if not config.raw["reporting"].get("excel_enabled", True):
        return None, ["Excel export disabled in configuration"]
    node = Path(str(config.raw["reporting"]["node_executable"]))
    node_modules = Path(str(config.raw["reporting"]["artifact_tool_node_modules"]))
    if not node.is_file() or not node_modules.is_dir():
        return None, ["Artifact-tool runtime is unavailable; JSONL and CSV reporting completed"]
    builder = PIPELINE_ROOT / "reporting" / "build_tracker.mjs"
    with tempfile.TemporaryDirectory(prefix="nltl_tracker_") as temp_name:
        temp = Path(temp_name)
        os.symlink(node_modules, temp / "node_modules", target_is_directory=True)
        copied_builder = temp / "build_tracker.mjs"
        shutil.copy2(builder, copied_builder)
        result = subprocess.run(
            [str(node), str(copied_builder), str(payload_path), str(output)],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        return None, [f"Excel export failed: {result.stderr.strip() or result.stdout.strip()}"]
    return output, []
