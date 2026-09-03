from __future__ import annotations

import subprocess
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = PIPELINE_ROOT.parent
PREPARATION = Path(__file__).resolve().parent


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> None:
    status = git("status", "--short", "--branch", "--untracked-files=all")
    if status.returncode != 0:
        raise SystemExit(status.stderr or status.stdout)
    protected = git(
        "status",
        "--short",
        "--",
        "SHACL_GENERATION_PIPELINE/experiments/FINAL_LUNA_MAIN",
        "BENCHMARK_VOCABULARY/FINAL_LOCK_R13",
        "benchmark_vocabulary_stage2_LOCK-2026-08-22-R13.lock.json",
    )
    if protected.returncode != 0:
        raise SystemExit(protected.stderr or protected.stdout)
    status_text = status.stdout
    status_text += "\nPROTECTED R13/FINAL_LUNA_MAIN STATUS:\n"
    status_text += protected.stdout or "CLEAN / UNCHANGED\n"
    (PREPARATION / "git_status_after.txt").write_text(status_text, encoding="utf-8")

    tracked = git("diff", "--", "SHACL_GENERATION_PIPELINE/src/nltl_pipeline/cli.py")
    if tracked.returncode != 0:
        raise SystemExit(tracked.stderr or tracked.stdout)
    pieces = [tracked.stdout]
    new_files = [
        "SHACL_GENERATION_PIPELINE/src/nltl_pipeline/orchestration/singleshot.py",
        "SHACL_GENERATION_PIPELINE/tests/test_contextual_singleshot.py",
        "SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/CONFIGS/pipeline.luna-contextual-singleshot-smoke.json",
        "SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/CONFIGS/pipeline.luna-contextual-singleshot-run01.json",
        "SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/QUEUES/luna_contextual_singleshot_268_frozen.json",
        "SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/PREPARATION/architecture_audit.md",
        "SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/PREPARATION/verify_first_call_equivalence.py",
        "SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/PREPARATION/capture_repository_state.py",
    ]
    for relative in new_files:
        result = git("diff", "--no-index", "--", "/dev/null", relative)
        if result.returncode not in {0, 1}:
            raise SystemExit(result.stderr or result.stdout)
        pieces.append(result.stdout)
    (PREPARATION / "implementation.patch").write_text("".join(pieces), encoding="utf-8")


if __name__ == "__main__":
    main()
