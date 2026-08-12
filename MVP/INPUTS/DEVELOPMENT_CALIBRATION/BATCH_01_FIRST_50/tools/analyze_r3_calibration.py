#!/usr/bin/env python3
"""Create a requirement-level classification of the completed R3 development run."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BATCH = ROOT / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_01_FIRST_50"
RUNS = ROOT / "SHACL_GENERATION_PIPELINE/outputs/development_batch01/runs"
EVALUATIONS = ROOT / "SHACL_GENERATION_PIPELINE/outputs/development_batch01/evaluations"

CONFIRMED_SCHEMA_GAPS = {
    "TRF-014", "TRF-015", "TRF-016", "TRF-020", "TRF-030", "TRF-034",
    "TRF-046", "TRF-047", "TRF-048", "TRF-049", "TRF-051", "TRF-053",
    "TRF-054", "TRF-056",
}


def latest_runs() -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for path in RUNS.glob("RUN-*/events.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("event_type") != "run_finished":
                continue
            rid = event["requirement_id"]
            if rid not in latest or event["timestamp_utc"] > latest[rid]["timestamp_utc"]:
                latest[rid] = event
    return latest


def evaluation_results() -> dict[str, list[dict]]:
    candidates = sorted(EVALUATIONS.glob("EVAL-BATCH01-R3-LATEST-ACCEPTED-SHAPES-*/evaluation_results.jsonl"))
    if not candidates:
        return {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for line in candidates[-1].read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        grouped[row["requirement_ids"][0]].append(row)
    return grouped


def main() -> None:
    runs = latest_runs()
    evaluations = evaluation_results()
    rows = []
    for rid in sorted(runs):
        run = runs[rid]
        eval_rows = evaluations.get(rid, [])
        execution_failures = sum(row.get("execution_ok") is not True for row in eval_rows)
        expectation_mismatches = sum(row.get("expected_match") is False for row in eval_rows)
        if not run.get("accepted"):
            if rid in CONFIRMED_SCHEMA_GAPS:
                classification = "CONFIRMED_SCHEMA_GAP"
                rationale = "Clause-backed missing class/property/relationship/unit or applicability operand was added to R4."
            else:
                classification = "PIPELINE_OR_MODEL_REPAIR"
                rationale = "Required terms already existed; repair retrieval, prompt behavior, query syntax, or generated logic."
        elif execution_failures:
            classification = "RUNTIME_INVALID_ACCEPTANCE"
            rationale = "R3 static checks accepted SHACL-SPARQL rejected by the actual SHACL engine; R4 adds a compilation gate."
        elif expectation_mismatches:
            classification = "RDF_EXPECTATION_MISMATCH"
            rationale = "Executable shape disagreed with one or more authored pass/fail/boundary fixtures; fixture and logic were reviewed."
        else:
            classification = "R3_CLEAN_CALIBRATION"
            rationale = "Generation accepted and all three R3 fixture expectations matched; retain as development evidence."
        rows.append({
            "requirement_id": rid,
            "r3_run_id": run["run_id"],
            "r3_generation_status": run["status"],
            "r3_attempts": run["attempts"],
            "r3_accepted": bool(run["accepted"]),
            "r3_evaluated_cases": len(eval_rows),
            "r3_execution_failures": execution_failures,
            "r3_expectation_mismatches": expectation_mismatches,
            "classification": classification,
            "r4_action": "RERUN_AFFECTED" if classification != "R3_CLEAN_CALIBRATION" else "RETAIN_DEVELOPMENT_EVIDENCE",
            "rationale": rationale,
            "final_feedback": run.get("final_feedback", ""),
        })
    payload = {
        "analysis_id": "BATCH01-R3-POSTRUN-ANALYSIS",
        "status": "DEVELOPMENT_CALIBRATION_ONLY",
        "requirements": len(rows),
        "counts": {category: sum(row["classification"] == category for row in rows) for category in sorted({row["classification"] for row in rows})},
        "next_development_vocabulary": "VOCAB-DEV-2026-08-12-BATCH01-R4",
        "rows": rows,
    }
    json_path = BATCH / "r3_calibration_analysis.json"
    csv_path = BATCH / "r3_calibration_analysis.csv"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"status": "PASS", "counts": payload["counts"], "json": str(json_path), "csv": str(csv_path)}, indent=2))


if __name__ == "__main__":
    main()
