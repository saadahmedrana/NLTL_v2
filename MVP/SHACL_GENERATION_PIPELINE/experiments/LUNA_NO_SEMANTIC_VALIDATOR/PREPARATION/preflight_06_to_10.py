from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.retrieval.context import VocabularyRepository


EXPERIMENT = Path(__file__).resolve().parents[1]
PIPELINE = EXPERIMENT.parents[1]
QUEUE = EXPERIMENT / "QUEUES/luna_no_semantic_validator_268_frozen.json"
FULL_QUEUE = PIPELINE / "experiments/FINAL_LUNA_MAIN/QUEUES/luna_main_268_frozen.json"
BASELINE = EXPERIMENT / "PREPARATION/run01_to_run05_integrity_baseline.json"
EXPECTED_QUEUE_SHA256 = "d6b540573dd7b6af5c59e369b2f37b86a864eefd81ea44ef49f137af07bd7331"
MODEL = "gpt-5.6-luna-2026-07-09"
LOCK = "VOCAB-LOCK-2026-08-22-R13"
EXPECTED_ABLATION = {
    "execution_mode": "LUNA_NO_SEMANTIC_VALIDATOR",
    "semantic_validator_enabled": False,
    "syntax_repair_enabled": True,
    "vocabulary_matcher_enabled": False,
    "semantic_regeneration_enabled": False,
    "deterministic_diagnostics_trigger_regeneration": False,
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(directory: Path) -> tuple[str, int, int]:
    aggregate = hashlib.sha256()
    count = 0
    total_bytes = 0
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        file_hash = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                file_hash.update(chunk)
                total_bytes += len(chunk)
        relative = path.relative_to(directory).as_posix().encode("utf-8")
        aggregate.update(
            relative + b"\0" + str(path.stat().st_size).encode("ascii") + b"\0" + file_hash.digest()
        )
        count += 1
    return aggregate.hexdigest(), count, total_bytes


def config_path(number: int) -> Path:
    return EXPERIMENT / "CONFIGS" / f"pipeline.luna-no-semantic-validator-run{number:02d}.json"


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(raw))
    payload["pipeline_version"] = "<RUN_SPECIFIC>"
    payload["paths"]["outputs"] = "<RUN_SPECIFIC>"
    return payload


def verify_completed(number: int) -> None:
    output = EXPERIMENT / f"RUN_{number:02d}"
    batches = list(output.glob("sessions/*/batch_result.json"))
    if len(batches) != 1:
        raise SystemExit(f"RUN_{number:02d} has {len(batches)} batch results, expected exactly one")
    result = json.loads(batches[0].read_text(encoding="utf-8"))
    if result.get("total_items") != 268 or len(result.get("results", [])) != 268:
        raise SystemExit(f"RUN_{number:02d} batch result is incomplete")
    if result.get("execution_mode") != "LUNA_NO_SEMANTIC_VALIDATOR":
        raise SystemExit(f"RUN_{number:02d} execution mode mismatch")
    if result.get("vocabulary_lock_id") != LOCK:
        raise SystemExit(f"RUN_{number:02d} vocabulary lock mismatch")


def verify_historical_runs() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["runs"]
    for number in range(1, 6):
        name = f"RUN_{number:02d}"
        verify_completed(number)
        actual_hash, actual_files, actual_bytes = tree_digest(EXPERIMENT / name)
        expected = baseline[name]
        if (
            actual_hash != expected["tree_sha256"]
            or actual_files != expected["files"]
            or actual_bytes != expected["bytes"]
        ):
            raise SystemExit(f"{name} differs from its frozen integrity baseline")


def validate_common() -> None:
    if digest(QUEUE) != EXPECTED_QUEUE_SHA256 or QUEUE.read_bytes() != FULL_QUEUE.read_bytes():
        raise SystemExit("Frozen queue hash/content does not match FINAL_LUNA_MAIN")
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    requirements = queue.get("requirements", [])
    if len(requirements) != 268 or len(set(requirements)) != 268 or queue.get("repetitions") != 1:
        raise SystemExit("Frozen queue is not exactly 268 unique requirements with one repetition")

    normalized: list[dict[str, Any]] = []
    for number in range(1, 11):
        path = config_path(number)
        if not path.is_file():
            raise SystemExit(f"Missing formal config: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        expected_output = f"experiments/LUNA_NO_SEMANTIC_VALIDATOR/RUN_{number:02d}"
        expected_version = f"luna-no-semantic-validator-run{number:02d}-v1"
        if raw.get("pipeline_version") != expected_version:
            raise SystemExit(f"RUN_{number:02d} pipeline version mismatch")
        if raw.get("paths", {}).get("outputs") != expected_output:
            raise SystemExit(f"RUN_{number:02d} output path mismatch")
        if set(raw.get("models", {}).values()) != {MODEL}:
            raise SystemExit(f"RUN_{number:02d} does not use Luna for every configured role")
        if raw.get("ablation") != EXPECTED_ABLATION:
            raise SystemExit(f"RUN_{number:02d} ablation controls are not exact")
        normalized.append(normalize(raw))
    if any(item != normalized[0] for item in normalized[1:]):
        raise SystemExit("RUN_01–RUN_10 configs differ in scientific fields")

    config = PipelineConfig.load(config_path(6))
    vocabulary = VocabularyRepository(config)
    eligible = [item for item in vocabulary.requirements.values() if vocabulary.is_generation_eligible(item)]
    if vocabulary.lock_info["lock_id"] != LOCK:
        raise SystemExit("Continuation configs do not resolve R13")
    if len(eligible) != 268:
        raise SystemExit(f"Continuation configs resolve {len(eligible)} eligible requirements, not 268")


def require_empty(number: int) -> None:
    output = EXPERIMENT / f"RUN_{number:02d}"
    output.mkdir(parents=True, exist_ok=True)
    entries = list(output.iterdir())
    if entries:
        completed = list(output.glob("sessions/*/batch_result.json"))
        label = "completed formal results" if completed else "existing/incomplete artifacts"
        raise SystemExit(f"RUN_{number:02d} is not empty ({label}); refusing overwrite")


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--run", type=int, choices=range(6, 11))
    group.add_argument("--verify-completed", type=int, choices=range(6, 11))
    args = parser.parse_args()

    validate_common()
    if args.check:
        verify_historical_runs()
        for number in range(6, 11):
            require_empty(number)
        print(json.dumps({
            "status": "PASS",
            "api_calls": 0,
            "historical_runs_verified_unchanged": 5,
            "configs_scientifically_identical": 10,
            "continuation_configs": 5,
            "queue_sha256": EXPECTED_QUEUE_SHA256,
            "requirements": 268,
            "lock": LOCK,
            "model": MODEL,
            "semantic_validator_enabled": False,
            "syntax_repair_enabled": True,
            "vocabulary_matcher_enabled": False,
            "semantic_regeneration_enabled": False,
            "run_06_to_10_outputs_empty": True,
        }, indent=2))
    elif args.run:
        require_empty(args.run)
        print(f"RUN_{args.run:02d} PRE-RUN CHECK PASS")
    else:
        verify_completed(args.verify_completed)
        print(f"RUN_{args.verify_completed:02d} COMPLETION CHECK PASS")


if __name__ == "__main__":
    main()
