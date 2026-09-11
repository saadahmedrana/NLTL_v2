from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pyshacl
import rdflib
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

from . import RUNNER_VERSION
from .core import (
    Benchmark,
    BenchmarkCase,
    PreflightError,
    composite_hash,
    requirement_sort_key,
    run_integrity_check,
    sha256,
)


SH = Namespace("http://www.w3.org/ns/shacl#")
PYSHACL_OPTIONS = {
    "inference": "rdfs",
    "advanced": True,
    "meta_shacl": True,
    "do_owl_imports": False,
    "abort_on_first": False,
    "allow_infos": False,
    "allow_warnings": False,
    "ontology_graph_usage": True,
}
INFRASTRUCTURE_OUTCOMES = {
    "SHAPE_MISSING",
    "GENERATION_ERROR",
    "SHAPE_SYNTAX_ERROR",
    "SHAPE_LOAD_ERROR",
    "IDENTITY_MISMATCH",
    "DUPLICATE_GENERATED_RULE",
    "RDF_LOAD_ERROR",
    "PYSHACL_EXECUTION_ERROR",
    "BENCHMARK_INFRASTRUCTURE_ERROR",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def safe_component(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def load_ledger(path: Path) -> tuple[list[dict[str, Any]], set[tuple[str, str, str]]]:
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, str, str]] = set()
    if not path.exists():
        return rows, keys
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PreflightError(f"Malformed resume ledger at line {line_number}: {exc}") from exc
        key = (row["configuration"], row["requirement_id"], row["case_id"])
        if key in keys:
            raise PreflightError(f"Duplicate result row in ledger: {key}")
        keys.add(key)
        rows.append(row)
    return rows, keys


def git_state(repo: Path) -> tuple[str | None, bool | None]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True, capture_output=True, check=True
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=True
        ).stdout.strip())
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def register_project_math_functions(repo: Path) -> None:
    src = repo / "MVP/SHACL_GENERATION_PIPELINE/src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from nltl_pipeline.validation.sparql_extensions import register_math_functions

    register_math_functions()


def _objects_as_strings(graph: Graph, subject: Any, predicate: Any) -> list[str]:
    return sorted({str(value) for value in graph.objects(subject, predicate)})


def extract_validation_results(report_graph: Graph) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for result in sorted(report_graph.subjects(RDF.type, SH.ValidationResult), key=str):
        results.append({
            "result_node": str(result),
            "focus_nodes": _objects_as_strings(report_graph, result, SH.focusNode),
            "result_paths": _objects_as_strings(report_graph, result, SH.resultPath),
            "source_shapes": _objects_as_strings(report_graph, result, SH.sourceShape),
            "constraint_components": _objects_as_strings(report_graph, result, SH.sourceConstraintComponent),
            "severities": _objects_as_strings(report_graph, result, SH.resultSeverity),
            "messages": _objects_as_strings(report_graph, result, SH.resultMessage),
            "values": _objects_as_strings(report_graph, result, SH.value),
        })
    return results


def _flatten(results: list[dict[str, Any]], field: str) -> list[str]:
    return sorted({value for result in results for value in result[field]})


def semantic_outcome(expected: str, conforms: bool) -> tuple[str, bool]:
    if expected == "PASS":
        return ("CORRECT_BEHAVIOR", True) if conforms else ("FALSE_REJECT", False)
    if expected == "FAIL":
        return ("CORRECT_BEHAVIOR", True) if not conforms else ("FALSE_ACCEPT", False)
    raise ValueError(f"Invalid expected outcome: {expected}")


