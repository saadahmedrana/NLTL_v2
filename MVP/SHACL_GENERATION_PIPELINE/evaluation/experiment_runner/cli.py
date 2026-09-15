from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .analysis import analyze
from .core import (
    CONFIGURATIONS,
    GENERATION_RUNS,
    PreflightError,
    build_generated_manifest,
    find_repo_root,
    load_benchmark,
    load_generated_manifest,
    run_integrity_check,
    select_cases,
    validate_generated_manifest,
)
from .execution import execute


def default_run_id(generation_runs: list[str]) -> str:
    scope = "RUN01-RUN10" if generation_runs == list(GENERATION_RUNS) else generation_runs[0]
    return f"BEHAVIORAL-R13-{scope}-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Execute frozen generation runs against matching frozen R13 cases")
    selection = result.add_mutually_exclusive_group(required=True)
    selection.add_argument("--config", choices=CONFIGURATIONS)
    selection.add_argument("--all", action="store_true", help="Evaluate FULL_REPAIR_V2, FULL, NO_SEMANTIC, and available SINGLESHOT runs")
    result.add_argument(
        "--build-manifests-only",
        action="store_true",
        help="Build only the manifests selected by --config/--all and --generation-run/--all-generation-runs",
    )
    result.add_argument("--requirement")
    result.add_argument("--family", choices=("I2", "TRF", "TRAFICOM", "IMO", "IMO26"))
    result.add_argument("--case")
    result.add_argument("--smoke", action="store_true", help="Development run; first requirement unless another filter is supplied")
    runs = result.add_mutually_exclusive_group()
    runs.add_argument("--generation-run", choices=GENERATION_RUNS, default="RUN_01")
    runs.add_argument("--all-generation-runs", action="store_true", help="Select RUN_01 through RUN_10")
    result.add_argument("--run-id")
    result.add_argument("--resume", action="store_true")
    result.add_argument("--output-root", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    repo = find_repo_root()
    evaluation_root = repo / "MVP/SHACL_GENERATION_PIPELINE/evaluation"
    generation_runs = list(GENERATION_RUNS) if args.all_generation_runs else [args.generation_run]
    configurations = list(CONFIGURATIONS) if args.all else [args.config]
    try:
        integrity = run_integrity_check(repo)
        benchmark = load_benchmark(repo, strict_counts=True)
        generated_paths: dict[str, dict[str, Path]] = {}
        generated_indexes: dict[str, dict[str, dict[str, dict]]] = {}
        for generation_run in generation_runs:
            generated_root = evaluation_root / "generated_rule_manifests" / generation_run
            generated_paths[generation_run] = {}
            generated_indexes[generation_run] = {}
            for configuration in configurations:
                if configuration == "SINGLESHOT":
                    run_root = evaluation_root.parent / "experiments/LUNA_CONTEXTUAL_SINGLESHOT" / generation_run / "runs"
                    if not run_root.is_dir() or not any(path.is_dir() for path in run_root.iterdir()):
                        # SINGLESHOT was only actually generated where run artifacts exist;
                        # absent RUN_02--RUN_10 are unavailable comparisons, not failures.
                        continue
                path = generated_root / f"{configuration.lower()}_generated_rules.jsonl"
                build_generated_manifest(repo, configuration, generation_run, path)
                rows = load_generated_manifest(path, configuration, generation_run)
                generated_indexes[generation_run][configuration] = validate_generated_manifest(
                    repo, benchmark, configuration, generation_run, rows, strict_counts=True
                )
                generated_paths[generation_run][configuration] = path
        if args.build_manifests_only:
            print("Generated-rule manifests built and validated:")
            for generation_run in generation_runs:
                for configuration in generated_indexes[generation_run]:
                    statuses: dict[str, int] = {}
                    for row in generated_indexes[generation_run][configuration].values():
                        status = row["generation_status"]
                        statuses[status] = statuses.get(status, 0) + 1
                    print(
                        f"  {generation_run} {configuration}: "
                        f"{generated_paths[generation_run][configuration].relative_to(repo)} "
                        f"{json.dumps(statuses, sort_keys=True)}"
                    )
            print("Frozen benchmark integrity: PASS (268 requirements / 2186 cases)")
            return 0
        if (args.requirement or args.family or args.case) and not args.smoke:
            raise PreflightError("Development filters require --smoke; final mode always evaluates complete selected configurations")
        cases = select_cases(benchmark, args.requirement, args.family, args.case, args.smoke)
        run_id = args.run_id or default_run_id(generation_runs)
        if args.resume and not args.run_id:
            raise PreflightError("--resume requires --run-id")
        output_root = args.output_root or evaluation_root / "experiment_results"
        output_dir = output_root / run_id
        ledger = execute(
            repo=repo,
            benchmark=benchmark,
            cases=cases,
            generation_runs=generation_runs,
            configurations=configurations,
            generated_by_run_config=generated_indexes,
            generated_manifest_paths=generated_paths,
            output_dir=output_dir,
            run_id=run_id,
            command_line=[sys.executable, str(Path(sys.argv[0]).resolve()), *(argv if argv is not None else sys.argv[1:])],
            integrity_result=integrity,
            resume=args.resume,
        )
        summaries = analyze(ledger)
        print(f"Run complete: {run_id}")
        print(f"Raw ledger: {ledger.relative_to(repo)}")
        print(f"Summaries: {summaries.relative_to(repo)}")
        print(f"Rows: {sum(1 for line in ledger.read_text(encoding='utf-8').splitlines() if line.strip())}")
        print("Frozen benchmark modified: NO")
        return 0
    except PreflightError as exc:
        print(f"PREFLIGHT/FINALIZATION FAILURE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
