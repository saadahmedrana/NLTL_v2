#!/usr/bin/env python3
"""Run the frozen R13 behavioral evaluation for one immutable GPT-5.6 Sol batch."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
EVALUATION_ROOT = HERE.parent
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

from experiment_runner.analysis import analyze
from experiment_runner.core import (
    EXPECTED_CASES,
    EXPECTED_REQUIREMENTS,
    PreflightError,
    find_repo_root,
    load_benchmark,
    load_generated_manifest,
    run_integrity_check,
    sha256,
    validate_generated_manifest,
)
from experiment_runner.execution import PYSHACL_OPTIONS, atomic_json, execute, load_ledger


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_path(repo: Path, value: str) -> Path:
    path = (repo / value).resolve()
    try:
        path.relative_to(repo.resolve())
    except ValueError as exc:
        raise PreflightError(f"Configured path escapes repository: {value}") from exc
    return path


def require_hash(repo: Path, value: str, expected: str, label: str) -> Path:
    path = repo_path(repo, value)
    if not path.is_file():
        raise PreflightError(f"Missing {label}: {path}")
    actual = sha256(path)
    if actual != expected:
        raise PreflightError(f"{label} hash mismatch: expected {expected}, found {actual}")
    return path


def _one_csv_row(path: Path) -> dict[str, str]:
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    if len(rows) != 1:
        raise PreflightError(f"Expected one metadata row in {path}, found {len(rows)}")
    return rows[0]


def preflight(repo: Path, config: dict[str, Any]) -> tuple[Any, Path, dict[str, dict[str, Any]], dict[str, Any]]:
    integrity = run_integrity_check(repo)
    benchmark = load_benchmark(repo, strict_counts=True)
    if len(benchmark.requirement_ids) != EXPECTED_REQUIREMENTS or len(benchmark.cases) != EXPECTED_CASES:
        raise PreflightError("Frozen R13 benchmark is not 268 requirements / 2,186 cases")

    source_config_path = require_hash(
        repo, config["source_config_path"], config["source_config_sha256"], "source generation config"
    )
    source_config = load_config(source_config_path)
    if source_config.get("models", {}).get("generator") != config["model_identifier"]:
        raise PreflightError("Recorded generator model differs from the selected Sol model")
    if source_config.get("pipeline_version") != config["pipeline_version"]:
        raise PreflightError("Recorded pipeline version differs from the selected batch")

    authoritative_manifest_path = require_hash(
        repo,
        config["authoritative_run_manifest_path"],
        config["authoritative_run_manifest_sha256"],
        "authoritative RUN_01 manifest",
    )
    authoritative = load_config(authoritative_manifest_path)
    if authoritative.get("status") != "COMPLETE":
        raise PreflightError("Authoritative RUN_01 behavioral experiment is not complete")
    if authoritative.get("pyshacl_options") != PYSHACL_OPTIONS:
        raise PreflightError("Current evaluator options differ from authoritative RUN_01")
    ontology_path = require_hash(repo, authoritative["ontology_path"], authoritative["ontology_sha256"], "R13 ontology")
    if ontology_path != repo_path(repo, config["ontology_path"]):
        raise PreflightError("Configured ontology differs from authoritative RUN_01")

    manifest_path = require_hash(
        repo, config["generated_manifest_path"], config["generated_manifest_sha256"], "immutable Sol manifest"
    )
    rows = load_generated_manifest(manifest_path, config["configuration"], config["generation_run"])
    generated = validate_generated_manifest(
        repo, benchmark, config["configuration"], config["generation_run"], rows, strict_counts=True
    )

    source_root = repo_path(repo, config["source_output_root"])
    models_seen: set[str] = set()
    session_rows = 0
    for requirement_id, row in generated.items():
        if row.get("source_session_id") != config["generation_run"]:
            raise PreflightError(f"Session identity mismatch for {requirement_id}")
        if row.get("model_identifier") != config["model_identifier"]:
            raise PreflightError(f"Model identity mismatch for {requirement_id}")
        metadata_value = row.get("run_metadata_path")
        if not metadata_value:
            raise PreflightError(f"Missing run metadata path for {requirement_id}")
        locked_sources = (
            ("run metadata", metadata_value, row.get("run_metadata_sha256")),
            ("artifact metadata", row.get("artifact_metadata_path"), row.get("artifact_metadata_sha256")),
            ("API metadata", row.get("api_metadata_path"), row.get("api_metadata_sha256")),
            ("context pack", row.get("context_pack_path"), row.get("context_pack_sha256")),
        )
        locked_paths: dict[str, Path] = {}
        for label, path_value, expected_hash in locked_sources:
            if not path_value or not expected_hash:
                raise PreflightError(f"Missing locked {label} identity for {requirement_id}")
            path = require_hash(repo, str(path_value), str(expected_hash), f"{label} for {requirement_id}")
            try:
                path.relative_to(source_root)
            except ValueError as exc:
                raise PreflightError(f"{label} does not belong to selected output root: {path}") from exc
            locked_paths[label] = path
        metadata_path = locked_paths["run metadata"]
        metadata = _one_csv_row(metadata_path)
        if metadata.get("SESSION_ID") != config["generation_run"]:
            raise PreflightError(f"Recorded session mismatch for {requirement_id}")
        if metadata.get("REQUIREMENT_ID") != requirement_id or metadata.get("RUN_ID") != row.get("run_id"):
            raise PreflightError(f"Recorded requirement/run identity mismatch for {requirement_id}")
        if metadata.get("PIPELINE_VERSION") != config["pipeline_version"]:
            raise PreflightError(f"Recorded pipeline version mismatch for {requirement_id}")
        accepted = metadata.get("FINAL_STATUS") == "GENERATION_ACCEPTED" and metadata.get("ACCEPTED") == "True"
        if accepted != (row.get("generation_status") == "GENERATED"):
            raise PreflightError(f"Generation availability mismatch for {requirement_id}")
        session_rows += 1
        api_path = locked_paths["API metadata"]
        for api_row in csv.DictReader(api_path.open(encoding="utf-8", newline="")):
            if api_row.get("RUN_ID") != row.get("run_id") or api_row.get("REQUIREMENT_ID") != requirement_id:
                raise PreflightError(f"API metadata identity mismatch for {requirement_id}")
            if api_row.get("MODEL"):
                models_seen.add(api_row["MODEL"])
    if session_rows != EXPECTED_REQUIREMENTS or models_seen != {config["model_identifier"]}:
        raise PreflightError(f"Sol metadata coverage/model mismatch: rows={session_rows}, models={sorted(models_seen)}")

    status_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        status_counts[str(row["generation_status"])] += 1
    expected_statuses = config["expected_generation_status_counts"]
    if dict(sorted(status_counts.items())) != dict(sorted(expected_statuses.items())):
        raise PreflightError(f"Manifest status counts changed: {dict(status_counts)}")
    return benchmark, manifest_path, generated, integrity


def requested_summary(ledger_path: Path, output_path: Path) -> dict[str, Any]:
    rows, _ = load_ledger(ledger_path)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["requirement_id"]].append(row)
    executable = [row for row in rows if row.get("execution_status") == "EXECUTED"]
    correct = [row for row in executable if row.get("behavioral_match") is True]
    generated_requirements = sum(all(row.get("generation_status") == "GENERATED" for row in values) for values in grouped.values())
    available_cases = sum(row.get("generation_status") == "GENERATED" for row in rows)
    equal_weight = sum(
        sum(row.get("behavioral_match") is True for row in values) / len(values)
        for values in grouped.values()
    ) / len(grouped)
    payload = {
        "denominator_cases": EXPECTED_CASES,
        "denominator_requirements": EXPECTED_REQUIREMENTS,
        "retained_artifact_availability": {
            "requirements_available": generated_requirements,
            "requirements_total": len(grouped),
            "requirement_rate": generated_requirements / len(grouped),
            "cases_with_available_artifact": available_cases,
            "cases_total": len(rows),
            "case_rate": available_cases / len(rows),
        },
        "correct_cases": len(correct),
        "correct_cases_over_2186": len(correct) / EXPECTED_CASES,
        "end_to_end_accuracy": len(correct) / len(rows),
        "conditional_accuracy_among_executable_verdicts": len(correct) / len(executable) if executable else None,
        "equal_weight_requirement_accuracy": equal_weight,
        "requirements_with_every_case_correct": sum(
            all(row.get("behavioral_match") is True for row in values) for values in grouped.values()
        ),
        "incorrect_PASS": sum(
            row.get("expected_outcome") == "PASS" and row.get("behavioral_match") is False for row in rows
        ),
        "incorrect_FAIL": sum(
            row.get("expected_outcome") == "FAIL" and row.get("behavioral_match") is False for row in rows
        ),
        "cases_without_verdict": sum(row.get("actual_conforms") is None for row in rows),
        "executable_verdicts": len(executable),
    }
    atomic_json(output_path, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=HERE / "evaluation_config.json")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        repo = find_repo_root()
        config = load_config(args.config.resolve())
        benchmark, manifest_path, generated, integrity = preflight(repo, config)
        print(
            f"Preflight PASS: {len(benchmark.requirement_ids)} requirements / {len(benchmark.cases)} cases; "
            f"manifest {sha256(manifest_path)}"
        )
        if args.preflight_only:
            print("Behavioral evaluation not run.")
            return 0
        output_root = repo_path(repo, config["output_root"])
        output_dir = output_root / config["run_id"]
        ledger = execute(
            repo=repo,
            benchmark=benchmark,
            cases=benchmark.cases,
            generation_runs=[config["generation_run"]],
            configurations=[config["configuration"]],
            generated_by_run_config={config["generation_run"]: {config["configuration"]: generated}},
            generated_manifest_paths={config["generation_run"]: {config["configuration"]: manifest_path}},
            output_dir=output_dir,
            run_id=config["run_id"],
            command_line=[sys.executable, str(Path(__file__).resolve()), "--config", str(args.config.resolve())],
            integrity_result=integrity,
            resume=False,
        )
        summaries = analyze(ledger)
        metrics = requested_summary(ledger, summaries / "sol_requested_metrics.json")
        print(f"Run complete: {config['run_id']}")
        print(f"Rows: {len(load_ledger(ledger)[0])}")
        print(json.dumps(metrics, indent=2, sort_keys=True))
        return 0
    except (PreflightError, KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"PREFLIGHT/EXECUTION FAILURE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