def infrastructure_row(
    base: dict[str, Any], outcome: str, stage: str, message: str, exception_type: str | None = None
) -> dict[str, Any]:
    if outcome not in INFRASTRUCTURE_OUTCOMES:
        raise ValueError(f"Unknown infrastructure outcome: {outcome}")
    return {
        **base,
        "shape_parse_status": "NOT_PARSED" if outcome in {"SHAPE_MISSING", "GENERATION_ERROR"} else "FAILED",
        "execution_status": "INFRASTRUCTURE_FAILURE",
        "actual_conforms": None,
        "behavioral_match": None,
        "end_to_end_success": False,
        "outcome_class": outcome,
        "failure_stage": stage,
        "validation_result_count": 0,
        "validation_results_json": [],
        "focus_nodes": [],
        "result_paths": [],
        "source_shapes": [],
        "constraint_components": [],
        "severities": [],
        "result_messages": [],
        "exception_type": exception_type,
        "exception_message": message,
        "traceback_path": None,
        "report_graph_path": None,
        "report_text_path": None,
        "runtime_ms": 0.0,
    }


def case_base(
    run_context: dict[str, Any], configuration: str, case: BenchmarkCase, generated: dict[str, Any]
) -> dict[str, Any]:
    return {
        "run_id": run_context["run_id"],
        "run_timestamp_utc": run_context["run_timestamp_utc"],
        "configuration": configuration,
        "source_family": case.source_family,
        "source_id": case.source_id,
        "source_clause": case.source_clause,
        "requirement_id": case.requirement_id,
        "verification_mode": case.verification_mode,
        "verification_mode_source": case.verification_mode_source,
        "case_id": case.case_id,
        "rdf_path": case.rdf_path,
        "rdf_sha256": case.rdf_sha256,
        "expected_outcome": case.expected_outcome,
        "source_oracle_rationale": case.source_oracle_rationale,
        "test_pattern": case.test_pattern,
        "generated_shape_path": generated.get("generated_shacl_path"),
        "generated_shape_sha256": generated.get("generated_shacl_sha256"),
        "generated_shape_manifest_id": generated.get("manifest_id"),
        "generation_status": generated.get("generation_status"),
        "generation_pipeline_status": generated.get("pipeline_final_status"),
        "generation_run_id": generated.get("run_id"),
        "generation_config_identifier": generated.get("generation_config_identifier"),
        "r13_contract_identifier": generated.get("r13_contract_identifier"),
        "git_commit": run_context["git_commit"],
        "repository_dirty_state": run_context["repository_dirty_state"],
        "python_version": platform.python_version(),
        "rdflib_version": rdflib.__version__,
        "pyshacl_version": pyshacl.__version__,
        "runner_version": RUNNER_VERSION,
        "benchmark_version_or_lock_identifier": run_context["benchmark_integrity_hash"],
        "pyshacl_options": PYSHACL_OPTIONS,
    }


