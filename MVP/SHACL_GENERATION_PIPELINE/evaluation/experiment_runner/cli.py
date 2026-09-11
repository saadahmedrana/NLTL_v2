from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .analysis import analyze
from .core import (
    CONFIGURATIONS,
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


def default_run_id() -> str:
    return "BEHAVIORAL-R13-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Execute RUN01 generated SHACL against matching frozen R13 cases")
    selection = result.add_mutually_exclusive_group(required=True)
    selection.add_argument("--config", choices=CONFIGURATIONS)
    selection.add_argument("--all", action="store_true", help="Evaluate FULL, NO_SEMANTIC, and SINGLESHOT")
    selection.add_argument("--build-manifests-only", action="store_true")
    result.add_argument("--requirement")
    result.add_argument("--family", choices=("I2", "TRF", "TRAFICOM", "IMO", "IMO26"))
    result.add_argument("--case")
    result.add_argument("--smoke", action="store_true", help="Development run; first requirement unless another filter is supplied")
    result.add_argument("--run-id")
    result.add_argument("--resume", action="store_true")
    result.add_argument("--output-root", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    repo = find_repo_root()
    evaluation_root = repo / "MVP/SHACL_GENERATION_PIPELINE/evaluation"
    generated_root = evaluation_root / "generated_rule_manifests/RUN_01"
    configurations = list(CONFIGURATIONS) if args.all or args.build_manifests_only else [args.config]
    try:
        integrity = run_integrity_check(repo)
        benchmark = load_benchmark(repo, strict_counts=True)
        generated_paths: dict[str, Path] = {}
        generated_indexes: dict[str, dict[str, dict]] = {}
        for configuration in configurations:
            path = generated_root / f"{configuration.lower()}_generated_rules.jsonl"
            build_generated_manifest(repo, configuration, path)
            rows = load_generated_manifest(path, configuration)
            generated_indexes[configuration] = validate_generated_manifest(
                repo, benchmark, configuration, rows, strict_counts=True
            )
            generated_paths[configuration] = path
        if args.build_manifests_only:
            print("Generated-rule manifests built and validated:")
            for configuration in configurations:
                statuses: dict[str, int] = {}
                for row in generated_indexes[configuration].values():
                    status = row["generation_status"]
                    statuses[status] = statuses.get(status, 0) + 1
                print(f"  {configuration}: {generated_paths[configuration].relative_to(repo)} {json.dumps(statuses, sort_keys=True)}")
            print("Frozen benchmark integrity: PASS (268 requirements / 2186 cases)")
            return 0
        if (args.requirement or args.family or args.case) and not args.smoke:
            raise PreflightError("Development filters require --smoke; final mode always evaluates complete selected configurations")
        cases = select_cases(benchmark, args.requirement, args.family, args.case, args.smoke)
        run_id = args.run_id or default_run_id()
        if args.resume and not args.run_id:
            raise PreflightError("--resume requires --run-id")
        output_root = args.output_root or evaluation_root / "experiment_results"
        output_dir = output_root / run_id
        ledger = execute(
            repo=repo,
            benchmark=benchmark,
            cases=cases,
            configurations=configurations,
            generated_by_config=generated_indexes,
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
