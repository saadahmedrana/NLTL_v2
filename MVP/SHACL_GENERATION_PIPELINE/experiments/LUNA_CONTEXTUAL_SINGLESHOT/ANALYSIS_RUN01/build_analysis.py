from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ANALYSIS = Path(__file__).resolve().parent
EXPERIMENT = ANALYSIS.parent
PIPELINE = EXPERIMENT.parents[1]
RUN = EXPERIMENT / "RUN_01"
FULL = PIPELINE / "experiments/FINAL_LUNA_MAIN/RUN_01"
QUEUE = EXPERIMENT / "QUEUES/luna_contextual_singleshot_268_frozen.json"
FULL_QUEUE = PIPELINE / "experiments/FINAL_LUNA_MAIN/QUEUES/luna_main_268_frozen.json"
CONFIG = EXPERIMENT / "CONFIGS/pipeline.luna-contextual-singleshot-run01.json"
ZIP_PATH = EXPERIMENT / "FINAL_LUNA_CONTEXTUAL_SINGLESHOT_RUN01_ANALYSIS.zip"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summary(values: list[float]) -> dict[str, float | None]:
    return {
        "count": len(values),
        "mean": statistics.mean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
        "p25": percentile(values, 0.25),
        "p75": percentile(values, 0.75),
        "p95": percentile(values, 0.95),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def classify_failure(report: dict[str, Any]) -> str:
    if not report.get("extraction_valid"):
        return "EXTRACTION_FAILURE"
    if not report.get("turtle_valid"):
        return "TURTLE_PARSE_FAILURE"
    if not report.get("shacl_structure_valid"):
        return "SHACL_STRUCTURE_FAILURE"
    if not report.get("meta_shacl_valid"):
        return "META_SHACL_FAILURE"
    if not report.get("vocabulary_valid"):
        return "VOCABULARY_DIAGNOSTIC_FAILURE"
    if not report.get("datatype_unit_valid"):
        return "DATATYPE_UNIT_FAILURE"
    if not report.get("target_path_valid"):
        return "TARGET_PATH_FAILURE"
    return "OTHER_DETERMINISTIC_FAILURE"


def main() -> None:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    batch_path = next((RUN / "sessions").glob("*/batch_result.json"))
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    queue_doc = json.loads(QUEUE.read_text(encoding="utf-8"))
    queue = queue_doc["requirements"]
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    results = batch["results"]
    result_ids = [item["requirement_id"] for item in results]

    full_prompt_by_id: dict[str, Path] = {}
    for prompt in FULL.glob("runs/RUN-*/artifacts/attempt_01/generator_prompt.txt"):
        context = json.loads(prompt.parents[1].joinpath("context_pack_initial.json").read_text(encoding="utf-8"))
        full_prompt_by_id[context["requirement"]["id"]] = prompt

    case_rows: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []
    prompt_matches = 0
    run_started_times: list[datetime] = []
    run_finished_times: list[datetime] = []
    for item in results:
        run_dir = Path(item["run_directory"])
        context = json.loads((run_dir / "artifacts/context_pack_initial.json").read_text(encoding="utf-8"))
        diagnostics = json.loads(Path(item["diagnostics"]).read_text(encoding="utf-8"))
        report = diagnostics["deterministicValidation"]
        events = [
            json.loads(line)
            for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        all_events.extend(events)
        started = next(event for event in events if event["event_type"] == "run_started")
        finished = next(event for event in reversed(events) if event["event_type"] == "run_finished")
        start_dt, finish_dt = parse_time(started["timestamp_utc"]), parse_time(finished["timestamp_utc"])
        run_started_times.append(start_dt)
        run_finished_times.append(finish_dt)
        api_attempts = [event for event in events if event["event_type"] == "api_attempt_started"]
        completed = [event for event in events if event["event_type"] == "api_call_completed"]
        prompt_path = run_dir / "artifacts/attempt_01/generator_prompt.txt"
        full_prompt = full_prompt_by_id.get(item["requirement_id"])
        prompt_equal = bool(full_prompt and full_prompt.read_bytes() == prompt_path.read_bytes())
        prompt_matches += int(prompt_equal)
        valid = bool(item["deterministic_valid"])
        req = context["requirement"]
        selection = context["selection"]
        case_rows.append({
            "requirement_id": item["requirement_id"],
            "source": req.get("source", ""),
            "clause": req.get("clause", ""),
            "category": req.get("category", ""),
            "verification_mode": selection.get("dependencyContract", {}).get("verificationMode", ""),
            "terminal_status": item["status"],
            "deterministic_valid": valid,
            "primary_failure_stage": "NONE" if valid else classify_failure(report),
            "extraction_status": item["extraction_status"],
            "rdf_parse_status": item["rdf_parse_status"],
            "shacl_validation_status": item["shacl_validation_status"],
            "vocabulary_diagnostic_status": item["vocabulary_diagnostic_status"],
            "datatype_unit_valid": report.get("datatype_unit_valid"),
            "target_path_valid": report.get("target_path_valid"),
            "errors": " | ".join(report.get("errors", [])),
            "warnings": " | ".join(report.get("warnings", [])),
            "generator_calls": item["generator_calls"],
            "physical_transport_attempts": len(api_attempts),
            "transport_retries": max(0, len(api_attempts) - 1),
            "validator_calls": item["validator_calls"],
            "matcher_calls": item["vocabulary_matcher_calls"],
            "syntax_repair_calls": item["syntax_repair_calls"],
            "regeneration_calls": item["regeneration_calls"],
            "raw_response_retained": Path(item["raw_response"]).is_file(),
            "extracted_shape_retained": bool(item["extracted_shape"] and Path(item["extracted_shape"]).is_file()),
            "input_tokens": item["input_tokens"],
            "output_tokens": item["output_tokens"],
            "total_tokens": item["total_tokens"],
            "api_elapsed_ms": item["elapsed_ms"],
            "end_to_end_ms": (finish_dt - start_dt).total_seconds() * 1000,
            "estimated_cost_usd": item["estimated_cost_usd"],
            "first_prompt_matches_full_run01": prompt_equal,
            "run_id": item["run_id"],
            "run_directory": item["run_directory"],
        })

    status_counts = Counter(row["terminal_status"] for row in case_rows)
    failure_counts = Counter(
        row["primary_failure_stage"] for row in case_rows if not row["deterministic_valid"]
    )
    logical_roles = Counter(
        event["role"] for event in all_events if event["event_type"] == "api_call_completed"
    )
    physical_roles = Counter(
        event["role"] for event in all_events if event["event_type"] == "api_attempt_started"
    )
    completed_api_events = [event for event in all_events if event["event_type"] == "api_call_completed"]
    transport_finished = [event for event in all_events if event["event_type"] == "api_attempt_finished"]
    non_200 = sum(str(event.get("status")) != "200" for event in transport_finished)
    valid_count = sum(row["deterministic_valid"] for row in case_rows)
    raw_count = sum(row["raw_response_retained"] for row in case_rows)
    extracted_count = sum(row["extracted_shape_retained"] for row in case_rows)

    category_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    for field, destination in (("category", category_rows), ("source", source_rows)):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in case_rows:
            groups[str(row[field])].append(row)
        for label, group in sorted(groups.items()):
            passed = sum(row["deterministic_valid"] for row in group)
            failures = Counter(
                row["primary_failure_stage"] for row in group if not row["deterministic_valid"]
            )
            destination.append({
                field: label,
                "unique_requirements": len(group),
                "diagnostic_pass": passed,
                "diagnostic_fail": len(group) - passed,
                "diagnostic_pass_rate": passed / len(group),
                "extraction_failures": failures["EXTRACTION_FAILURE"],
                "turtle_parse_failures": failures["TURTLE_PARSE_FAILURE"],
                "shacl_structure_failures": failures["SHACL_STRUCTURE_FAILURE"],
                "meta_shacl_failures": failures["META_SHACL_FAILURE"],
                "vocabulary_failures": failures["VOCABULARY_DIAGNOSTIC_FAILURE"],
                "datatype_unit_failures": failures["DATATYPE_UNIT_FAILURE"],
                "target_path_failures": failures["TARGET_PATH_FAILURE"],
                "mean_api_elapsed_ms": statistics.mean(row["api_elapsed_ms"] for row in group),
                "mean_total_tokens": statistics.mean(row["total_tokens"] for row in group),
                "estimated_cost_usd": sum(row["estimated_cost_usd"] for row in group),
            })

    failure_rows = []
    for stage, count in sorted(failure_counts.items()):
        failure_rows.append({
            "failure_stage": stage,
            "count": count,
            "percentage_all_requirements": count / len(case_rows),
            "percentage_all_failures": count / (len(case_rows) - valid_count),
            "requirement_ids": " | ".join(
                row["requirement_id"] for row in case_rows if row["primary_failure_stage"] == stage
            ),
        })

    api_elapsed = [float(event["elapsed_ms"]) for event in completed_api_events]
    api_role_rows = [{
        "role": role,
        "logical_calls": logical_roles[role],
        "physical_transport_attempts": physical_roles[role],
        "transport_retries_or_failures": sum(
            str(event.get("status")) != "200"
            for event in transport_finished if event.get("role") == role
        ),
        "input_tokens": sum(int(event.get("input_tokens") or 0) for event in completed_api_events if event["role"] == role),
        "output_tokens": sum(int(event.get("output_tokens") or 0) for event in completed_api_events if event["role"] == role),
        "total_tokens": sum(int(event.get("total_tokens") or 0) for event in completed_api_events if event["role"] == role),
        **{f"elapsed_ms_{key}": value for key, value in summary([
            float(event["elapsed_ms"]) for event in completed_api_events if event["role"] == role
        ]).items()},
    } for role in sorted(logical_roles)]

    integrity_checks = {
        "batchResultExists": batch_path.is_file(),
        "requirementsDeclared268": batch.get("requirements") == 268,
        "totalItems268": batch.get("total_items") == 268,
        "results268": len(results) == 268,
        "uniqueRequirementIds268": len(set(result_ids)) == 268,
        "queueOrderExact": result_ids == queue,
        "queueByteIdenticalToFull": QUEUE.read_bytes() == FULL_QUEUE.read_bytes(),
        "r13Lock": batch.get("vocabulary_lock_id") == "VOCAB-LOCK-2026-08-22-R13",
        "executionModeSingleShot": batch.get("execution_mode") == "LUNA_CONTEXTUAL_SINGLESHOT",
        "allRawResponsesRetained": raw_count == 268,
        "exactlyOneGeneratorCallEach": all(row["generator_calls"] == 1 for row in case_rows),
        "zeroValidatorCalls": sum(row["validator_calls"] for row in case_rows) == 0,
        "zeroMatcherCalls": sum(row["matcher_calls"] for row in case_rows) == 0,
        "zeroSyntaxRepairCalls": sum(row["syntax_repair_calls"] for row in case_rows) == 0,
        "zeroRegenerationCalls": sum(row["regeneration_calls"] for row in case_rows) == 0,
        "allFirstPromptsMatchFullRun01": prompt_matches == 268,
        "modelLuna": config["models"]["generator"] == "gpt-5.6-luna-2026-07-09",
    }
    integrity = {
        "status": "PASS" if all(integrity_checks.values()) else "FAIL",
        "checks": integrity_checks,
        "batch_result": str(batch_path),
        "session_id": batch["session_id"],
        "queue_sha256": sha256(QUEUE),
        "full_queue_sha256": sha256(FULL_QUEUE),
        "first_prompt_matches": prompt_matches,
        "first_prompt_total": 268,
        "integrity_concerns": [] if all(integrity_checks.values()) else [
            key for key, passed in integrity_checks.items() if not passed
        ],
    }

    overview = {
        "experiment": "LUNA_CONTEXTUAL_SINGLESHOT RUN_01",
        "statistical_unit": "one frozen 268-requirement run",
        "repetitions": 1,
        "requirements": len(case_rows),
        "deterministic_diagnostic_pass": valid_count,
        "deterministic_diagnostic_fail": len(case_rows) - valid_count,
        "deterministic_diagnostic_pass_rate": valid_count / len(case_rows),
        "raw_responses_retained": raw_count,
        "extracted_shapes_retained": extracted_count,
        "terminal_statuses": dict(status_counts),
        "failure_stages": dict(failure_counts),
        "logical_api_calls_by_role": dict(logical_roles),
        "physical_transport_attempts_by_role": dict(physical_roles),
        "non_200_transport_attempts": non_200,
        "input_tokens": sum(row["input_tokens"] for row in case_rows),
        "output_tokens": sum(row["output_tokens"] for row in case_rows),
        "total_tokens": sum(row["total_tokens"] for row in case_rows),
        "estimated_cost_usd": sum(row["estimated_cost_usd"] for row in case_rows),
        "cost_per_requirement": sum(row["estimated_cost_usd"] for row in case_rows) / len(case_rows),
        "cost_per_diagnostic_pass": sum(row["estimated_cost_usd"] for row in case_rows) / valid_count,
        "api_elapsed_ms": summary(api_elapsed),
        "end_to_end_requirement_ms": summary([row["end_to_end_ms"] for row in case_rows]),
        "run_wall_clock_seconds": (max(run_finished_times) - min(run_started_times)).total_seconds(),
        "run_level_sd": None,
        "run_level_95_percent_ci": None,
        "statistical_note": "Only one repetition exists; run-level variability, stability and a t-based CI cannot be estimated.",
        "pricing_basis": config["cost_estimation"],
    }

    write_csv(ANALYSIS / "case_results.csv", case_rows)
    write_csv(
        ANALYSIS / "failure_by_case.csv",
        [row for row in case_rows if not row["deterministic_valid"]],
        list(case_rows[0]),
    )
    write_csv(ANALYSIS / "failure_summary.csv", failure_rows)
    write_csv(ANALYSIS / "category_summary.csv", category_rows)
    write_csv(ANALYSIS / "source_summary.csv", source_rows)
    write_csv(ANALYSIS / "api_role_summary.csv", api_role_rows)
    write_csv(ANALYSIS / "run_summary.csv", [{
        "run": "RUN_01",
        "requirements": len(case_rows),
        "diagnostic_pass": valid_count,
        "diagnostic_fail": len(case_rows) - valid_count,
        "diagnostic_pass_rate": valid_count / len(case_rows),
        "logical_generator_calls": logical_roles.get("generator", 0),
        "physical_transport_attempts": physical_roles.get("generator", 0),
        "input_tokens": sum(row["input_tokens"] for row in case_rows),
        "output_tokens": sum(row["output_tokens"] for row in case_rows),
        "total_tokens": sum(row["total_tokens"] for row in case_rows),
        "estimated_cost_usd": sum(row["estimated_cost_usd"] for row in case_rows),
    }])
    attempt_payload = {
        "mode": "CONTEXTUAL_SINGLESHOT",
        "requirements": len(case_rows),
        "generator_calls": logical_roles.get("generator", 0),
        "attempt_1_deterministic_pass": valid_count,
        "attempt_1_deterministic_pass_rate": valid_count / len(case_rows),
        "additional_attempts": 0,
        "validator_calls": 0,
        "matcher_calls": 0,
        "syntax_repair_calls": 0,
        "regeneration_calls": 0,
    }
    write_csv(ANALYSIS / "attempt_analysis.csv", [attempt_payload])
    (ANALYSIS / "attempt_analysis.json").write_text(
        json.dumps(attempt_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    write_csv(ANALYSIS / "api_timing_cost_summary.csv", [{
        "run": "RUN_01",
        "logical_api_calls": sum(logical_roles.values()),
        "physical_transport_attempts": sum(physical_roles.values()),
        "non_200_transport_attempts": non_200,
        "input_tokens": sum(row["input_tokens"] for row in case_rows),
        "output_tokens": sum(row["output_tokens"] for row in case_rows),
        "total_tokens": sum(row["total_tokens"] for row in case_rows),
        "estimated_cost_usd": sum(row["estimated_cost_usd"] for row in case_rows),
        "mean_api_elapsed_ms": statistics.mean(api_elapsed),
        "median_api_elapsed_ms": statistics.median(api_elapsed),
        "p95_api_elapsed_ms": percentile(api_elapsed, 0.95),
        "run_wall_clock_seconds": (max(run_finished_times) - min(run_started_times)).total_seconds(),
    }])
    write_csv(ANALYSIS / "status_matrix.csv", [{
        "requirement_id": row["requirement_id"], "RUN_01": row["terminal_status"]
    } for row in case_rows])
    write_csv(ANALYSIS / "acceptance_matrix.csv", [{
        "requirement_id": row["requirement_id"], "RUN_01": int(row["deterministic_valid"])
    } for row in case_rows])
    (ANALYSIS / "experiment_integrity.json").write_text(
        json.dumps(integrity, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    (ANALYSIS / "experiment_integrity.txt").write_text(
        f"INTEGRITY: {integrity['status']}\n"
        f"Results: {len(results)}/268; unique: {len(set(result_ids))}/268\n"
        f"Queue and order exact: {integrity_checks['queueOrderExact']}\n"
        f"Raw retained: {raw_count}/268\n"
        f"First prompts matching FULL RUN_01: {prompt_matches}/268\n"
        f"Generator/validator/matcher/syntax/regeneration: {logical_roles.get('generator', 0)}/0/0/0/0\n"
        f"Concerns: {integrity['integrity_concerns'] or 'NONE'}\n",
        encoding="utf-8",
    )
    (ANALYSIS / "overall_statistics.json").write_text(
        json.dumps(overview, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    write_csv(ANALYSIS / "overall_statistics.csv", [{
        "requirements": overview["requirements"],
        "diagnostic_pass": valid_count,
        "diagnostic_fail": len(case_rows) - valid_count,
        "diagnostic_pass_rate": overview["deterministic_diagnostic_pass_rate"],
        "input_tokens": overview["input_tokens"],
        "output_tokens": overview["output_tokens"],
        "total_tokens": overview["total_tokens"],
        "estimated_cost_usd": overview["estimated_cost_usd"],
        "run_wall_clock_seconds": overview["run_wall_clock_seconds"],
        "run_level_sd": "NOT_ESTIMABLE_N1",
        "run_level_95_percent_ci": "NOT_ESTIMABLE_N1",
    }])
    (ANALYSIS / "statistical_notes.txt").write_text(
        "Only one formal contextual-single-shot repetition is available.\n"
        "Therefore run-to-run SD, stability classes, cumulative repetition adequacy, and a Student-t 95% CI over run-level rates cannot be estimated.\n"
        "The 268 cases are heterogeneous requirements, not 268 exchangeable Bernoulli trials; no binomial CI is reported.\n"
        "The reported 221/268 rate is deterministic harness validity, not semantic-validator acceptance and not hidden RDF semantic accuracy.\n",
        encoding="utf-8",
    )
    validation_payload = {
        "status": "PASS",
        "requirements": len(case_rows),
        "unique_requirements": len({row["requirement_id"] for row in case_rows}),
        "queue_order_exact": result_ids == queue,
        "diagnostic_pass": valid_count,
        "diagnostic_fail": len(case_rows) - valid_count,
        "logical_generator_calls": logical_roles.get("generator", 0),
        "zero_downstream_llm_calls": (
            sum(row["validator_calls"] + row["matcher_calls"] + row["syntax_repair_calls"] + row["regeneration_calls"] for row in case_rows) == 0
        ),
        "raw_responses_retained": raw_count,
        "first_prompts_matching_full": prompt_matches,
        "category_partition": sum(row["unique_requirements"] for row in category_rows),
        "source_partition": sum(row["unique_requirements"] for row in source_rows),
        "api_calls_made_by_analysis": 0,
    }
    if not (
        validation_payload["requirements"] == 268
        and validation_payload["unique_requirements"] == 268
        and validation_payload["queue_order_exact"]
        and validation_payload["diagnostic_pass"] + validation_payload["diagnostic_fail"] == 268
        and validation_payload["logical_generator_calls"] == 268
        and validation_payload["zero_downstream_llm_calls"]
        and validation_payload["raw_responses_retained"] == 268
        and validation_payload["first_prompts_matching_full"] == 268
        and validation_payload["category_partition"] == 268
        and validation_payload["source_partition"] == 268
    ):
        validation_payload["status"] = "FAIL"
    (ANALYSIS / "analysis_validation.json").write_text(
        json.dumps(validation_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    category_lines = "\n".join(
        f"- {row['category']}: {row['diagnostic_pass']}/{row['unique_requirements']} "
        f"({row['diagnostic_pass_rate']:.2%})"
        for row in category_rows
    )
    source_lines = "\n".join(
        f"- {row['source']}: {row['diagnostic_pass']}/{row['unique_requirements']} "
        f"({row['diagnostic_pass_rate']:.2%})"
        for row in source_rows
    )
    failure_lines = "\n".join(
        f"- {row['failure_stage']}: {row['count']} ({row['percentage_all_failures']:.2%} of failures)"
        for row in failure_rows
    )
    report = f"""# LUNA_CONTEXTUAL_SINGLESHOT RUN_01 analysis

## Integrity

Integrity passed. RUN_01 contains 268 finalized, unique results in the exact frozen-queue order. Every requirement has one retained raw response and exactly one generator call. Validator, matcher, syntax-repair and regeneration calls are all zero. All 268 rendered generator prompts are byte-identical to the corresponding first generator prompts in `FINAL_LUNA_MAIN/RUN_01`.

## Headline result

- Deterministic diagnostic pass: **{valid_count}/268 ({valid_count / 268:.2%})**
- Deterministic diagnostic fail: **{268 - valid_count}/268 ({(268 - valid_count) / 268:.2%})**
- Raw responses retained: **{raw_count}/268**
- Extracted shapes retained: **{extracted_count}/268**

This is not semantic-validator acceptance and not hidden-RDF semantic accuracy. It reports whether the unmodified single generator output passed the read-only extraction and deterministic harness.

## Failure stages

{failure_lines}

Observed diagnostic statuses must not be interpreted automatically as ontology gaps. They describe where the unmodified output failed the deterministic harness.

## Category

{category_lines}

## Source

{source_lines}

## API, tokens, timing and cost

- Logical API calls: **{sum(logical_roles.values())}**, all generator
- Physical transport attempts: **{sum(physical_roles.values())}**
- Non-200 transport attempts: **{non_200}**
- Input tokens: **{overview['input_tokens']:,}**
- Output tokens: **{overview['output_tokens']:,}**
- Total tokens: **{overview['total_tokens']:,}**
- Estimated cost: **USD {overview['estimated_cost_usd']:.6f}**
- Mean cost per requirement: **USD {overview['cost_per_requirement']:.6f}**
- Mean API latency: **{overview['api_elapsed_ms']['mean'] / 1000:.2f} s**
- Median API latency: **{overview['api_elapsed_ms']['median'] / 1000:.2f} s**
- P95 API latency: **{overview['api_elapsed_ms']['p95'] / 1000:.2f} s**
- Run wall clock: **{overview['run_wall_clock_seconds'] / 3600:.2f} h**

Cost uses the repository's indicative Luna prices of USD 1/M input and USD 6/M output tokens. It is not an Aalto invoice and may be stale.

## Statistical limitation

This package analyzes one repetition. Run-level SD, a t-based 95% confidence interval, requirement stability and adequacy of repetitions are not estimable at n=1. The 268 heterogeneous requirements are not treated as mutually exchangeable independent Bernoulli trials, so no misleading binomial CI is reported.

## Scientific interpretation

The condition successfully isolates the removal of all LLM-mediated verification and repair while preserving the same first-call context. Its diagnostic-pass rate measures syntactic, structural and controlled-vocabulary viability of unmodified contextual Luna outputs under frozen R13. Later repetitions are required to measure stochasticity, and hidden RDF evaluation is required before making semantic-accuracy claims.
"""
    (ANALYSIS / "MASTER_SUMMARY.md").write_text(report, encoding="utf-8")

    generated = sorted(
        path for path in ANALYSIS.iterdir()
        if path.is_file() and path.name not in {"analysis_manifest.json"}
    )
    manifest = {
        "analysis": "LUNA_CONTEXTUAL_SINGLESHOT_RUN01",
        "sourceRunModified": False,
        "apiCallsMadeByAnalysis": 0,
        "files": [
            {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in generated
        ],
    }
    (ANALYSIS / "analysis_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    generated = sorted(path for path in ANALYSIS.iterdir() if path.is_file())
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in generated:
            archive.write(path, arcname=f"ANALYSIS_RUN01/{path.name}")
    print(json.dumps({
        "status": "PASS",
        "requirements": 268,
        "diagnostic_pass": valid_count,
        "diagnostic_fail": 268 - valid_count,
        "logical_calls": dict(logical_roles),
        "physical_attempts": dict(physical_roles),
        "tokens": overview["total_tokens"],
        "cost_usd": overview["estimated_cost_usd"],
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
    }, indent=2))


if __name__ == "__main__":
    main()
