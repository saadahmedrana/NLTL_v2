from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..config import PipelineConfig
from ..errors import ConfigurationError
from ..models import ApiCallResult, ContextPack
from ..telemetry.events import EventLogger
from .runner import LLMClient, PipelineRunner, hash_text, identifier


@dataclass(slots=True)
class SingleShotRunResult:
    run_id: str
    requirement_id: str
    status: str
    attempts: int
    run_directory: Path
    raw_response: Path
    extracted_shape: Path | None
    diagnostics: Path
    extraction_status: str
    rdf_parse_status: str
    shacl_validation_status: str
    vocabulary_diagnostic_status: str
    deterministic_valid: bool
    generator_calls: int
    validator_calls: int
    vocabulary_matcher_calls: int
    syntax_repair_calls: int
    regeneration_calls: int
    elapsed_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("run_directory", "raw_response", "extracted_shape", "diagnostics"):
            value = payload[key]
            payload[key] = str(value) if value else None
        return payload


def render_first_generator_request(
    runner: PipelineRunner,
    requirement_id: str,
) -> tuple[ContextPack, list[dict[str, Any]], str, str]:
    """Render the normal pipeline's pre-repair first generator request offline."""
    context = runner.vocabulary.build_context_pack(requirement_id)
    selected_few_shots = runner.few_shots.select(
        context,
        count=int(runner.config.raw["generation"]["few_shot_count"]),
    )
    generated_namespace = str(runner.config.raw["generation"]["generated_shape_namespace"])
    user_prompt = runner.prompts.generator_user(
        context,
        selected_few_shots,
        "",
        generated_namespace,
    )
    return context, selected_few_shots, runner.prompts.generator_instructions, user_prompt


def estimate_call_cost(config: PipelineConfig, result: ApiCallResult) -> float:
    rates = config.raw.get("cost_estimation", {}).get("usd_per_million_tokens", {})
    model_rates = rates.get(result.model) or rates.get(config.model("generator")) or {}
    input_rate = float(model_rates.get("input", 0.0))
    output_rate = float(model_rates.get("output", 0.0))
    input_tokens = int(result.usage.get("input_tokens") or 0)
    output_tokens = int(result.usage.get("output_tokens") or 0)
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


