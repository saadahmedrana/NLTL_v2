#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
PIPELINE = EXPERIMENT.parents[1]
EVALUATION = PIPELINE / "evaluation"
if str(EVALUATION) not in sys.path:
    sys.path.insert(0, str(EVALUATION))

from experiment_runner.analysis import analyze
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


MODELS = {
    "sol": ("gpt-5.6-sol-2026-07-09", "SCALING50_SOL"),
    "gemini": ("gemini-3.5-flash", "SCALING50_GEMINI"),
    "gpt_oss": ("gpt-oss-120b", "SCALING50_GPT_OSS"),
}
SOURCE_IDS = {"IACS_UR_I2": "SRC-IACS-I2-R4", "TRAFICOM": "SRC-TRAFICOM-2021", "IMO_POLAR_CODE": "SRC-IMO-MSC385-94", "IMO_AMEND_2026": "SRC-IMO26-SUPPLEMENT"}


def csv_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def build_manifest(repo: Path, model_key: str, benchmark, sample: dict[str, Any]) -> Path:
    model_id, generation_run = MODELS[model_key]
    output_root = EXPERIMENT / f"OUTPUTS/FINAL/{model_key}"
    control = output_root / "scaling_control"
    run_manifest = json.loads((control / "run_manifest.json").read_text(encoding="utf-8"))
    if run_manifest.get("status") != "COMPLETE" or run_manifest.get("completed_requirements") != 50:
        raise PreflightError(f"Generation run is not complete for {model_key}")
    ledger = [json.loads(line) for line in (control / "requirement_results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    by_requirement = {row["requirement_id"]: row for row in ledger}
    if set(by_requirement) != set(sample["requirements"]):
        raise PreflightError(f"Generation result coverage mismatch for {model_key}")
    benchmark_sources = {case.requirement_id: case.source_id for case in benchmark.cases}
    rows: list[dict[str, Any]] = []
    for requirement_id in sample["requirements"]:
        result = by_requirement[requirement_id]
        run_dir_value = result.get("run_directory")
        source_id = benchmark_sources[requirement_id]
        base = {
            "manifest_id": f"{generation_run}-FULL_REPAIR_V2-{requirement_id}",
            "generation_run": generation_run,
            "configuration": "FULL_REPAIR_V2",
            "requirement_id": requirement_id,
            "source_id": source_id,
            "model_identifier": model_id,
            "generation_config_identifier": run_manifest["effective_config_sha256"],
            "r13_contract_identifier": "VOCAB-LOCK-2026-08-22-R13",
            "queue_identifier": run_manifest["sample_manifest_sha256"],
            "run_id": result.get("run_id"),
            "pipeline_final_status": result.get("status"),
        }
        if not run_dir_value:
            rows.append({**base, "source_identity_locator": None, "source_clause": None, "generated_shacl_path": None, "generated_shacl_sha256": None, "generation_status": "GENERATION_ERROR", "failure_stage": result.get("status"), "failure_detail": result.get("final_feedback")})
            continue
        run_dir = Path(run_dir_value)
        if not run_dir.is_absolute():
            run_dir = repo / run_dir
        try:
            run_dir.resolve().relative_to(output_root.resolve())
        except ValueError as exc:
            raise PreflightError(f"Run artifact outside selected model root: {run_dir}") from exc
        metadata_rows = csv_rows(run_dir / "tables/runs.csv")
        if len(metadata_rows) != 1:
            raise PreflightError(f"Invalid run metadata: {run_dir}")
        metadata = metadata_rows[0]
        if metadata["REQUIREMENT_ID"] != requirement_id or metadata["RUN_ID"] != result.get("run_id"):
            raise PreflightError(f"Run identity mismatch: {requirement_id}")
        context_path = run_dir / "artifacts/context_pack_initial.json"
        context = json.loads(context_path.read_text(encoding="utf-8"))["requirement"]
        locator = context.get("sourceSheet")
        if context.get("id") != requirement_id or SOURCE_IDS.get(str(locator)) != source_id:
            raise PreflightError(f"Context identity mismatch: {requirement_id}")
        artifacts_path = run_dir / "tables/artifacts.csv"
        artifacts = csv_rows(artifacts_path)
        final_rows = [row for row in artifacts if row.get("ARTIFACT_TYPE") == "final_accepted_shape"]
        accepted = metadata["FINAL_STATUS"] == "GENERATION_ACCEPTED" and metadata["ACCEPTED"] == "True"
        if accepted != (len(final_rows) == 1):
            raise PreflightError(f"Final artifact/status mismatch: {requirement_id}")
        shape_path = run_dir / final_rows[0]["ARTIFACT_PATH"] if final_rows else None
        if shape_path and sha256(shape_path) != final_rows[0]["SHA256"]:
            raise PreflightError(f"Final artifact hash mismatch: {shape_path}")
        rows.append({
            **base,
            "source_identity_locator": locator,
            "source_clause": context.get("clause"),
            "generated_shacl_path": str(shape_path.relative_to(repo)) if shape_path else None,
            "generated_shacl_sha256": sha256(shape_path) if shape_path else None,
            "recorded_generated_shacl_sha256": final_rows[0]["SHA256"] if final_rows else None,
            "generation_status": "GENERATED" if accepted else "GENERATION_ERROR",
            "failure_stage": None if accepted else metadata["FINAL_STATUS"],
            "failure_detail": None if accepted else metadata.get("FINAL_FEEDBACK"),
            "generation_timestamp": metadata.get("FINISHED_UTC") or metadata.get("STARTED_UTC"),
            "run_metadata_path": str((run_dir / "tables/runs.csv").relative_to(repo)),
            "artifact_metadata_path": str(artifacts_path.relative_to(repo)),
            "context_pack_path": str(context_path.relative_to(repo)),
        })
    path = EXPERIMENT / f"RDF/{model_key}/generated_rules.jsonl"
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    if path.exists() and path.read_text(encoding="utf-8") != payload:
        raise PreflightError(f"Existing generated manifest differs: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(payload, encoding="utf-8")
    return path


def run_model(repo: Path, model_key: str, benchmark, sample: dict[str, Any], integrity: dict[str, Any]) -> None:
    _model_id, generation_run = MODELS[model_key]
    manifest_path = build_manifest(repo, model_key, benchmark, sample)
    rows = load_generated_manifest(manifest_path, "FULL_REPAIR_V2", generation_run)
    generated = validate_generated_manifest(repo, benchmark, "FULL_REPAIR_V2", generation_run, rows, strict_counts=False)
    if set(generated) != set(sample["requirements"]):
        raise PreflightError(f"Generated manifest sample mismatch for {model_key}")
    cases = [case for case in benchmark.cases if case.requirement_id in generated]
    output_dir = EXPERIMENT / f"RDF/{model_key}/RESULTS/BEHAVIORAL-R13-SCALING50-{model_key.upper()}"
    prior = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8")) if (output_dir / "run_manifest.json").exists() else None
    if prior and prior.get("status") == "COMPLETE":
        print(f"[RESUME] RDF already complete for {model_key}")
        return
    ledger = execute(
        repo=repo,
        benchmark=benchmark,
        cases=cases,
        generation_runs=[generation_run],
        configurations=["FULL_REPAIR_V2"],
        generated_by_run_config={generation_run: {"FULL_REPAIR_V2": generated}},
        generated_manifest_paths={generation_run: {"FULL_REPAIR_V2": manifest_path}},
        output_dir=output_dir,
        run_id=f"BEHAVIORAL-R13-SCALING50-{model_key.upper()}",
        command_line=[sys.executable, str(Path(__file__).resolve()), "--model", model_key],
        integrity_result=integrity,
        resume=prior is not None,
    )
    analyze(ledger)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=(*MODELS, "all"), required=True)
    args = parser.parse_args()
    repo = find_repo_root()
    integrity = run_integrity_check(repo)
    benchmark = load_benchmark(repo, strict_counts=True)
    lock = json.loads((EXPERIMENT / "MANIFESTS/manifest_lock.json").read_text(encoding="utf-8"))
    sample_path = repo / lock["files"]["sample"]["path"]
    if sha256(sample_path) != lock["files"]["sample"]["sha256"]:
        raise PreflightError("Frozen sample hash mismatch")
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    for model_key in MODELS if args.model == "all" else (args.model,):
        run_model(repo, model_key, benchmark, sample, integrity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
