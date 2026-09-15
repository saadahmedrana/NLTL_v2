from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .candidate_diagnostics import (
    _parse_candidate,
    discover_candidates,
    execute_diagnostic,
)
from .core import PreflightError, find_repo_root, load_benchmark, run_integrity_check


DIAGNOSTIC_CONFIGURATION = "FULL_REPAIR_V2_REJECTED_ATTEMPT4_DIAGNOSTIC"
PARENT_CONFIGURATION = "FULL_REPAIR_V2"
GENERATION_RUN = "RUN_01"
CANDIDATE_ATTEMPT = 4
MANIFEST_RELATIVE_PATH = Path(
    "MVP/SHACL_GENERATION_PIPELINE/evaluation/generated_rule_manifests/RUN_01/"
    "full_repair_v2_rejected_attempt4_diagnostic.jsonl"
)


def _payload(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def select_population(repo: Path, benchmark: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, inventory = discover_candidates(repo, [GENERATION_RUN], PARENT_CONFIGURATION)
    candidates_by_requirement: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_requirement[candidate["requirement_id"]].append(candidate)

    unsuccessful = [record for record in inventory if record["overall_requirement_eventually_aborted"]]
    attempt4_final = [
        record for record in unsuccessful
        if record["pipeline_attempts_recorded"] == CANDIDATE_ATTEMPT
    ]
    stopped_before_attempt4 = [
        record for record in unsuccessful
        if record["pipeline_attempts_recorded"] < CANDIDATE_ATTEMPT
    ]
    if any(record["pipeline_attempts_recorded"] > CANDIDATE_ATTEMPT for record in unsuccessful):
        raise PreflightError("An unsuccessful V2 RUN_01 requirement records an attempt after attempt 4")

    available: list[tuple[dict[str, Any], dict[str, Any]]] = []
    parse_failures: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    benchmark_sources = {case.requirement_id: case.source_id for case in benchmark.cases}
    for record in attempt4_final:
        requirement_candidates = candidates_by_requirement.get(record["requirement_id"], [])
        attempt4 = [candidate for candidate in requirement_candidates if candidate["attempt_number"] == CANDIDATE_ATTEMPT]
        later = [candidate for candidate in requirement_candidates if candidate["attempt_number"] > CANDIDATE_ATTEMPT]
        if later:
            raise PreflightError(f"Later candidate exists for final-attempt-4 requirement {record['requirement_id']}")
        if len(attempt4) > 1:
            raise PreflightError(f"Duplicate attempt-4 candidate for {record['requirement_id']}")
        if not attempt4:
            continue
        candidate = attempt4[0]
        available.append((record, candidate))
        if candidate["candidate_artifact_type"] != "candidate_shape" or candidate["candidate_artifact_iteration"] != 4:
            raise PreflightError(f"Attempt-4 artifact metadata mismatch for {record['requirement_id']}")
        if candidate["became_official_accepted_output"] or record["overall_final_status"] == "GENERATION_ACCEPTED":
            raise PreflightError(f"Accepted output entered rejected-attempt-4 selection: {record['requirement_id']}")
        if benchmark_sources.get(record["requirement_id"]) != candidate["source_id"]:
            raise PreflightError(f"Frozen benchmark source mismatch for {record['requirement_id']}")
        _graph, parse_error = _parse_candidate(repo, candidate)
        if parse_error:
            parse_failures.append({"requirement_id": record["requirement_id"], "error": parse_error})
            continue
        selected.append({
            **candidate,
            "diagnostic_configuration": DIAGNOSTIC_CONFIGURATION,
            "parent_configuration": PARENT_CONFIGURATION,
            "configuration": DIAGNOSTIC_CONFIGURATION,
            "candidate_attempt": CANDIDATE_ATTEMPT,
            "pipeline_attempts_recorded": record["pipeline_attempts_recorded"],
            "final_preserved_candidate_attempt": max(candidate["preserved_attempt_numbers"]),
            "original_final_status": record["overall_final_status"],
            "official_final_shape": False,
            "diagnostic_only": True,
            "generation_status": "GENERATED",
            "generated_shacl_path": candidate["candidate_path"],
            "generated_shacl_sha256": candidate["candidate_sha256"],
            "selection_basis": (
                "Rejected FULL_REPAIR_V2 RUN_01 run metadata records ATTEMPTS=4; "
                "candidate_shape artifact metadata records ITERATION=4; no later candidate exists"
            ),
        })

    selected.sort(key=lambda row: row["requirement_id"])
    selected_inventory = [
        record for record in unsuccessful
        if record["requirement_id"] in {candidate["requirement_id"] for candidate in selected}
    ]
    selected_ids = [candidate["requirement_id"] for candidate in selected]
    if len(selected_ids) != len(set(selected_ids)):
        raise PreflightError("Duplicate selected rejected-attempt-4 requirement")
    selected_cases = [case for case in benchmark.cases if case.requirement_id in set(selected_ids)]
    if {case.requirement_id for case in selected_cases} != set(selected_ids):
        raise PreflightError("A selected diagnostic requirement is absent from frozen R13")

    summary = {
        "unsuccessful_official_requirements": len(unsuccessful),
        "unsuccessful_by_final_status": dict(sorted(Counter(r["overall_final_status"] for r in unsuccessful).items())),
        "final_candidate_generation_attempt4": len(attempt4_final),
        "available_attempt4_ttl": len(available),
        "parseable_attempt4_ttl": len(selected),
        "excluded_stopped_before_attempt4": len(stopped_before_attempt4),
        "excluded_no_usable_attempt4_ttl": len(attempt4_final) - len(selected),
        "selected_requirements": len(selected),
        "expected_diagnostic_case_rows": len(selected_cases),
        "parse_failures": parse_failures,
    }
    return selected, selected_inventory, summary


def _prepare_manifest(path: Path, candidates: list[dict[str, Any]]) -> str:
    content = _payload(candidates)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise PreflightError(f"Existing diagnostic manifest differs; refusing overwrite: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Evaluate only rejected final attempt-4 FULL_REPAIR_V2 RUN_01 candidates")
    result.add_argument("--configuration", choices=(DIAGNOSTIC_CONFIGURATION,), required=True)
    result.add_argument("--generation-run", choices=(GENERATION_RUN,), required=True)
    result.add_argument("--run-id")
    result.add_argument("--prepare-only", action="store_true")
    result.add_argument("--resume", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.prepare_only and args.resume:
        print("DIAGNOSTIC PREFLIGHT FAILURE: --prepare-only and --resume are incompatible", file=sys.stderr)
        return 2
    if args.resume and not args.run_id:
        print("DIAGNOSTIC PREFLIGHT FAILURE: --resume requires --run-id", file=sys.stderr)
        return 2
    repo = find_repo_root()
    manifest_path = repo / MANIFEST_RELATIVE_PATH
    try:
        integrity = run_integrity_check(repo)
        benchmark = load_benchmark(repo, strict_counts=True)
        candidates, inventory, population = select_population(repo, benchmark)
        manifest_sha = _prepare_manifest(manifest_path, candidates)
        print(json.dumps({**population, "manifest": str(MANIFEST_RELATIVE_PATH), "manifest_sha256": manifest_sha}, indent=2, sort_keys=True))
        if args.prepare_only:
            print("Rejected-attempt-4 diagnostic preparation complete; no behavioural cases executed")
            return 0

        content = _payload(candidates)
        if manifest_path.read_text(encoding="utf-8") != content:
            raise PreflightError("Prepared rejected-attempt-4 manifest changed")
        run_id = args.run_id or (
            "BEHAVIORAL-R13-FULL-REPAIR-V2-REJECTED-A4-RUN01-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        )
        output_dir = repo / "MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results" / run_id
        selected_ids = {candidate["requirement_id"] for candidate in candidates}
        cases = [case for case in benchmark.cases if case.requirement_id in selected_ids]
        ledger = execute_diagnostic(
            repo=repo,
            benchmark=benchmark,
            cases=cases,
            candidates=candidates,
            inventory=inventory,
            output_dir=output_dir,
            diagnostic_id=run_id,
            command_line=[sys.executable, str(Path(sys.argv[0]).resolve()), *(argv if argv is not None else sys.argv[1:])],
            integrity=integrity,
            resume=args.resume,
            candidate_manifest_filename="diagnostic_candidate_manifest.jsonl",
            inventory_filename="diagnostic_requirement_inventory.jsonl",
            ledger_filename="raw_case_results.jsonl",
            run_manifest_filename="run_manifest.json",
            standard_outputs=True,
        )
        print(f"Diagnostic run complete: {run_id}")
        print(f"Configuration: {DIAGNOSTIC_CONFIGURATION}")
        print(f"Rejected attempt-4 requirements: {len(candidates)}")
        print(f"Case rows: {sum(1 for line in ledger.read_text(encoding='utf-8').splitlines() if line.strip())}")
        print(f"Raw ledger: {ledger.relative_to(repo)}")
        print("Official FULL_REPAIR_V2 results modified: NO")
        print("Frozen benchmark modified: NO")
        return 0
    except PreflightError as exc:
        print(f"DIAGNOSTIC PREFLIGHT/FINALIZATION FAILURE: {exc}", file=sys.stderr)
        return 2
