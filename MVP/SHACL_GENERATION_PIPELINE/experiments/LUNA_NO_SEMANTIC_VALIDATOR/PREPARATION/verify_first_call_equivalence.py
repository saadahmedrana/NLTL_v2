from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.orchestration.no_semantic_validator import NoSemanticValidatorRunner
from nltl_pipeline.orchestration.runner import PipelineRunner
from nltl_pipeline.orchestration.singleshot import render_first_generator_request


EXPERIMENT = Path(__file__).resolve().parents[1]
PIPELINE = EXPERIMENT.parents[1]
REQUIREMENT = "IMO26-014"
FULL_CONFIG = PIPELINE / "experiments/FINAL_LUNA_MAIN/CONFIGS/pipeline.final-luna-main-run01.json"
ABLATION_CONFIG = EXPERIMENT / "CONFIGS/pipeline.luna-no-semantic-validator-minitest.json"
HISTORICAL = PIPELINE / (
    "experiments/FINAL_LUNA_MAIN/RUN_01/runs/"
    "RUN-IMO26-014-20260827T151107173451Z/artifacts/attempt_01/generator_prompt.txt"
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render(runner: PipelineRunner) -> tuple[str, str, str, list[dict]]:
    _, few, developer, user = render_first_generator_request(runner, REQUIREMENT)
    return developer, user, developer + "\n\n--- USER INPUT ---\n" + user, few


def main() -> None:
    full_config = PipelineConfig.load(FULL_CONFIG)
    ablation_config = PipelineConfig.load(ABLATION_CONFIG)
    full_developer, full_user, full_combined, full_few = render(PipelineRunner(full_config))
    abl_developer, abl_user, abl_combined, abl_few = render(
        NoSemanticValidatorRunner(ablation_config)
    )
    historical = HISTORICAL.read_text(encoding="utf-8")
    full_settings = {
        "model": full_config.model("generator"),
        "max_output_tokens": full_config.raw["api"]["max_output_tokens"]["generator"],
        "few_shot_count": full_config.raw["generation"]["few_shot_count"],
        "generated_shape_namespace": full_config.raw["generation"]["generated_shape_namespace"],
    }
    ablation_settings = {
        "model": ablation_config.model("generator"),
        "max_output_tokens": ablation_config.raw["api"]["max_output_tokens"]["generator"],
        "few_shot_count": ablation_config.raw["generation"]["few_shot_count"],
        "generated_shape_namespace": ablation_config.raw["generation"]["generated_shape_namespace"],
    }
    checks = {
        "developer_prompt_equal": full_developer == abl_developer,
        "user_prompt_equal": full_user == abl_user,
        "few_shots_equal": full_few == abl_few,
        "historical_full_prompt_equal": historical == full_combined,
        "historical_ablation_prompt_equal": historical == abl_combined,
        "generation_settings_equal": full_settings == ablation_settings,
        "repair_feedback_none": json.loads(abl_user)["repairFeedback"] == "NONE",
    }
    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "requirement_id": REQUIREMENT,
        "checks": checks,
        "sha256": {
            "historical": digest(historical),
            "full_renderer": digest(full_combined),
            "ablation_renderer": digest(abl_combined),
        },
        "full_settings": full_settings,
        "ablation_settings": ablation_settings,
        "few_shot_ids": [item["exampleId"] for item in abl_few],
    }
    Path(__file__).with_name("first_call_equivalence.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
