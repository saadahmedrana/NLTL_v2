from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .core import requirement_sort_key
from .execution import INFRASTRUCTURE_OUTCOMES, atomic_json, load_ledger


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    semantic = [row for row in rows if row.get("execution_status") == "EXECUTED"]
    correct = [row for row in semantic if row.get("behavioral_match") is True]
    expected_pass = [row for row in semantic if row.get("expected_outcome") == "PASS"]
    expected_fail = [row for row in semantic if row.get("expected_outcome") == "FAIL"]
    all_expected_pass = [row for row in rows if row.get("expected_outcome") == "PASS"]
    all_expected_fail = [row for row in rows if row.get("expected_outcome") == "FAIL"]
    infra = [row for row in rows if row.get("outcome_class") in INFRASTRUCTURE_OUTCOMES]
    return {
        "rows_total": len(rows),
        "semantic_results": len(semantic),
        "infrastructure_failures": len(infra),
        "generated_rows": sum(row.get("generation_status") == "GENERATED" for row in rows),
        "shape_parsed_rows": sum(row.get("shape_parse_status") == "PARSED" for row in rows),
        "executable_shape_coverage": _ratio(len(semantic), len(rows)),
        "behavioral_correct": len(correct),
        "behavioral_accuracy_among_usable": _ratio(len(correct), len(semantic)),
        "end_to_end_case_success": len(correct),
        "end_to_end_case_accuracy": _ratio(len(correct), len(rows)),
        "expected_pass_correct": sum(row.get("behavioral_match") is True for row in expected_pass),
        "expected_pass_total": len(all_expected_pass),
        "expected_pass_total_usable": len(expected_pass),
        "expected_pass_accuracy_usable": _ratio(sum(row.get("behavioral_match") is True for row in expected_pass), len(expected_pass)),
        "expected_pass_end_to_end_accuracy": _ratio(sum(row.get("behavioral_match") is True for row in expected_pass), len(all_expected_pass)),
        "expected_fail_correct": sum(row.get("behavioral_match") is True for row in expected_fail),
        "expected_fail_total": len(all_expected_fail),
        "expected_fail_total_usable": len(expected_fail),
        "expected_fail_accuracy_usable": _ratio(sum(row.get("behavioral_match") is True for row in expected_fail), len(expected_fail)),
        "expected_fail_end_to_end_accuracy": _ratio(sum(row.get("behavioral_match") is True for row in expected_fail), len(all_expected_fail)),
        "false_accepts": sum(row.get("outcome_class") == "FALSE_ACCEPT" for row in rows),
        "false_rejects": sum(row.get("outcome_class") == "FALSE_REJECT" for row in rows),
        "outcome_counts": dict(sorted(Counter(row.get("outcome_class") for row in rows).items())),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze(ledger_path: Path) -> Path:
    rows, _ = load_ledger(ledger_path)
    output = ledger_path.parent / "summaries"
    output.mkdir(parents=True, exist_ok=True)
    dimensions = {
        "configuration": lambda row: row["configuration"],
        "source_family": lambda row: row["source_family"],
        "verification_mode": lambda row: row["verification_mode"],
        "configuration_and_source_family": lambda row: f"{row['configuration']}|{row['source_family']}",
        "configuration_and_verification_mode": lambda row: f"{row['configuration']}|{row['verification_mode']}",
    }
    summary: dict[str, Any] = {"overall": summarize_rows(rows)}
    for name, function in dimensions.items():
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(function(row))].append(row)
        summary[f"by_{name}"] = {key: summarize_rows(value) for key, value in sorted(grouped.items())}
    patterns: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("test_pattern"):
            patterns[row["test_pattern"]].append(row)
    summary["by_explicit_test_pattern"] = {key: summarize_rows(value) for key, value in sorted(patterns.items())}

    requirement_rows: list[dict[str, Any]] = []
    grouped_requirements: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped_requirements[(row["configuration"], row["requirement_id"])].append(row)
    for (configuration, requirement_id), values in sorted(
        grouped_requirements.items(), key=lambda item: (item[0][0], requirement_sort_key(item[0][1]))
    ):
        semantic = [row for row in values if row["execution_status"] == "EXECUTED"]
        correct = sum(row.get("behavioral_match") is True for row in values)
        usable = len(semantic) == len(values)
        false_accepts = sum(row["outcome_class"] == "FALSE_ACCEPT" for row in values)
        false_rejects = sum(row["outcome_class"] == "FALSE_REJECT" for row in values)
        if not usable:
            defect = "GENERATION_OR_USABILITY_DEFECT"
        elif false_accepts and false_rejects:
            defect = "MIXED_SEMANTIC_ERRORS"
        elif false_accepts:
            defect = "ONLY_FALSE_ACCEPTS"
        elif false_rejects:
            defect = "ONLY_FALSE_REJECTS"
        else:
            defect = "NONE"
        requirement_rows.append({
            "configuration": configuration,
            "source_family": values[0]["source_family"],
            "requirement_id": requirement_id,
            "verification_mode": values[0]["verification_mode"],
            "cases_correct": correct,
            "cases_total": len(values),
            "incorrect_cases": len(values) - correct,
            "requirement_generated": all(row.get("generation_status") == "GENERATED" for row in values),
            "requirement_parseable": all(row.get("shape_parse_status") == "PARSED" for row in values),
            "requirement_usable": usable,
            "requirement_exact_behavioral_success": usable and correct == len(values),
            "end_to_end_requirement_exact_success": usable and correct == len(values),
            "false_accepts": false_accepts,
            "false_rejects": false_rejects,
            "infrastructure_failures": len(values) - len(semantic),
            "defect_profile": defect,
        })
    summary["requirement_level"] = {
        configuration: {
            "requirements_total": len([r for r in requirement_rows if r["configuration"] == configuration]),
            "requirements_generated": sum(r["requirement_generated"] for r in requirement_rows if r["configuration"] == configuration),
            "requirements_parseable": sum(r["requirement_parseable"] for r in requirement_rows if r["configuration"] == configuration),
            "requirements_usable": sum(r["requirement_usable"] for r in requirement_rows if r["configuration"] == configuration),
            "requirements_exact": sum(r["end_to_end_requirement_exact_success"] for r in requirement_rows if r["configuration"] == configuration),
        }
        for configuration in sorted({r["configuration"] for r in requirement_rows})
    }
    atomic_json(output / "behavioral_summary.json", summary)
    _write_csv(output / "requirement_summary.csv", requirement_rows)
    architecture_rows = []
    for configuration, values in summary["by_configuration"].items():
        req = summary["requirement_level"][configuration]
        architecture_rows.append({"configuration": configuration, **{k: v for k, v in values.items() if k != "outcome_counts"}, **req})
    _write_csv(output / "configuration_summary.csv", architecture_rows)
    configurations = sorted({row["configuration"] for row in rows})
    pairwise_rows: list[dict[str, Any]] = []
    requirement_lookup = {(row["configuration"], row["requirement_id"]): row for row in requirement_rows}
    for left_index, left in enumerate(configurations):
        for right in configurations[left_index + 1:]:
            shared = sorted(
                {req for config, req in requirement_lookup if config == left}
                & {req for config, req in requirement_lookup if config == right},
                key=requirement_sort_key,
            )
            left_exact = sum(requirement_lookup[(left, req)]["end_to_end_requirement_exact_success"] for req in shared)
            right_exact = sum(requirement_lookup[(right, req)]["end_to_end_requirement_exact_success"] for req in shared)
            pairwise_rows.append({
                "left_configuration": left,
                "right_configuration": right,
                "shared_requirements": len(shared),
                "left_exact_requirements": left_exact,
                "right_exact_requirements": right_exact,
                "left_only_exact": sum(
                    requirement_lookup[(left, req)]["end_to_end_requirement_exact_success"]
                    and not requirement_lookup[(right, req)]["end_to_end_requirement_exact_success"] for req in shared
                ),
                "right_only_exact": sum(
                    requirement_lookup[(right, req)]["end_to_end_requirement_exact_success"]
                    and not requirement_lookup[(left, req)]["end_to_end_requirement_exact_success"] for req in shared
                ),
                "both_exact": sum(
                    requirement_lookup[(left, req)]["end_to_end_requirement_exact_success"]
                    and requirement_lookup[(right, req)]["end_to_end_requirement_exact_success"] for req in shared
                ),
                "neither_exact": sum(
                    not requirement_lookup[(left, req)]["end_to_end_requirement_exact_success"]
                    and not requirement_lookup[(right, req)]["end_to_end_requirement_exact_success"] for req in shared
                ),
            })
    summary["pairwise_requirement_comparisons"] = pairwise_rows
    atomic_json(output / "behavioral_summary.json", summary)
    _write_csv(output / "pairwise_requirement_comparison.csv", pairwise_rows)
    return output