class ContextualSingleShotRunner(PipelineRunner):
    """One contextual generator call followed only by read-only diagnostics."""

    def run_requirement(
        self,
        requirement_id: str,
        client: LLMClient,
        *,
        allow_deferred: bool = False,
        session_id: str | None = None,
    ) -> SingleShotRunResult:
        requirement = self.vocabulary.requirement(requirement_id)
        if not allow_deferred and not self.vocabulary.is_generation_eligible(requirement):
            raise ConfigurationError(
                f"{requirement_id} is not generation-eligible: "
                f"{requirement.get('activeStatus')}"
            )
        if bool(self.config.raw["generation"].get("require_complete_dependency_contracts", False)):
            contract = self.vocabulary.dependency_contracts.get(requirement_id, {})
            if contract.get("status") != "COMPLETE":
                raise ConfigurationError(
                    f"{requirement_id} requires a COMPLETE dependency contract for generation"
                )

        session_id = session_id or identifier("SESSION-SINGLESHOT")
        run_id = identifier(f"RUN-{requirement_id}")
        logger = EventLogger(
            self.config.path("outputs") / "runs" / run_id,
            session_id,
            run_id,
            requirement_id,
            live_progress=self.live_progress,
        )
        run_directory = logger.run_directory
        client.telemetry = lambda event, payload: logger.emit(event, payload)

        context, selected_few_shots, developer_prompt, user_prompt = render_first_generator_request(
            self, requirement_id
        )
        logger.emit(
            "run_started",
            pipeline_version=str(self.config.raw["pipeline_version"]),
            vocabulary_lock_id=context.source_lock["lock_id"],
            requirement_category=requirement.get("category", ""),
            eligibility=context.selection["eligibleForGeneration"],
            execution_mode="LUNA_CONTEXTUAL_SINGLESHOT",
        )
        logger.write_artifact(
            "artifacts/context_pack_initial.json",
            json.dumps(context.to_dict(), indent=2, ensure_ascii=True) + "\n",
            artifact_type="initial_context_pack",
        )
        logger.write_artifact(
            "artifacts/few_shots_selected.json",
            json.dumps(selected_few_shots, indent=2, ensure_ascii=True) + "\n",
            artifact_type="few_shot_selection",
        )
        self._log_context(logger, context, 0)
        for item in selected_few_shots:
            logger.emit(
                "few_shot_selected",
                example_id=item["exampleId"],
                case_id=item["caseId"],
                score=item["selectionScore"],
                matched_tags=item["selectionReasons"],
                status=item["status"],
            )

        combined_prompt = developer_prompt + "\n\n--- USER INPUT ---\n" + user_prompt
        logger.write_artifact(
            "artifacts/attempt_01/generator_prompt.txt",
            combined_prompt,
            artifact_type="generator_prompt",
            iteration=1,
        )

        result = client.call("generator", developer_prompt, user_prompt)
        usage = result.usage
        logger.emit(
            "api_call_completed",
            role="generator",
            model=result.model,
            response_id=result.response_id,
            transport_attempts=result.transport_attempts,
            elapsed_ms=result.elapsed_ms,
            input_tokens=usage.get("input_tokens", ""),
            output_tokens=usage.get("output_tokens", ""),
            total_tokens=usage.get("total_tokens", ""),
            prompt_sha256=hash_text(developer_prompt + "\n" + user_prompt),
            response_sha256=hash_text(result.text),
            iteration=1,
        )
        raw_path = logger.write_artifact(
            "artifacts/attempt_01/generator_raw.txt",
            result.text,
            artifact_type="generator_raw_response",
            iteration=1,
        )

        candidate_turtle, validation = self.static_validator.validate_raw(result.text, context)
        extracted_path: Path | None = None
        if candidate_turtle:
            extracted_path = logger.write_artifact(
                "artifacts/attempt_01/extracted_shape.ttl",
                candidate_turtle,
                artifact_type="single_shot_extracted_shape",
                iteration=1,
            )
        diagnostics_payload = {
            "mode": "LUNA_CONTEXTUAL_SINGLESHOT",
            "readOnlyDiagnostics": True,
            "noRepairOrFeedback": True,
            "extractionStatus": "PASS" if validation.extraction_valid else "FAIL",
            "rdfParseStatus": (
                "PASS" if validation.turtle_valid else "FAIL"
                if validation.extraction_valid else "NOT_RUN"
            ),
            "shaclValidationStatus": (
                "PASS"
                if validation.shacl_structure_valid and validation.meta_shacl_valid
                else "FAIL"
                if validation.turtle_valid
                else "NOT_RUN"
            ),
            "vocabularyDiagnosticStatus": (
                "PASS" if validation.vocabulary_valid else "FAIL"
                if validation.extraction_valid else "NOT_RUN"
            ),
            "deterministicValidation": validation.to_dict(),
            "llmCallCounts": {
                "generator": 1,
                "validator": 0,
                "vocabulary_matcher": 0,
                "syntax_repair": 0,
                "regeneration": 0,
            },
        }
        diagnostics_path = logger.write_artifact(
            "artifacts/attempt_01/single_shot_diagnostics.json",
            json.dumps(diagnostics_payload, indent=2, ensure_ascii=True) + "\n",
            artifact_type="single_shot_diagnostics",
            iteration=1,
        )
        logger.emit("validation_completed", iteration=1, **validation.to_dict())
        logger.emit(
            "single_shot_diagnostics_completed",
            iteration=1,
            extraction_status=diagnostics_payload["extractionStatus"],
            rdf_parse_status=diagnostics_payload["rdfParseStatus"],
            shacl_validation_status=diagnostics_payload["shaclValidationStatus"],
            vocabulary_diagnostic_status=diagnostics_payload["vocabularyDiagnosticStatus"],
            llm_call_counts=diagnostics_payload["llmCallCounts"],
            blocking=False,
        )
        status = "SINGLESHOT_CAPTURED_DIAGNOSTIC_PASS" if validation.valid else "SINGLESHOT_CAPTURED_DIAGNOSTIC_FAIL"
        logger.emit(
            "run_finished",
            status=status,
            attempts=1,
            accepted=False,
            deterministic_valid=validation.valid,
            final_shape="",
            extracted_shape=(
                str(extracted_path.relative_to(run_directory)) if extracted_path else ""
            ),
            final_feedback="No semantic validator was called; raw output retained without repair.",
        )
        try:
            workbook, warnings = self.tracker.export(run_directory)
            for warning in warnings:
                logger.emit("reporting_warning", warning=warning)
            if workbook:
                logger.emit(
                    "reporting_completed",
                    workbook=str(workbook.relative_to(run_directory)),
                    sha256=hashlib.sha256(workbook.read_bytes()).hexdigest(),
                )
        except Exception as exc:
            logger.emit(
                "reporting_warning",
                warning=f"Tracker export failed without changing diagnostics: {type(exc).__name__}: {exc}",
            )

        return SingleShotRunResult(
            run_id=run_id,
            requirement_id=requirement_id,
            status=status,
            attempts=1,
            run_directory=run_directory,
            raw_response=raw_path,
            extracted_shape=extracted_path,
            diagnostics=diagnostics_path,
            extraction_status=diagnostics_payload["extractionStatus"],
            rdf_parse_status=diagnostics_payload["rdfParseStatus"],
            shacl_validation_status=diagnostics_payload["shaclValidationStatus"],
            vocabulary_diagnostic_status=diagnostics_payload["vocabularyDiagnosticStatus"],
            deterministic_valid=validation.valid,
            generator_calls=1,
            validator_calls=0,
            vocabulary_matcher_calls=0,
            syntax_repair_calls=0,
            regeneration_calls=0,
            elapsed_ms=result.elapsed_ms,
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            estimated_cost_usd=estimate_call_cost(self.config, result),
        )
