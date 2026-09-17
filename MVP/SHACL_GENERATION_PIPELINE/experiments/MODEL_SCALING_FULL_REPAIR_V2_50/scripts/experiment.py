#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
PIPELINE = EXPERIMENT.parents[1]
SRC = PIPELINE / "src"
EVALUATION = PIPELINE / "evaluation"
for path in (SRC, EVALUATION):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_runner.core import find_repo_root, sha256
from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.orchestration.runner import PipelineRunner
from provider_clients import client_for_config


MODELS = {
    "sol": ("CONFIGS/sol.json", "gpt-5.6-sol-2026-07-09"),
    "gemini": ("CONFIGS/gemini.json", "gemini-3.5-flash"),
    "gpt_oss": ("CONFIGS/gpt_oss.json", "gpt-oss-120b"),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_manifests(repo: Path) -> dict[str, Any]:
    lock_path = EXPERIMENT / "MANIFESTS/manifest_lock.json"
    lock = load_json(lock_path)
    for record in lock["files"].values():
        path = repo / record["path"]
        if not path.is_file() or sha256(path) != record["sha256"]:
            raise RuntimeError(f"Frozen manifest hash mismatch: {path}")
    configuration_lock = load_json(EXPERIMENT / "MANIFESTS/configuration_lock.json")
    for record in configuration_lock["configs"].values():
        path = repo / record["path"]
        if sha256(path) != record["sha256"]:
            raise RuntimeError(f"Frozen configuration hash mismatch: {path}")
    reference_path = repo / configuration_lock["authoritative_reference_config"]
    if sha256(reference_path) != configuration_lock["authoritative_reference_config_sha256"]:
        raise RuntimeError("Authoritative FULL_REPAIR_V2 RUN_01 configuration changed")
    for relative, expected in configuration_lock["implementation_file_sha256"].items():
        if sha256(repo / relative) != expected:
            raise RuntimeError(f"Fixed pipeline/evaluator implementation changed: {relative}")
    prompt_root = repo / configuration_lock["prompt_directory"]
    for relative, expected in configuration_lock["prompt_file_sha256"].items():
        if sha256(prompt_root / relative) != expected:
            raise RuntimeError(f"Frozen prompt changed: {relative}")
    lock["configuration_lock_sha256"] = sha256(EXPERIMENT / "MANIFESTS/configuration_lock.json")
    return lock


def load_model(model_key: str, *, scope: str) -> tuple[PipelineConfig, Path, str]:
    config_rel, exact_model = MODELS[model_key]
    config_path = EXPERIMENT / config_rel
    config = PipelineConfig.load(config_path)
    configured_models = set(config.raw["models"].values())
    if configured_models != {exact_model}:
        raise RuntimeError(f"All live FULL_REPAIR_V2 roles must use {exact_model}: {configured_models}")
    if config.raw.get("architecture") != "FULL_REPAIR_V2":
        raise RuntimeError("Scaling config is not FULL_REPAIR_V2")
    generation = config.raw["generation"]
    if generation.get("maximum_semantic_attempts") != 4 or generation.get("maximum_syntax_repairs_per_semantic_attempt") != 3:
        raise RuntimeError("FULL_REPAIR_V2 attempt limits changed")
    if scope == "smoke":
        raw = copy.deepcopy(config.raw)
        raw["generation_run"] = str(raw["generation_run"]) + "_SMOKE"
        raw["paths"]["outputs"] = f"experiments/MODEL_SCALING_FULL_REPAIR_V2_50/OUTPUTS/SMOKE/{model_key}"
        config = PipelineConfig(raw=raw, config_path=config_path)
    return config, config_path, exact_model


def verified_client(config: PipelineConfig, **kwargs: Any):
    client = client_for_config(config, **kwargs)
    expected = str(config.raw["api"]["expected_endpoint_url"]).rstrip("/")
    if client.base_url.rstrip("/") != expected:
        raise RuntimeError(f"Endpoint mismatch for {config.raw['api']['endpoint_type']}: expected {expected}")
    return client


def connectivity(model_key: str) -> int:
    repo = find_repo_root()
    verify_manifests(repo)
    config, config_path, exact_model = load_model(model_key, scope="final")
    raw = copy.deepcopy(config.raw)
    raw["api"]["persistent_transient_retries"] = False
    raw["api"]["max_retry_cycles"] = 1
    raw["api"]["initial_backoff_seconds"] = 0
    raw["api"]["maximum_backoff_seconds"] = 0
    raw["api"]["auth_retry_seconds"] = 0
    raw["api"]["max_output_tokens"] = {role: 16 for role in raw["models"]}
    live_config = PipelineConfig(raw=raw, config_path=config_path)
    events: list[dict[str, Any]] = []
    client = verified_client(live_config, telemetry=lambda event, payload: events.append({"event": event, **payload}))
    started = now()
    result = client.call(
        "generator",
        "Connectivity check only. Return exactly OK.",
        "Return exactly OK. Do not generate SHACL or analyze a requirement.",
    )
    output = EXPERIMENT / f"OUTPUTS/CONNECTIVITY/{model_key}/connectivity.json"
    payload = {
        "started_utc": started,
        "finished_utc": now(),
        "requested_model": exact_model,
        "returned_model": result.model,
        "endpoint_type": client.endpoint_type,
        "endpoint_url": client.base_url,
        "response_id": result.response_id,
        "response_text": result.text,
        "usage": result.usage,
        "transport_attempts": result.transport_attempts,
        "elapsed_ms": result.elapsed_ms,
        "config_path": str(config_path.relative_to(repo)),
        "config_sha256": sha256(config_path),
        "telemetry": events,
        "api_key_retained": False,
    }
    atomic_json(output, payload)
    if result.model and result.model != exact_model:
        raise RuntimeError(f"Gateway returned model {result.model!r}; expected exact model {exact_model!r}")
    print(json.dumps({"status": "PASS", "model": exact_model, "output": str(output.relative_to(repo))}, indent=2))
    return 0


def generation(model_key: str, scope: str) -> int:
    repo = find_repo_root()
    lock = verify_manifests(repo)
    config, config_path, exact_model = load_model(model_key, scope=scope)
    manifest_name = "smoke" if scope == "smoke" else "sample"
    sample_path = repo / lock["files"][manifest_name]["path"]
    sample = load_json(sample_path)
    requirements = list(sample["requirements"])
    expected = 2 if scope == "smoke" else 50
    if len(requirements) != expected or len(set(requirements)) != expected:
        raise RuntimeError(f"Invalid {scope} queue coverage")
    output_root = config.path("outputs")
    control = output_root / "scaling_control"
    ledger_path = control / "requirement_results.jsonl"
    run_manifest_path = control / "run_manifest.json"
    effective_config_path = control / "effective_config.json"
    config_text = json.dumps(config.raw, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    effective_hash = hashlib.sha256(config_text.encode()).hexdigest()
    if effective_config_path.exists() and effective_config_path.read_text(encoding="utf-8") != config_text:
        raise RuntimeError("Effective configuration changed; refusing to resume")
    control.mkdir(parents=True, exist_ok=True)
    if not effective_config_path.exists():
        effective_config_path.write_text(config_text, encoding="utf-8")
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()] if ledger_path.exists() else []
    completed = {row["requirement_id"] for row in rows}
    if len(completed) != len(rows) or not completed.issubset(requirements):
        raise RuntimeError("Resume ledger has duplicate or out-of-scope requirements")
    session_id = f"MODEL-SCALING-{model_key.upper()}-{scope.upper()}-{lock['files'][manifest_name]['sha256'][:12]}"
    state = load_json(run_manifest_path) if run_manifest_path.exists() else {
        "experiment": "FULL_REPAIR_V2_MODEL_SCALING_50",
        "scope": scope,
        "session_id": session_id,
        "status": "IN_PROGRESS",
        "model_id": exact_model,
        "endpoint_type": config.raw["api"]["endpoint_type"],
        "endpoint_env": config.raw["api"]["endpoint_env"],
        "api_key_env": config.raw["api"]["api_key_env"],
        "sample_manifest_path": str(sample_path.relative_to(repo)),
        "sample_manifest_sha256": sha256(sample_path),
        "source_config_path": str(config_path.relative_to(repo)),
        "source_config_sha256": sha256(config_path),
        "configuration_lock_sha256": lock["configuration_lock_sha256"],
        "effective_config_sha256": effective_hash,
        "expected_requirements": expected,
        "started_utc": now(),
    }
    invariants = {
        "scope": scope,
        "session_id": session_id,
        "model_id": exact_model,
        "sample_manifest_sha256": sha256(sample_path),
        "effective_config_sha256": effective_hash,
        "expected_requirements": expected,
    }
    disagreements = {key: (state.get(key), value) for key, value in invariants.items() if state.get(key) != value}
    if disagreements:
        raise RuntimeError(f"Resume invariants changed: {disagreements}")
    state["completed_requirements"] = len(rows)
    atomic_json(run_manifest_path, state)
    client = verified_client(config)
    runner = PipelineRunner(config, live_progress=True)
    for requirement_id in requirements:
        if requirement_id in completed:
            print(f"[RESUME] skip recorded requirement={requirement_id}", file=sys.stderr, flush=True)
            continue
        try:
            result = runner.run_requirement(requirement_id, client, session_id=session_id)
            row = {
                "requirement_id": requirement_id,
                "recorded_utc": now(),
                "result_kind": "PIPELINE_RESULT",
                **result.to_dict(),
            }
        except KeyboardInterrupt:
            state["status"] = "INTERRUPTED"
            state["completed_requirements"] = len(rows)
            atomic_json(run_manifest_path, state)
            raise
        except Exception as exc:
            row = {
                "requirement_id": requirement_id,
                "recorded_utc": now(),
                "result_kind": "RUNNER_EXCEPTION",
                "status": "BATCH_ITEM_ERROR",
                "accepted": False,
                "attempts": None,
                "run_id": None,
                "run_directory": None,
                "final_shape": None,
                "final_feedback": f"{type(exc).__name__}: {exc}",
            }
        append_jsonl(ledger_path, row)
        rows.append(row)
        completed.add(requirement_id)
        state["completed_requirements"] = len(rows)
        state["status_counts"] = {
            status: sum(item.get("status") == status for item in rows)
            for status in sorted({str(item.get("status")) for item in rows})
        }
        atomic_json(run_manifest_path, state)
    state["status"] = "COMPLETE"
    state["finished_utc"] = now()
    state["completed_requirements"] = len(rows)
    state["smoke_excluded_from_final_results"] = scope == "smoke"
    atomic_json(run_manifest_path, state)
    print(json.dumps({"status": "COMPLETE", "model": exact_model, "scope": scope, "requirements": len(rows), "output": str(output_root.relative_to(repo))}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlled FULL_REPAIR_V2 model-scaling runner")
    sub = parser.add_subparsers(dest="command", required=True)
    connect = sub.add_parser("connectivity")
    connect.add_argument("--model", choices=MODELS, required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--model", choices=MODELS, required=True)
    generate.add_argument("--scope", choices=("smoke", "final"), required=True)
    args = parser.parse_args()
    return connectivity(args.model) if args.command == "connectivity" else generation(args.model, args.scope)


if __name__ == "__main__":
    raise SystemExit(main())
