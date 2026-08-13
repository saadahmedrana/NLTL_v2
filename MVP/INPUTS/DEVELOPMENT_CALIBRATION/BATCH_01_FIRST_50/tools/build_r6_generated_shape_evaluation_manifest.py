#!/usr/bin/env python3
"""Bind the latest R6-accepted Batch 01 shapes to the R6 RDF fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BATCH = ROOT / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_01_FIRST_50"
RUNS = ROOT / "SHACL_GENERATION_PIPELINE/outputs/development_batch01/runs"
CATALOG = BATCH / "rdf_fixtures/fixture_catalog.json"
OUTPUT = BATCH / "r6_generated_shape_evaluation_manifest.json"
TARGET_VOCABULARY_ID = "VOCAB-DEV-2026-08-13-BATCH01-R6"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latest_results() -> dict[str, dict]:
    results: dict[str, dict] = {}
    for events_path in RUNS.glob("RUN-*/events.jsonl"):
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        start = next((event for event in events if event.get("event_type") == "run_started"), {})
        if start.get("vocabulary_lock_id") != TARGET_VOCABULARY_ID:
            continue
        finish = next((event for event in reversed(events) if event.get("event_type") == "run_finished"), None)
        if not finish:
            continue
        requirement_id = finish["requirement_id"]
        if requirement_id not in results or finish["timestamp_utc"] > results[requirement_id]["timestamp_utc"]:
            results[requirement_id] = finish
    return results


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    results = latest_results()
    items = []
    for case in catalog["caseRecords"]:
        requirement_id = case["requirementId"]
        result = results.get(requirement_id)
        if not result or not result.get("accepted"):
            continue
        shape = RUNS / result["run_id"] / result["final_shape"]
        data = ROOT / case["rdfFile"]
        items.append({
            "case_id": case["caseId"],
            "variant_id": case["caseKind"],
            "case_level": "r6-requirement-development-calibration",
            "requirement_ids": [requirement_id],
            "shape_file": str(shape.resolve()),
            "data_file": str(data.resolve()),
            "shape_sha256": sha256(shape),
            "data_sha256": case["rdfSha256"],
            "expected_conforms": case["expectedConforms"],
            "generation_run_id": result["run_id"],
            "development_vocabulary_id": TARGET_VOCABULARY_ID,
        })
    payload = {
        "evaluation_id": "BATCH01-R6-ACCEPTED-SHAPES",
        "status": "DEVELOPMENT_CALIBRATION_ONLY",
        "warning": "Visible fixtures used for vocabulary/pipeline development; not final hidden evaluation.",
        "accepted_requirements": len({item["requirement_ids"][0] for item in items}),
        "development_vocabulary_id": TARGET_VOCABULARY_ID,
        "items": items,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest": str(OUTPUT),
        "accepted_requirements": payload["accepted_requirements"],
        "items": len(items),
    }, indent=2))


if __name__ == "__main__":
    main()
