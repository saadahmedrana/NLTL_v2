#!/usr/bin/env python3
"""Bind R5-accepted shapes to rebuilt R6 fixtures as a zero-API migration check."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BATCH = ROOT / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_01_FIRST_50"
RUNS = ROOT / "SHACL_GENERATION_PIPELINE/outputs/development_batch01/runs"
CATALOG = BATCH / "rdf_fixtures/fixture_catalog.json"
OUTPUT = BATCH / "r6_migration_evaluation_manifest.json"
SOURCE_VOCABULARY = "VOCAB-DEV-2026-08-12-BATCH01-R5"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accepted_r5_runs() -> dict[str, tuple[dict, Path]]:
    results = {}
    for events_path in RUNS.glob("RUN-*/events.jsonl"):
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        start = next((event for event in events if event.get("event_type") == "run_started"), {})
        finish = next((event for event in reversed(events) if event.get("event_type") == "run_finished"), None)
        if not finish or not finish.get("accepted") or start.get("vocabulary_lock_id") != SOURCE_VOCABULARY:
            continue
        rid = finish["requirement_id"]
        if rid not in results or finish["timestamp_utc"] > results[rid][0]["timestamp_utc"]:
            results[rid] = (finish, events_path.parent)
    return results


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    runs = accepted_r5_runs()
    items = []
    for case in catalog["caseRecords"]:
        run = runs.get(case["requirementId"])
        if not run:
            continue
        finish, run_dir = run
        shape = run_dir / "final/final_shape.ttl"
        data = ROOT / case["rdfFile"]
        items.append({
            "case_id": case["caseId"], "variant_id": case["caseKind"],
            "case_level": "r5-shape-r6-fixture-migration-diagnostic",
            "requirement_ids": [case["requirementId"]],
            "shape_file": str(shape.resolve()), "data_file": str(data.resolve()),
            "shape_sha256": sha256(shape), "data_sha256": sha256(data),
            "expected_conforms": case["expectedConforms"],
            "generation_run_id": finish["run_id"],
            "development_vocabulary_id": case["developmentVocabularyId"],
        })
    payload = {
        "evaluation_id": "BATCH01-R6-MIGRATION-R5-SHAPES",
        "status": "DEVELOPMENT_MIGRATION_DIAGNOSTIC",
        "warning": "R5 shapes against R6 fixtures; used only to reduce unnecessary R6 API reruns.",
        "accepted_requirements": len({item["requirement_ids"][0] for item in items}),
        "items": items,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(OUTPUT), "requirements": payload["accepted_requirements"], "items": len(items)}, indent=2))


if __name__ == "__main__":
    main()
