#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
EVALUATION = EXPERIMENT.parents[1] / "evaluation"
if str(EVALUATION) not in sys.path:
    sys.path.insert(0, str(EVALUATION))

from experiment_runner.core import FAMILY_ORDER, find_repo_root, load_benchmark, requirement_sort_key, sha256


SEED = "NLTL-FULL-REPAIR-V2-MODEL-SCALING-50-20260917-v1"
AUDIT_SEED = "NLTL-FULL-REPAIR-V2-MODEL-SCALING-AUDIT-20-20260917-v1"
MODE_TARGETS = {"DIRECT_STATIC": 20, "DIRECT_CALCULATION": 15, "COMPLEX_READINESS": 15}
AUDIT_TARGETS = {"DIRECT_STATIC": 8, "DIRECT_CALCULATION": 6, "COMPLEX_READINESS": 6}
MODE_ORDER = {name: index for index, name in enumerate(MODE_TARGETS)}


def stable_score(seed: str, purpose: str, mode: str, family: str, requirement_id: str) -> str:
    return hashlib.sha256(f"{seed}|{purpose}|{mode}|{family}|{requirement_id}".encode()).hexdigest()


def allocate(target: int, counts: dict[str, int]) -> dict[str, int]:
    families = [family for family in FAMILY_ORDER if counts.get(family, 0)]
    if target < len(families):
        raise RuntimeError("Target cannot represent every available family")
    allocation = {family: 1 for family in families}
    remaining = target - len(families)
    total = sum(counts[family] for family in families)
    ideals = {family: remaining * counts[family] / total for family in families}
    for family in families:
        allocation[family] += int(ideals[family])
    left = target - sum(allocation.values())
    order = sorted(families, key=lambda f: (-(ideals[f] - int(ideals[f])), FAMILY_ORDER[f]))
    for family in order[:left]:
        allocation[family] += 1
    if any(allocation[family] > counts[family] for family in families):
        raise RuntimeError(f"Allocation exceeds a source stratum: {allocation} vs {counts}")
    return allocation


def select(rows: list[dict], targets: dict[str, int], seed: str, purpose: str) -> tuple[list[dict], dict[str, dict[str, int]]]:
    pools: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        pools[(row["verification_mode"], row["source_family"])].append(row)
    selected: list[dict] = []
    allocations: dict[str, dict[str, int]] = {}
    for mode, target in targets.items():
        counts = {family: len(pools[(mode, family)]) for family in FAMILY_ORDER}
        allocations[mode] = allocate(target, counts)
        for family, quota in allocations[mode].items():
            candidates = sorted(
                pools[(mode, family)],
                key=lambda row: (stable_score(seed, purpose, mode, family, row["requirement_id"]), row["requirement_id"]),
            )
            selected.extend(candidates[:quota])
    return sorted(
        selected,
        key=lambda row: (MODE_ORDER[row["verification_mode"]], FAMILY_ORDER[row["source_family"]], row["requirement_id"]),
    ), allocations


def counts(rows: list[dict]) -> dict:
    return {
        "total": len(rows),
        "by_verification_mode": dict(sorted(Counter(row["verification_mode"] for row in rows).items())),
        "by_source_family": dict(sorted(Counter(row["source_family"] for row in rows).items(), key=lambda x: FAMILY_ORDER[x[0]])),
        "by_mode_and_family": {
            mode: {
                family: sum(row["verification_mode"] == mode and row["source_family"] == family for row in rows)
                for family in FAMILY_ORDER
            }
            for mode in MODE_TARGETS
        },
    }


