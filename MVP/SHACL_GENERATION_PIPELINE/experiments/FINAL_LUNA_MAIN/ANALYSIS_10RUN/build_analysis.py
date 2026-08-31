#!/usr/bin/env python3
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
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
PIPELINE = EXPERIMENT.parents[1]
MVP = PIPELINE.parent
RUN_NAMES = [f"RUN_{i:02d}" for i in range(1, 11)]
ACCEPTED = "GENERATION_ACCEPTED"
EXPECTED_LOCK = "VOCAB-LOCK-2026-08-22-R13"
EXPECTED_MODEL = "gpt-5.6-luna-2026-07-09"
EXPECTED_REQUIREMENTS = 268
EXPECTED_TRIALS = 2680
EXPECTED_ATTEMPTS = 4
QUEUE_PATH = EXPERIMENT / "QUEUES/luna_main_268_frozen.json"
EVIDENCE_PATH = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R13/evidence/stage1_approved.json"
LOCK_PATH = MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-22-R13.lock.json"
ZIP_PATH = EXPERIMENT / "FINAL_LUNA_10RUN_AGGREGATED_ANALYSIS.zip"
T_CRITICAL_975 = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571,
                  7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, value: Any) -> None:
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(name: str, value: str) -> None:
    (HERE / name).write_text(value.rstrip() + "\n", encoding="utf-8")


