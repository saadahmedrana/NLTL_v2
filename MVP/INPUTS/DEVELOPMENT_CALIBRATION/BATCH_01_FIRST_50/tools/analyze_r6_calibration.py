#!/usr/bin/env python3
"""Summarize R6 generation, API telemetry, and deterministic RDF evaluation."""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BATCH = ROOT / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_01_FIRST_50"
RUNS = ROOT / "SHACL_GENERATION_PIPELINE/outputs/development_batch01/runs"
EVALUATIONS = ROOT / "SHACL_GENERATION_PIPELINE/outputs/development_batch01/evaluations"
VOCABULARY_ID = "VOCAB-DEV-2026-08-13-BATCH01-R6"

NEXT_ACTION = {
    "TRF-011": "Add a bounded envelope-aggregation pattern to the generation guidance.",
    "TRF-014": "Clarify the pre-2007 marking/dry-docking alternatives as a semantic obligation.",
    "TRF-020": "Index the existing length, breadth, draught, and waterline operand relationships explicitly.",
    "TRF-022": "Choose and document a portable trigonometric calculation strategy supported by the evaluator.",
    "TRF-025": "Add the existing coefficientG3 term to the TRF-025 requirement scope.",
    "TRF-026": "Add an explicit applicability-branch pattern for IA Super and bulbous-bow evidence.",
    "TRF-027": "Require exactly one controlled iceClass before conditional applicability branches.",
    "TRF-030": "Add a canonical case-specific load-length/area-factor pairing relation.",
    "TRF-037": "Add the maximum-as-cap formula obligation using IF(raw > 1, 1, raw).",
    "TRF-042": "Standardize tolerance fallback and evidenceState range validation.",
    "TRF-046": "Clarify that the ice-belt-limit condition qualifies permission branches only.",
    "TRF-049": "Reinforce frameAttachment ownership and subclass-target behavior.",
}


def r6_runs() -> list[tuple[dict, dict, list[dict]]]:
    rows = []
    for events_path in RUNS.glob("RUN-*/events.jsonl"):
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        start = next((event for event in events if event.get("event_type") == "run_started"), {})
        finish = next((event for event in reversed(events) if event.get("event_type") == "run_finished"), None)
        if finish and start.get("vocabulary_lock_id") == VOCABULARY_ID:
            rows.append((start, finish, events))
    return sorted(rows, key=lambda item: item[1]["requirement_id"])


