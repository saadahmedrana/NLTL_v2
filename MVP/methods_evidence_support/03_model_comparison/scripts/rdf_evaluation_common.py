from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


MODES = ("SELF_REPAIR_FINAL", "FIRST_GENERATION")
MODELS = ("luna", "sol", "gemini", "gpt_oss")
FINAL_CASES = 381
SMOKE_CASES = 9


def safe_rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def output_directory(experiment: Path, scope: str, mode: str, model: str) -> Path:
    if scope not in {"smoke", "final"}:
        raise ValueError(f"Unknown evaluation scope: {scope}")
    if mode not in MODES or model not in MODELS:
        raise ValueError(f"Unknown evaluation target: {mode}/{model}")
    root = experiment / "OUTPUTS/RDF_EVALUATION"
    return root / ("SMOKE" if scope == "smoke" else "") / mode / model


def summarize_cases(rows: list[dict[str, Any]]) -> dict[str, Any]:
    executable = [row for row in rows if row.get("execution_status") == "EXECUTED"]
    tp = sum(row.get("expected_outcome") == "PASS" and row.get("actual_conforms") is True for row in executable)
    tn = sum(row.get("expected_outcome") == "FAIL" and row.get("actual_conforms") is False for row in executable)
    fp = sum(row.get("expected_outcome") == "FAIL" and row.get("actual_conforms") is True for row in executable)
    fn = sum(row.get("expected_outcome") == "PASS" and row.get("actual_conforms") is False for row in executable)
    correct = tp + tn
    total = len(rows)
    by_requirement: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_requirement[str(row["requirement_id"])].append(row)
    exact = sum(
        len(values) > 0
        and all(row.get("execution_status") == "EXECUTED" and row.get("behavioral_match") is True for row in values)
        for values in by_requirement.values()
    )
    available_requirements = sum(
        all(row.get("generation_status") == "GENERATED" for row in values)
        for values in by_requirement.values()
    )
    precision = safe_rate(tp, tp + fp)
    recall = safe_rate(tp, tp + fn)
    return {
        "tp": tp,
        "tn": tn,
        "fp_false_accept": fp,
        "fn_false_reject": fn,
        "correct_cases": correct,
        "total_cases": total,
        "executable_cases": len(executable),
        "no_verdict_count": total - len(executable),
        "end_to_end_accuracy": safe_rate(correct, total),
        "executable_accuracy": safe_rate(correct, len(executable)),
        "precision": precision,
        "recall": recall,
        "specificity": safe_rate(tn, tn + fp),
        "f1": (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else None,
        "artifact_requirements_available": available_requirements,
        "artifact_requirements_total": len(by_requirement),
        "artifact_coverage": safe_rate(available_requirements, len(by_requirement)),
        "exact_requirement_success_count": exact,
        "exact_requirement_total": len(by_requirement),
        "exact_requirement_success_rate": safe_rate(exact, len(by_requirement)),
    }


def requirement_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["requirement_id"])].append(row)
    result: list[dict[str, Any]] = []
    for requirement_id, values in sorted(grouped.items()):
        metrics = summarize_cases(values)
        result.append({
            "requirement_id": requirement_id,
            "source_family": values[0].get("source_family"),
            "verification_mode": values[0].get("verification_mode"),
            "candidate_path": values[0].get("generated_shape_path"),
            "candidate_sha256": values[0].get("generated_shape_sha256"),
            "generation_status": values[0].get("generation_status"),
            **metrics,
        })
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise RuntimeError(f"Refusing to write an empty result table: {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    temporary.replace(path)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def materialize_required_outputs(output_dir: Path, raw_ledger: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    rows = load_jsonl(raw_ledger)
    expected = SMOKE_CASES if metadata["scope"] == "smoke" else FINAL_CASES
    if len(rows) != expected:
        raise RuntimeError(f"Result row count mismatch for {output_dir}: {len(rows)} != {expected}")
    case_jsonl = output_dir / "case_results.jsonl"
    case_temporary = case_jsonl.with_suffix(case_jsonl.suffix + ".tmp")
    case_temporary.write_bytes(raw_ledger.read_bytes())
    case_temporary.replace(case_jsonl)
    write_csv(output_dir / "case_results.csv", rows)
    requirements = requirement_results(rows)
    write_csv(output_dir / "requirement_results.csv", requirements)
    summary = {
        **metadata,
        **summarize_cases(rows),
        "case_results_sha256": __import__("hashlib").sha256(case_jsonl.read_bytes()).hexdigest(),
        "candidate_hashes": {
            row["requirement_id"]: row.get("candidate_sha256")
            for row in requirements
        },
    }
    summary_path = output_dir / "summary.json"
    summary_temporary = summary_path.with_suffix(summary_path.suffix + ".tmp")
    summary_temporary.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary_temporary.replace(summary_path)
    return summary
