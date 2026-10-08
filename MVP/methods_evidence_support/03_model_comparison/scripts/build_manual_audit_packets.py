#!/usr/bin/env python3
"""Build blank, rubric-compatible manual-audit packets for the frozen subset."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

EXPERIMENT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = EXPERIMENT.parents[1]
EVALUATION = PIPELINE_ROOT / "evaluation"
sys.path.insert(0, str(PIPELINE_ROOT / "src"))
sys.path.insert(0, str(EVALUATION))

from experiment_runner.core import find_repo_root, load_benchmark  # noqa: E402

import summarize  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


RUBRIC = [
    ("Q1", "Applicability and target", "semantic_fidelity", 2),
    ("Q2", "Ontology terms, ownership and paths", "semantic_fidelity", 2),
    ("Q3", "Required obligations are complete", "semantic_fidelity", 2),
    ("Q4", "Constraint parameters, units and calculations", "semantic_fidelity", 2),
    ("Q5", "Logic, branches, exceptions and boundaries", "semantic_fidelity", 2),
    ("Q6", "No unsupported restrictions", "semantic_fidelity", 2),
    ("Q7", "Source traceability", "semantic_fidelity", 2),
    ("CQ1", "Analyzability and maintainability", "implementation_quality", 2),
    ("CQ2", "Internal consistency and non-redundancy", "implementation_quality", 2),
    ("CQ3", "Diagnostic usefulness", "implementation_quality", 2),
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def shape_text(row: dict[str, Any]) -> str | None:
    run_dir_raw = row.get("run_dir")
    if not run_dir_raw:
        return None
    explicit = row.get("final_shape_path")
    if explicit:
        raw_path = Path(str(explicit))
        path = raw_path if raw_path.is_absolute() else summarize.REPO_ROOT / raw_path
    else:
        artifact_candidates = sorted((Path(str(run_dir_raw)) / "artifacts").glob("final_accepted_shape*.ttl"))
        path = artifact_candidates[0] if len(artifact_candidates) == 1 else Path("/__unavailable__")
    return path.read_text(encoding="utf-8") if path.exists() else None


def stable_cases(cases: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for expected in ("PASS", "FAIL"):
        candidates = sorted((c for c in cases if c.expected_outcome == expected), key=lambda c: c.case_id)
        if candidates:
            c = candidates[0]
            result.append({
                "case_id": c.case_id,
                "expected_verdict": c.expected_outcome,
                "fixture_path": c.rdf_path,
                "source_oracle_rationale": c.source_oracle_rationale,
                "test_pattern": c.test_pattern,
            })
    return result


def main() -> int:
    audit = load_json(EXPERIMENT / "MANIFESTS" / "manual_audit_20.json")
    req_ids = [str(r["requirement_id"]) for r in audit["requirements"]]
    repo = find_repo_root()
    benchmark = load_benchmark(repo)
    grouped_cases = benchmark.by_requirement()
    gen_by_model: dict[str, dict[str, dict[str, Any]]] = {}
    behavior_by_model: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for model_key in summarize.MODEL_ORDER:
        rows = summarize.generation_rows(model_key, set(load_json(EXPERIMENT / "MANIFESTS" / "sample_50.json")["requirement_ids"]))
        gen_by_model[model_key] = {str(r["requirement_id"]): r for r in rows}
        behavior: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in summarize.behavior_rows(model_key):
            behavior[str(row["requirement_id"])].append(row)
        behavior_by_model[model_key] = behavior

    out = EXPERIMENT / "MANUAL_AUDIT"
    packets = out / "packets"
    packets.mkdir(parents=True, exist_ok=True)
    packet_manifest: list[dict[str, Any]] = []
    scoring_rows: list[dict[str, Any]] = []
    for rid in req_ids:
        cases = grouped_cases[rid]
        luna_row = gen_by_model["luna"][rid]
        context_path = repo / str(luna_row["context_path"])
        context = load_json(context_path)["requirement"]
        selected_cases = stable_cases(cases)
        selected_case_ids = {row["case_id"] for row in selected_cases}
        packet: dict[str, Any] = {
            "requirement_id": rid,
            "family": cases[0].source_family,
            "verification_mode": cases[0].verification_mode,
            "requirement_text": context.get("requirementText"),
            "context": context,
            "selected_cases": selected_cases,
            "rubric": [
                {"code": code, "criterion": criterion, "dimension": dimension, "max_score": maximum}
                for code, criterion, dimension, maximum in RUBRIC
            ],
            "rubric_totals": {"semantic_fidelity_max": 14, "implementation_quality_max": 6},
            "models": {},
        }
        for model_key in summarize.MODEL_ORDER:
            grow = gen_by_model[model_key][rid]
            packet["models"][model_key] = {
                "model_id": summarize.MODEL_IDS[model_key],
                "generation_status": grow.get("status"),
                "accepted": bool(grow.get("accepted")),
                "attempts": grow.get("attempts"),
                "artifact_available": bool(grow.get("artifact_available")),
                "artifact_sha256": grow.get("artifact_sha256"),
                "generated_shacl": shape_text(grow),
                "behavioral_case_observations": sorted(
                    (r for r in behavior_by_model[model_key][rid] if r.get("case_id") in selected_case_ids),
                    key=lambda r: str(r.get("case_id", "")),
                ),
            }
            scoring_row: dict[str, Any] = {
                "requirement_id": rid,
                "family": cases[0].source_family,
                "verification_mode": cases[0].verification_mode,
                "model_key": model_key,
                "model_id": summarize.MODEL_IDS[model_key],
            }
            for code, _criterion, _dimension, _maximum in RUBRIC:
                scoring_row[code] = ""
                scoring_row[f"{code}_notes"] = ""
            scoring_row["semantic_fidelity_total_max_14"] = ""
            scoring_row["implementation_quality_total_max_6"] = ""
            scoring_row["auditor"] = ""
            scoring_row["audit_notes"] = ""
            scoring_rows.append(scoring_row)
        packet_path = packets / f"{rid}.json"
        packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        packet_manifest.append({"requirement_id": rid, "path": str(packet_path), "sha256": sha256_file(packet_path)})

    csv_path = out / "manual_audit_scoring.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(scoring_rows[0]))
        writer.writeheader()
        writer.writerows(scoring_rows)
    manifest_path = out / "packet_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "audit_manifest_sha256": sha256_file(EXPERIMENT / "MANIFESTS" / "manual_audit_20.json"),
                "rubric": [{"code": c, "criterion": q, "dimension": d, "max_score": m} for c, q, d, m in RUBRIC],
                "semantic_fidelity_max": 14,
                "implementation_quality_max": 6,
                "packets": packet_manifest,
                "scoring_csv": str(csv_path),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"packets": len(packet_manifest), "scoring_rows": len(scoring_rows), "manifest": str(manifest_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