def payload(rows: list[dict], *, seed: str, purpose: str, targets: dict[str, int], allocations: dict) -> dict:
    return {
        "manifest_version": "1.0.0",
        "purpose": purpose,
        "seed": seed,
        "selection_inputs": "Frozen R13 benchmark metadata only; no generation, ablation, or RDF performance fields.",
        "algorithm": "Within verification mode, allocate target counts across source families by minimum-one Hamilton proportional allocation using population sizes; rank each stratum by SHA256(seed|purpose|mode|family|requirement_id), tie-break by requirement_id.",
        "stable_output_order": "verification mode target order, source family order I2/TRAFICOM/IMO/IMO26, requirement_id",
        "targets": targets,
        "family_allocations": allocations,
        "counts": counts(rows),
        "requirements": [row["requirement_id"] for row in rows],
        "records": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write frozen manifests; otherwise verify existing files")
    args = parser.parse_args()
    repo = find_repo_root()
    benchmark = load_benchmark(repo, strict_counts=True)
    grouped = benchmark.by_requirement()
    population = [{
        "requirement_id": requirement_id,
        "verification_mode": cases[0].verification_mode,
        "source_family": cases[0].source_family,
        "source_id": cases[0].source_id,
        "source_clause": cases[0].source_clause,
        "frozen_case_count": len(cases),
    } for requirement_id, cases in grouped.items()]
    sample_rows, sample_allocations = select(population, MODE_TARGETS, SEED, "SAMPLE50")
    sample = payload(sample_rows, seed=SEED, purpose="SAMPLE50", targets=MODE_TARGETS, allocations=sample_allocations)
    audit_rows, audit_allocations = select(sample_rows, AUDIT_TARGETS, AUDIT_SEED, "MANUAL_AUDIT20")
    audit = payload(audit_rows, seed=AUDIT_SEED, purpose="MANUAL_AUDIT20", targets=AUDIT_TARGETS, allocations=audit_allocations)
    simple_static = min(
        (row for row in sample_rows if row["verification_mode"] == "DIRECT_STATIC"),
        key=lambda row: (row["frozen_case_count"], stable_score(SEED, "SMOKE_STATIC", row["verification_mode"], row["source_family"], row["requirement_id"])),
    )
    complex_row = min(
        (row for row in sample_rows if row["verification_mode"] == "COMPLEX_READINESS"),
        key=lambda row: (row["frozen_case_count"], stable_score(SEED, "SMOKE_COMPLEX", row["verification_mode"], row["source_family"], row["requirement_id"])),
    )
    smoke = {
        "manifest_version": "1.0.0",
        "purpose": "PIPELINE_SMOKE_ONLY_EXCLUDED_FROM_FINAL_RESULTS",
        "sample_manifest_seed": SEED,
        "requirements": [simple_static["requirement_id"], complex_row["requirement_id"]],
        "records": [simple_static, complex_row],
    }
    manifests = EXPERIMENT / "MANIFESTS"
    paths = {
        "sample": manifests / "sample_50.json",
        "manual_audit": manifests / "manual_audit_20.json",
        "smoke": manifests / "smoke_2.json",
    }
    values = {"sample": sample, "manual_audit": audit, "smoke": smoke}
    encoded = {name: json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n" for name, value in values.items()}
    if args.write:
        manifests.mkdir(parents=True, exist_ok=True)
        for name, path in paths.items():
            path.write_text(encoded[name], encoding="utf-8")
        lock = {
            "lock_version": "1.0.0",
            "benchmark_integrity_hash": benchmark.integrity_hash,
            "files": {name: {"path": str(path.relative_to(repo)), "sha256": sha256(path)} for name, path in paths.items()},
        }
        (manifests / "manifest_lock.json").write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        lock = json.loads((manifests / "manifest_lock.json").read_text(encoding="utf-8"))
        if lock["benchmark_integrity_hash"] != benchmark.integrity_hash:
            raise RuntimeError("Frozen benchmark identity changed")
        for name, path in paths.items():
            if path.read_text(encoding="utf-8") != encoded[name] or sha256(path) != lock["files"][name]["sha256"]:
                raise RuntimeError(f"Frozen manifest mismatch: {path}")
    print(json.dumps({"sample": counts(sample_rows), "manual_audit": counts(audit_rows), "smoke": smoke["requirements"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
