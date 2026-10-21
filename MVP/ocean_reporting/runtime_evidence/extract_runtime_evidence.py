#!/usr/bin/env python3
"""Extract existing runtime and iteration evidence without executing experiments."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT = Path("/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2")
MVP = PROJECT / "MVP"
PIPELINE = MVP / "SHACL_GENERATION_PIPELINE"
EXPERIMENTS = PIPELINE / "experiments"


EXPERIMENT_SPECS = [
    {
        "experiment": "LUNA_NO_SEMANTIC_VALIDATOR",
        "publication_label": "NLTL_v2",
        "scope": "main_paper_formal_repetitions",
        "subset": "268-requirement full benchmark",
        "roots": [EXPERIMENTS / "LUNA_NO_SEMANTIC_VALIDATOR" / f"RUN_{i:02d}" for i in range(1, 11)],
        "success_rule": "Completed output is successful when deterministic_valid is true and the recorded candidate shape exists; accepted=False is not treated as failure because semantic acceptance was disabled.",
    },
    {
        "experiment": "LUNA_CONTEXTUAL_SINGLESHOT",
        "publication_label": "Single-shot",
        "scope": "main_paper_selected_run",
        "subset": "268-requirement full benchmark",
        "roots": [EXPERIMENTS / "LUNA_CONTEXTUAL_SINGLESHOT" / "RUN_01"],
        "success_rule": "Completed output is successful when deterministic_valid is true and the recorded extracted or final shape exists.",
    },
    {
        "experiment": "FULL_REPAIR_V2",
        "publication_label": "Full repair reference",
        "scope": "model_scaling_luna_reference_source",
        "subset": "268-requirement full benchmark; 50-requirement subset referenced by scaling manifest",
        "roots": [EXPERIMENTS / "FULL_REPAIR_V2" / "RUN_01"],
        "success_rule": "Successful output requires GENERATION_ACCEPTED, accepted=True and a recorded final shape.",
    },
    {
        "experiment": "FINAL_LUNA_MAIN",
        "publication_label": "Historical full workflow",
        "scope": "supporting_10_run_experiment",
        "subset": "268-requirement full benchmark",
        "roots": [EXPERIMENTS / "FINAL_LUNA_MAIN" / f"RUN_{i:02d}" for i in range(1, 11)],
        "success_rule": "Successful output requires GENERATION_ACCEPTED, accepted=True and a recorded final shape.",
    },
    {
        "experiment": "MODEL_SCALING_FULL_REPAIR_V2_50",
        "publication_label": "Four-model comparison",
        "scope": "model_comparison_formal",
        "subset": "50-requirement stratified sample",
        "roots": [
            EXPERIMENTS / "MODEL_SCALING_FULL_REPAIR_V2_50" / "OUTPUTS" / "FINAL" / model
            for model in ("gemini", "gpt_oss", "sol")
        ],
        "success_rule": "Successful output requires GENERATION_ACCEPTED, accepted=True and a recorded final shape.",
    },
]


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def elapsed_seconds(start: str | None, finish: str | None) -> float | None:
    a, b = parse_time(start), parse_time(finish)
    if not a or not b:
        return None
    return (b - a).total_seconds()


def scalar(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return value


def read_events(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except Exception as exc:
            errors.append(f"{path}:{line_no}: {type(exc).__name__}: {exc}")
    return events, errors


def last_event(events: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return next((event for event in reversed(events) if event.get("event_type") == kind), {})


def first_event(events: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return next((event for event in events if event.get("event_type") == kind), {})


def path_exists(run_dir: Path, relative: str | None) -> bool:
    return bool(relative and (run_dir / relative).is_file())


def infer_repetition(run_dir: Path, root: Path) -> str:
    for part in root.parts:
        if part.startswith("RUN_"):
            return part
    return root.name


def extract_generation() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    runs: list[dict[str, Any]] = []
    iterations: list[dict[str, Any]] = []
    api_calls: list[dict[str, Any]] = []
    index: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    seen_runs: dict[str, str] = {}
    sample_manifest = json.loads((EXPERIMENTS / "MODEL_SCALING_FULL_REPAIR_V2_50" / "MANIFESTS" / "sample_50.json").read_text())
    scaling_requirements = {record["requirement_id"] for record in sample_manifest["records"]}

    for spec in EXPERIMENT_SPECS:
        exp_rows: list[dict[str, Any]] = []
        for root in spec["roots"]:
            if not root.exists():
                audit.append({"severity": "ERROR", "category": "missing_source", "experiment": spec["experiment"], "run_id": "", "detail": f"Expected formal root is missing: {root}"})
                continue
            for event_path in sorted(root.rglob("events.jsonl")):
                events, errors = read_events(event_path)
                for error in errors:
                    audit.append({"severity": "ERROR", "category": "invalid_jsonl", "experiment": spec["experiment"], "run_id": "", "detail": error})
                started = first_event(events, "run_started")
                finished = last_event(events, "run_finished")
                run_id = str(started.get("run_id") or finished.get("run_id") or event_path.parent.name)
                requirement_id = str(started.get("requirement_id") or finished.get("requirement_id") or "")
                source_path = str(event_path.relative_to(PROJECT))
                if run_id in seen_runs:
                    audit.append({"severity": "ERROR", "category": "duplicate_run_identity", "experiment": spec["experiment"], "run_id": run_id, "detail": f"Duplicate run in {source_path}; first seen in {seen_runs[run_id]}"})
                    continue
                seen_runs[run_id] = source_path

                completed_calls_raw = [event for event in events if event.get("event_type") == "api_call_completed"]
                completed_calls: list[dict[str, Any]] = []
                seen_call_ids: dict[str, str] = {}
                for ordinal, event in enumerate(completed_calls_raw, 1):
                    key = str(event.get("event_id") or f"{run_id}:logical:{ordinal}")
                    payload_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
                    if key in seen_call_ids:
                        severity = "WARNING" if seen_call_ids[key] == payload_hash else "ERROR"
                        audit.append({"severity": severity, "category": "duplicate_api_call", "experiment": spec["experiment"], "run_id": run_id, "detail": f"Duplicate logical API call {key}; identical={seen_call_ids[key] == payload_hash}"})
                        continue
                    seen_call_ids[key] = payload_hash
                    completed_calls.append(event)

                role_counts = Counter(str(event.get("role") or "UNKNOWN") for event in completed_calls)
                api_ms = sum(float(event.get("elapsed_ms") or 0) for event in completed_calls)
                transport_attempts = sum(int(event.get("transport_attempts") or 0) for event in completed_calls)
                models_by_role: dict[str, set[str]] = defaultdict(set)
                for event in completed_calls:
                    models_by_role[str(event.get("role") or "UNKNOWN")].add(str(event.get("model") or ""))
                model_config = "; ".join(f"{role}={','.join(sorted(models))}" for role, models in sorted(models_by_role.items()))

                iteration_events = [event for event in events if event.get("event_type") == "iteration_completed"]
                iteration_seen: dict[int, str] = {}
                terminal_iteration = None
                for event in iteration_events:
                    iteration = int(event.get("iteration") or 0)
                    payload_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
                    if iteration in iteration_seen:
                        audit.append({"severity": "ERROR" if iteration_seen[iteration] != payload_hash else "WARNING", "category": "duplicate_iteration", "experiment": spec["experiment"], "run_id": run_id, "detail": f"Duplicate iteration {iteration}; identical={iteration_seen[iteration] == payload_hash}"})
                        continue
                    iteration_seen[iteration] = payload_hash
                    terminal_iteration = max(terminal_iteration or 0, iteration)
                    iterations.append({
                        "experiment": spec["experiment"], "publication_label": spec["publication_label"],
                        "scope": spec["scope"], "session_id": str(event.get("session_id") or started.get("session_id") or ""),
                        "run_id": run_id, "requirement_id": requirement_id, "repetition": infer_repetition(event_path.parent, root),
                        "iteration": iteration, "record_source": "iteration_completed", "mode": str(event.get("mode") or ""),
                        "static_valid": event.get("static_valid"), "validator_accept": event.get("validator_accept"),
                        "matcher_activated": event.get("matcher_activated"), "decision": str(event.get("decision") or ""),
                        "generator_seconds": (float(event.get("generator_elapsed_ms")) / 1000 if event.get("generator_elapsed_ms") is not None else None),
                        "validator_seconds": (float(event.get("validator_elapsed_ms")) / 1000 if event.get("validator_elapsed_ms") is not None else None),
                        "stalled": event.get("stalled"), "oscillation_detected": event.get("oscillation_detected"),
                        "feedback": str(event.get("feedback") or ""), "timestamp_utc": str(event.get("timestamp_utc") or ""),
                        "source_path": source_path,
                    })

                diagnostic = last_event(events, "single_shot_diagnostics_completed")
                if not iteration_events and diagnostic:
                    terminal_iteration = int(diagnostic.get("iteration") or finished.get("attempts") or 1)
                    generator_elapsed = sum(float(event.get("elapsed_ms") or 0) for event in completed_calls if event.get("role") == "generator") / 1000
                    iterations.append({
                        "experiment": spec["experiment"], "publication_label": spec["publication_label"],
                        "scope": spec["scope"], "session_id": str(diagnostic.get("session_id") or started.get("session_id") or ""),
                        "run_id": run_id, "requirement_id": requirement_id, "repetition": infer_repetition(event_path.parent, root),
                        "iteration": terminal_iteration, "record_source": "single_shot_diagnostics_completed",
                        "mode": "single_shot", "static_valid": finished.get("deterministic_valid"), "validator_accept": None,
                        "matcher_activated": False, "decision": "PASS" if not diagnostic.get("blocking") else "BLOCKED",
                        "generator_seconds": generator_elapsed, "validator_seconds": None, "stalled": None,
                        "oscillation_detected": None,
                        "feedback": f"extraction={diagnostic.get('extraction_status','')}; rdf_parse={diagnostic.get('rdf_parse_status','')}; shacl={diagnostic.get('shacl_validation_status','')}; vocabulary={diagnostic.get('vocabulary_diagnostic_status','')}",
                        "timestamp_utc": str(diagnostic.get("timestamp_utc") or ""), "source_path": source_path,
                    })

                candidate_path = str(finished.get("candidate_shape") or "")
                final_path = str(finished.get("final_shape") or finished.get("extracted_shape") or "")
                output_available = path_exists(event_path.parent, final_path) or path_exists(event_path.parent, candidate_path)
                deterministic_valid = finished.get("deterministic_valid")
                if spec["experiment"] == "LUNA_NO_SEMANTIC_VALIDATOR":
                    successful = bool(deterministic_valid and path_exists(event_path.parent, candidate_path))
                elif spec["experiment"] == "LUNA_CONTEXTUAL_SINGLESHOT":
                    successful = bool(deterministic_valid and output_available)
                else:
                    successful = bool(finished.get("status") == "GENERATION_ACCEPTED" and finished.get("accepted") is True and path_exists(event_path.parent, final_path))
                complete = bool(started.get("timestamp_utc") and finished.get("timestamp_utc"))
                attempts = finished.get("attempts")
                if attempts is None and terminal_iteration is not None:
                    attempts = terminal_iteration
                if attempts is not None:
                    attempts = int(attempts)
                if attempts is not None and terminal_iteration is not None and attempts != terminal_iteration:
                    audit.append({"severity": "WARNING", "category": "attempt_iteration_mismatch", "experiment": spec["experiment"], "run_id": run_id, "detail": f"run_finished attempts={attempts}; terminal recorded iteration={terminal_iteration}"})

                row = {
                    "experiment": spec["experiment"], "publication_label": spec["publication_label"], "scope": spec["scope"],
                    "session_id": str(started.get("session_id") or finished.get("session_id") or ""), "run_id": run_id,
                    "requirement_id": requirement_id, "repetition": infer_repetition(event_path.parent, root),
                    "scaling_sample_member": requirement_id in scaling_requirements,
                    "pipeline_version": str(started.get("pipeline_version") or ""), "model_role_configuration": model_config,
                    "generator_model": ",".join(sorted(models_by_role.get("generator", set()))),
                    "validator_model": ",".join(sorted(models_by_role.get("validator", set()))),
                    "syntax_repair_model": ",".join(sorted(models_by_role.get("syntax_repair", set()))),
                    "started_utc": str(started.get("timestamp_utc") or ""), "finished_utc": str(finished.get("timestamp_utc") or ""),
                    "elapsed_seconds": elapsed_seconds(started.get("timestamp_utc"), finished.get("timestamp_utc")),
                    "api_seconds": api_ms / 1000 if completed_calls else None,
                    "candidate_attempts": attempts, "terminal_candidate_iteration": terminal_iteration,
                    "generator_calls": role_counts.get("generator", 0), "semantic_validator_calls": role_counts.get("validator", 0),
                    "syntax_repair_calls": role_counts.get("syntax_repair", 0), "vocabulary_matcher_calls": role_counts.get("vocabulary_matcher", 0),
                    "logical_api_calls": len(completed_calls), "transport_attempts": transport_attempts,
                    "final_status": str(finished.get("status") or "INCOMPLETE"), "accepted_flag": finished.get("accepted"),
                    "deterministic_valid": deterministic_valid, "eligible_at_start": started.get("eligibility"),
                    "output_available": output_available, "successful_output": successful,
                    "completed": complete, "completed_unsuccessful": bool(complete and not successful),
                    "final_shape_or_candidate": final_path or candidate_path, "source_path": source_path,
                    "success_definition": spec["success_rule"],
                    "behavioral_cases": None, "behavioral_executed": None, "behavioral_correct": None,
                    "behavioral_all_correct": None, "behavioral_source": "",
                }
                runs.append(row)
                exp_rows.append(row)

                for ordinal, event in enumerate(completed_calls, 1):
                    api_calls.append({
                        "experiment": spec["experiment"], "publication_label": spec["publication_label"], "scope": spec["scope"],
                        "session_id": str(event.get("session_id") or row["session_id"]), "run_id": run_id,
                        "requirement_id": requirement_id, "repetition": row["repetition"], "call_ordinal": ordinal,
                        "event_id": str(event.get("event_id") or ""), "timestamp_utc": str(event.get("timestamp_utc") or ""),
                        "role": str(event.get("role") or ""), "model": str(event.get("model") or ""),
                        "iteration": event.get("iteration"), "syntax_repair_attempt": event.get("syntax_repair_attempt"),
                        "contract_attempt": event.get("contract_attempt"), "elapsed_seconds": float(event.get("elapsed_ms") or 0) / 1000,
                        "transport_attempts": int(event.get("transport_attempts") or 0),
                        "input_tokens": event.get("input_tokens"), "output_tokens": event.get("output_tokens"),
                        "total_tokens": event.get("total_tokens"), "response_id": str(event.get("response_id") or ""),
                        "source_path": source_path,
                    })

        by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in exp_rows:
            by_session[row["session_id"]].append(row)
        for session, rows_for_session in sorted(by_session.items()):
            index.append({
                "original_experiment": spec["experiment"], "publication_label": spec["publication_label"],
                "scope": spec["scope"], "session_id": session,
                "model_role_configuration": rows_for_session[0]["model_role_configuration"], "benchmark_subset": spec["subset"],
                "repetition": rows_for_session[0]["repetition"], "requirement_runs": len(rows_for_session),
                "unique_requirements": len({row["requirement_id"] for row in rows_for_session}),
                "source_root": str((PROJECT / rows_for_session[0]["source_path"]).parent.parent.relative_to(PROJECT)),
                "success_definition": spec["success_rule"],
            })

    # Explain deliberately excluded non-formal scopes.
    exclusions = [
        ("LUNA_NO_SEMANTIC_VALIDATOR", "MINI_TEST", 3),
        ("LUNA_CONTEXTUAL_SINGLESHOT", "MINI_TEST_3 + SMOKE_TEST", 4),
        ("FULL_REPAIR_V2", "LIVE_SMOKE + SMOKE_TEST", 2),
        ("MODEL_SCALING_FULL_REPAIR_V2_50", "OUTPUTS/SMOKE", 18),
    ]
    for exp, name, count in exclusions:
        audit.append({"severity": "INFO", "category": "excluded_development_or_smoke", "experiment": exp, "run_id": "", "detail": f"Excluded {count} non-formal requirement runs from {name}."})
    audit.append({"severity": "WARNING", "category": "hidden_evaluation_unavailable", "experiment": "HIDDEN_RDF_EVALUATION", "run_id": "", "detail": "Audit stopped before evaluation: no formal independent hidden R13 benchmark was present; zero hidden evaluation runs exist."})
    audit.append({"severity": "WARNING", "category": "dataset_version_difference", "experiment": "MODEL_SCALING_FULL_REPAIR_V2_50", "run_id": "", "detail": "Existing model-scaling RDF timing ledgers contain 381 cases, while the current Paper Tables/manuscript dataset reports 373 configurations. Runtime rows preserve the logged 381-case evidence and must not be interpreted as the revised behavioural denominator."})
    audit.append({"severity": "WARNING", "category": "dataset_version_difference", "experiment": "BEHAVIORAL_R13_MAIN", "run_id": "", "detail": "Existing full-benchmark RDF timing ledgers contain 2,186 cases, while the current Paper Tables/manuscript dataset reports 2,160 configurations. Runtime rows preserve the logged 2,186-case evidence and must not be interpreted as the revised behavioural denominator."})
    return runs, iterations, api_calls, index, audit


def extract_rdf() -> list[dict[str, Any]]:
    sources: list[tuple[Path, str, str, str, str]] = []
    main = PIPELINE / "evaluation" / "experiment_results" / "BEHAVIORAL-R13-20260911T080233539977Z" / "raw_case_results.jsonl"
    sources.append((main, "BEHAVIORAL_R13_MAIN", "Recorded three-workflow evaluation", "main_and_historical", ""))
    full_v2 = PIPELINE / "evaluation" / "experiment_results" / "BEHAVIORAL-R13-FULL-REPAIR-V2-RUN01-20260915T144116505813Z" / "raw_case_results.jsonl"
    sources.append((full_v2, "FULL_REPAIR_V2", "Full repair reference", "full_benchmark_reference", "FINAL_OUTPUT"))
    scaling_root = EXPERIMENTS / "MODEL_SCALING_FULL_REPAIR_V2_50" / "OUTPUTS" / "RDF_EVALUATION"
    for stage in ("FIRST_GENERATION", "SELF_REPAIR_FINAL"):
        for model in ("luna", "sol", "gemini", "gpt_oss"):
            sources.append((scaling_root / stage / model / "raw_case_results.jsonl", "MODEL_SCALING_FULL_REPAIR_V2_50", "Four-model comparison", "model_comparison_formal", stage))

    rows: list[dict[str, Any]] = []
    seen: dict[tuple[str, str, str], str] = {}
    for path, experiment, pub_label, scope, stage in sources:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            configuration = str(row.get("configuration") or "")
            model = ""
            if experiment == "MODEL_SCALING_FULL_REPAIR_V2_50":
                model = path.parent.name
                pub_label = {"luna": "GPT-5.6 Luna", "sol": "GPT-5.6 Sol", "gemini": "Gemini 3.5 Flash", "gpt_oss": "GPT-OSS 120B"}[model]
            elif configuration == "NO_SEMANTIC":
                pub_label = "NLTL_v2"
            elif configuration == "SINGLESHOT":
                pub_label = "Single-shot"
            elif configuration == "FULL":
                pub_label = "Historical full workflow"
            key = (str(row.get("run_id") or ""), str(row.get("generation_run") or stage), str(row.get("case_id") or ""))
            payload_hash = hashlib.sha256(line.encode()).hexdigest()
            if key in seen:
                if seen[key] == payload_hash:
                    continue
            seen[key] = payload_hash
            rows.append({
                "experiment": experiment, "publication_label": pub_label, "scope": scope, "stage": stage or configuration,
                "model": model, "evaluation_run_id": str(row.get("run_id") or ""),
                "generation_run": str(row.get("generation_run") or ""), "generation_run_id": str(row.get("generation_run_id") or ""),
                "configuration": configuration, "requirement_id": str(row.get("requirement_id") or ""),
                "case_id": str(row.get("case_id") or ""), "expected_outcome": str(row.get("expected_outcome") or ""),
                "actual_conforms": row.get("actual_conforms"), "behavioral_match": row.get("behavioral_match"),
                "execution_status": str(row.get("execution_status") or ""), "end_to_end_success": row.get("end_to_end_success"),
                "outcome_class": str(row.get("outcome_class") or ""),
                "runtime_seconds": (float(row.get("runtime_ms")) / 1000 if row.get("runtime_ms") is not None else None),
                "generation_status": str(row.get("generation_status") or ""), "shape_parse_status": str(row.get("shape_parse_status") or ""),
                "failure_stage": str(row.get("failure_stage") or ""), "source_family": str(row.get("source_family") or ""),
                "source_path": str(path.relative_to(PROJECT)),
            })
    return rows


def link_behavioral(runs: list[dict[str, Any]], rdf: list[dict[str, Any]]) -> None:
    preferred = [row for row in rdf if row["stage"] in {"SELF_REPAIR_FINAL", "FULL_REPAIR_V2", "NO_SEMANTIC", "SINGLESHOT", "FULL"}]
    by_generation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in preferred:
        if row["generation_run_id"]:
            by_generation[row["generation_run_id"]].append(row)
    for run in runs:
        linked = by_generation.get(run["run_id"], [])
        if not linked:
            continue
        run["behavioral_cases"] = len(linked)
        run["behavioral_executed"] = sum(row["execution_status"] == "EXECUTED" for row in linked)
        run["behavioral_correct"] = sum(row["behavioral_match"] is True for row in linked)
        run["behavioral_all_correct"] = bool(linked and all(row["behavioral_match"] is True for row in linked))
        run["behavioral_source"] = linked[0]["source_path"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runs, iterations, api_calls, index, audit = extract_generation()
    rdf = extract_rdf()
    link_behavioral(runs, rdf)
    runs.sort(key=lambda r: (r["experiment"], r["session_id"], r["requirement_id"], r["run_id"]))
    iterations.sort(key=lambda r: (r["experiment"], r["session_id"], r["requirement_id"], r["run_id"], r["iteration"]))
    api_calls.sort(key=lambda r: (r["experiment"], r["session_id"], r["requirement_id"], r["run_id"], r["call_ordinal"]))
    rdf.sort(key=lambda r: (r["experiment"], r["publication_label"], r["stage"], r["requirement_id"], r["case_id"]))
    index.sort(key=lambda r: (r["original_experiment"], r["session_id"]))

    # Add completeness audit after linking.
    for exp in sorted({r["experiment"] for r in runs}):
        subset = [r for r in runs if r["experiment"] == exp]
        missing_elapsed = sum(r["elapsed_seconds"] is None for r in subset)
        missing_attempts = sum(r["candidate_attempts"] is None for r in subset)
        zero_api = sum(r["logical_api_calls"] == 0 for r in subset)
        if missing_elapsed or missing_attempts or zero_api:
            audit.append({"severity": "WARNING", "category": "missing_generation_evidence", "experiment": exp, "run_id": "", "detail": f"missing elapsed={missing_elapsed}; missing candidate attempts={missing_attempts}; zero logical API calls={zero_api}; runs={len(subset)}"})

    payload = {
        "metadata": {
            "created_utc": datetime.now().astimezone().isoformat(),
            "project": str(PROJECT),
            "metric_definitions": {
                "requirement_run_elapsed": "Seconds from run_started timestamp to run_finished timestamp; includes all pipeline work inside those events.",
                "api_seconds": "Sum of logical api_call_completed elapsed_ms only. Transport-attempt rows are not added; transport_attempts is reported separately.",
                "rdf_seconds": "Per-case runtime_ms from the existing RDF evaluation ledger; kept separate from generation runtime.",
                "candidate_attempts": "run_finished attempts, checked against terminal recorded iteration. Single-shot uses its recorded one-attempt diagnostic event.",
            },
            "counts": {"requirement_runs": len(runs), "iterations": len(iterations), "api_calls": len(api_calls), "rdf_cases": len(rdf), "experiment_index_rows": len(index), "audit_rows": len(audit)},
        },
        "experiment_index": index,
        "requirement_runs": runs,
        "iterations": iterations,
        "api_calls": api_calls,
        "rdf_evaluation": rdf,
        "audit": audit,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(payload["metadata"]["counts"], indent=2))


if __name__ == "__main__":
    main()