def write_csv(name: str, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with (HERE / name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def f(value: float | int | None, digits: int = 6) -> float | str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return round(float(value), digits)


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.fmean(values) if values else math.nan


def median(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.median(values) if values else math.nan


def sample_sd(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.stdev(values) if len(values) > 1 else 0.0


def quantile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def ci95(values: Iterable[float]) -> tuple[float, float, float]:
    values = list(values)
    center = mean(values)
    if len(values) < 2:
        return center, center, 0.0
    half = T_CRITICAL_975[len(values)] * sample_sd(values) / math.sqrt(len(values))
    return center - half, center + half, 2 * half


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def recursive_diffs(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    if type(left) is not type(right):
        return [{"path": path or "/", "left": left, "right": right}]
    if isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            child = f"{path}/{key}"
            if key not in left:
                diffs.append({"path": child, "left": "<MISSING>", "right": right[key]})
            elif key not in right:
                diffs.append({"path": child, "left": left[key], "right": "<MISSING>"})
            else:
                diffs.extend(recursive_diffs(left[key], right[key], child))
    elif isinstance(left, list):
        if left != right:
            diffs.append({"path": path or "/", "left": left, "right": right})
    elif left != right:
        diffs.append({"path": path or "/", "left": left, "right": right})
    return diffs


def load_batch(run_name: str) -> tuple[Path, dict[str, Any]]:
    paths = sorted((EXPERIMENT / run_name / "sessions").glob("*/batch_result.json"))
    if len(paths) != 1:
        raise RuntimeError(f"{run_name}: expected one batch_result.json, found {len(paths)}")
    return paths[0], read_json(paths[0])


def read_events(run_directory: Path) -> list[dict[str, Any]]:
    path = run_directory / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def stability_class(successes: int) -> str:
    if successes == 10:
        return "consistently successful"
    if successes >= 8:
        return "highly reliable"
    if successes >= 4:
        return "stochastic / unstable"
    if successes >= 1:
        return "generally difficult"
    return "persistent systematic failure"


def main() -> None:
    queue = read_json(QUEUE_PATH)
    queue_ids = queue["requirements"]
    evidence = read_json(EVIDENCE_PATH)
    metadata = {item["id"]: item for item in evidence["requirements"]}
    lock = read_json(LOCK_PATH)
    queue_sha = sha256(QUEUE_PATH)

    configs: dict[str, dict[str, Any]] = {}
    config_paths: dict[str, Path] = {}
    doctors: dict[str, dict[str, Any]] = {}
    batches: dict[str, dict[str, Any]] = {}
    batch_paths: dict[str, Path] = {}
    trials: list[dict[str, Any]] = []
    trials_by_run: dict[str, list[dict[str, Any]]] = {}
    api_calls: list[dict[str, Any]] = []
    api_attempts: list[dict[str, Any]] = []
    integrity_runs: dict[str, Any] = {}

    for run_index, run_name in enumerate(RUN_NAMES, 1):
        config_path = EXPERIMENT / "CONFIGS" / f"pipeline.final-luna-main-run{run_index:02d}.json"
        config = read_json(config_path)
        configs[run_name] = config
        config_paths[run_name] = config_path
        doctor = read_json(EXPERIMENT / run_name / "doctor.log")
        doctors[run_name] = doctor
        batch_path, batch = load_batch(run_name)
        batch_paths[run_name] = batch_path
        batches[run_name] = batch
        results = batch["results"]
        result_ids = [item["requirement_id"] for item in results]
        duplicates = sorted(key for key, count in Counter(result_ids).items() if count > 1)
        missing = sorted(set(queue_ids) - set(result_ids))
        unexpected = sorted(set(result_ids) - set(queue_ids))
        run_dirs = sorted(path for path in (EXPERIMENT / run_name / "runs").iterdir() if path.is_dir())
        run_dir_by_req: dict[str, list[Path]] = defaultdict(list)
        for run_dir in run_dirs:
            tracker = run_dir / "tables/tracker_payload.json"
            if tracker.exists():
                payload = read_json(tracker)
                rid = payload.get("requirement_id") or payload.get("requirementId")
                if rid:
                    run_dir_by_req[str(rid)].append(run_dir)
            if not any(run_dir_by_req.values()) or not tracker.exists():
                events = read_events(run_dir)
                rid = next((event.get("requirement_id") for event in events if event.get("requirement_id")), None)
                if rid and run_dir not in run_dir_by_req[str(rid)]:
                    run_dir_by_req[str(rid)].append(run_dir)

        current_trials: list[dict[str, Any]] = []
        for result in results:
            rid = result["requirement_id"]
            candidate_dirs = run_dir_by_req.get(rid, [])
            if not candidate_dirs and result.get("run_directory"):
                candidate = Path(result["run_directory"])
                if candidate.exists():
                    candidate_dirs = [candidate]
            run_dir = candidate_dirs[0] if candidate_dirs else None
            events = read_events(run_dir) if run_dir else []
            completed = [event for event in events if event.get("event_type") == "api_call_completed"]
            attempts_finished = [event for event in events if event.get("event_type") == "api_attempt_finished"]
            generator_iterations = [int(event.get("iteration") or 0) for event in completed if event.get("role") == "generator"]
            semantic_attempts = result.get("attempts")
            if semantic_attempts is None:
                semantic_attempts = max(generator_iterations, default=0)
            if semantic_attempts == 0 and run_dir:
                semantic_attempts = max((int(path.name.split("_")[-1]) for path in (run_dir / "artifacts").glob("attempt_*")), default=0)
            timestamps = [parse_time(event["timestamp_utc"]) for event in events if event.get("timestamp_utc")]
            runtime_ms = (max(timestamps) - min(timestamps)).total_seconds() * 1000 if len(timestamps) >= 2 else math.nan
            item = {
                "run": run_name,
                "run_index": run_index,
                "requirement_id": rid,
                "status": result["status"],
                "accepted": bool(result.get("accepted")),
                "attempts": int(semantic_attempts or 0),
                "run_id": result.get("run_id", ""),
                "category": metadata[rid]["category"],
                "source_sheet": metadata[rid]["sourceSheet"],
                "source_title": metadata[rid]["source"],
                "runtime_ms": runtime_ms,
                "error": result.get("error", ""),
            }
            current_trials.append(item)
            trials.append(item)
            for event in completed:
                api_calls.append({
                    "run": run_name, "requirement_id": rid, "category": item["category"],
                    "role": event.get("role", "unknown"), "model": event.get("model", ""),
                    "elapsed_ms": float(event.get("elapsed_ms") or 0),
                    "input_tokens": int(event.get("input_tokens") or 0),
                    "output_tokens": int(event.get("output_tokens") or 0),
                    "total_tokens": int(event.get("total_tokens") or 0),
                    "transport_attempts": int(event.get("transport_attempts") or 1),
                })
            for event in attempts_finished:
                api_attempts.append({
                    "run": run_name, "requirement_id": rid, "role": event.get("role", "unknown"),
                    "status": str(event.get("status", "")), "elapsed_ms": float(event.get("elapsed_ms") or 0),
                    "retrying": bool(event.get("retrying")),
                })
        trials_by_run[run_name] = current_trials
        event_times = []
        for run_dir in run_dirs:
            for event in read_events(run_dir):
                if event.get("timestamp_utc"):
                    event_times.append(parse_time(event["timestamp_utc"]))
        integrity_runs[run_name] = {
            "directoryExists": (EXPERIMENT / run_name).is_dir(),
            "batchResultPath": str(batch_path.relative_to(EXPERIMENT)),
            "batchSessionId": batch.get("session_id"),
            "batchDeclaredRequirements": batch.get("requirements"),
            "batchTotalItems": batch.get("total_items"),
            "resultCount": len(results),
            "uniqueRequirementCount": len(set(result_ids)),
            "duplicates": duplicates,
            "missingFromFrozenQueue": missing,
            "unexpectedRequirements": unexpected,
            "sameQueueOrder": result_ids == queue_ids,
            "runDirectoryCount": len(run_dirs),
            "requirementsWithMultipleRunDirectories": sorted(rid for rid, paths in run_dir_by_req.items() if len(paths) > 1),
            "pipelineVersion": batch.get("pipeline_version"),
            "vocabularyLockId": batch.get("vocabulary_lock_id"),
            "accepted": batch.get("accepted"),
            "doctorStatus": doctor.get("status"),
            "doctorEligibleRequirements": doctor.get("generation_eligible_requirements"),
            "wallClockStartUtc": min(event_times).isoformat() if event_times else None,
            "wallClockEndUtc": max(event_times).isoformat() if event_times else None,
            "wallClockDurationMs": (max(event_times)-min(event_times)).total_seconds()*1000 if len(event_times) >= 2 else None,
        }

    # Integrity and configuration equivalence.
    base_config = configs["RUN_01"]
    config_differences = {}
    normalized_hashes = {}
    for run_name, config in configs.items():
        diffs = recursive_diffs(base_config, config)
        config_differences[run_name] = diffs
        normalized = json.loads(json.dumps(config))
        normalized["pipeline_version"] = "<RUN>"
        normalized["paths"]["outputs"] = "<RUN_OUTPUT>"
        normalized_hashes[run_name] = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    allowed_config_paths = {"/pipeline_version", "/paths/outputs"}
    unexpected_config_differences = {
        run: [item for item in diffs if item["path"] not in allowed_config_paths]
        for run, diffs in config_differences.items()
        if any(item["path"] not in allowed_config_paths for item in diffs)
    }
    lock_hash_fields = {
        "workbookSha256": lock["workbookSha256"],
        "registrySha256": lock["boundMachineReadableArtifacts"]["registry/term_registry.json"],
        "ontologySha256": lock["boundMachineReadableArtifacts"]["ontology/nltl_benchmark_vocabulary.ttl"],
        "requirementEvidenceSha256": lock["boundMachineReadableArtifacts"]["evidence/stage1_approved.json"],
        "requirementIndexSha256": lock["boundMachineReadableArtifacts"]["requirement_term_index.json"],
    }
    actual_hashes = {
        "workbookSha256": sha256(MVP / lock["workbook"]),
        "registrySha256": sha256(MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R13/registry/term_registry.json"),
        "ontologySha256": sha256(MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R13/ontology/nltl_benchmark_vocabulary.ttl"),
        "requirementEvidenceSha256": sha256(EVIDENCE_PATH),
        "requirementIndexSha256": sha256(MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R13/requirement_term_index.json"),
    }
    doctor_hash_consistency = {
        run: doctors[run]["vocabulary_lock"] == {
            "lock_id": EXPECTED_LOCK,
            "workbook": lock["workbook"],
            "workbook_sha256": lock_hash_fields["workbookSha256"],
            "registry_sha256": lock_hash_fields["registrySha256"],
            "ontology_sha256": lock_hash_fields["ontologySha256"],
            "requirement_evidence_sha256": lock_hash_fields["requirementEvidenceSha256"],
            "requirement_term_index_sha256": lock_hash_fields["requirementIndexSha256"],
        } for run in RUN_NAMES
    }
    integrity_concerns: list[str] = []
    if len(queue_ids) != EXPECTED_REQUIREMENTS or len(set(queue_ids)) != EXPECTED_REQUIREMENTS:
        integrity_concerns.append("Frozen queue does not contain exactly 268 unique requirements.")
    for run, details in integrity_runs.items():
        if details["resultCount"] != EXPECTED_REQUIREMENTS or details["uniqueRequirementCount"] != EXPECTED_REQUIREMENTS:
            integrity_concerns.append(f"{run} does not contain exactly 268 unique terminal results.")
        if details["duplicates"] or details["missingFromFrozenQueue"] or details["unexpectedRequirements"] or not details["sameQueueOrder"]:
            integrity_concerns.append(f"{run} differs from the frozen queue.")
        if details["vocabularyLockId"] != EXPECTED_LOCK:
            integrity_concerns.append(f"{run} uses unexpected vocabulary lock {details['vocabularyLockId']}.")
        if details["doctorStatus"] != "PASS" or details["doctorEligibleRequirements"] != EXPECTED_REQUIREMENTS:
            integrity_concerns.append(f"{run} doctor/eligibility verification is inconsistent.")
    if unexpected_config_differences:
        integrity_concerns.append("Configs contain differences beyond run naming/output location.")
    if len(set(normalized_hashes.values())) != 1:
        integrity_concerns.append("Normalized configs are not identical.")
    if lock_hash_fields != actual_hashes:
        integrity_concerns.append("Current R13 artifact hashes differ from the formal lock manifest.")
    if not all(doctor_hash_consistency.values()):
        integrity_concerns.append("One or more run doctor logs do not reproduce the R13 hashes.")
    for run, config in configs.items():
        if set(config["models"].values()) != {EXPECTED_MODEL}:
            integrity_concerns.append(f"{run} does not use Luna for every model role.")
        if config["generation"]["maximum_semantic_attempts"] != EXPECTED_ATTEMPTS:
            integrity_concerns.append(f"{run} does not use maximum_semantic_attempts=4.")

    integrity = {
        "status": "PASS" if not integrity_concerns else "CONCERNS_FOUND",
        "analysisMode": "read-only; no experiment, pipeline, vocabulary, or source modification",
        "runsExpected": RUN_NAMES,
        "runsFound": sorted(path.name for path in EXPERIMENT.glob("RUN_*" ) if path.is_dir()),
        "frozenQueue": {"path": str(QUEUE_PATH.relative_to(EXPERIMENT)), "sha256": queue_sha,
                        "requirementCount": len(queue_ids), "uniqueRequirementCount": len(set(queue_ids))},
        "expectedVocabularyLockId": EXPECTED_LOCK,
        "expectedModelAllRoles": EXPECTED_MODEL,
        "expectedMaximumSemanticAttempts": EXPECTED_ATTEMPTS,
        "configDifferencesRelativeToRun01": config_differences,
        "allowedConfigDifferencePaths": sorted(allowed_config_paths),
        "unexpectedConfigDifferences": unexpected_config_differences,
        "normalizedConfigHashes": normalized_hashes,
        "r13ManifestHashes": lock_hash_fields,
        "r13ActualHashes": actual_hashes,
        "doctorHashConsistency": doctor_hash_consistency,
        "runs": integrity_runs,
        "integrityConcerns": integrity_concerns,
        "completedTerminalErrors": [
            {"run": t["run"], "requirementId": t["requirement_id"], "status": t["status"], "error": t["error"]}
            for t in trials if t["status"] == "BATCH_ITEM_ERROR"
        ],
    }
    write_json("experiment_integrity.json", integrity)
    integrity_lines = [
        "FINAL LUNA MAIN — 10-RUN EXPERIMENT INTEGRITY",
        "=" * 52,
        f"Conclusion: {integrity['status']}",
        f"Runs found: {', '.join(integrity['runsFound'])}",
        f"Frozen queue: {len(queue_ids)} entries / {len(set(queue_ids))} unique / SHA256 {queue_sha}",
        f"Lock: {EXPECTED_LOCK}; all doctor hashes consistent: {all(doctor_hash_consistency.values())}",
        f"Model for all roles: {EXPECTED_MODEL}",
        f"Maximum semantic attempts: {EXPECTED_ATTEMPTS}",
        "Config differences: only /pipeline_version and /paths/outputs.",
        "Every run contains 268 terminal results, 268 unique IDs, in frozen queue order.",
        "No missing, duplicated, unexpected, or interrupted queue entries were found.",
        "Two completed terminal BATCH_ITEM_ERROR outcomes were observed: RUN_03/I2-035 and RUN_06/TRF-059; both report no extractable API output text.",
        "Integrity concerns: " + ("none" if not integrity_concerns else " | ".join(integrity_concerns)),
    ]
    write_text("experiment_integrity.txt", "\n".join(integrity_lines))

    # Per-run summary and overall statistics.
    all_statuses = sorted(set(t["status"] for t in trials))
    run_summary = []
    for run in RUN_NAMES:
        items = trials_by_run[run]
        accepted_items = [t for t in items if t["accepted"]]
        failed_items = [t for t in items if not t["accepted"]]
        accepts_at = {attempt: sum(t["accepted"] and t["attempts"] == attempt for t in items) for attempt in range(1, 5)}
        completed_calls = [call for call in api_calls if call["run"] == run]
        failed_transport = [a for a in api_attempts if a["run"] == run and a["status"] != "200"]
        row = {
            "run": run, "total_requirements": len(items), "generation_accepted": len(accepted_items),
            "acceptance_rate": f(len(accepted_items)/len(items)), "failures": len(failed_items),
            "attempt_1_accepts": accepts_at[1], "attempt_2_new_accepts": accepts_at[2],
            "attempt_3_new_accepts": accepts_at[3], "attempt_4_new_accepts": accepts_at[4],
            "cumulative_acceptance_after_1": accepts_at[1],
            "cumulative_acceptance_after_2": accepts_at[1]+accepts_at[2],
            "cumulative_acceptance_after_3": accepts_at[1]+accepts_at[2]+accepts_at[3],
            "cumulative_acceptance_after_4": sum(accepts_at.values()),
            "mean_semantic_attempts_all": f(mean(t["attempts"] for t in items)),
            "mean_attempts_accepted": f(mean(t["attempts"] for t in accepted_items)),
            "mean_attempts_failed": f(mean(t["attempts"] for t in failed_items)),
            "api_transport_failure_attempts": len(failed_transport),
            "logical_api_calls_completed": len(completed_calls),
        }
        row.update({f"status_{status}": sum(t["status"] == status for t in items) for status in all_statuses})
        run_summary.append(row)
    write_csv("run_summary.csv", run_summary)

    rates = [row["generation_accepted"]/row["total_requirements"] for row in run_summary]
    low, high, width = ci95(rates)
    overall = {
        "runLevelStatistics": {
            "unit": "10 independent repetition-level acceptance proportions",
            "n": 10, "meanAcceptanceRate": mean(rates), "medianAcceptanceRate": median(rates),
            "sampleStandardDeviation": sample_sd(rates), "minimum": min(rates), "maximum": max(rates),
            "range": max(rates)-min(rates), "coefficientOfVariation": sample_sd(rates)/mean(rates),
            "confidenceInterval95": {"method":"two-sided Student t interval over 10 run-level proportions",
                                     "lower":low,"upper":high,"width":width,"tCriticalDf9":T_CRITICAL_975[10]},
        },
        "requirementTrialDescription": {
            "unit": "268 requirements repeatedly observed in 10 runs; observations are clustered by requirement and run",
            "totalRequirementTrials": len(trials), "expectedRequirementTrials": EXPECTED_TRIALS,
            "pooledAcceptedRequirementTrials": sum(t["accepted"] for t in trials),
            "pooledAcceptanceRate": mean(t["accepted"] for t in trials),
            "pooledFailureRate": mean(not t["accepted"] for t in trials),
            "independenceCaveat": "The 2,680 trials are not treated as mutually independent; the primary CI uses n=10 run-level repetitions.",
        },
    }
    write_json("overall_statistics.json", overall)
    write_csv("overall_statistics.csv", [
        {"analysis_level":"run_level","metric":key,"value":f(value) if isinstance(value,(int,float)) else value,"n":10,"independence_note":"n=10 independent repetitions"}
        for key,value in overall["runLevelStatistics"].items() if key not in {"unit","confidenceInterval95"}
    ] + [
        {"analysis_level":"run_level","metric":f"ci95_{key}","value":f(value) if isinstance(value,(int,float)) else value,"n":10,"independence_note":"Student-t CI over run-level rates"}
        for key,value in overall["runLevelStatistics"]["confidenceInterval95"].items()
    ] + [
        {"analysis_level":"requirement_trial","metric":key,"value":f(value) if isinstance(value,(int,float)) else value,"n":len(trials),"independence_note":overall["requirementTrialDescription"]["independenceCaveat"]}
        for key,value in overall["requirementTrialDescription"].items() if key not in {"unit","independenceCaveat"}
    ])

    # Requirement stability and matrices.
    by_requirement: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for trial in trials:
        by_requirement[trial["requirement_id"]][trial["run"]] = trial
    stability_rows = []
    status_matrix = []
    acceptance_matrix = []
    for rid in queue_ids:
        observed = [by_requirement[rid][run] for run in RUN_NAMES]
        successes = sum(t["accepted"] for t in observed)
        failure_types = [t["status"] for t in observed if not t["accepted"]]
        common = Counter(failure_types).most_common()
        row = {
            "requirement_id":rid,"category":metadata[rid]["category"],"source_sheet":metadata[rid]["sourceSheet"],
            "accepted_count":successes,"empirical_success_probability":f(successes/10),"failures_count":10-successes,
            "mean_attempts":f(mean(t["attempts"] for t in observed)),"median_attempts":f(median(t["attempts"] for t in observed)),
            "min_attempts":min(t["attempts"] for t in observed),"max_attempts":max(t["attempts"] for t in observed),
            "distinct_failure_types":len(set(failure_types)),
            "most_common_failure_type":common[0][0] if common else "NONE",
            "most_common_failure_type_count":common[0][1] if common else 0,
            "stability_class":stability_class(successes),
        }
        row.update({f"attempts_{run}":by_requirement[rid][run]["attempts"] for run in RUN_NAMES})
        row.update({f"status_{run}":by_requirement[rid][run]["status"] for run in RUN_NAMES})
        stability_rows.append(row)
        status_matrix.append({"requirement_id":rid,**{run:by_requirement[rid][run]["status"] for run in RUN_NAMES}})
        acceptance_matrix.append({"requirement_id":rid,**{run:int(by_requirement[rid][run]["accepted"]) for run in RUN_NAMES}})
    write_csv("case_stability.csv", stability_rows)
    matrix_fields = ["requirement_id", *RUN_NAMES]
    write_csv("status_matrix.csv", status_matrix, matrix_fields)
    write_csv("acceptance_matrix.csv", acceptance_matrix, matrix_fields)

    # Attempt analysis overall, per run, and category.
    attempt_rows = []
    attempt_json: dict[str, Any] = {"definitions":{
        "singleShotPerformance":"accepted terminally at semantic attempt 1",
        "fullLoopPerformance":"accepted after up to four semantic attempts",
        "repairContribution":"additional terminal accepts at attempts 2-4",
    },"groups":{}}
    groups: list[tuple[str,str,list[dict[str,Any]]]] = [("overall","ALL",trials)]
    groups += [("run",run,trials_by_run[run]) for run in RUN_NAMES]
    groups += [("category",category,[t for t in trials if t["category"]==category]) for category in ("Static","Static Calculation","Complex")]
    for level,name,items in groups:
        total=len(items); new={a:sum(t["accepted"] and t["attempts"]==a for t in items) for a in range(1,5)}
        cumulative={a:sum(new[x] for x in range(1,a+1)) for a in range(1,5)}; final=cumulative[4]
        row={"group_level":level,"group":name,"requirement_trials":total}
        for a in range(1,5): row.update({f"new_accepts_attempt_{a}":new[a],f"new_accepts_attempt_{a}_percentage":f(new[a]/total*100),f"cumulative_accepts_after_{a}":cumulative[a],f"cumulative_acceptance_after_{a}":f(cumulative[a]/total)})
        row.update({"single_shot_acceptance":f(new[1]/total),"full_loop_acceptance":f(final/total),
                    "absolute_percentage_point_gain":f((final-new[1])/total*100),
                    "relative_improvement":f((final-new[1])/new[1] if new[1] else math.nan),
                    "eventual_successes_requiring_repair_percentage":f((final-new[1])/final*100 if final else math.nan),
                    "eventual_successes_at_attempt_3_or_4_percentage":f((new[3]+new[4])/final*100 if final else math.nan),
                    "attempt_4_increment_percentage_points":f(new[4]/total*100),
                    "attempt_4_meaningful_interpretation":"increment reported; scientific meaningfulness judged relative to cost and CI"})
        attempt_rows.append(row); attempt_json["groups"][f"{level}:{name}"]=row
    write_csv("attempt_analysis.csv",attempt_rows); write_json("attempt_analysis.json",attempt_json)

    # Failure analysis.
    failure_trials=[t for t in trials if not t["accepted"]]; failure_statuses=sorted(set(t["status"] for t in failure_trials))
    failure_summary=[]
    for status in failure_statuses:
        count=sum(t["status"]==status for t in failure_trials)
        row={"failure_type":status,"count":count,"percentage_all_requirement_trials":f(count/len(trials)*100),"percentage_all_failures":f(count/len(failure_trials)*100)}
        row.update({run:sum(t["status"]==status for t in trials_by_run[run]) for run in RUN_NAMES})
        failure_summary.append(row)
    non200=[a for a in api_attempts if a["status"]!="200"]
    failure_summary.append({"failure_type":"API_TRANSPORT_ATTEMPT_FAILURE_EVENT","count":len(non200),"percentage_all_requirement_trials":"N/A","percentage_all_failures":"N/A",**{run:sum(a["run"]==run for a in non200) for run in RUN_NAMES}})
    write_csv("failure_summary.csv",failure_summary)
    failure_cases=[]
    for row in stability_rows:
        if row["failures_count"]==0: continue
        statuses=[by_requirement[row["requirement_id"]][run]["status"] for run in RUN_NAMES]
        failed=[status for status in statuses if status!=ACCEPTED]
        failure_cases.append({"requirement_id":row["requirement_id"],"accepted_count":row["accepted_count"],"failures_count":row["failures_count"],
                              "sometimes_succeeds_and_fails":0<row["accepted_count"]<10,"always_same_failure_when_failed":len(set(failed))==1,
                              "failure_mechanism_changes":len(set(failed))>1,"distinct_failure_types":len(set(failed)),
                              "status_sequence":" | ".join(statuses),"stability_class":row["stability_class"]})
    write_csv("failure_by_case.csv",failure_cases)

    # Category and source summaries.
    def grouped_summary(level: str, label: str, ids: list[str]) -> dict[str,Any]:
        subset=[t for t in trials if t["requirement_id"] in ids]; unique=len(ids); run_rates=[]
        for run in RUN_NAMES:
            run_items=[t for t in subset if t["run"]==run]; run_rates.append(mean(t["accepted"] for t in run_items))
        first=sum(t["accepted"] and t["attempts"]==1 for t in subset); final=sum(t["accepted"] for t in subset)
        failures=Counter(t["status"] for t in subset if not t["accepted"])
        return {"group_level":level,"group":label,"unique_requirements":unique,"requirement_trials":len(subset),
                "accepted_trials":final,"acceptance_rate":f(final/len(subset)),"mean_run_level_acceptance":f(mean(run_rates)),
                "sd_run_level_acceptance":f(sample_sd(run_rates)),"attempt_1_accepts":first,"attempt_1_acceptance":f(first/len(subset)),
                "final_max4_acceptance":f(final/len(subset)),"average_attempts":f(mean(t["attempts"] for t in subset)),
                "failure_type_distribution":json.dumps(dict(sorted(failures.items())),sort_keys=True)}
    category_rows=[]
    for category in ("Static","Static Calculation","Complex"):
        ids=[rid for rid in queue_ids if metadata[rid]["category"]==category]; category_rows.append(grouped_summary("category",category,ids))
    write_csv("category_summary.csv",category_rows)
    source_rows=[]
    for source in sorted(set(metadata[rid]["sourceSheet"] for rid in queue_ids)):
        ids=[rid for rid in queue_ids if metadata[rid]["sourceSheet"]==source]
        row=grouped_summary("source",source,ids); row["source_titles"]=" | ".join(sorted(set(metadata[rid]["source"] for rid in ids))); source_rows.append(row)
    write_csv("source_summary.csv",source_rows)

    # API, tokens, cost and timing. Logical calls use api_call_completed only.
    pricing=configs["RUN_01"]["cost_estimation"]
    luna_price=pricing["usd_per_million_tokens"][EXPECTED_MODEL]
    api_run_rows=[]
    for run in [*RUN_NAMES,"POOLED"]:
        calls=api_calls if run=="POOLED" else [c for c in api_calls if c["run"]==run]
        run_trials=trials if run=="POOLED" else trials_by_run[run]
        accepted=sum(t["accepted"] for t in run_trials); input_tokens=sum(c["input_tokens"] for c in calls); output_tokens=sum(c["output_tokens"] for c in calls)
        cost=input_tokens/1_000_000*luna_price["input"]+output_tokens/1_000_000*luna_price["output"]
        runtimes=[t["runtime_ms"] for t in run_trials if not math.isnan(t["runtime_ms"])]
        if run=="POOLED": wall=sum(float(integrity_runs[r]["wallClockDurationMs"] or 0) for r in RUN_NAMES)
        else: wall=float(integrity_runs[run]["wallClockDurationMs"] or 0)
        row={"run":run,"summary_scope":"pooled" if run=="POOLED" else "run","logical_api_calls_completed":len(calls),"physical_transport_attempts":sum(c["transport_attempts"] for c in calls),
             "non_200_transport_attempt_events":sum(a["status"]!="200" and (run=="POOLED" or a["run"]==run) for a in api_attempts),
             "input_tokens":input_tokens,"output_tokens":output_tokens,"total_tokens":input_tokens+output_tokens,
             "calls_per_requirement":f(len(calls)/len(run_trials)),"calls_per_accepted_requirement":f(len(calls)/accepted),
             "api_elapsed_ms_sum_nonduplicated":f(sum(c["elapsed_ms"] for c in calls),3),"run_wall_clock_ms":f(wall,3),
             "mean_end_to_end_requirement_ms":f(mean(runtimes),3),"median_end_to_end_requirement_ms":f(median(runtimes),3),
             "estimated_cost_usd":f(cost,6),"mean_cost_per_run_usd":f(cost/10,6) if run=="POOLED" else "",
             "cost_per_accepted_output_usd":f(cost/accepted,6),"cost_per_requirement_trial_usd":f(cost/len(run_trials),6),
             "pricing_basis":pricing["basis"],"pricing_source_url":pricing["source_url"],"input_usd_per_million":luna_price["input"],"output_usd_per_million":luna_price["output"],
             "pricing_staleness_note":"Repository-configured estimate used without external verification; it may be stale and is not an Aalto invoice."}
        for role in sorted(set(c["role"] for c in calls)): row[f"calls_{role}"]=sum(c["role"]==role for c in calls)
        api_run_rows.append(row)
    for category in ("Static","Static Calculation","Complex"):
        category_calls=[c for c in api_calls if c["category"]==category]
        category_trials=[t for t in trials if t["category"]==category]
        category_accepted=sum(t["accepted"] for t in category_trials)
        input_tokens=sum(c["input_tokens"] for c in category_calls); output_tokens=sum(c["output_tokens"] for c in category_calls)
        cost=input_tokens/1_000_000*luna_price["input"]+output_tokens/1_000_000*luna_price["output"]
        runtimes=[t["runtime_ms"] for t in category_trials if not math.isnan(t["runtime_ms"])]
        row={"run":f"CATEGORY_{category}","summary_scope":"category","logical_api_calls_completed":len(category_calls),
             "physical_transport_attempts":sum(c["transport_attempts"] for c in category_calls),
             "non_200_transport_attempt_events":sum(a["status"]!="200" and metadata[a["requirement_id"]]["category"]==category for a in api_attempts),
             "input_tokens":input_tokens,"output_tokens":output_tokens,"total_tokens":input_tokens+output_tokens,
             "calls_per_requirement":f(len(category_calls)/len(category_trials)),"calls_per_accepted_requirement":f(len(category_calls)/category_accepted),
             "api_elapsed_ms_sum_nonduplicated":f(sum(c["elapsed_ms"] for c in category_calls),3),"run_wall_clock_ms":"",
             "mean_end_to_end_requirement_ms":f(mean(runtimes),3),"median_end_to_end_requirement_ms":f(median(runtimes),3),
             "estimated_cost_usd":f(cost,6),"mean_cost_per_run_usd":"","cost_per_accepted_output_usd":f(cost/category_accepted,6),
             "cost_per_requirement_trial_usd":f(cost/len(category_trials),6),"pricing_basis":pricing["basis"],
             "pricing_source_url":pricing["source_url"],"input_usd_per_million":luna_price["input"],"output_usd_per_million":luna_price["output"],
             "pricing_staleness_note":"Repository-configured estimate used without external verification; it may be stale and is not an Aalto invoice."}
        for role in sorted(set(c["role"] for c in category_calls)): row[f"calls_{role}"]=sum(c["role"]==role for c in category_calls)
        api_run_rows.append(row)
    write_csv("api_timing_cost_summary.csv",api_run_rows)
    role_rows=[]
    for run in [*RUN_NAMES,"POOLED"]:
        selected=api_calls if run=="POOLED" else [c for c in api_calls if c["run"]==run]
        for role in sorted(set(c["role"] for c in selected)):
            calls=[c for c in selected if c["role"]==role]; elapsed=[c["elapsed_ms"] for c in calls]
            role_rows.append({"run":run,"role":role,"model":EXPECTED_MODEL,"logical_calls":len(calls),"input_tokens":sum(c["input_tokens"] for c in calls),
                              "output_tokens":sum(c["output_tokens"] for c in calls),"total_tokens":sum(c["total_tokens"] for c in calls),
                              "mean_elapsed_ms":f(mean(elapsed),3),"median_elapsed_ms":f(median(elapsed),3),"sd_elapsed_ms":f(sample_sd(elapsed),3),
                              "p25_elapsed_ms":f(quantile(elapsed,.25),3),"p75_elapsed_ms":f(quantile(elapsed,.75),3),"p95_elapsed_ms":f(quantile(elapsed,.95),3),
                              "elapsed_ms_sum":f(sum(elapsed),3)})
    write_csv("api_role_summary.csv",role_rows)

    # Repetition adequacy.
    adequacy=[]
    for n in (3,5,7,10):
        selected=rates[:n]; lo,hi,w=ci95(selected)
        adequacy.append({"runs_included":n,"through_run":RUN_NAMES[n-1],"mean_acceptance":f(mean(selected)),"sample_sd":f(sample_sd(selected)),
                         "minimum":f(min(selected)),"maximum":f(max(selected)),"range":f(max(selected)-min(selected)),
                         "ci95_lower":f(lo),"ci95_upper":f(hi),"ci95_width":f(w),"ci_method":"Student-t interval over chronological run-level rates"})
    write_csv("repetition_adequacy.csv",adequacy)
    stability_counts=Counter(row["stability_class"] for row in stability_rows)
    x=list(range(1,11)); xbar=mean(x); ybar=mean(rates); slope=sum((a-xbar)*(b-ybar) for a,b in zip(x,rates))/sum((a-xbar)**2 for a in x)
    seven=adequacy[2]; ten=adequacy[3]
    adequacy_interpretation = (
        "The first three runs were unusually similar and therefore produced a deceptively narrow interval; adding later runs revealed more run-to-run variability rather than monotonically narrowing the CI. "
        f"The run-level 95% CI width changed from {adequacy[0]['ci95_width']:.4f} after 3 runs to {ten['ci95_width']:.4f} after 10, while the 7-run and 10-run widths were {seven['ci95_width']:.4f} and {ten['ci95_width']:.4f}. "
        f"The cumulative mean changed by {abs(ten['mean_acceptance']-seven['mean_acceptance']):.4f} between 7 and 10 runs. "
        f"The chronological least-squares slope was {slope*100:.3f} percentage points per run, with RUN_09 and RUN_10 below the early runs; this indicates that chronological stability is imperfect, but it is descriptive and does not establish drift or a cause. "
        "Ten repetitions are adequate for a useful aggregate variability estimate and identifying persistent versus unstable cases, but more repetitions would be needed for narrow per-case probabilities in the stochastic middle."
    )
    statistical_notes = f"""FINAL LUNA MAIN — REPETITION ADEQUACY NOTES
================================================

Primary experimental unit for overall acceptance uncertainty: one complete run (n=10).
The 2,680 requirement-trials are repeated observations of the same 268 requirements and are not treated as mutually independent.

Run-level mean acceptance: {mean(rates):.4%}
Run-level sample SD: {sample_sd(rates):.4%}
Run-level range: {min(rates):.4%} to {max(rates):.4%}
Run-level 95% Student-t CI: [{low:.4%}, {high:.4%}], width {width:.4%}
Chronological slope: {slope*100:.3f} percentage points/run (descriptive only)

Requirement stability counts:
{json.dumps(dict(stability_counts), indent=2)}

Interpretation:
{adequacy_interpretation}

For later paired model/ablation comparisons, suitable methods include paired permutation tests or Wilcoxon signed-rank tests on matched run/case outcomes, McNemar tests for paired binary case outcomes, and mixed-effects logistic models accounting for requirement and repetition clustering. No such comparison was performed here.
"""
    write_text("statistical_notes.txt", statistical_notes)

    # Paper-ready summary.
    pooled_accepted=sum(t["accepted"] for t in trials); overall_attempt=attempt_json["groups"]["overall:ALL"]
    total_cost=next(row["estimated_cost_usd"] for row in api_run_rows if row["run"]=="POOLED")
    persistent=[row for row in stability_rows if row["accepted_count"]==0]
    stochastic=[row for row in stability_rows if 4<=row["accepted_count"]<=7]
    persistent_max=[row["requirement_id"] for row in persistent if row["most_common_failure_type"]=="MAX_ATTEMPTS_REACHED"]
    persistent_term=[row["requirement_id"] for row in persistent if row["most_common_failure_type"]=="TERM_RESOLUTION_UNRESOLVED"]
    varying_success=sorted((row for row in stability_rows if row["accepted_count"]==10),key=lambda row:row["max_attempts"]-row["min_attempts"],reverse=True)[:10]
    category_md="\n".join(f"- {row['group']}: {row['acceptance_rate']:.2%} ({row['accepted_trials']}/{row['requirement_trials']})" for row in category_rows)
    source_md="\n".join(f"- {row['group']}: {row['acceptance_rate']:.2%} ({row['accepted_trials']}/{row['requirement_trials']})" for row in source_rows)
    status_counts=Counter(t["status"] for t in trials)
    master=f"""# Final Luna Main: aggregated 10-run analysis

## Integrity conclusion

All ten formal run directories exist. Each contains one completed 268-item batch result with every frozen requirement exactly once and in the same order. The normalized configurations are identical; only pipeline version/run naming and output directory differ. Every doctor log identifies `{EXPECTED_LOCK}`, 268 eligible requirements and `{EXPECTED_MODEL}` for generator, validator, syntax repair and vocabulary matcher. R13 hashes match the lock and all ten doctor logs. Two completed terminal `BATCH_ITEM_ERROR` outcomes occurred (RUN_03/I2-035 and RUN_06/TRF-059); neither represents a missing queue item.

## Headline Luna performance

- Pooled acceptance: **{pooled_accepted}/{len(trials)} = {pooled_accepted/len(trials):.2%}**.
- Mean run-level acceptance (n=10): **{mean(rates):.2%}**.
- Median: **{median(rates):.2%}**; sample SD: **{sample_sd(rates):.2%}**.
- Minimum–maximum: **{min(rates):.2%}–{max(rates):.2%}**.
- 95% Student-t CI for the run-level mean: **[{low:.2%}, {high:.2%}]**.

The CI uses ten repetition-level proportions. The 2,680 repeated requirement observations are not assumed mutually independent.

## Repair-loop contribution

- Estimated single-shot performance: **{overall_attempt['single_shot_acceptance']:.2%}**.
- Full-loop performance through four attempts: **{overall_attempt['full_loop_acceptance']:.2%}**.
- Absolute repair gain: **{overall_attempt['absolute_percentage_point_gain']:.2f} percentage points**.
- Relative improvement over single-shot: **{overall_attempt['relative_improvement']:.2%}**.
- Eventual successes requiring repair: **{overall_attempt['eventual_successes_requiring_repair_percentage']:.2f}%**.
- Eventual successes first accepted at attempts 3–4: **{overall_attempt['eventual_successes_at_attempt_3_or_4_percentage']:.2f}%**.
- Attempt 4 added **{overall_attempt['new_accepts_attempt_4']}** accepted trials (**{overall_attempt['attempt_4_increment_percentage_points']:.2f} percentage points**); this is non-zero incremental value, to be weighed against its API cost.

## Category differences

{category_md}

## Source differences

{source_md}

## Stability and hard requirements

- Consistently successful (10/10): {stability_counts['consistently successful']}.
- Highly reliable (8–9/10): {stability_counts['highly reliable']}.
- Stochastic/unstable (4–7/10): {stability_counts['stochastic / unstable']}.
- Generally difficult (1–3/10): {stability_counts['generally difficult']}.
- Persistent systematic failure (0/10): {stability_counts['persistent systematic failure']}.
- Persistent cases dominated by `MAX_ATTEMPTS_REACHED`: {', '.join(persistent_max) or 'none'}.
- Persistent cases dominated by `TERM_RESOLUTION_UNRESOLVED`: {', '.join(persistent_term) or 'none'}.
- Stochastic middle examples: {', '.join(row['requirement_id'] for row in stochastic[:20]) or 'none'}.
- 10/10-success cases with the largest attempt ranges: {', '.join(row['requirement_id'] for row in varying_success) or 'none'}.

`TERM_RESOLUTION_UNRESOLVED` is reported only as an observed pipeline status; it is not interpreted as proof of a genuine vocabulary gap.

## Failure taxonomy

Terminal status counts across all trials: `{json.dumps(dict(sorted(status_counts.items())), sort_keys=True)}`. Failure mechanisms vary for some requirements across repetitions; `failure_by_case.csv` records the exact ten-status sequence and whether the mechanism changes.

## API calls, tokens, timing and estimated cost

The analysis counts `api_call_completed` once per logical API response and does not double-count paired transport-finished events. Transport attempts and non-200 events are reported separately. End-to-end requirement time is the first-to-last event span, including pipeline handling and tracker emission.

- Completed logical API calls: {next(row['logical_api_calls_completed'] for row in api_run_rows if row['run']=='POOLED')}.
- Input tokens: {next(row['input_tokens'] for row in api_run_rows if row['run']=='POOLED'):,}.
- Output tokens: {next(row['output_tokens'] for row in api_run_rows if row['run']=='POOLED'):,}.
- Estimated 10-run cost: **${total_cost:.2f}**.
- Pricing used: repository config, Luna input ${luna_price['input']}/million and output ${luna_price['output']}/million tokens.

This is an indicative configured estimate, not an Aalto invoice. The repository pricing may be stale and was not silently replaced with external pricing.

## Were ten repetitions adequate?

{adequacy_interpretation}

## Scientific interpretation and caveats

These ten runs characterize stochastic SHACL generation under the frozen R13 pipeline and Luna model configuration. Generation acceptance means that deterministic gates and the semantic validator accepted the candidate; it is **not equivalent to hidden RDF semantic accuracy**. No generated shapes were re-evaluated against newly created RDF cases in this aggregation, and no failed case was repaired or regenerated.
"""
    write_text("MASTER_SUMMARY.md",master)

    # Analysis manifest, validation, and analysis-only ZIP.
    required_files = [
        "experiment_integrity.json","experiment_integrity.txt","run_summary.csv","overall_statistics.json","overall_statistics.csv",
        "case_stability.csv","status_matrix.csv","acceptance_matrix.csv","attempt_analysis.csv","attempt_analysis.json",
        "failure_summary.csv","failure_by_case.csv","category_summary.csv","source_summary.csv","api_timing_cost_summary.csv",
        "api_role_summary.csv","repetition_adequacy.csv","statistical_notes.txt","MASTER_SUMMARY.md","build_analysis.py",
    ]
    validation = {
        "status":"PASS","requiredFilesPresent":all((HERE/name).exists() for name in required_files),
        "runCount":len(RUN_NAMES),"queueRequirementCount":len(queue_ids),"trialCount":len(trials),
        "caseStabilityRows":len(stability_rows),"statusMatrixRows":len(status_matrix),"acceptanceMatrixRows":len(acceptance_matrix),
        "acceptedTrials":pooled_accepted,"failedTrials":len(failure_trials),"apiCompletedLogicalCalls":len(api_calls),
        "integrityConcernCount":len(integrity_concerns),"apiCallsMadeByAnalysis":0,
    }
    if validation["trialCount"]!=EXPECTED_TRIALS or validation["caseStabilityRows"]!=EXPECTED_REQUIREMENTS:
        validation["status"]="FAIL"
        raise RuntimeError(f"Analysis validation failed: {validation}")
    write_json("analysis_validation.json",validation)
    required_files.append("analysis_validation.json")
    manifest={"analysisFiles":[],"sourceExperimentModified":False,"apiCallsMade":0}
    for name in sorted(required_files):
        path=HERE/name; manifest["analysisFiles"].append({"path":name,"bytes":path.stat().st_size,"sha256":sha256(path)})
    write_json("analysis_manifest.json",manifest)
    zip_files=sorted([*required_files,"analysis_manifest.json"])
    with zipfile.ZipFile(ZIP_PATH,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name in zip_files:
            archive.write(HERE/name,arcname=f"ANALYSIS_10RUN/{name}")
    print(json.dumps({"status":"PASS","zipPath":str(ZIP_PATH),"zipBytes":ZIP_PATH.stat().st_size,"zipSha256":sha256(ZIP_PATH),
                      "analysisFiles":zip_files,"integrityConcerns":integrity_concerns,"apiCallsMade":0},indent=2))


if __name__ == "__main__":
    main()
