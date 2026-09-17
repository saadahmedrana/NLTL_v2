#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
PIPELINE = EXPERIMENT.parents[1]
EVALUATION = PIPELINE / "evaluation"
if str(EVALUATION) not in sys.path:
    sys.path.insert(0, str(EVALUATION))

from experiment_runner.core import find_repo_root, sha256


MODEL = "gpt-5.6-luna-2026-07-09"
SOURCE_CONFIG = "MVP/SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/CONFIGS/pipeline.full-repair-v2-run01.json"
SOURCE_RUN = "MVP/SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/RUN_01"
SOURCE_BEHAVIOR = "MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results/BEHAVIORAL-R13-FULL-REPAIR-V2-RUN01-20260915T144116505813Z/raw_case_results.jsonl"


def csv_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    if path.exists() and path.read_text(encoding="utf-8") != payload:
        raise RuntimeError(f"Refusing to replace a different frozen Luna extraction: {path}")
    if not path.exists():
        path.write_text(payload, encoding="utf-8")


def summarize_run(repo: Path, run_dir: Path, run: dict[str, str]) -> dict[str, Any]:
    validation = csv_rows(run_dir / "tables/validation.csv")
    iterations = csv_rows(run_dir / "tables/iterations.csv")
    calls = [row for row in csv_rows(run_dir / "tables/api_calls.csv") if row.get("STATUS") == "COMPLETED"]
    artifacts = csv_rows(run_dir / "tables/artifacts.csv")
    first = next((row for row in validation if row.get("ITERATION") == "1"), {})
    accepted = run["FINAL_STATUS"] == "GENERATION_ACCEPTED" and run["ACCEPTED"] == "True"
    final_rows = [row for row in artifacts if row.get("ARTIFACT_TYPE") == "final_accepted_shape"]
    if accepted != (len(final_rows) == 1):
        raise RuntimeError(f"Luna final artifact mismatch: {run['REQUIREMENT_ID']}")
    shape_path = run_dir / final_rows[0]["ARTIFACT_PATH"] if final_rows else None
    if shape_path and sha256(shape_path) != final_rows[0]["SHA256"]:
        raise RuntimeError(f"Luna artifact hash mismatch: {shape_path}")
    models = {row["MODEL"] for row in calls if row.get("MODEL")}
    if models and models != {MODEL}:
        raise RuntimeError(f"Luna API metadata model mismatch: {run['REQUIREMENT_ID']}: {models}")
    return {
        "model_id": MODEL,
        "endpoint_type": "responses",
        "requirement_id": run["REQUIREMENT_ID"],
        "run_id": run["RUN_ID"],
        "run_directory": str(run_dir.relative_to(repo)),
        "pipeline_status": run["FINAL_STATUS"],
        "accepted": accepted,
        "attempts": int(run.get("ATTEMPTS") or 0),
        "first_attempt_turtle_parse": first.get("TURTLE_VALID") == "True",
        "first_attempt_operational_shacl_valid": first.get("VALID") == "True",
        "repair_success": accepted and int(run.get("ATTEMPTS") or 0) > 1,
        "final_shape_path": str(shape_path.relative_to(repo)) if shape_path else None,
        "final_shape_sha256": sha256(shape_path) if shape_path else None,
        "api_call_count": len(calls),
        "input_tokens": sum(int(row["INPUT_TOKENS"]) for row in calls if row.get("INPUT_TOKENS")),
        "output_tokens": sum(int(row["OUTPUT_TOKENS"]) for row in calls if row.get("OUTPUT_TOKENS")),
        "total_tokens": sum(int(row["TOTAL_TOKENS"]) for row in calls if row.get("TOTAL_TOKENS")),
        "api_latency_ms": sum(float(row["ELAPSED_MS"]) for row in calls if row.get("ELAPSED_MS")),
        "run_metadata_path": str((run_dir / "tables/runs.csv").relative_to(repo)),
        "artifact_metadata_path": str((run_dir / "tables/artifacts.csv").relative_to(repo)),
        "context_path": str((run_dir / "artifacts/context_pack_initial.json").relative_to(repo)),
        "iteration_rows": iterations,
    }