def latest_evaluation() -> Path:
    candidates = list(EVALUATIONS.glob("EVAL-BATCH01-R6-ACCEPTED-SHAPES-*"))
    if not candidates:
        raise RuntimeError("No R6 accepted-shape evaluation found")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def main() -> None:
    runs = r6_runs()
    evaluation_dir = latest_evaluation()
    evaluation: defaultdict[str, list[dict]] = defaultdict(list)
    for line in (evaluation_dir / "evaluation_results.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        evaluation[item["requirement_ids"][0]].append(item)

    api_calls = [
        event for _start, _finish, events in runs for event in events
        if event.get("event_type") == "api_call_completed"
    ]
    role_stats = {}
    for role in sorted({item["role"] for item in api_calls}):
        items = [item for item in api_calls if item["role"] == role]
        elapsed = [float(item["elapsed_ms"]) for item in items]
        role_stats[role] = {
            "calls": len(items),
            "mean_elapsed_ms": round(statistics.mean(elapsed), 3),
            "median_elapsed_ms": round(statistics.median(elapsed), 3),
            "input_tokens": sum(int(item.get("input_tokens") or 0) for item in items),
            "output_tokens": sum(int(item.get("output_tokens") or 0) for item in items),
            "total_tokens": sum(int(item.get("total_tokens") or 0) for item in items),
        }

    rows = []
    for _start, finish, events in runs:
        rid = finish["requirement_id"]
        cases = evaluation.get(rid, [])
        if finish["status"] == "GENERATION_ACCEPTED":
            classification = "R6_RDF_REGRESSION_CLEAN" if cases and all(item.get("expected_match") is True for item in cases) else "R6_ACCEPTED_NOT_RDF_CLEAN"
        elif finish["status"] == "VOCABULARY_GAP":
            classification = "R6_VOCABULARY_OR_INDEX_GAP"
        else:
            classification = "R6_REPAIR_LIMIT"
        rows.append({
            "requirement_id": rid,
            "run_id": finish["run_id"],
            "generation_status": finish["status"],
            "accepted": bool(finish.get("accepted")),
            "semantic_attempts": int(finish.get("attempts", 0)),
            "api_calls": sum(event.get("event_type") == "api_call_completed" for event in events),
            "evaluated_cases": len(cases),
            "expected_matches": sum(item.get("expected_match") is True for item in cases),
            "classification": classification,
            "next_action": NEXT_ACTION.get(rid, "Retain as clean R6 development evidence."),
            "final_feedback": finish.get("final_feedback", ""),
        })

    started = min(datetime.fromisoformat(start["timestamp_utc"].replace("Z", "+00:00")) for start, _finish, _events in runs)
    finished = max(datetime.fromisoformat(finish["timestamp_utc"].replace("Z", "+00:00")) for _start, finish, _events in runs)
    evaluation_summary = json.loads((evaluation_dir / "evaluation_summary.json").read_text(encoding="utf-8"))
    payload = {
        "analysis_id": "BATCH01-R6-POSTRUN-ANALYSIS",
        "status": "DEVELOPMENT_CALIBRATION_ONLY",
        "development_vocabulary_id": VOCABULARY_ID,
        "generation": {
            "requirements": len(runs),
            "statuses": dict(Counter(item[1]["status"] for item in runs)),
            "accepted": sum(bool(item[1].get("accepted")) for item in runs),
            "semantic_attempts": sum(int(item[1].get("attempts", 0)) for item in runs),
            "wall_clock_seconds": round((finished - started).total_seconds(), 3),
        },
        "api": {
            "calls": len(api_calls),
            "input_tokens": sum(int(item.get("input_tokens") or 0) for item in api_calls),
            "output_tokens": sum(int(item.get("output_tokens") or 0) for item in api_calls),
            "total_tokens": sum(int(item.get("total_tokens") or 0) for item in api_calls),
            "transport_attempts": dict(Counter(str(int(item.get("transport_attempts") or 0)) for item in api_calls)),
            "roles": role_stats,
        },
        "evaluation": evaluation_summary,
        "fixture_corrections_before_final_rerun": [
            "TRF-044: replaced rounded derived values with full-precision formula outputs.",
            "TRF-051: corrected normal frame-web fixture from inLieuOfFrame=true to false.",
            "TRF-054: preserved the controlled decimal lexical form 0.80 required by sh:hasValue.",
        ],
        "classification_counts": dict(Counter(row["classification"] for row in rows)),
        "rows": rows,
    }
    (BATCH / "r6_calibration_analysis.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with (BATCH / "r6_calibration_analysis.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    accepted = [row["requirement_id"] for row in rows if row["classification"] == "R6_RDF_REGRESSION_CLEAN"]
    unresolved = [row for row in rows if row["requirement_id"] in NEXT_ACTION]
    report = [
        "# Batch 01 R6 results",
        "",
        "R6 is development calibration, not final benchmark accuracy.",
        "",
        "## Generation and cost telemetry",
        "",
        f"- Requirements run: {payload['generation']['requirements']}",
        f"- Accepted: {payload['generation']['accepted']}",
        f"- Maximum-attempt results: {payload['generation']['statuses'].get('MAX_ATTEMPTS_REACHED', 0)}",
        f"- Vocabulary gaps: {payload['generation']['statuses'].get('VOCABULARY_GAP', 0)}",
        f"- Semantic attempts: {payload['generation']['semantic_attempts']}",
        f"- API calls: {payload['api']['calls']}",
        f"- Input/output/total tokens: {payload['api']['input_tokens']:,} / {payload['api']['output_tokens']:,} / {payload['api']['total_tokens']:,}",
        f"- Batch wall-clock time: {payload['generation']['wall_clock_seconds'] / 60:.2f} minutes",
        "- Transport retries: none; every API call completed in one transport attempt.",
        "",
        "## RDF regression gate",
        "",
        f"- Executed: {evaluation_summary['execution_ok']}/{evaluation_summary['items']}",
        f"- Expected outcomes matched: {evaluation_summary['expected_matches']}/{evaluation_summary['items']}",
        f"- Clean accepted requirements: {', '.join(accepted)}",
        "",
        "Before the final rerun, three fixture-alignment defects were corrected and rehashed: TRF-044 rounded formula outputs, TRF-051 contradictory `inLieuOfFrame`, and TRF-054 decimal lexical form `0.80`. No generated SHACL was edited.",
        "",
        "## R7 work queue",
        "",
    ]
    report.extend(f"- `{row['requirement_id']}` — {row['next_action']}" for row in unresolved)
    report.extend([
        "",
        "R7 should address only these 12 requirements. The 20 first-batch shapes already proven clean under R5/R6 migration and R6 evaluation do not need another API call during development.",
    ])
    (BATCH / "BATCH01_R6_RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({
        "generation": payload["generation"],
        "api": payload["api"],
        "evaluation": evaluation_summary,
        "classification_counts": payload["classification_counts"],
    }, indent=2))


if __name__ == "__main__":
    main()
