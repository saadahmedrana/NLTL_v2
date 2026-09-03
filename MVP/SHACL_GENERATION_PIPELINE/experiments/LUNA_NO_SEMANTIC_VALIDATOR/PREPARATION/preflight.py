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
EXPECTED_QUEUE_SHA256 = "d6b540573dd7b6af5c59e369b2f37b86a864eefd81ea44ef49f137af07bd7331"
MODEL = "gpt-5.6-luna-2026-07-09"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_path(number: int) -> Path:
    return EXPERIMENT / "CONFIGS" / f"pipeline.luna-no-semantic-validator-run{number:02d}.json"


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(raw))
    payload["pipeline_version"] = "<RUN_SPECIFIC>"
    payload["paths"]["outputs"] = "<RUN_SPECIFIC>"
    return payload


def validate_common() -> list[dict[str, Any]]:
    if digest(QUEUE) != EXPECTED_QUEUE_SHA256 or QUEUE.read_bytes() != FULL_QUEUE.read_bytes():
        raise SystemExit("Frozen queue hash/content does not match FINAL_LUNA_MAIN")
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    requirements = queue.get("requirements", [])
    if len(requirements) != 268 or len(set(requirements)) != 268 or queue.get("repetitions") != 1:
        raise SystemExit("Frozen queue is not exactly 268 unique requirements with one repetition")

    configs: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    for number in range(1, 6):
        path = config_path(number)
        if not path.is_file():
            raise SystemExit(f"Missing formal config: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        expected_output = f"experiments/LUNA_NO_SEMANTIC_VALIDATOR/RUN_{number:02d}"
        if raw["paths"]["outputs"] != expected_output:
            raise SystemExit(f"RUN_{number:02d} output path mismatch")
        if set(raw["models"].values()) != {MODEL}:
            raise SystemExit(f"RUN_{number:02d} does not use Luna for every configured role")
        expected_ablation = {
            "execution_mode": "LUNA_NO_SEMANTIC_VALIDATOR",
            "semantic_validator_enabled": False,
            "syntax_repair_enabled": True,
            "vocabulary_matcher_enabled": False,
            "semantic_regeneration_enabled": False,
            "deterministic_diagnostics_trigger_regeneration": False,
        }
        if raw.get("ablation") != expected_ablation:
            raise SystemExit(f"RUN_{number:02d} ablation controls are not exact")
        config = PipelineConfig.load(path)
        vocabulary = VocabularyRepository(config)
        eligible = [item for item in vocabulary.requirements.values() if vocabulary.is_generation_eligible(item)]
        if vocabulary.lock_info["lock_id"] != "VOCAB-LOCK-2026-08-22-R13":
            raise SystemExit(f"RUN_{number:02d} does not resolve R13")
        if len(eligible) != 268:
            raise SystemExit(f"RUN_{number:02d} resolves {len(eligible)} eligible requirements, not 268")
        configs.append(raw)
        normalized.append(normalize(raw))
    if any(item != normalized[0] for item in normalized[1:]):
        raise SystemExit("Formal configs differ in scientific fields")
    return configs


def require_empty(number: int) -> None:
    output = EXPERIMENT / f"RUN_{number:02d}"
    output.mkdir(parents=True, exist_ok=True)
    entries = list(output.iterdir())
    if entries:
        completed = list(output.glob("sessions/*/batch_result.json"))
        label = "completed formal results" if completed else "existing/incomplete artifacts"
        raise SystemExit(f"RUN_{number:02d} is not empty ({label}); refusing overwrite")


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


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--run", type=int, choices=range(1, 6))
    group.add_argument("--verify-completed", type=int, choices=range(1, 6))
    args = parser.parse_args()
    validate_common()
    if args.check:
        for number in range(1, 6):
            require_empty(number)
        print(json.dumps({
            "status": "PASS",
            "api_calls": 0,
            "configs": 5,
            "queue_sha256": EXPECTED_QUEUE_SHA256,
            "requirements": 268,
            "lock": "VOCAB-LOCK-2026-08-22-R13",
            "model": MODEL,
            "semantic_validator_enabled": False,
            "syntax_repair_enabled": True,
            "vocabulary_matcher_enabled": False,
            "semantic_regeneration_enabled": False,
            "outputs_empty": True,
        }, indent=2))
    elif args.run:
        require_empty(args.run)
        print(f"RUN_{args.run:02d} PRE-RUN CHECK PASS")
    else:
        verify_completed(args.verify_completed)
        print(f"RUN_{args.verify_completed:02d} COMPLETION CHECK PASS")


if __name__ == "__main__":
    main()