def main() -> int:
    repo = find_repo_root()
    lock = json.loads((EXPERIMENT / "MANIFESTS/manifest_lock.json").read_text(encoding="utf-8"))
    sample_path = repo / lock["files"]["sample"]["path"]
    if sha256(sample_path) != lock["files"]["sample"]["sha256"]:
        raise RuntimeError("Frozen sample hash mismatch")
    selected = set(json.loads(sample_path.read_text(encoding="utf-8"))["requirements"])
    config_path = repo / SOURCE_CONFIG
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if set(config["models"].values()) != {MODEL} or config.get("architecture") != "FULL_REPAIR_V2":
        raise RuntimeError("Luna FULL_REPAIR_V2 source config identity mismatch")
    by_requirement: dict[str, tuple[Path, dict[str, str]]] = {}
    source_root = repo / SOURCE_RUN
    for metadata_path in source_root.glob("runs/*/tables/runs.csv"):
        rows = csv_rows(metadata_path)
        if len(rows) != 1:
            raise RuntimeError(f"Unexpected run metadata rows: {metadata_path}")
        row = rows[0]
        if row["REQUIREMENT_ID"] in by_requirement:
            raise RuntimeError(f"Duplicate Luna requirement: {row['REQUIREMENT_ID']}")
        by_requirement[row["REQUIREMENT_ID"]] = (metadata_path.parent.parent, row)
    if len(by_requirement) != 268 or not selected.issubset(by_requirement):
        raise RuntimeError("Luna RUN_01 coverage mismatch")
    generation_rows = [summarize_run(repo, *by_requirement[requirement_id]) for requirement_id in sorted(selected)]

    behavior_path = repo / SOURCE_BEHAVIOR
    behavior_rows = [
        row for row in jsonl(behavior_path)
        if row.get("generation_run") == "RUN_01"
        and row.get("configuration") == "FULL_REPAIR_V2"
        and row["requirement_id"] in selected
    ]
    if {row["requirement_id"] for row in behavior_rows} != selected:
        raise RuntimeError("Luna behavioral subset coverage mismatch")
    by_case = [row["case_id"] for row in behavior_rows]
    if len(by_case) != len(set(by_case)):
        raise RuntimeError("Duplicate Luna behavioral case")

    output = EXPERIMENT / "REFERENCE/LUNA"
    generation_out = output / "generation_subset.jsonl"
    behavior_out = output / "behavioral_subset.jsonl"
    write_jsonl(generation_out, generation_rows)
    write_jsonl(behavior_out, sorted(behavior_rows, key=lambda row: row["case_id"]))
    manifest = {
        "status": "COMPLETE",
        "model_id": MODEL,
        "requirements": len(generation_rows),
        "behavioral_cases": len(behavior_rows),
        "sample_manifest_path": str(sample_path.relative_to(repo)),
        "sample_manifest_sha256": sha256(sample_path),
        "source_config_path": SOURCE_CONFIG,
        "source_config_sha256": sha256(config_path),
        "source_run_root": SOURCE_RUN,
        "source_behavioral_ledger": SOURCE_BEHAVIOR,
        "source_behavioral_ledger_sha256": sha256(behavior_path),
        "generation_subset_sha256": sha256(generation_out),
        "behavioral_subset_sha256": sha256(behavior_out),
        "no_generation_or_evaluation_executed": True,
    }
    manifest_path = output / "extraction_manifest.json"
    manifest_payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != manifest_payload:
        raise RuntimeError(f"Refusing to replace a different frozen Luna extraction manifest: {manifest_path}")
    if not manifest_path.exists():
        manifest_path.write_text(manifest_payload, encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
