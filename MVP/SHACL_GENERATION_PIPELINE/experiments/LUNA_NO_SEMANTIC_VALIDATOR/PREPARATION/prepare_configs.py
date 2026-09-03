from __future__ import annotations

import copy
import json
from pathlib import Path


EXPERIMENT = Path(__file__).resolve().parents[1]
PIPELINE = EXPERIMENT.parents[1]
FULL_CONFIG = PIPELINE / "experiments/FINAL_LUNA_MAIN/CONFIGS/pipeline.final-luna-main-run01.json"
FROZEN_QUEUE = EXPERIMENT / "QUEUES/luna_no_semantic_validator_268_frozen.json"
CONFIGS = EXPERIMENT / "CONFIGS"


ABLATION = {
    "execution_mode": "LUNA_NO_SEMANTIC_VALIDATOR",
    "semantic_validator_enabled": False,
    "syntax_repair_enabled": True,
    "vocabulary_matcher_enabled": False,
    "semantic_regeneration_enabled": False,
    "deterministic_diagnostics_trigger_regeneration": False,
}


def write_config(name: str, version: str, output: str) -> None:
    raw = copy.deepcopy(json.loads(FULL_CONFIG.read_text(encoding="utf-8")))
    raw["pipeline_version"] = version
    raw["paths"]["outputs"] = output
    raw["ablation"] = copy.deepcopy(ABLATION)
    (CONFIGS / name).write_text(
        json.dumps(raw, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    CONFIGS.mkdir(parents=True, exist_ok=True)
    for number in range(1, 6):
        run = f"RUN_{number:02d}"
        write_config(
            f"pipeline.luna-no-semantic-validator-run{number:02d}.json",
            f"luna-no-semantic-validator-run{number:02d}-v1",
            f"experiments/LUNA_NO_SEMANTIC_VALIDATOR/{run}",
        )
    write_config(
        "pipeline.luna-no-semantic-validator-minitest.json",
        "luna-no-semantic-validator-minitest-v1",
        "experiments/LUNA_NO_SEMANTIC_VALIDATOR/MINI_TEST",
    )

    frozen = json.loads(FROZEN_QUEUE.read_text(encoding="utf-8"))
    selected = ["IMO-088", "TRF-081", "TRF-012"]
    if not all(item in frozen["requirements"] for item in selected):
        raise SystemExit("Mini-test selection is not a subset of the frozen queue")
    mini = {
        "queue_id": "LUNA-NO-SEMANTIC-VALIDATOR-MINITEST-3",
        "development_vocabulary_id": "VOCAB-LOCK-2026-08-22-R13",
        "purpose": "Development-only stratified no-semantic-validator mini-test; not formal output.",
        "repetitions": 1,
        "requirements": selected,
    }
    (EXPERIMENT / "QUEUES/luna_no_semantic_validator_MINITEST_3.json").write_text(
        json.dumps(mini, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
