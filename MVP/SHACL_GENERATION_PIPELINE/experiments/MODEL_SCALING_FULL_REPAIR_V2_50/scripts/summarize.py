#!/usr/bin/env python3
"""Combine the frozen Luna reference and three scaling runs into one summary.

This script is offline. It reads already-produced generation and RDF ledgers and
does not call a provider or execute pySHACL.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EXPERIMENT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = EXPERIMENT.parents[1]
REPO_ROOT = PIPELINE_ROOT.parent.parent
sys.path.insert(0, str(PIPELINE_ROOT / "src"))


MODEL_ORDER = ("luna", "sol", "gemini", "gpt_oss")
MODEL_IDS = {
    "luna": "gpt-5.6-luna-2026-07-09",
    "sol": "gpt-5.6-sol-2026-07-09",
    "gemini": "gemini-3.5-flash",
    "gpt_oss": "gpt-oss-120b",
}
MODE_WEIGHTS = {
    "DIRECT_STATIC": 190 / 268,
    "DIRECT_CALCULATION": 41 / 268,
    "COMPLEX_READINESS": 37 / 268,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def safe_rate(num: int | float, den: int | float) -> float | None:
    return (num / den) if den else None


def mean_or_none(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def weighted_mode_metric(by_mode: dict[str, dict[str, Any]], key: str) -> float | None:
    values: list[tuple[float, float]] = []
    for mode, weight in MODE_WEIGHTS.items():
        value = by_mode.get(mode, {}).get(key)
        if value is None:
            return None
        values.append((weight, float(value)))
    return sum(weight * value for weight, value in values)


def latest_rdf_ledger(model_key: str) -> Path:
    roots = sorted((EXPERIMENT / "RDF" / model_key / "RESULTS").glob("*/raw_case_results.jsonl"))
    if len(roots) != 1:
        raise RuntimeError(f"Expected exactly one RDF ledger for {model_key}, found {len(roots)}: {roots}")
    return roots[0]


def new_generation_rows(model_key: str, sample_ids: set[str]) -> list[dict[str, Any]]:
    control = EXPERIMENT / "OUTPUTS" / "FINAL" / model_key / "scaling_control" / "requirement_results.jsonl"
    rows = load_jsonl(control)
    by_req: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = str(row.get("requirement_id", ""))
        if rid in by_req:
            raise RuntimeError(f"Duplicate final control-ledger row for {model_key}/{rid}")
        by_req[rid] = row
    if set(by_req) != sample_ids:
        raise RuntimeError(
            f"Final generation ledger for {model_key} is incomplete: "
            f"missing={sorted(sample_ids-set(by_req))}, extra={sorted(set(by_req)-sample_ids)}"
        )

    result: list[dict[str, Any]] = []
    for rid in sorted(sample_ids):
        control_row = by_req[rid]
        base: dict[str, Any] = {
            "requirement_id": rid,
            "status": control_row.get("status"),
            "accepted": False,
            "attempts": None,
            "artifact_available": False,
            "first_attempt_turtle_parse": False,
            "first_attempt_operational_validity": False,
            "input_tokens": 0,
            "output_tokens": 0,
            "api_calls": 0,
            "latency_ms": 0.0,
        }
        run_dir_raw = control_row.get("run_directory")
        if not run_dir_raw:
            base["error"] = control_row.get("error")
            result.append(base)
            continue
        run_dir = Path(str(run_dir_raw)).resolve()
        if EXPERIMENT not in run_dir.parents:
            raise RuntimeError(f"Run directory escapes experiment tree: {run_dir}")
        metadata_rows = list(csv.DictReader((run_dir / "tables" / "runs.csv").open(encoding="utf-8", newline="")))
        if len(metadata_rows) != 1:
            raise RuntimeError(f"Expected one run row for {model_key}/{rid}")
        metadata_row = metadata_rows[0]
        iterations = list(csv.DictReader((run_dir / "tables" / "iterations.csv").open(encoding="utf-8", newline="")))
        validations = list(csv.DictReader((run_dir / "tables" / "validation.csv").open(encoding="utf-8", newline="")))
        calls = list(csv.DictReader((run_dir / "tables" / "api_calls.csv").open(encoding="utf-8", newline="")))
        first_validations = [r for r in validations if str(r.get("ITERATION")) == "1"]
        first_validation = first_validations[0] if first_validations else None
        completed_calls = [r for r in calls if r.get("status") == "completed"]
        completed_calls = [r for r in calls if r.get("STATUS") == "COMPLETED"]
        artifact_raw = control_row.get("final_shape")
        artifact = Path(str(artifact_raw)) if artifact_raw else None
        accepted = bool(control_row.get("accepted"))
        if accepted and not (artifact and artifact.exists()):
            raise RuntimeError(f"Accepted artifact is missing for {model_key}/{rid}: {artifact}")
        base.update(
            {
                "accepted": accepted,
                "attempts": int(control_row.get("attempts") or len(iterations)),
                "artifact_available": bool(artifact and artifact.exists()),
                "artifact_sha256": sha256_file(artifact) if artifact and artifact.exists() else None,
                "first_attempt_turtle_parse": bool(first_validation and first_validation.get("TURTLE_VALID") == "True"),
                "first_attempt_operational_validity": bool(first_validation and first_validation.get("VALID") == "True"),
                "input_tokens": sum(int(r.get("INPUT_TOKENS") or 0) for r in completed_calls),
                "output_tokens": sum(int(r.get("OUTPUT_TOKENS") or 0) for r in completed_calls),
                "api_calls": len(completed_calls),
                "latency_ms": sum(float(r.get("ELAPSED_MS") or 0.0) for r in completed_calls),
                "run_dir": str(run_dir),
                "final_shape_path": str(artifact) if artifact else None,
            }
        )
        result.append(base)
    return result


def generation_rows(model_key: str, sample_ids: set[str]) -> list[dict[str, Any]]:
    if model_key == "luna":
        rows = load_jsonl(EXPERIMENT / "REFERENCE" / "LUNA" / "generation_subset.jsonl")
        if {str(r["requirement_id"]) for r in rows} != sample_ids:
            raise RuntimeError("Luna generation subset does not match frozen sample")
        for row in rows:
            row["artifact_available"] = bool(row.get("final_shape_path"))
            row["first_attempt_operational_validity"] = bool(row.get("first_attempt_operational_shacl_valid"))
            row["api_calls"] = int(row.get("api_call_count") or 0)
            row["latency_ms"] = float(row.get("api_latency_ms") or 0.0)
            row["run_dir"] = str(REPO_ROOT / str(row["run_directory"]))
            row["artifact_sha256"] = row.get("final_shape_sha256")
        return rows
    return new_generation_rows(model_key, sample_ids)


def behavior_rows(model_key: str) -> list[dict[str, Any]]:
    if model_key == "luna":
        return load_jsonl(EXPERIMENT / "REFERENCE" / "LUNA" / "behavioral_subset.jsonl")
    return load_jsonl(latest_rdf_ledger(model_key))


def generation_metrics(rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]) -> dict[str, Any]:
    def block(items: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(items)
        attempts = [int(r["attempts"]) for r in items if r.get("attempts") is not None]
        repair_attempted = [r for r in items if int(r.get("attempts") or 0) > 1]
        repair_success = [r for r in repair_attempted if r.get("accepted")]
        return {
            "requirements": total,
            "first_attempt_turtle_parse_count": sum(bool(r.get("first_attempt_turtle_parse")) for r in items),
            "first_attempt_turtle_parse_rate": safe_rate(sum(bool(r.get("first_attempt_turtle_parse")) for r in items), total),
            "first_attempt_operational_validity_count": sum(bool(r.get("first_attempt_operational_validity")) for r in items),
            "first_attempt_operational_validity_rate": safe_rate(
                sum(bool(r.get("first_attempt_operational_validity")) for r in items), total
            ),
            "final_pipeline_acceptance_count": sum(bool(r.get("accepted")) for r in items),
            "final_pipeline_acceptance_rate": safe_rate(sum(bool(r.get("accepted")) for r in items), total),
            "retained_artifact_availability_count": sum(bool(r.get("artifact_available")) for r in items),
            "retained_artifact_availability_rate": safe_rate(sum(bool(r.get("artifact_available")) for r in items), total),
            "attempts_total": sum(attempts),
            "attempts_mean": mean_or_none([float(v) for v in attempts]),
            "repair_attempted": len(repair_attempted),
            "repair_success": len(repair_success),
            "repair_success_rate": safe_rate(len(repair_success), len(repair_attempted)),
            "input_tokens": sum(int(r.get("input_tokens") or 0) for r in items),
            "output_tokens": sum(int(r.get("output_tokens") or 0) for r in items),
            "api_calls": sum(int(r.get("api_calls") or 0) for r in items),
            "latency_ms": sum(float(r.get("latency_ms") or 0.0) for r in items),
        }

    result = block(rows)
    by_mode: dict[str, dict[str, Any]] = {}
    for mode in MODE_WEIGHTS:
        by_mode[mode] = block([r for r in rows if metadata[str(r["requirement_id"])]["verification_mode"] == mode])
    result["by_verification_mode"] = by_mode
    result["weighted_benchmark_distribution"] = {
        "first_attempt_turtle_parse_rate": weighted_mode_metric(by_mode, "first_attempt_turtle_parse_rate"),
        "first_attempt_operational_validity_rate": weighted_mode_metric(by_mode, "first_attempt_operational_validity_rate"),
        "final_pipeline_acceptance_rate": weighted_mode_metric(by_mode, "final_pipeline_acceptance_rate"),
        "retained_artifact_availability_rate": weighted_mode_metric(by_mode, "retained_artifact_availability_rate"),
    }
    return result


def behavior_metrics(rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]) -> dict[str, Any]:
    def block(items: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(items)
        correct = sum(r.get("behavioral_match") is True for r in items)
        executable = sum(r.get("execution_status") == "EXECUTED" for r in items)
        expected_fail = sum(r.get("expected_outcome") == "FAIL" for r in items)
        expected_pass = sum(r.get("expected_outcome") == "PASS" for r in items)
        false_accept = sum(r.get("outcome_class") == "FALSE_ACCEPT" for r in items)
        false_reject = sum(r.get("outcome_class") == "FALSE_REJECT" for r in items)
        no_verdict = sum(r.get("execution_status") != "EXECUTED" for r in items)
        req_cases: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in items:
            req_cases[str(row["requirement_id"])].append(row)
        req_acc = [safe_rate(sum(r.get("behavioral_match") is True for r in rs), len(rs)) for rs in req_cases.values()]
        req_acc_values = [float(v) for v in req_acc if v is not None]
        return {
            "sampled_cases": total,
            "correct_rdf_cases": correct,
            "end_to_end_behavioral_accuracy": safe_rate(correct, total),
            "executable_verdicts": executable,
            "conditional_accuracy_executable": safe_rate(correct, executable),
            "false_accept_count": false_accept,
            "expected_fail_denominator": expected_fail,
            "false_accept_rate": safe_rate(false_accept, expected_fail),
            "false_reject_count": false_reject,
            "expected_pass_denominator": expected_pass,
            "false_reject_rate": safe_rate(false_reject, expected_pass),
            "cases_without_verdict": no_verdict,
            "equal_weight_requirement_accuracy": mean_or_none(req_acc_values),
            "requirements_with_every_case_correct": sum(all(r.get("behavioral_match") is True for r in rs) for rs in req_cases.values()),
            "requirements": len(req_cases),
        }

    result = block(rows)
    by_mode: dict[str, dict[str, Any]] = {}
    for mode in MODE_WEIGHTS:
        by_mode[mode] = block([r for r in rows if metadata[str(r["requirement_id"])]["verification_mode"] == mode])
    result["by_verification_mode"] = by_mode
    result["weighted_benchmark_distribution"] = {
        "end_to_end_behavioral_accuracy": weighted_mode_metric(by_mode, "end_to_end_behavioral_accuracy"),
        "conditional_accuracy_executable": weighted_mode_metric(by_mode, "conditional_accuracy_executable"),
        "false_accept_rate": weighted_mode_metric(by_mode, "false_accept_rate"),
        "false_reject_rate": weighted_mode_metric(by_mode, "false_reject_rate"),
        "equal_weight_requirement_accuracy": weighted_mode_metric(by_mode, "equal_weight_requirement_accuracy"),
    }
    return result


def flatten(model_key: str, summary: dict[str, Any]) -> dict[str, Any]:
    g = summary["generation"]
    b = summary["behavior"]
    return {
        "model_key": model_key,
        "model_id": MODEL_IDS[model_key],
        "first_attempt_turtle_parse_rate": g["first_attempt_turtle_parse_rate"],
        "first_attempt_operational_validity_rate": g["first_attempt_operational_validity_rate"],
        "final_pipeline_acceptance_count": g["final_pipeline_acceptance_count"],
        "final_pipeline_acceptance_rate": g["final_pipeline_acceptance_rate"],
        "repair_attempted": g["repair_attempted"],
        "repair_success": g["repair_success"],
        "repair_success_rate": g["repair_success_rate"],
        "retained_artifact_availability_count": g["retained_artifact_availability_count"],
        "correct_rdf_cases": b["correct_rdf_cases"],
        "sampled_cases": b["sampled_cases"],
        "end_to_end_behavioral_accuracy": b["end_to_end_behavioral_accuracy"],
        "conditional_accuracy_executable": b["conditional_accuracy_executable"],
        "false_accept_count": b["false_accept_count"],
        "expected_fail_denominator": b["expected_fail_denominator"],
        "false_accept_rate": b["false_accept_rate"],
        "false_reject_count": b["false_reject_count"],
        "expected_pass_denominator": b["expected_pass_denominator"],
        "false_reject_rate": b["false_reject_rate"],
        "cases_without_verdict": b["cases_without_verdict"],
        "equal_weight_requirement_accuracy": b["equal_weight_requirement_accuracy"],
        "requirements_with_every_case_correct": b["requirements_with_every_case_correct"],
        "weighted_final_pipeline_acceptance_rate": g["weighted_benchmark_distribution"]["final_pipeline_acceptance_rate"],
        "weighted_end_to_end_behavioral_accuracy": b["weighted_benchmark_distribution"]["end_to_end_behavioral_accuracy"],
        "weighted_conditional_accuracy_executable": b["weighted_benchmark_distribution"]["conditional_accuracy_executable"],
        "weighted_equal_weight_requirement_accuracy": b["weighted_benchmark_distribution"]["equal_weight_requirement_accuracy"],
        "input_tokens": g["input_tokens"],
        "output_tokens": g["output_tokens"],
        "api_calls": g["api_calls"],
        "latency_ms": g["latency_ms"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=EXPERIMENT / "SUMMARY")
    args = parser.parse_args()
    sample = load_json(EXPERIMENT / "MANIFESTS" / "sample_50.json")
    metadata = {str(r["requirement_id"]): r for r in sample["records"]}
    sample_ids = set(metadata)
    combined: dict[str, Any] = {
        "experiment_id": "MODEL_SCALING_FULL_REPAIR_V2_50",
        "sample_manifest_sha256": sha256_file(EXPERIMENT / "MANIFESTS" / "sample_50.json"),
        "post_stratification": {mode: {"count": count, "weight": count / 268} for mode, count in {
            "DIRECT_STATIC": 190,
            "DIRECT_CALCULATION": 41,
            "COMPLEX_READINESS": 37,
        }.items()},
        "models": {},
    }
    flat: list[dict[str, Any]] = []
    for model_key in MODEL_ORDER:
        gen_rows = generation_rows(model_key, sample_ids)
        beh_rows = behavior_rows(model_key)
        case_req_ids = {str(r["requirement_id"]) for r in beh_rows}
        if case_req_ids != sample_ids:
            raise RuntimeError(f"Behavioral ledger for {model_key} does not cover exactly the frozen requirements")
        entry = {
            "model_id": MODEL_IDS[model_key],
            "generation": generation_metrics(gen_rows, metadata),
            "behavior": behavior_metrics(beh_rows, metadata),
        }
        combined["models"][model_key] = entry
        flat.append(flatten(model_key, entry))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "combined_scaling_summary.json"
    json_path.write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_path = args.output_dir / "combined_scaling_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    print(json.dumps({"json": str(json_path), "csv": str(csv_path), "models": MODEL_ORDER}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
