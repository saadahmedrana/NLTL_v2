#!/usr/bin/env python3
"""Summarize R5 generation, API usage, and deterministic RDF evaluation."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BATCH = ROOT / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_01_FIRST_50"
RUNS = ROOT / "SHACL_GENERATION_PIPELINE/outputs/development_batch01/runs"
EVAL = ROOT / "SHACL_GENERATION_PIPELINE/outputs/development_batch01/evaluations/EVAL-BATCH01-R5-TARGETED-ACCEPTED-SHAPES-20260812T210527852905Z"
VOCABULARY_ID = "VOCAB-DEV-2026-08-12-BATCH01-R5"

ALIGNMENT_REVIEW = {
    "TRF-007", "TRF-009", "TRF-013", "TRF-024", "TRF-032", "TRF-034",
    "TRF-036", "TRF-037", "TRF-048", "TRF-053", "TRF-054", "TRF-059",
}
SEMANTIC_SHAPE_DEFECT = {"TRF-011"}
QUERY_PORTABILITY_DEFECT = {"TRF-041"}
NODE_MODEL_DECISION = {"TRF-016"}


def r5_runs() -> list[tuple[Path, dict, dict, list[dict]]]:
    rows = []
    for events_path in RUNS.glob("RUN-*/events.jsonl"):
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        start = next((event for event in events if event.get("event_type") == "run_started"), {})
        finish = next((event for event in reversed(events) if event.get("event_type") == "run_finished"), None)
        if finish and start.get("vocabulary_lock_id") == VOCABULARY_ID:
            rows.append((events_path.parent, start, finish, events))
    return sorted(rows, key=lambda item: item[2]["requirement_id"])


def main() -> None:
    runs = r5_runs()
    evaluation: defaultdict[str, list[dict]] = defaultdict(list)
    for line in (EVAL / "evaluation_results.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        evaluation[item["requirement_ids"][0]].append(item)

    api_calls = [
        event for _path, _start, _finish, events in runs for event in events
        if event.get("event_type") == "api_call_completed"
    ]
    role_stats = {}
    for role in sorted({item["role"] for item in api_calls}):
        items = [item for item in api_calls if item["role"] == role]
        role_stats[role] = {
            "calls": len(items),
            "mean_elapsed_ms": round(sum(item["elapsed_ms"] for item in items) / len(items), 3),
            "input_tokens": sum(item["input_tokens"] for item in items),
            "output_tokens": sum(item["output_tokens"] for item in items),
            "total_tokens": sum(item["total_tokens"] for item in items),
        }

    rows = []
    for _path, _start, finish, _events in runs:
        rid = finish["requirement_id"]
        cases = evaluation.get(rid, [])
        mismatches = [item["variant_id"] for item in cases if item.get("expected_match") is False]
        if not finish.get("accepted"):
            classification = "VOCABULARY_OR_INDEX_GAP" if finish["status"] == "VOCABULARY_GAP" else "GENERATOR_VALIDATOR_REPAIR"
        elif rid in ALIGNMENT_REVIEW:
            classification = "CANONICAL_DOMAIN_FIXTURE_ALIGNMENT"
        elif rid in SEMANTIC_SHAPE_DEFECT:
            classification = "SEMANTIC_SHAPE_UNDERCONSTRAINT"
        elif rid in QUERY_PORTABILITY_DEFECT:
            classification = "SPARQL_QUERY_PORTABILITY"
        elif rid in NODE_MODEL_DECISION:
            classification = "NODE_MODEL_DECISION"
        else:
            classification = "R5_CLEAN"
        rows.append({
            "requirement_id": rid,
            "run_id": finish["run_id"],
            "generation_status": finish["status"],
            "accepted": bool(finish.get("accepted")),
            "attempts": finish.get("attempts", 0),
            "evaluated_cases": len(cases),
            "expected_matches": sum(item.get("expected_match") is True for item in cases),
            "expected_mismatches": len(mismatches),
            "mismatch_variants": " | ".join(mismatches),
            "classification": classification,
            "final_feedback": finish.get("final_feedback", ""),
        })

    summary = json.loads((EVAL / "evaluation_summary.json").read_text(encoding="utf-8"))
    payload = {
        "analysis_id": "BATCH01-R5-POSTRUN-ANALYSIS",
        "status": "DEVELOPMENT_CALIBRATION_ONLY",
        "development_vocabulary_id": VOCABULARY_ID,
        "generation": {
            "requirements": len(runs),
            "statuses": dict(Counter(item[2]["status"] for item in runs)),
            "accepted": sum(bool(item[2].get("accepted")) for item in runs),
            "semantic_attempts": sum(item[2].get("attempts", 0) for item in runs),
        },
        "api": {
            "calls": len(api_calls),
            "input_tokens": sum(item["input_tokens"] for item in api_calls),
            "output_tokens": sum(item["output_tokens"] for item in api_calls),
            "total_tokens": sum(item["total_tokens"] for item in api_calls),
            "roles": role_stats,
        },
        "evaluation": summary,
        "classification_counts": dict(Counter(row["classification"] for row in rows)),
        "rows": rows,
    }
    (BATCH / "r5_calibration_analysis.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with (BATCH / "r5_calibration_analysis.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({key: payload[key] for key in ("generation", "api", "classification_counts")}, indent=2))


if __name__ == "__main__":
    main()
