#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
PIPELINE = EXPERIMENT.parents[1]
EVALUATION = PIPELINE / "evaluation"
SRC = PIPELINE / "src"
for path in (EVALUATION, SRC, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment import verify_manifests
from experiment_runner.core import (
    PreflightError,
    find_repo_root,
    load_benchmark,
    load_generated_manifest,
    run_integrity_check,
    sha256,
    validate_generated_manifest,
)
from experiment_runner.execution import execute
from nltl_pipeline.validation.shacl import ShaclWrapperError, normalize_shacl_wrapper
from rdf_evaluation_common import MODES, MODELS, materialize_required_outputs, output_directory

MODEL_IDS = {
    "luna": "gpt-5.6-luna-2026-07-09",
    "sol": "gpt-5.6-sol-2026-07-09",
    "gemini": "gemini-3.5-flash",
    "gpt_oss": "gpt-oss-120b",
}
SOURCE_IDS = {
    "IACS_UR_I2": "SRC-IACS-I2-R4",
    "TRAFICOM": "SRC-TRAFICOM-2021",
    "IMO_POLAR_CODE": "SRC-IMO-MSC385-94",
    "IMO_AMEND_2026": "SRC-IMO26-SUPPLEMENT",
}
FENCE_RE = re.compile(
    r"^[ \t]*```(?:turtle|ttl|shacl)?[ \t]*\r?\n(?P<body>.*?)(?:\r?\n)?^[ \t]*```[ \t]*(?:\r?\n|$)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PreflightError(f"Missing required metadata table: {path}")
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise PreflightError(f"Missing required ledger: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def immutable_write(path: Path, payload: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != payload:
        raise PreflightError(f"Refusing to replace a different frozen evaluation input: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(payload, encoding="utf-8")


def extract_first_generation(raw: str) -> tuple[str, str]:
    """Extract wrapper/fence content only; never parse, repair, or rewrite Turtle."""
    try:
        wrapper = normalize_shacl_wrapper(raw)
    except ShaclWrapperError as wrapper_error:
        fences = list(FENCE_RE.finditer(raw))
        if len(fences) != 1 or not fences[0].group("body").strip():
            raise ValueError(f"No unambiguous wrapper or Markdown Turtle block: {wrapper_error}") from wrapper_error
        fenced = fences[0].group("body")
        try:
            nested_wrapper = normalize_shacl_wrapper(fenced)
        except ShaclWrapperError:
            return fenced, "MARKDOWN_CODE_FENCE"
        return nested_wrapper.turtle, "MARKDOWN_CODE_FENCE_AND_SHACL_RESPONSE_WRAPPER"
    return wrapper.turtle, "SHACL_RESPONSE_WRAPPER"


def select_first_generator_artifact(artifacts: list[dict[str, str]]) -> dict[str, str] | None:
    selected = [
        row for row in artifacts
        if row.get("ITERATION") == "1" and row.get("ARTIFACT_TYPE") == "generator_raw_response"
    ]
    if len(selected) > 1:
        raise PreflightError("Multiple preserved iteration-1 generator responses")
    return selected[0] if selected else None


def source_records(repo: Path, model: str, sample_requirements: list[str]) -> dict[str, dict[str, Any]]:
    selected = set(sample_requirements)
    if model == "luna":
        extraction_path = EXPERIMENT / "REFERENCE/LUNA/extraction_manifest.json"
        extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
        generation_path = EXPERIMENT / "REFERENCE/LUNA/generation_subset.jsonl"
        if extraction.get("status") != "COMPLETE" or extraction.get("model_id") != MODEL_IDS[model]:
            raise PreflightError("Frozen Luna extraction identity/status mismatch")
        if sha256(generation_path) != extraction.get("generation_subset_sha256"):
            raise PreflightError("Frozen Luna generation subset hash mismatch")
        rows = load_jsonl(generation_path)
        converted = {
            row["requirement_id"]: {
                **row,
                "status": row.get("pipeline_status"),
                "final_shape": row.get("final_shape_path"),
                "_generation_config_identifier": extraction.get("source_config_sha256"),
            }
            for row in rows
        }
    else:
        control = EXPERIMENT / f"OUTPUTS/FINAL/{model}/scaling_control"
        run_manifest = json.loads((control / "run_manifest.json").read_text(encoding="utf-8"))
        if run_manifest.get("status") != "COMPLETE" or run_manifest.get("completed_requirements") != 50:
            raise PreflightError(f"Generation run is not complete for {model}")
        if run_manifest.get("requested_model") != MODEL_IDS[model]:
            raise PreflightError(f"Locked model identity mismatch for {model}")
        rows = load_jsonl(control / "requirement_results.jsonl")
        converted = {
            row["requirement_id"]: {
                **row,
                "_generation_config_identifier": run_manifest.get("effective_config_sha256"),
            }
            for row in rows
        }
    if set(converted) != selected:
        raise PreflightError(f"Generation coverage mismatch for {model}")
    return converted


def resolve_run_directory(repo: Path, value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else repo / path


def artifact_path(repo: Path, run_dir: Path, row: dict[str, str]) -> Path:
    value = Path(row["ARTIFACT_PATH"])
    path = value if value.is_absolute() else run_dir / value
    try:
        path.resolve().relative_to(repo.resolve())
    except ValueError as exc:
        raise PreflightError(f"Artifact escapes repository: {path}") from exc
    return path


def build_manifest(
    repo: Path,
    model: str,
    mode: str,
    scope: str,
    benchmark: Any,
    sample: dict[str, Any],
    selected_requirements: list[str],
) -> tuple[Path, str]:
    records = source_records(repo, model, list(sample["requirements"]))
    source_by_requirement = {case.requirement_id: case.source_id for case in benchmark.cases}
    generation_run = f"SCALING50_{model.upper()}_{mode}_{scope.upper()}"
    manifest_root = EXPERIMENT / f"RDF_INPUTS/{scope.upper()}/{mode}/{model}"
    rows: list[dict[str, Any]] = []
    for requirement_id in selected_requirements:
        record = records[requirement_id]
        run_dir = resolve_run_directory(repo, record.get("run_directory"))
        base = {
            "manifest_id": f"{generation_run}-{requirement_id}",
            "generation_run": generation_run,
            "configuration": "FULL_REPAIR_V2",
            "evaluation_mode": mode,
            "requirement_id": requirement_id,
            "source_id": source_by_requirement[requirement_id],
            "model_identifier": MODEL_IDS[model],
            "run_id": record.get("run_id"),
            "pipeline_final_status": record.get("status"),
            "generation_config_identifier": record.get("_generation_config_identifier"),
            "queue_identifier": sample["sample_manifest_sha256"],
            "r13_contract_identifier": "VOCAB-LOCK-2026-08-22-R13",
        }
        if run_dir is None:
            rows.append({**base, "generation_status": "GENERATION_ERROR", "failure_stage": "RUN_UNAVAILABLE", "failure_detail": record.get("final_feedback"), "generated_shacl_path": None, "generated_shacl_sha256": None})
            continue
        metadata_rows = csv_rows(run_dir / "tables/runs.csv")
        if len(metadata_rows) != 1 or metadata_rows[0].get("REQUIREMENT_ID") != requirement_id or metadata_rows[0].get("RUN_ID") != record.get("run_id"):
            raise PreflightError(f"Run identity mismatch for {model}/{requirement_id}")
        metadata = metadata_rows[0]
        context_path = run_dir / "artifacts/context_pack_initial.json"
        context = json.loads(context_path.read_text(encoding="utf-8"))["requirement"]
        locator = str(context.get("sourceSheet"))
        if context.get("id") != requirement_id or SOURCE_IDS.get(locator) != source_by_requirement[requirement_id]:
            raise PreflightError(f"Source identity mismatch for {model}/{requirement_id}")
        artifacts_path = run_dir / "tables/artifacts.csv"
        artifacts = csv_rows(artifacts_path)
        common = {
            **base,
            "source_identity_locator": locator,
            "source_clause": context.get("clause"),
            "generation_timestamp": metadata.get("FINISHED_UTC") or metadata.get("STARTED_UTC"),
            "run_metadata_path": str((run_dir / "tables/runs.csv").relative_to(repo)),
            "artifact_metadata_path": str(artifacts_path.relative_to(repo)),
            "context_pack_path": str(context_path.relative_to(repo)),
        }
        if mode == "SELF_REPAIR_FINAL":
            final_rows = [row for row in artifacts if row.get("ARTIFACT_TYPE") == "final_accepted_shape"]
            accepted = metadata.get("FINAL_STATUS") == "GENERATION_ACCEPTED" and metadata.get("ACCEPTED") == "True"
            if accepted != (len(final_rows) == 1):
                raise PreflightError(f"Final artifact/status mismatch for {model}/{requirement_id}")
            if not accepted:
                rows.append({**common, "generation_status": "GENERATION_ERROR", "failure_stage": metadata.get("FINAL_STATUS"), "failure_detail": metadata.get("FINAL_FEEDBACK"), "generated_shacl_path": None, "generated_shacl_sha256": None})
                continue
            candidate = artifact_path(repo, run_dir, final_rows[0])
            if not candidate.is_file() or sha256(candidate) != final_rows[0].get("SHA256"):
                raise PreflightError(f"Final candidate hash mismatch: {candidate}")
            rows.append({
                **common,
                "generation_status": "GENERATED",
                "failure_stage": None,
                "failure_detail": None,
                "candidate_selection": "FINAL_ACCEPTED_FULL_REPAIR_V2_ARTIFACT",
                "generated_shacl_path": str(candidate.relative_to(repo)),
                "generated_shacl_sha256": sha256(candidate),
                "recorded_generated_shacl_sha256": final_rows[0].get("SHA256"),
            })
            continue

        raw_row = select_first_generator_artifact(artifacts)
        if raw_row is None:
            rows.append({**common, "generation_status": "GENERATION_ERROR", "failure_stage": "FIRST_GENERATOR_RESPONSE_MISSING", "failure_detail": "No preserved iteration-1 generator response", "generated_shacl_path": None, "generated_shacl_sha256": None})
            continue
        raw_path = artifact_path(repo, run_dir, raw_row)
        if not raw_path.is_file() or sha256(raw_path) != raw_row.get("SHA256"):
            raise PreflightError(f"First generator response hash mismatch: {raw_path}")
        raw = raw_path.read_text(encoding="utf-8")
        try:
            candidate_text, extraction_method = extract_first_generation(raw)
        except ValueError as exc:
            rows.append({
                **common,
                "generation_status": "GENERATION_ERROR",
                "failure_stage": "FIRST_GENERATION_EXTRACTION",
                "failure_detail": str(exc),
                "generated_shacl_path": None,
                "generated_shacl_sha256": None,
                "source_raw_path": str(raw_path.relative_to(repo)),
                "source_raw_sha256": sha256(raw_path),
            })
            continue
        candidate_path = manifest_root / "candidates" / f"{requirement_id}.ttl"
        immutable_write(candidate_path, candidate_text)
        rows.append({
            **common,
            "generation_status": "GENERATED",
            "failure_stage": None,
            "failure_detail": None,
            "candidate_selection": "ORIGINAL_ITERATION_1_GENERATOR_RESPONSE",
            "extraction_method": extraction_method,
            "source_raw_path": str(raw_path.relative_to(repo)),
            "source_raw_sha256": sha256(raw_path),
            "recorded_source_raw_sha256": raw_row.get("SHA256"),
            "generated_shacl_path": str(candidate_path.relative_to(repo)),
            "generated_shacl_sha256": sha256(candidate_path),
        })

    manifest_path = manifest_root / "generated_rules.jsonl"
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    immutable_write(manifest_path, payload)
    return manifest_path, generation_run


def selected_manifest(repo: Path, lock: dict[str, Any], scope: str) -> tuple[dict[str, Any], list[str]]:
    key = "smoke" if scope == "smoke" else "sample"
    path = repo / lock["files"][key]["path"]
    if sha256(path) != lock["files"][key]["sha256"]:
        raise PreflightError(f"Frozen {key} manifest hash mismatch")
    selection = json.loads(path.read_text(encoding="utf-8"))
    requirements = list(selection["requirements"])
    expected = 2 if scope == "smoke" else 50
    if len(requirements) != expected or len(set(requirements)) != expected:
        raise PreflightError(f"Frozen {scope} requirement coverage mismatch")
    return selection, requirements


def run_one(repo: Path, model: str, mode: str, scope: str) -> None:
    manifest_lock = verify_manifests(repo)
    benchmark = load_benchmark(repo, strict_counts=True)
    if benchmark.integrity_hash != manifest_lock.get("benchmark_integrity_hash"):
        raise PreflightError("Frozen R13 benchmark integrity hash mismatch")
    sample_path = repo / manifest_lock["files"]["sample"]["path"]
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    sample["sample_manifest_sha256"] = sha256(sample_path)
    _selection, requirements = selected_manifest(repo, manifest_lock, scope)
    cases = [case for case in benchmark.cases if case.requirement_id in set(requirements)]
    expected_cases = 9 if scope == "smoke" else 381
    if len(cases) != expected_cases or {case.requirement_id for case in cases} != set(requirements):
        raise PreflightError(f"Frozen {scope} RDF mapping mismatch: {len(cases)} cases")
    manifest_path, generation_run = build_manifest(repo, model, mode, scope, benchmark, sample, requirements)
    manifest_rows = load_generated_manifest(manifest_path, "FULL_REPAIR_V2", generation_run)
    generated = validate_generated_manifest(repo, benchmark, "FULL_REPAIR_V2", generation_run, manifest_rows, strict_counts=False)
    if set(generated) != set(requirements):
        raise PreflightError(f"Generated manifest selection mismatch for {scope}/{mode}/{model}")
    output_dir = output_directory(EXPERIMENT, scope, mode, model)
    run_id = f"RDF-SCALING50-{scope.upper()}-{mode}-{model.upper()}"
    prior_path = output_dir / "run_manifest.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.exists() else None
    integrity = run_integrity_check(repo)
    if prior and prior.get("status") == "COMPLETE":
        ledger = output_dir / "raw_case_results.jsonl"
    else:
        ledger = execute(
            repo=repo,
            benchmark=benchmark,
            cases=cases,
            generation_runs=[generation_run],
            configurations=["FULL_REPAIR_V2"],
            generated_by_run_config={generation_run: {"FULL_REPAIR_V2": generated}},
            generated_manifest_paths={generation_run: {"FULL_REPAIR_V2": manifest_path}},
            output_dir=output_dir,
            run_id=run_id,
            command_line=[sys.executable, str(Path(__file__).resolve()), "--scope", scope, "--mode", mode, "--model", model],
            integrity_result=integrity,
            resume=prior is not None,
        )
    materialize_required_outputs(output_dir, ledger, {
        "scope": scope,
        "evaluation_mode": mode,
        "model": model,
        "model_id": MODEL_IDS[model],
        "requirements": len(requirements),
        "sample_manifest_sha256": sample["sample_manifest_sha256"],
        "selection_manifest_sha256": manifest_lock["files"]["smoke" if scope == "smoke" else "sample"]["sha256"],
        "generated_manifest_path": str(manifest_path.relative_to(repo)),
        "generated_manifest_sha256": sha256(manifest_path),
        "benchmark_integrity_hash": benchmark.integrity_hash,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen 50-requirement dual-mode RDF behavioral evaluator")
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--scope", choices=("smoke", "final"), required=True)
    args = parser.parse_args()
    run_one(find_repo_root(), args.model, args.mode, args.scope)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