def evaluate_case(
    *,
    repo: Path,
    output_dir: Path,
    run_context: dict[str, Any],
    configuration: str,
    case: BenchmarkCase,
    generated: dict[str, Any],
    shape_graph: Graph | None,
    ontology_graph: Graph,
    validate_fn: Callable[..., Any] = pyshacl.validate,
) -> dict[str, Any]:
    base = case_base(run_context, configuration, case, generated)
    if generated.get("requirement_id") != case.requirement_id:
        return infrastructure_row(base, "IDENTITY_MISMATCH", "IDENTITY_CHECK", "Generated rule and case requirement IDs differ")
    if generated.get("source_id") != case.source_id:
        return infrastructure_row(base, "IDENTITY_MISMATCH", "SOURCE_ID_CHECK", "Generated rule and case source IDs differ")
    if generated.get("generation_status") != "GENERATED":
        outcome = "SHAPE_MISSING" if generated.get("generation_status") == "NOT_GENERATED" else "GENERATION_ERROR"
        return infrastructure_row(
            base, outcome, str(generated.get("failure_stage") or "GENERATION"), str(generated.get("failure_detail") or "No usable generated SHACL")
        )
    if shape_graph is None:
        return infrastructure_row(base, "SHAPE_LOAD_ERROR", "SHAPE_LOAD", "Usable generation record has no parsed shape")
    rdf_path = repo / "MVP/SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13" / case.rdf_path
    if not rdf_path.exists() or sha256(rdf_path) != case.rdf_sha256:
        return infrastructure_row(base, "BENCHMARK_INFRASTRUCTURE_ERROR", "RDF_INTEGRITY", "Frozen RDF fixture is missing or changed")
    started = time.perf_counter()
    try:
        data_graph = Graph().parse(rdf_path, format="turtle")
    except Exception as exc:
        row = infrastructure_row(base, "RDF_LOAD_ERROR", "RDF_PARSE", str(exc), type(exc).__name__)
        row["runtime_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return row
    try:
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
        results = extract_validation_results(report_graph)
        outcome, match = semantic_outcome(case.expected_outcome, bool(conforms))
        report_dir = output_dir / "reports" / configuration / case.requirement_id
        report_dir.mkdir(parents=True, exist_ok=True)
        graph_path = report_dir / f"{safe_component(case.case_id)}.ttl"
        text_path = report_dir / f"{safe_component(case.case_id)}.txt"
        report_graph.serialize(destination=graph_path, format="turtle")
        text_path.write_text(str(report_text), encoding="utf-8")
        return {
            **base,
            "shape_parse_status": "PARSED",
            "execution_status": "EXECUTED",
            "actual_conforms": bool(conforms),
            "behavioral_match": match,
            "end_to_end_success": match,
            "outcome_class": outcome,
            "failure_stage": None,
            "validation_result_count": len(results),
            "validation_results_json": results,
            "focus_nodes": _flatten(results, "focus_nodes"),
            "result_paths": _flatten(results, "result_paths"),
            "source_shapes": _flatten(results, "source_shapes"),
            "constraint_components": _flatten(results, "constraint_components"),
            "severities": _flatten(results, "severities"),
            "result_messages": _flatten(results, "messages"),
            "exception_type": None,
            "exception_message": None,
            "traceback_path": None,
            "report_graph_path": str(graph_path.relative_to(output_dir)),
            "report_text_path": str(text_path.relative_to(output_dir)),
            "runtime_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    except Exception as exc:
        trace_dir = output_dir / "tracebacks" / configuration / case.requirement_id
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_path = trace_dir / f"{safe_component(case.case_id)}.txt"
        trace_path.write_text(traceback.format_exc(), encoding="utf-8")
        message = str(exc)
        meta_failure = "SHACL File does not validate" in message or "MetaSHACL" in message
        outcome = "SHAPE_LOAD_ERROR" if meta_failure else "PYSHACL_EXECUTION_ERROR"
        stage = "META_SHACL" if meta_failure else "PYSHACL_EXECUTION"
        row = infrastructure_row(base, outcome, stage, message, type(exc).__name__)
        row["shape_parse_status"] = "PARSED"
        row["traceback_path"] = str(trace_path.relative_to(output_dir))
        row["runtime_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return row


def parse_shape(repo: Path, generated: dict[str, Any]) -> tuple[Graph | None, str | None, str | None]:
    if generated.get("generation_status") != "GENERATED":
        return None, None, None
    path_value = generated.get("generated_shacl_path")
    if not path_value:
        return None, "SHAPE_MISSING", "Generated manifest has no SHACL path"
    path = repo / path_value
    if not path.exists():
        return None, "SHAPE_MISSING", f"Generated SHACL does not exist: {path}"
    if sha256(path) != generated.get("generated_shacl_sha256"):
        return None, "SHAPE_LOAD_ERROR", f"Generated SHACL hash mismatch: {path}"
    try:
        return Graph().parse(path, format="turtle"), None, None
    except Exception as exc:
        return None, "SHAPE_SYNTAX_ERROR", f"{type(exc).__name__}: {exc}"


def ledger_csv(jsonl_path: Path, csv_path: Path) -> None:
    rows, _ = load_ledger(jsonl_path)
    if not rows:
        return
    fieldnames = list(rows[0])
    for row in rows[1:]:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def validation_results_ledger(rows: list[dict[str, Any]], path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for row in rows:
            for index, result in enumerate(row.get("validation_results_json", []), 1):
                stream.write(json.dumps({
                    "run_id": row["run_id"],
                    "configuration": row["configuration"],
                    "requirement_id": row["requirement_id"],
                    "case_id": row["case_id"],
                    "validation_result_index": index,
                    **result,
                }, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    temporary.replace(path)


def validate_expected_keys(
    rows: list[dict[str, Any]], expected_keys: set[tuple[str, str, str]]
) -> None:
    actual = {(row["configuration"], row["requirement_id"], row["case_id"]) for row in rows}
    if len(rows) != len(actual):
        raise PreflightError("Raw ledger contains duplicate experiment keys")
    if actual != expected_keys:
        missing = sorted(expected_keys - actual)
        extra = sorted(actual - expected_keys)
        raise PreflightError(f"Final result-key mismatch; missing={missing[:10]}, extra={extra[:10]}")


def execute(
    *,
    repo: Path,
    benchmark: Benchmark,
    cases: list[BenchmarkCase],
    configurations: list[str],
    generated_by_config: dict[str, dict[str, dict[str, Any]]],
    generated_manifest_paths: dict[str, Path],
    output_dir: Path,
    run_id: str,
    command_line: list[str],
    integrity_result: dict[str, Any],
    resume: bool,
) -> Path:
    if resume and not output_dir.is_dir():
        raise PreflightError(f"Resume output does not exist: {output_dir}")
    if not resume and output_dir.exists():
        raise PreflightError(f"Output run already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=resume)
    ledger_path = output_dir / "raw_case_results.jsonl"
    manifest_path = output_dir / "run_manifest.json"
    if ledger_path.exists() and not resume:
        raise PreflightError(f"Output run already exists; use --resume: {output_dir}")
    existing_rows, completed_keys = load_ledger(ledger_path)
    expected_keys = {case.key(config) for config in configurations for case in cases}
    if not completed_keys.issubset(expected_keys):
        raise PreflightError("Resume ledger contains rows outside this run's selected key set")
    commit, dirty = git_state(repo)
    started = existing_rows[0]["run_timestamp_utc"] if existing_rows else utc_now()
    context = {
        "run_id": run_id,
        "run_timestamp_utc": started,
        "git_commit": commit,
        "repository_dirty_state": dirty,
        "benchmark_integrity_hash": benchmark.integrity_hash,
        "benchmark_manifest_hashes": {
            str(path.relative_to(repo)): sha256(path) for path in benchmark.manifest_paths
        },
    }
    if resume and not manifest_path.exists():
        raise PreflightError(f"Resume run manifest does not exist: {manifest_path}")
    prior_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if resume else {}
    current_generated_hashes = {key: sha256(path) for key, path in generated_manifest_paths.items()}
    if prior_manifest:
        resume_invariants = {
            "run_id": run_id,
            "configurations": configurations,
            "benchmark_integrity_hash": benchmark.integrity_hash,
            "expected_result_rows": len(expected_keys),
            "generated_manifest_hashes": current_generated_hashes,
            "pyshacl_options": PYSHACL_OPTIONS,
        }
        disagreements = {
            key: (prior_manifest.get(key), value)
            for key, value in resume_invariants.items()
            if prior_manifest.get(key) != value
        }
        if disagreements:
            raise PreflightError(f"Resume invariants changed: {disagreements}")
    command_history = list(prior_manifest.get("command_history", []))
    command_history.append(command_line)
    manifest = {
        **context,
        "runner_version": RUNNER_VERSION,
        "status": "IN_PROGRESS",
        "configurations": configurations,
        "benchmark_integrity_status": integrity_result["status"],
        "benchmark_integrity_command": integrity_result["command"],
        "benchmark_integrity_output": integrity_result["output"],
        "benchmark_requirements": len(benchmark.requirement_ids),
        "benchmark_cases": len(benchmark.cases),
        "selected_requirements": len({case.requirement_id for case in cases}),
        "selected_cases": len(cases),
        "expected_result_rows": len(expected_keys),
        "generated_manifest_hashes": current_generated_hashes,
        "ontology_path": "MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/ontology/nltl_benchmark_vocabulary.ttl",
        "ontology_sha256": sha256(repo / "MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/ontology/nltl_benchmark_vocabulary.ttl"),
        "pyshacl_options": PYSHACL_OPTIONS,
        "python_version": platform.python_version(),
        "rdflib_version": rdflib.__version__,
        "pyshacl_version": pyshacl.__version__,
        "exact_command_line": prior_manifest.get("exact_command_line", command_line),
        "command_history": command_history,
        "number_completed": len(existing_rows),
        "number_infrastructure_failures": sum(r.get("outcome_class") in INFRASTRUCTURE_OUTCOMES for r in existing_rows),
        "number_semantic_results": sum(r.get("execution_status") == "EXECUTED" for r in existing_rows),
    }
    atomic_json(manifest_path, manifest)
    register_project_math_functions(repo)
    ontology_graph = Graph().parse(repo / manifest["ontology_path"], format="turtle")
    grouped: dict[str, list[BenchmarkCase]] = defaultdict(list)
    for case in cases:
        grouped[case.requirement_id].append(case)

    for configuration in configurations:
        for requirement_id in sorted(grouped, key=requirement_sort_key):
            generated = generated_by_config[configuration][requirement_id]
            shape_graph, shape_error, shape_message = parse_shape(repo, generated)
            for case in sorted(grouped[requirement_id], key=lambda item: item.case_id):
                key = case.key(configuration)
                if key in completed_keys:
                    continue
                if shape_error:
                    row = infrastructure_row(
                        case_base(context, configuration, case, generated),
                        shape_error,
                        "SHAPE_PARSE" if shape_error == "SHAPE_SYNTAX_ERROR" else "SHAPE_LOAD",
                        str(shape_message),
                    )
                else:
                    row = evaluate_case(
                        repo=repo,
                        output_dir=output_dir,
                        run_context=context,
                        configuration=configuration,
                        case=case,
                        generated=generated,
                        shape_graph=shape_graph,
                        ontology_graph=ontology_graph,
                    )
                append_jsonl(ledger_path, row)
                completed_keys.add(key)
                existing_rows.append(row)
                manifest["number_completed"] = len(existing_rows)
                manifest["number_infrastructure_failures"] = sum(
                    r.get("outcome_class") in INFRASTRUCTURE_OUTCOMES for r in existing_rows
                )
                manifest["number_semantic_results"] = sum(r.get("execution_status") == "EXECUTED" for r in existing_rows)
                atomic_json(manifest_path, manifest)

    validate_expected_keys(existing_rows, expected_keys)
    ending_hash = composite_hash(benchmark.locked_paths, repo)
    if ending_hash != benchmark.integrity_hash:
        manifest["status"] = "FAILED_BENCHMARK_CHANGED"
        atomic_json(manifest_path, manifest)
        raise PreflightError("Frozen benchmark hash changed during evaluation")
    post_integrity = run_integrity_check(repo)
    manifest.update({
        "status": "COMPLETE",
        "finished_utc": utc_now(),
        "benchmark_integrity_hash_after": ending_hash,
        "benchmark_integrity_status_after": post_integrity["status"],
        "benchmark_integrity_output_after": post_integrity["output"],
        "fixture_hashes_unchanged": True,
    })
    atomic_json(manifest_path, manifest)
    ledger_csv(ledger_path, output_dir / "raw_case_results.csv")
    validation_results_ledger(existing_rows, output_dir / "validation_results.jsonl")
    return ledger_path
