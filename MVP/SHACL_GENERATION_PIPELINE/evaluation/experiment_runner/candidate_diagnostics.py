from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyshacl
import rdflib
from rdflib import Graph

from . import RUNNER_VERSION
from .analysis import analyze, summarize_rows
from .core import (
    GENERATION_RUNS,
    SOURCE_IDS,
    Benchmark,
    BenchmarkCase,
    PreflightError,
    composite_hash,
    find_repo_root,
    load_benchmark,
    requirement_sort_key,
    run_integrity_check,
    select_cases,
    sha256,
)
from .execution import (
    PYSHACL_OPTIONS,
    atomic_json,
    extract_validation_results,
    git_state,
    ledger_csv,
    register_project_math_functions,
    safe_component,
    semantic_outcome,
    utc_now,
    validation_results_ledger,
)


DIAGNOSTIC_VERSION = "1.0.0"
ABORTED_STATUSES = {
    "MAX_ATTEMPTS_REACHED",
    "TERM_RESOLUTION_UNRESOLVED",
    "SYNTAX_REPAIR_EXHAUSTED",
    "PIPELINE_ERROR",
}


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PreflightError(f"Missing FULL history table: {path}")
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def _one_row(path: Path) -> dict[str, str]:
    rows = _csv_rows(path)
    if len(rows) != 1:
        raise PreflightError(f"Expected exactly one FULL run row in {path}; found {len(rows)}")
    return rows[0]


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def validator_confusion(validator_accept: bool, behaviorally_exact: bool) -> str:
    if validator_accept:
        return "TRUE_ACCEPT" if behaviorally_exact else "FALSE_ACCEPT"
    return "FALSE_REJECT" if behaviorally_exact else "TRUE_REJECT"


def repair_transition(previous_exact: bool, current_exact: bool) -> str:
    if not previous_exact and current_exact:
        return "IMPROVED"
    if previous_exact and current_exact:
        return "STABLE_CORRECT"
    if not previous_exact and not current_exact:
        return "STABLE_WRONG"
    return "REPAIR_DRIFT"


def unavailable_attempts(available: list[int]) -> list[int]:
    if not available:
        return []
    present = set(available)
    return [number for number in range(1, max(available) + 1) if number not in present]


def _artifact_map(
    rows: list[dict[str, str]], artifact_type: str, *, allow_retries: bool = False
) -> dict[int, dict[str, str]]:
    result: dict[int, dict[str, str]] = {}
    for row in rows:
        if row.get("ARTIFACT_TYPE") != artifact_type:
            continue
        iteration = int(row["ITERATION"])
        if iteration in result and not allow_retries:
            raise PreflightError(f"Duplicate {artifact_type} artifact at iteration {iteration}")
        # Validator calls may be retried within one generation attempt.  Their
        # artifact table order is chronological, so the last preserved response
        # is the attempt's final validator record.  Generated candidate shapes
        # and all other artifact types remain strictly unique per attempt.
        result[iteration] = row
    return result


