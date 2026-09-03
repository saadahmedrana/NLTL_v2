from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.orchestration.runner import PipelineRunner
from nltl_pipeline.orchestration.singleshot import (
    ContextualSingleShotRunner,
    render_first_generator_request,
)


ROOT = Path(__file__).resolve().parents[3]
REQUIREMENT_ID = "IMO26-014"
FULL_CONFIG = ROOT / "experiments/FINAL_LUNA_MAIN/CONFIGS/pipeline.final-luna-main-run01.json"
SINGLE_CONFIG = ROOT / "experiments/LUNA_CONTEXTUAL_SINGLESHOT/CONFIGS/pipeline.luna-contextual-singleshot-smoke.json"
REFERENCE_PROMPT = ROOT / (
    "experiments/FINAL_LUNA_MAIN/RUN_01/runs/"
    "RUN-IMO26-014-20260827T151107173451Z/artifacts/attempt_01/generator_prompt.txt"
)
OUTPUT = Path(__file__).with_name("first_call_equivalence.json")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render(runner: PipelineRunner) -> tuple[str, str, str, list[dict]]:
    _context, few_shots, developer, user = render_first_generator_request(
        runner, REQUIREMENT_ID
    )
    combined = developer + "\n\n--- USER INPUT ---\n" + user
    return developer, user, combined, few_shots


def main() -> None:
    full_config = PipelineConfig.load(FULL_CONFIG)
    single_config = PipelineConfig.load(SINGLE_CONFIG)
    full_dev, full_user, full_combined, full_few = render(PipelineRunner(full_config))
    single_dev, single_user, single_combined, single_few = render(
        ContextualSingleShotRunner(single_config)
    )
    historical = REFERENCE_PROMPT.read_text(encoding="utf-8")
    fields = (
        "generator",
        "few_shot_count",
        "generated_shape_namespace",
        "generator_max_output_tokens",
    )
    full_values = {
        "generator": full_config.model("generator"),
        "few_shot_count": full_config.raw["generation"]["few_shot_count"],
        "generated_shape_namespace": full_config.raw["generation"]["generated_shape_namespace"],
        "generator_max_output_tokens": full_config.raw["api"]["max_output_tokens"]["generator"],
    }
    single_values = {
        "generator": single_config.model("generator"),
        "few_shot_count": single_config.raw["generation"]["few_shot_count"],
        "generated_shape_namespace": single_config.raw["generation"]["generated_shape_namespace"],
        "generator_max_output_tokens": single_config.raw["api"]["max_output_tokens"]["generator"],
    }
    checks = {
        "developerPromptMatches": full_dev == single_dev,
        "userPromptMatches": full_user == single_user,
        "combinedPromptMatches": full_combined == single_combined,
        "fewShotsMatch": full_few == single_few,
        "historicalFullPromptMatchesCurrentRenderer": historical == full_combined,
        "historicalFullPromptMatchesSingleShotRenderer": historical == single_combined,
        "modelAndGenerationSettingsMatch": all(
            full_values[field] == single_values[field] for field in fields
        ),
    }
    payload = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "requirementId": REQUIREMENT_ID,
        "referencePrompt": str(REFERENCE_PROMPT),
        "checks": checks,
        "sha256": {
            "historicalFullPrompt": sha256(historical),
            "currentFullRenderer": sha256(full_combined),
            "singleShotRenderer": sha256(single_combined),
            "developerPrompt": sha256(single_dev),
            "userPrompt": sha256(single_user),
        },
        "fullSettings": full_values,
        "singleShotSettings": single_values,
        "fewShotExampleIds": [item["exampleId"] for item in single_few],
        "repairFeedback": json.loads(single_user)["repairFeedback"],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    if payload["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
