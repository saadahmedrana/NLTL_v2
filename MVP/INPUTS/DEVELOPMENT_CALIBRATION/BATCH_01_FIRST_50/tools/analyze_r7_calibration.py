#!/usr/bin/env python3
"""Summarize R7 generation telemetry and deterministic RDF evaluation."""

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
VOCABULARY_ID = "VOCAB-DEV-2026-08-13-BATCH01-R7"


def r7_runs() -> list[tuple[dict, dict, list[dict]]]:
    rows = []
    for events_path in RUNS.glob("RUN-*/events.jsonl"):
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        start = next((event for event in events if event.get("event_type") == "run_started"), {})
        finish = next((event for event in reversed(events) if event.get("event_type") == "run_finished"), None)
        if finish and start.get("vocabulary_lock_id") == VOCABULARY_ID:
            rows.append((start, finish, events))
    latest = {}
    for row in rows:
        rid = row[1]["requirement_id"]
        if rid not in latest or row[1]["timestamp_utc"] > latest[rid][1]["timestamp_utc"]:
            latest[rid] = row
    return sorted(latest.values(), key=lambda item: item[1]["requirement_id"])


def latest_evaluation() -> Path:
    candidates = list(EVALUATIONS.glob("EVAL-BATCH01-R7-ACCEPTED-SHAPES-*"))
    if not candidates:
        raise RuntimeError("No R7 accepted-shape evaluation found")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def main() -> None:
    runs = r7_runs()
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
            classification = "R7_RDF_CLEAN" if len(cases) == 3 and all(item.get("expected_match") is True for item in cases) else "R7_ACCEPTED_RDF_MISMATCH"
        elif finish["status"] == "VOCABULARY_GAP":
            classification = "R7_VOCABULARY_OR_INDEX_GAP"
        else:
            classification = "R7_REPAIR_LIMIT"
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
            "final_feedback": finish.get("final_feedback", ""),
        })

    started = min(datetime.fromisoformat(start["timestamp_utc"].replace("Z", "+00:00")) for start, _finish, _events in runs)
    finished = max(datetime.fromisoformat(finish["timestamp_utc"].replace("Z", "+00:00")) for _start, finish, _events in runs)
    evaluation_summary = json.loads((evaluation_dir / "evaluation_summary.json").read_text(encoding="utf-8"))
    payload = {
        "analysis_id": "BATCH01-R7-POSTRUN-ANALYSIS",
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
            "roles": role_stats,
        },
        "evaluation": evaluation_summary,
        "fixture_corrections_before_final_evaluation": [
            "TRF-020: restored Newton units, source-scale resistance, and full-precision formula outputs.",
            "TRF-022/TRF-027: restored verified table constants; RDF decimal lexical-form sensitivity remains a benchmark serialization issue rather than a vocabulary gap.",
            "TRF-046: made helper main-frame nodes complete targets and represented the two-adjacent-frame alternative.",
            "TRF-049: linked every identified support to the shared confirmed attachment.",
        ],
        "classification_counts": dict(Counter(row["classification"] for row in rows)),
        "rows": rows,
    }
    (BATCH / "r7_calibration_analysis.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with (BATCH / "r7_calibration_analysis.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    clean = [row["requirement_id"] for row in rows if row["classification"] == "R7_RDF_CLEAN"]
    unresolved = [row["requirement_id"] for row in rows if row["classification"] != "R7_RDF_CLEAN"]
    report = [
        "# Batch 01 R7 results",
        "",
        "R7 is development calibration, not final benchmark accuracy.",
        "",
        "## Generation and telemetry",
        "",
        f"- Requirements run: {payload['generation']['requirements']}",
        f"- LLM-validator accepted: {payload['generation']['accepted']}",
        f"- Semantic attempts: {payload['generation']['semantic_attempts']}",
        f"- API calls: {payload['api']['calls']}",
        f"- Input/output/total tokens: {payload['api']['input_tokens']:,} / {payload['api']['output_tokens']:,} / {payload['api']['total_tokens']:,}",
        f"- Wall-clock time: {payload['generation']['wall_clock_seconds'] / 60:.2f} minutes",
        "",
        "## Deterministic RDF gate",
        "",
        f"- Evaluations executed: {evaluation_summary['execution_ok']}/{evaluation_summary['items']}",
        f"- Expected outcomes matched: {evaluation_summary['expected_matches']}/{evaluation_summary['items']}",
        f"- R7 RDF-clean requirements: {', '.join(clean)}",
        f"- R7 unresolved requirements: {', '.join(unresolved)}",
        "",
        "TRF-022 and TRF-027 expose brittle exact-decimal `sh:hasValue` behavior in addition to generated logic checks; this should be normalized in the final benchmark serialization policy. TRF-030 is a genuine over-constraint: every direct-analysis case was forced to carry both vertical and horizontal positions, and reference-position facts were required even though the regulation permits separate checks.",
        "",
        "## Decision",
        "",
        "Stop first-50 prompt tuning here. Carry these seven unresolved cases into the broader discovery ledger, distinguish true missing vocabulary from generator/validator errors, and do not report the development results as final benchmark accuracy.",
    ]
    (BATCH / "BATCH01_R7_RESULTS.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