def discover_candidates(repo: Path, generation_runs: list[str], configuration: str = "FULL") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if configuration not in {"FULL", "FULL_REPAIR_V2"}:
        raise PreflightError(f"Unsupported candidate-diagnostic configuration: {configuration}")
    directory = "FINAL_LUNA_MAIN" if configuration == "FULL" else "FULL_REPAIR_V2"
    full_root = repo / "MVP/SHACL_GENERATION_PIPELINE/experiments" / directory
    candidates: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for generation_run in generation_runs:
        if generation_run not in GENERATION_RUNS:
            raise PreflightError(f"Unknown generation run: {generation_run}")
        runs_root = full_root / generation_run / "runs"
        run_dirs = sorted(path for path in runs_root.iterdir() if path.is_dir()) if runs_root.is_dir() else []
        if len(run_dirs) != 268:
            raise PreflightError(f"{configuration} {generation_run} has {len(run_dirs)} requirement runs, expected 268")
        requirement_seen: set[str] = set()
        for run_dir in run_dirs:
            run = _one_row(run_dir / "tables/runs.csv")
            requirement_id = run["REQUIREMENT_ID"]
            if requirement_id in requirement_seen:
                raise PreflightError(f"Duplicate {configuration} requirement in {generation_run}: {requirement_id}")
            requirement_seen.add(requirement_id)
            if run["RUN_ID"] != run_dir.name:
                raise PreflightError(f"{configuration} run ID mismatch: {run_dir}")
            context_path = run_dir / "artifacts/context_pack_initial.json"
            context = json.loads(context_path.read_text(encoding="utf-8"))["requirement"]
            if context.get("id") != requirement_id:
                raise PreflightError(f"Context identity mismatch: {context_path}")
            source_id = SOURCE_IDS.get(str(context.get("sourceSheet")))
            if not source_id:
                raise PreflightError(f"Unknown source identity in {context_path}")

            artifacts = _csv_rows(run_dir / "tables/artifacts.csv")
            for artifact in artifacts:
                if artifact.get("RUN_ID") != run["RUN_ID"] or artifact.get("REQUIREMENT_ID") != requirement_id:
                    raise PreflightError(f"Artifact identity mismatch in {run_dir / 'tables/artifacts.csv'}")
            candidate_artifacts = _artifact_map(artifacts, "candidate_shape")
            deterministic_artifacts = _artifact_map(artifacts, "deterministic_validation")
            validator_raw_artifacts = _artifact_map(artifacts, "validator_raw_response", allow_retries=True)
            validator_prompt_artifacts = _artifact_map(artifacts, "validator_prompt", allow_retries=True)
            attempt_metadata_artifacts = _artifact_map(artifacts, "attempt_metadata")
            repair_diff_artifacts = _artifact_map(artifacts, "repair_diff")
            final_artifacts = [row for row in artifacts if row["ARTIFACT_TYPE"] == "final_accepted_shape"]
            if len(final_artifacts) > 1:
                raise PreflightError(f"Duplicate final accepted shapes in {run_dir}")
            final_hash = final_artifacts[0]["SHA256"] if final_artifacts else None
            iteration_rows = {int(row["ITERATION"]): row for row in _csv_rows(run_dir / "tables/iterations.csv")}
            validation_rows = {int(row["ITERATION"]): row for row in _csv_rows(run_dir / "tables/validation.csv")}
            available = sorted(candidate_artifacts)
            missing = unavailable_attempts(available)
            inventory.append({
                "generation_run": generation_run,
                "requirement_id": requirement_id,
                "source_id": source_id,
                "generation_pipeline_run_id": run["RUN_ID"],
                "overall_final_status": run["FINAL_STATUS"],
                "overall_requirement_eventually_aborted": run["FINAL_STATUS"] != "GENERATION_ACCEPTED",
                "iteration_limit_abort": run["FINAL_STATUS"] == "MAX_ATTEMPTS_REACHED",
                "pipeline_attempts_recorded": int(run["ATTEMPTS"]),
                "preserved_candidate_count": len(available),
                "preserved_attempt_numbers": available,
                "unavailable_attempt_numbers": missing,
                "earlier_attempts_unavailable": bool(missing),
                "run_metadata_path": str((run_dir / "tables/runs.csv").relative_to(repo)),
            })
            for attempt in available:
                artifact = candidate_artifacts[attempt]
                candidate_path = run_dir / artifact["ARTIFACT_PATH"]
                if not candidate_path.is_file():
                    raise PreflightError(f"Recorded candidate missing: {candidate_path}")
                actual_hash = sha256(candidate_path)
                if actual_hash != artifact["SHA256"]:
                    raise PreflightError(f"Candidate hash mismatch: {candidate_path}")
                deterministic_path: Path | None = None
                deterministic: dict[str, Any] = {}
                if attempt in deterministic_artifacts:
                    deterministic_artifact = deterministic_artifacts[attempt]
                    deterministic_path = run_dir / deterministic_artifact["ARTIFACT_PATH"]
                    if sha256(deterministic_path) != deterministic_artifact["SHA256"]:
                        raise PreflightError(f"Deterministic artifact hash mismatch: {deterministic_path}")
                    deterministic = json.loads(deterministic_path.read_text(encoding="utf-8"))
                validation = validation_rows.get(attempt, {})
                attempt_metadata: dict[str, Any] = {}
                if attempt in attempt_metadata_artifacts:
                    metadata_path = run_dir / attempt_metadata_artifacts[attempt]["ARTIFACT_PATH"]
                    if sha256(metadata_path) != attempt_metadata_artifacts[attempt]["SHA256"]:
                        raise PreflightError(f"Attempt metadata hash mismatch: {metadata_path}")
                    attempt_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                locality: dict[str, Any] | None = None
                if attempt in repair_diff_artifacts:
                    diff_path = run_dir / repair_diff_artifacts[attempt]["ARTIFACT_PATH"]
                    if sha256(diff_path) != repair_diff_artifacts[attempt]["SHA256"]:
                        raise PreflightError(f"Repair diff hash mismatch: {diff_path}")
                    locality = json.loads(diff_path.read_text(encoding="utf-8"))
                raw_artifact = validator_raw_artifacts.get(attempt)
                prompt_artifact = validator_prompt_artifacts.get(attempt)
                reached_validator = raw_artifact is not None
                raw_payload: dict[str, Any] = {}
                raw_path: Path | None = None
                if raw_artifact:
                    raw_path = run_dir / raw_artifact["ARTIFACT_PATH"]
                    if sha256(raw_path) != raw_artifact["SHA256"]:
                        raise PreflightError(f"Validator artifact hash mismatch: {raw_path}")
                    try:
                        raw_payload = json.loads(raw_path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        raw_payload = {}
                iteration = iteration_rows.get(attempt, {})
                validator_accept = _boolean(iteration.get("VALIDATOR_ACCEPT"))
                if validator_accept is None and reached_validator:
                    validator_accept = _boolean(raw_payload.get("accept"))
                feedback = iteration.get("FEEDBACK") or raw_payload.get("feedback")
                pipeline_decision = iteration.get("DECISION") or (
                    "ACCEPT" if validator_accept is True else "REJECT" if validator_accept is False else None
                )
                became_official = bool(
                    run["FINAL_STATUS"] == "GENERATION_ACCEPTED"
                    and validator_accept is True
                    and final_hash == actual_hash
                )
                candidates.append({
                    "candidate_manifest_id": f"{configuration}-{generation_run}-{requirement_id}-A{attempt:02d}",
                    "configuration": configuration,
                    "generation_run": generation_run,
                    "requirement_id": requirement_id,
                    "source_id": source_id,
                    "source_clause": context.get("clause"),
                    "attempt_number": attempt,
                    "candidate_path": str(candidate_path.relative_to(repo)),
                    "candidate_sha256": actual_hash,
                    "candidate_artifact_recorded_sha256": artifact["SHA256"],
                    "candidate_artifact_type": artifact["ARTIFACT_TYPE"],
                    "candidate_artifact_iteration": int(artifact["ITERATION"]),
                    "artifact_metadata_path": str((run_dir / "tables/artifacts.csv").relative_to(repo)),
                    "run_metadata_path": str((run_dir / "tables/runs.csv").relative_to(repo)),
                    "deterministic_validation_path": str(deterministic_path.relative_to(repo)) if deterministic_path else None,
                    "deterministic_validation_status": (
                        "PASS" if _boolean(deterministic.get("valid", validation.get("VALID"))) is True
                        else "FAIL" if _boolean(deterministic.get("valid", validation.get("VALID"))) is False
                        else "UNAVAILABLE"
                    ),
                    "deterministic_parse_status": (
                        "PASS" if _boolean(deterministic.get("turtle_valid", validation.get("TURTLE_VALID"))) is True
                        else "FAIL" if _boolean(deterministic.get("turtle_valid", validation.get("TURTLE_VALID"))) is False
                        else "UNAVAILABLE"
                    ),
                    "deterministic_extraction_valid": _boolean(deterministic.get("extraction_valid", validation.get("EXTRACTION_VALID"))),
                    "deterministic_turtle_valid": _boolean(deterministic.get("turtle_valid", validation.get("TURTLE_VALID"))),
                    "deterministic_shacl_structure_valid": _boolean(deterministic.get("shacl_structure_valid", validation.get("SHACL_STRUCTURE_VALID"))),
                    "deterministic_meta_shacl_valid": _boolean(deterministic.get("meta_shacl_valid", validation.get("META_SHACL_VALID"))),
                    "deterministic_vocabulary_valid": _boolean(deterministic.get("vocabulary_valid", validation.get("VOCABULARY_VALID"))),
                    "deterministic_datatype_unit_valid": _boolean(deterministic.get("datatype_unit_valid", validation.get("DATATYPE_UNIT_VALID"))),
                    "deterministic_target_path_valid": _boolean(deterministic.get("target_path_valid", validation.get("TARGET_PATH_VALID"))),
                    "deterministic_errors": deterministic.get("errors", [validation["ERRORS"]] if validation.get("ERRORS") else []),
                    "deterministic_warnings": deterministic.get("warnings", [validation["WARNINGS"]] if validation.get("WARNINGS") else []),
                    "reached_semantic_validator": reached_validator,
                    "semantic_validator_decision": (
                        "ACCEPT" if validator_accept is True else "REJECT" if validator_accept is False else None
                    ),
                    "semantic_validator_accept": validator_accept,
                    "semantic_validator_pipeline_decision": pipeline_decision,
                    "semantic_validator_feedback": feedback,
                    "semantic_validator_raw_path": str(raw_path.relative_to(repo)) if raw_path else None,
                    "semantic_validator_prompt_path": str((run_dir / prompt_artifact["ARTIFACT_PATH"]).relative_to(repo)) if prompt_artifact else None,
                    "became_official_accepted_output": became_official,
                    "overall_requirement_eventually_aborted": run["FINAL_STATUS"] != "GENERATION_ACCEPTED",
                    "iteration_limit_abort": run["FINAL_STATUS"] == "MAX_ATTEMPTS_REACHED",
                    "overall_final_status": run["FINAL_STATUS"],
                    "overall_final_feedback": run.get("FINAL_FEEDBACK"),
                    "repair_mode": attempt_metadata.get("mode"),
                    "repair_locality": locality,
                    "repair_stalled": attempt_metadata.get("stalled", False),
                    "repair_oscillation_detected": attempt_metadata.get("oscillation_detected", False),
                    "matcher_status": attempt_metadata.get("matcher_status"),
                    "matcher_assisted_repair": attempt_metadata.get("mode") == "MATCHER_ASSISTED_REPAIR",
                    "escape_hatch_attempt": attempt_metadata.get("mode") == "FRESH_REGENERATION_ESCAPE_HATCH",
                    "generation_pipeline_run_id": run["RUN_ID"],
                    "preserved_attempt_numbers": available,
                    "unavailable_attempt_numbers": missing,
                    "earlier_attempts_unavailable": bool(missing),
                })
        if len(requirement_seen) != 268:
            raise PreflightError(f"{configuration} {generation_run} has {len(requirement_seen)} unique requirements")
    candidates.sort(key=lambda row: (row["generation_run"], requirement_sort_key(row["requirement_id"]), row["attempt_number"]))
    inventory.sort(key=lambda row: (row["generation_run"], requirement_sort_key(row["requirement_id"])))
    return candidates, inventory


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    temporary.replace(path)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _load_case_ledger(path: Path) -> tuple[list[dict[str, Any]], set[tuple[str, str, str, int, str]]]:
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, str, str, int, str]] = set()
    if not path.exists():
        return rows, keys
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PreflightError(f"Malformed candidate ledger line {line_number}: {exc}") from exc
        key = (
            row["generation_run"],
            row.get("configuration", "FULL_CANDIDATE_DIAGNOSTIC"),
            row["requirement_id"],
            int(row["attempt_number"]),
            row["case_id"],
        )
        if key in keys:
            raise PreflightError(f"Duplicate candidate diagnostic key: {key}")
        keys.add(key)
        rows.append(row)
    return rows, keys


