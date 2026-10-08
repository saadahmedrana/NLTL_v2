#!/usr/bin/env python3
"""Freeze and verify the common FULL_REPAIR_V2 configuration surface."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

EXPERIMENT = Path(__file__).resolve().parents[1]
PIPELINE = EXPERIMENT.parents[1]
EVALUATION = PIPELINE / "evaluation"
sys.path.insert(0, str(PIPELINE / "src"))
sys.path.insert(0, str(EVALUATION))

from experiment_runner.core import find_repo_root, sha256  # noqa: E402
from nltl_pipeline.config import PipelineConfig  # noqa: E402

CONFIGS = ("sol.json", "gemini.json", "gpt_oss.json")
REFERENCE = PIPELINE / "experiments/FULL_REPAIR_V2/CONFIGS/pipeline.full-repair-v2-run01.json"


def directory_hash(path: Path) -> tuple[str, dict[str, str]]:
    files = {str(p.relative_to(path)): sha256(p) for p in sorted(path.rglob("*")) if p.is_file()}
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), files


def sanitized_common(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "architecture": raw["architecture"],
        "paths": {key: value for key, value in raw["paths"].items() if key != "outputs"},
        "generation": raw["generation"],
        "reporting": raw["reporting"],
        "api_pipeline_controls": {
            key: raw["api"][key]
            for key in (
                "requests_per_minute", "minimum_interval_seconds", "initial_backoff_seconds",
                "maximum_backoff_seconds", "auth_retry_seconds", "persistent_transient_retries",
                "contract_response_retries", "validator_response_retries", "max_output_tokens",
            )
        },
    }


def build() -> dict[str, Any]:
    repo = find_repo_root()
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    reference_common = sanitized_common(reference)
    configs: dict[str, Any] = {}
    for name in CONFIGS:
        path = EXPERIMENT / "CONFIGS" / name
        raw = json.loads(path.read_text(encoding="utf-8"))
        if sanitized_common(raw) != reference_common:
            raise RuntimeError(f"Fixed FULL_REPAIR_V2 configuration differs from authoritative RUN_01: {name}")
        if len(set(raw["models"].values())) != 1:
            raise RuntimeError(f"Generation and semantic validation do not use the same model: {name}")
        configs[name.removesuffix(".json")] = {
            "path": str(path.relative_to(repo)),
            "sha256": sha256(path),
            "model_id": next(iter(raw["models"].values())),
            "endpoint_type": raw["api"]["endpoint_type"],
            "endpoint_env": raw["api"]["endpoint_env"],
        }
    loaded = PipelineConfig.load(EXPERIMENT / "CONFIGS" / "sol.json")
    locked = loaded.verify_locked_inputs()
    prompt_hash, prompt_files = directory_hash(loaded.path("prompt_directory"))
    evaluator_files = {
        str(path.relative_to(repo)): sha256(path)
        for path in (
            PIPELINE / "evaluation/experiment_runner/execution.py",
            PIPELINE / "evaluation/experiment_runner/analysis.py",
            PIPELINE / "src/nltl_pipeline/validation/shacl.py",
            PIPELINE / "src/nltl_pipeline/validation/contracts.py",
            PIPELINE / "src/nltl_pipeline/models.py",
            PIPELINE / "src/nltl_pipeline/orchestration/runner.py",
            PIPELINE / "src/nltl_pipeline/reporting/tracker.py",
            EXPERIMENT / "scripts/provider_clients.py",
            EXPERIMENT / "scripts/experiment.py",
            EXPERIMENT / "scripts/run_rdf_evaluation.py",
            EXPERIMENT / "scripts/rdf_evaluation_common.py",
            EXPERIMENT / "scripts/summarize_rdf_evaluations.py",
            EXPERIMENT / "scripts/run_all_rdf_evaluations.sh",
            EXPERIMENT / "scripts/summarize.py",
            EXPERIMENT / "scripts/build_manual_audit_packets.py",
        )
    }
    return {
        "lock_version": "1.0.0",
        "authoritative_reference_config": str(REFERENCE.relative_to(repo)),
        "authoritative_reference_config_sha256": sha256(REFERENCE),
        "common_full_repair_v2_configuration_sha256": hashlib.sha256(
            json.dumps(reference_common, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "configs": configs,
        "locked_vocabulary": locked,
        "prompt_directory": str(loaded.path("prompt_directory").relative_to(repo)),
        "prompt_directory_sha256": prompt_hash,
        "prompt_file_sha256": prompt_files,
        "implementation_file_sha256": evaluator_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = build()
    path = EXPERIMENT / "MANIFESTS/configuration_lock.json"
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.write:
        path.write_text(encoded, encoding="utf-8")
    elif not path.exists() or path.read_text(encoding="utf-8") != encoded:
        raise RuntimeError("Frozen configuration lock mismatch")
    print(json.dumps({"configuration_lock": str(path), **value}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