def _flatten(results: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({value for result in results for value in result[key]})


def _case_result_base(
    diagnostic_id: str, candidate: dict[str, Any], case: BenchmarkCase
) -> dict[str, Any]:
    return {
        "run_id": diagnostic_id,
        "diagnostic_run_id": diagnostic_id,
        "configuration": candidate.get("diagnostic_configuration", "FULL_CANDIDATE_DIAGNOSTIC"),
        "parent_configuration": candidate.get("parent_configuration", candidate.get("configuration")),
        "generation_run": candidate["generation_run"],
        "requirement_id": candidate["requirement_id"],
        "source_id": candidate["source_id"],
        "source_family": case.source_family,
        "source_clause": case.source_clause,
        "attempt_number": candidate["attempt_number"],
        "candidate_attempt": candidate.get("candidate_attempt", candidate["attempt_number"]),
        "candidate_manifest_id": candidate["candidate_manifest_id"],
        "candidate_path": candidate["candidate_path"],
        "candidate_sha256": candidate["candidate_sha256"],
        "generated_shape_path": candidate["candidate_path"],
        "generated_shape_sha256": candidate["candidate_sha256"],
        "generation_status": candidate.get("generation_status", "GENERATED"),
        "original_final_status": candidate.get("original_final_status", candidate["overall_final_status"]),
        "diagnostic_only": candidate.get("diagnostic_only", True),
        "official_final_shape": candidate.get("official_final_shape", False),
        "deterministic_parse_status": candidate["deterministic_parse_status"],
        "deterministic_validation_status": candidate["deterministic_validation_status"],
        "deterministic_turtle_valid": candidate["deterministic_turtle_valid"],
        "deterministic_meta_shacl_valid": candidate["deterministic_meta_shacl_valid"],
        "deterministic_validation_path": candidate["deterministic_validation_path"],
        "reached_semantic_validator": candidate["reached_semantic_validator"],
        "semantic_validator_decision": candidate["semantic_validator_decision"],
        "semantic_validator_pipeline_decision": candidate["semantic_validator_pipeline_decision"],
        "semantic_validator_feedback": candidate["semantic_validator_feedback"],
        "became_official_accepted_output": candidate["became_official_accepted_output"],
        "overall_requirement_eventually_aborted": candidate["overall_requirement_eventually_aborted"],
        "iteration_limit_abort": candidate["iteration_limit_abort"],
        "overall_final_status": candidate["overall_final_status"],
        "case_id": case.case_id,
        "rdf_path": case.rdf_path,
        "rdf_sha256": case.rdf_sha256,
        "expected_behavioral_result": case.expected_outcome,
        "expected_outcome": case.expected_outcome,
        "source_oracle_rationale": case.source_oracle_rationale,
        "verification_mode": case.verification_mode,
        "pyshacl_options": PYSHACL_OPTIONS,
    }


def evaluate_candidate_case(
    *,
    repo: Path,
    output_dir: Path,
    diagnostic_id: str,
    candidate: dict[str, Any],
    case: BenchmarkCase,
    shape_graph: Graph | None,
    shape_error: tuple[str, str] | None,
    ontology_graph: Graph,
    validate_fn: Any = pyshacl.validate,
) -> dict[str, Any]:
    base = _case_result_base(diagnostic_id, candidate, case)
    if candidate["requirement_id"] != case.requirement_id or candidate["source_id"] != case.source_id:
        return {**base, "candidate_parse_status": "NOT_EXECUTED", "execution_status": "IDENTITY_MISMATCH", "actual_conforms": None, "behavioral_match": None, "false_accept": False, "false_reject": False, "outcome_class": "IDENTITY_MISMATCH", "validation_result_count": 0, "validation_results_json": [], "focus_nodes": [], "result_paths": [], "source_shapes": [], "constraint_components": [], "severities": [], "result_messages": [], "report_graph_path": None, "report_text_path": None, "exception_type": None, "exception_message": "Candidate/case identity mismatch", "traceback_path": None, "runtime_ms": 0.0}
    if shape_error:
        status, message = shape_error
        return {**base, "candidate_parse_status": "FAILED", "execution_status": status, "actual_conforms": None, "behavioral_match": None, "false_accept": False, "false_reject": False, "outcome_class": status, "validation_result_count": 0, "validation_results_json": [], "focus_nodes": [], "result_paths": [], "source_shapes": [], "constraint_components": [], "severities": [], "result_messages": [], "report_graph_path": None, "report_text_path": None, "exception_type": None, "exception_message": message, "traceback_path": None, "runtime_ms": 0.0}
    started = time.perf_counter()
    rdf_path = repo / "MVP/SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13" / case.rdf_path
    try:
        if sha256(rdf_path) != case.rdf_sha256:
            raise ValueError("Frozen RDF hash changed")
        data_graph = Graph().parse(rdf_path, format="turtle")
        conforms, report_graph, report_text = validate_fn(
            data_graph,
            shacl_graph=shape_graph,
            ont_graph=ontology_graph,
            inference="rdfs",
            meta_shacl=True,
            advanced=True,
            do_owl_imports=False,
            abort_on_first=False,
            allow_infos=False,
            allow_warnings=False,
        )
        if not isinstance(report_graph, Graph):
            raise TypeError(f"pySHACL returned no report graph: {report_text}")
        validation_results = extract_validation_results(report_graph)
        outcome, match = semantic_outcome(case.expected_outcome, bool(conforms))
        report_dir = output_dir / "reports" / candidate["generation_run"] / candidate["requirement_id"] / f"attempt_{candidate['attempt_number']:02d}"
        report_dir.mkdir(parents=True, exist_ok=True)
        graph_path = report_dir / f"{safe_component(case.case_id)}.ttl"
        text_path = report_dir / f"{safe_component(case.case_id)}.txt"
        report_graph.serialize(destination=graph_path, format="turtle")
        text_path.write_text(str(report_text), encoding="utf-8")
        return {
            **base,
            "candidate_parse_status": "PARSED",
            "execution_status": "EXECUTED",
            "actual_conforms": bool(conforms),
            "behavioral_match": match,
            "false_accept": outcome == "FALSE_ACCEPT",
            "false_reject": outcome == "FALSE_REJECT",
            "outcome_class": outcome,
            "validation_result_count": len(validation_results),
            "validation_results_json": validation_results,
            "focus_nodes": _flatten(validation_results, "focus_nodes"),
            "result_paths": _flatten(validation_results, "result_paths"),
            "source_shapes": _flatten(validation_results, "source_shapes"),
            "constraint_components": _flatten(validation_results, "constraint_components"),
            "severities": _flatten(validation_results, "severities"),
            "result_messages": _flatten(validation_results, "messages"),
            "report_graph_path": str(graph_path.relative_to(output_dir)),
            "report_text_path": str(text_path.relative_to(output_dir)),
            "exception_type": None,
            "exception_message": None,
            "traceback_path": None,
            "runtime_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    except Exception as exc:
        trace_dir = output_dir / "tracebacks" / candidate["generation_run"] / candidate["requirement_id"] / f"attempt_{candidate['attempt_number']:02d}"
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_path = trace_dir / f"{safe_component(case.case_id)}.txt"
        trace_path.write_text(traceback.format_exc(), encoding="utf-8")
        return {**base, "candidate_parse_status": "PARSED" if shape_graph is not None else "FAILED", "execution_status": "PYSHACL_EXECUTION_ERROR", "actual_conforms": None, "behavioral_match": None, "false_accept": False, "false_reject": False, "outcome_class": "PYSHACL_EXECUTION_ERROR", "validation_result_count": 0, "validation_results_json": [], "focus_nodes": [], "result_paths": [], "source_shapes": [], "constraint_components": [], "severities": [], "result_messages": [], "report_graph_path": None, "report_text_path": None, "exception_type": type(exc).__name__, "exception_message": str(exc), "traceback_path": str(trace_path.relative_to(output_dir)), "runtime_ms": round((time.perf_counter() - started) * 1000, 3)}


def _parse_candidate(repo: Path, candidate: dict[str, Any]) -> tuple[Graph | None, tuple[str, str] | None]:
    path = repo / candidate["candidate_path"]
    if not path.is_file() or sha256(path) != candidate["candidate_sha256"]:
        return None, ("CANDIDATE_LOAD_ERROR", "Candidate missing or hash changed")
    try:
        return Graph().parse(path, format="turtle"), None
    except Exception as exc:
        return None, ("CANDIDATE_SYNTAX_ERROR", f"{type(exc).__name__}: {exc}")


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(
    output_dir: Path,
    candidates: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> None:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["generation_run"], row["requirement_id"], int(row["attempt_number"]))].append(row)
    candidate_by_key = {(c["generation_run"], c["requirement_id"], c["attempt_number"]): c for c in candidates}
    candidate_summaries: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items(), key=lambda item: (item[0][0], requirement_sort_key(item[0][1]), item[0][2])):
        candidate = candidate_by_key[key]
        executed = [row for row in values if row["execution_status"] == "EXECUTED"]
        correct = sum(row["behavioral_match"] is True for row in values)
        pass_rows = [row for row in values if row["expected_behavioral_result"] == "PASS"]
        fail_rows = [row for row in values if row["expected_behavioral_result"] == "FAIL"]
        pass_executed = [row for row in pass_rows if row["execution_status"] == "EXECUTED"]
        fail_executed = [row for row in fail_rows if row["execution_status"] == "EXECUTED"]
        exact = len(executed) == len(values) and correct == len(values)
        confusion = None
        if candidate["reached_semantic_validator"] and candidate["semantic_validator_accept"] is not None and len(executed) == len(values):
            confusion = validator_confusion(candidate["semantic_validator_accept"], exact)
        candidate_summaries.append({
            "generation_run": key[0],
            "requirement_id": key[1],
            "source_id": candidate["source_id"],
            "attempt_number": key[2],
            "candidate_path": candidate["candidate_path"],
            "candidate_sha256": candidate["candidate_sha256"],
            "deterministic_validation_status": candidate["deterministic_validation_status"],
            "reached_semantic_validator": candidate["reached_semantic_validator"],
            "semantic_validator_decision": candidate["semantic_validator_decision"],
            "semantic_validator_pipeline_decision": candidate["semantic_validator_pipeline_decision"],
            "became_official_accepted_output": candidate["became_official_accepted_output"],
            "overall_requirement_eventually_aborted": candidate["overall_requirement_eventually_aborted"],
            "overall_final_status": candidate["overall_final_status"],
            "cases_correct": correct,
            "cases_total": len(values),
            "cases_executed": len(executed),
            "case_behavioral_accuracy": _ratio(correct, len(executed)),
            "end_to_end_case_accuracy": _ratio(correct, len(values)),
            "exact_requirement_behavioral_correctness": exact,
            "expected_pass_correct": sum(row["behavioral_match"] is True for row in pass_rows),
            "expected_pass_total": len(pass_rows),
            "expected_pass_accuracy": _ratio(sum(row["behavioral_match"] is True for row in pass_executed), len(pass_executed)),
            "expected_fail_correct": sum(row["behavioral_match"] is True for row in fail_rows),
            "expected_fail_total": len(fail_rows),
            "expected_fail_accuracy": _ratio(sum(row["behavioral_match"] is True for row in fail_executed), len(fail_executed)),
            "false_accepts": sum(row["false_accept"] for row in values),
            "false_rejects": sum(row["false_reject"] for row in values),
            "infrastructure_failures": len(values) - len(executed),
            "validator_confusion_class": confusion,
        })
    summary_dir = output_dir / "summaries"
    summary_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl_atomic(summary_dir / "candidate_summary.jsonl", candidate_summaries)
    _write_csv(summary_dir / "candidate_summary.csv", candidate_summaries)

    confusion_rows = [row for row in candidate_summaries if row["validator_confusion_class"]]
    _write_csv(summary_dir / "validator_confusion_candidates.csv", confusion_rows)
    reached = [row for row in candidate_summaries if row["reached_semantic_validator"]]
    confusion_summary = {
        "candidates_reaching_semantic_validator": len(reached),
        "behaviorally_scorable_validator_candidates": len(confusion_rows),
        "unscorable_validator_candidates": len(reached) - len(confusion_rows),
        "counts": dict(sorted(Counter(row["validator_confusion_class"] for row in confusion_rows).items())),
    }
    atomic_json(summary_dir / "validator_confusion_summary.json", confusion_summary)

    summary_lookup = {(r["generation_run"], r["requirement_id"], r["attempt_number"]): r for r in candidate_summaries}
    transitions: list[dict[str, Any]] = []
    by_requirement: dict[tuple[str, str], list[int]] = defaultdict(list)
    for generation_run, requirement_id, attempt in summary_lookup:
        by_requirement[(generation_run, requirement_id)].append(attempt)
    for (generation_run, requirement_id), attempts in sorted(by_requirement.items(), key=lambda item: (item[0][0], requirement_sort_key(item[0][1]))):
        ordered = sorted(attempts)
        for previous, current in zip(ordered, ordered[1:]):
            if current != previous + 1:
                continue
            before = summary_lookup[(generation_run, requirement_id, previous)]
            after = summary_lookup[(generation_run, requirement_id, current)]
            transitions.append({
                "generation_run": generation_run,
                "requirement_id": requirement_id,
                "from_attempt": previous,
                "to_attempt": current,
                "from_exact": before["exact_requirement_behavioral_correctness"],
                "to_exact": after["exact_requirement_behavioral_correctness"],
                "transition_class": repair_transition(before["exact_requirement_behavioral_correctness"], after["exact_requirement_behavioral_correctness"]),
            })
    _write_csv(summary_dir / "repair_transitions.csv", transitions)
    atomic_json(summary_dir / "repair_transition_summary.json", {
        "transitions": len(transitions),
        "counts": dict(sorted(Counter(row["transition_class"] for row in transitions).items())),
    })

    aborted_rows: list[dict[str, Any]] = []
    for record in inventory:
        if not record["overall_requirement_eventually_aborted"]:
            continue
        key_prefix = (record["generation_run"], record["requirement_id"])
        summaries = [row for key, row in summary_lookup.items() if key[:2] == key_prefix]
        final_attempt = max((row["attempt_number"] for row in summaries), default=None)
        final_exact = next((row["exact_requirement_behavioral_correctness"] for row in summaries if row["attempt_number"] == final_attempt), False)
        any_exact = any(row["exact_requirement_behavioral_correctness"] for row in summaries)
        aborted_rows.append({
            **record,
            "final_preserved_attempt": final_attempt,
            "final_rejected_candidate_behaviorally_exact": bool(final_exact),
            "any_behaviorally_exact_candidate_before_abort": any_exact,
            "never_contained_behaviorally_exact_candidate": not any_exact,
        })
    _write_csv(summary_dir / "aborted_requirements.csv", aborted_rows)
    atomic_json(summary_dir / "aborted_requirements_summary.json", {
        "aborted_requirements": len(aborted_rows),
        "iteration_limit_aborted_requirements": sum(row["iteration_limit_abort"] for row in aborted_rows),
        "final_rejected_candidate_behaviorally_exact": sum(row["final_rejected_candidate_behaviorally_exact"] for row in aborted_rows),
        "any_behaviorally_exact_candidate_before_abort": sum(row["any_behaviorally_exact_candidate_before_abort"] for row in aborted_rows),
        "never_contained_behaviorally_exact_candidate": sum(row["never_contained_behaviorally_exact_candidate"] for row in aborted_rows),
        "aborted_by_pipeline_status": dict(sorted(Counter(row["overall_final_status"] for row in aborted_rows).items())),
    })


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def execute_diagnostic(
    *,
    repo: Path,
    benchmark: Benchmark,
    cases: list[BenchmarkCase],
    candidates: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    output_dir: Path,
    diagnostic_id: str,
    command_line: list[str],
    integrity: dict[str, Any],
    resume: bool,
    candidate_manifest_filename: str = "full_candidate_manifest.jsonl",
    inventory_filename: str = "requirement_candidate_inventory.jsonl",
    ledger_filename: str = "full_candidate_case_results.jsonl",
    run_manifest_filename: str = "diagnostic_run_manifest.json",
    standard_outputs: bool = False,
) -> Path:
    if resume and not output_dir.is_dir():
        raise PreflightError(f"Diagnostic resume directory does not exist: {output_dir}")
    if not resume and output_dir.exists():
        raise PreflightError(f"Diagnostic output already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=resume)
    candidate_manifest_path = output_dir / candidate_manifest_filename
    inventory_path = output_dir / inventory_filename
    candidate_payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in candidates)
    inventory_payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in inventory)
    if resume:
        if not candidate_manifest_path.is_file() or candidate_manifest_path.read_text(encoding="utf-8") != candidate_payload:
            raise PreflightError("Candidate discovery manifest changed; refusing resume")
        if not inventory_path.is_file() or inventory_path.read_text(encoding="utf-8") != inventory_payload:
            raise PreflightError("Candidate inventory changed; refusing resume")
    else:
        candidate_manifest_path.write_text(candidate_payload, encoding="utf-8")
        inventory_path.write_text(inventory_payload, encoding="utf-8")
    case_by_requirement: dict[str, list[BenchmarkCase]] = defaultdict(list)
    for case in cases:
        case_by_requirement[case.requirement_id].append(case)
    expected_keys = {
        (
            candidate["generation_run"],
            candidate.get("diagnostic_configuration", "FULL_CANDIDATE_DIAGNOSTIC"),
            candidate["requirement_id"],
            candidate["attempt_number"],
            case.case_id,
        )
        for candidate in candidates
        for case in case_by_requirement[candidate["requirement_id"]]
    }
    ledger_path = output_dir / ledger_filename
    rows, completed = _load_case_ledger(ledger_path)
    if not completed.issubset(expected_keys):
        raise PreflightError("Candidate resume ledger contains out-of-scope keys")
    commit, dirty = git_state(repo)
    manifest_path = output_dir / run_manifest_filename
    prior = json.loads(manifest_path.read_text(encoding="utf-8")) if resume and manifest_path.is_file() else {}
    invariants = {
        "diagnostic_run_id": diagnostic_id,
        "generation_runs": sorted({candidate["generation_run"] for candidate in candidates}),
        "benchmark_integrity_hash": benchmark.integrity_hash,
        "candidate_manifest_sha256": hashlib.sha256(candidate_payload.encode("utf-8")).hexdigest(),
        "expected_case_rows": len(expected_keys),
        "pyshacl_options": PYSHACL_OPTIONS,
    }
    if prior:
        changed = {key: (prior.get(key), value) for key, value in invariants.items() if prior.get(key) != value}
        if changed:
            raise PreflightError(f"Candidate diagnostic resume invariants changed: {changed}")
    manifest = {
        **invariants,
        "diagnostic_only": True,
        "configurations": sorted({candidate.get("diagnostic_configuration", "FULL_CANDIDATE_DIAGNOSTIC") for candidate in candidates}),
        "parent_configurations": sorted({candidate.get("parent_configuration", candidate.get("configuration")) for candidate in candidates}),
        "official_full_metric_affected": False,
        "official_parent_metric_affected": False,
        "official_artifact_substitution_permitted": False,
        "status": "IN_PROGRESS",
        "started_utc": prior.get("started_utc", utc_now()),
        "command_line": prior.get("command_line", command_line),
        "command_history": [*prior.get("command_history", []), command_line],
        "benchmark_integrity_status": integrity["status"],
        "candidates_discovered": len(candidates),
        "requirements_with_preserved_candidates": len({(c["generation_run"], c["requirement_id"]) for c in candidates}),
        "requirement_run_inventory_count": len(inventory),
        "completed_case_rows": len(rows),
        "git_commit": commit,
        "repository_dirty_state": dirty,
        "python_version": platform.python_version(),
        "rdflib_version": rdflib.__version__,
        "pyshacl_version": pyshacl.__version__,
        "runner_version": RUNNER_VERSION,
        "candidate_diagnostic_version": DIAGNOSTIC_VERSION,
    }
    atomic_json(manifest_path, manifest)
    register_project_math_functions(repo)
    ontology = Graph().parse(repo / "MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    for candidate in candidates:
        shape_graph, shape_error = _parse_candidate(repo, candidate)
        for case in sorted(case_by_requirement[candidate["requirement_id"]], key=lambda item: item.case_id):
            key = (
                candidate["generation_run"],
                candidate.get("diagnostic_configuration", "FULL_CANDIDATE_DIAGNOSTIC"),
                candidate["requirement_id"],
                candidate["attempt_number"],
                case.case_id,
            )
            if key in completed:
                continue
            row = evaluate_candidate_case(repo=repo, output_dir=output_dir, diagnostic_id=diagnostic_id, candidate=candidate, case=case, shape_graph=shape_graph, shape_error=shape_error, ontology_graph=ontology)
            row["shape_parse_status"] = row["candidate_parse_status"]
            row["end_to_end_success"] = row.get("behavioral_match") is True
            _append_jsonl(ledger_path, row)
            rows.append(row)
            completed.add(key)
            manifest["completed_case_rows"] = len(rows)
            atomic_json(manifest_path, manifest)
    actual = {
        (r["generation_run"], r["configuration"], r["requirement_id"], int(r["attempt_number"]), r["case_id"])
        for r in rows
    }
    if len(rows) != len(actual) or actual != expected_keys:
        raise PreflightError("Candidate diagnostic final key-set validation failed")
    if composite_hash(benchmark.locked_paths, repo) != benchmark.integrity_hash:
        raise PreflightError("Frozen benchmark changed during candidate diagnostic")
    post = run_integrity_check(repo)
    summarize(output_dir, candidates, inventory, rows)
    if standard_outputs:
        ledger_csv(ledger_path, output_dir / "raw_case_results.csv")
        validation_results_ledger(rows, output_dir / "validation_results.jsonl")
        analyze(ledger_path)
        grouped_dimensions = {
            "original_final_status": lambda row: row["original_final_status"],
            "source_family": lambda row: row["source_family"],
            "verification_mode": lambda row: row["verification_mode"],
        }
        diagnostic_summary: dict[str, Any] = {
            "diagnostic_only": True,
            "configuration": sorted({row["configuration"] for row in rows}),
            "selected_rejected_attempt4_requirements": len({row["requirement_id"] for row in rows}),
            "expected_diagnostic_case_rows": len(expected_keys),
            "overall": summarize_rows(rows),
        }
        for dimension, key_fn in grouped_dimensions.items():
            grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                grouped_rows[str(key_fn(row))].append(row)
            diagnostic_summary[f"by_{dimension}"] = {
                key: summarize_rows(values) for key, values in sorted(grouped_rows.items())
            }
        requirement_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            requirement_groups[row["requirement_id"]].append(row)
        executable_requirements = sum(
            all(row["execution_status"] == "EXECUTED" for row in values)
            for values in requirement_groups.values()
        )
        exact_requirements = sum(
            all(row["execution_status"] == "EXECUTED" and row["behavioral_match"] is True for row in values)
            for values in requirement_groups.values()
        )
        diagnostic_summary.update({
            "executable_rejected_attempt4_requirements": executable_requirements,
            "behaviorally_exact_rejected_attempt4_requirements": exact_requirements,
            "exact_among_executable_rejected_attempt4_requirements": _ratio(exact_requirements, executable_requirements),
            "p_behaviorally_exact_given_rejected_final_attempt4_candidate": _ratio(exact_requirements, len(requirement_groups)),
        })
        atomic_json(output_dir / "summaries/diagnostic_summary.json", diagnostic_summary)
    manifest.update({"status": "COMPLETE", "finished_utc": utc_now(), "benchmark_integrity_status_after": post["status"], "benchmark_modified": False})
    atomic_json(manifest_path, manifest)
    return ledger_path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Read-only diagnostic evaluation of preserved FULL candidate trajectories")
    result.add_argument("--configuration", choices=("FULL", "FULL_REPAIR_V2"), default="FULL")
    runs = result.add_mutually_exclusive_group()
    runs.add_argument("--generation-run", choices=GENERATION_RUNS)
    runs.add_argument("--all-generation-runs", action="store_true")
    result.add_argument("--requirement")
    result.add_argument("--case")
    result.add_argument("--smoke", action="store_true")
    result.add_argument("--diagnostic-run-id")
    result.add_argument("--resume", action="store_true")
    result.add_argument("--discover-only", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    repo = find_repo_root()
    generation_runs = list(GENERATION_RUNS) if args.all_generation_runs or not args.generation_run else [args.generation_run]
    if (args.requirement or args.case) and not args.smoke:
        print("DIAGNOSTIC PREFLIGHT FAILURE: filters require --smoke", file=sys.stderr)
        return 2
    diagnostic_id = args.diagnostic_run_id or "FULL-CANDIDATES-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = repo / "MVP/SHACL_GENERATION_PIPELINE/evaluation/candidate_diagnostics" / diagnostic_id
    try:
        integrity = run_integrity_check(repo)
        benchmark = load_benchmark(repo, strict_counts=True)
        cases = select_cases(benchmark, args.requirement, None, args.case, args.smoke)
        candidates, inventory = discover_candidates(repo, generation_runs, args.configuration)
        if args.discover_only:
            if output_dir.exists():
                raise PreflightError(f"Diagnostic output already exists: {output_dir}")
            output_dir.mkdir(parents=True)
            _write_jsonl_atomic(output_dir / "full_candidate_manifest.jsonl", candidates)
            _write_jsonl_atomic(output_dir / "requirement_candidate_inventory.jsonl", inventory)
            atomic_json(output_dir / "diagnostic_run_manifest.json", {
                "diagnostic_run_id": diagnostic_id,
                "diagnostic_only": True,
                "status": "DISCOVERY_COMPLETE",
                "generation_runs": generation_runs,
                "candidates_discovered": len(candidates),
                "requirement_run_inventory_count": len(inventory),
                "benchmark_integrity_status": integrity["status"],
                "official_full_metric_affected": False,
            })
            print(f"Discovery complete: {len(candidates)} candidates; {len(inventory)} requirement-run records")
            print(output_dir.relative_to(repo))
            return 0
        selected_requirements = {case.requirement_id for case in cases}
        candidates = [candidate for candidate in candidates if candidate["requirement_id"] in selected_requirements]
        inventory = [record for record in inventory if record["requirement_id"] in selected_requirements]
        ledger = execute_diagnostic(repo=repo, benchmark=benchmark, cases=cases, candidates=candidates, inventory=inventory, output_dir=output_dir, diagnostic_id=diagnostic_id, command_line=[sys.executable, str(Path(sys.argv[0]).resolve()), *(argv if argv is not None else sys.argv[1:])], integrity=integrity, resume=args.resume)
        row_count = sum(1 for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip())
        print(f"FULL candidate diagnostic complete: {diagnostic_id}")
        print(f"Candidates evaluated: {len(candidates)}")
        print(f"Case rows: {row_count}")
        print(f"Ledger: {ledger.relative_to(repo)}")
        print("Official FULL results modified: NO")
        print("Frozen benchmark modified: NO")
        return 0
    except PreflightError as exc:
        print(f"DIAGNOSTIC PREFLIGHT/FINALIZATION FAILURE: {exc}", file=sys.stderr)
        return 2
