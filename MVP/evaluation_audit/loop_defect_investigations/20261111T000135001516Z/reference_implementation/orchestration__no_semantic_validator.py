from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..config import PipelineConfig
from ..errors import ConfigurationError
from ..models import ApiCallResult
from ..telemetry.events import EventLogger
from .runner import LLMClient, PipelineRunner, hash_text, identifier
from .singleshot import estimate_call_cost, render_first_generator_request


@dataclass(slots=True)
class NoSemanticValidatorRunResult:
    run_id: str
    requirement_id: str
    status: str
    attempts: int
    run_directory: Path
    raw_response: Path
    candidate_shape: Path | None
    diagnostics: Path
    deterministic_valid: bool
    generator_calls: int
    validator_calls: int
    syntax_repair_calls: int
    vocabulary_matcher_calls: int
    regeneration_calls: int
    physical_transport_attempts: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    elapsed_ms: float
    estimated_cost_usd: float

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("run_directory", "raw_response", "candidate_shape", "diagnostics"):
            value = payload[key]
            payload[key] = str(value) if value else None
        return payload


class NoSemanticValidatorRunner(PipelineRunner):
    """Full first call plus syntax-only recovery, with semantic validation removed."""

    def run_requirement(
        self,
        requirement_id: str,
        client: LLMClient,
        *,
        allow_deferred: bool = False,
        session_id: str | None = None,
    ) -> NoSemanticValidatorRunResult:
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

        session_id = session_id or identifier("SESSION-NO-SEMANTIC-VALIDATOR")
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
            execution_mode="LUNA_NO_SEMANTIC_VALIDATOR",
            semantic_validator_enabled=False,
            syntax_repair_enabled=True,
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

        logger.write_artifact(
            "artifacts/attempt_01/generator_prompt.txt",
            developer_prompt + "\n\n--- USER INPUT ---\n" + user_prompt,
            artifact_type="generator_prompt",
            iteration=1,
        )
        generator_result = client.call("generator", developer_prompt, user_prompt)
        call_results: list[ApiCallResult] = [generator_result]
        usage = generator_result.usage
        logger.emit(
            "api_call_completed",
            role="generator",
            model=generator_result.model,
            response_id=generator_result.response_id,
            transport_attempts=generator_result.transport_attempts,
            elapsed_ms=generator_result.elapsed_ms,
            input_tokens=usage.get("input_tokens", ""),
            output_tokens=usage.get("output_tokens", ""),
            total_tokens=usage.get("total_tokens", ""),
            prompt_sha256=hash_text(developer_prompt + "\n" + user_prompt),
            response_sha256=hash_text(generator_result.text),
            iteration=1,
        )
        raw_path = logger.write_artifact(
            "artifacts/attempt_01/generator_raw.txt",
            generator_result.text,
            artifact_type="generator_raw_response",
            iteration=1,
        )

        candidate_response = generator_result.text
        candidate_turtle, validation = self.static_validator.validate_raw(candidate_response, context)
        maximum_syntax_repairs = int(
            self.config.raw["generation"].get("maximum_syntax_repairs_per_semantic_attempt", 2)
        )
        syntax_repair_count = 0
        while (
            self.static_validator.is_syntax_failure(validation)
            and syntax_repair_count < maximum_syntax_repairs
        ):
            syntax_repair_count += 1
            syntax_diagnostics = self.static_validator.syntax_repair_diagnostics(
                candidate_response,
                candidate_turtle,
                validation,
            )
            logger.emit(
                "syntax_repair_started",
                iteration=1,
                syntax_repair_attempt=syntax_repair_count,
                errors=syntax_diagnostics["syntaxErrors"],
                offending_regions=syntax_diagnostics["offendingRegions"],
                semantic_attempt_consumed=False,
            )
            syntax_user = self.prompts.syntax_repair_user(
                candidate_response,
                syntax_diagnostics,
                str(self.config.raw["generation"]["generated_shape_namespace"]),
            )
            logger.write_artifact(
                f"artifacts/attempt_01/syntax_repair_prompt_{syntax_repair_count:02d}.txt",
                self.prompts.syntax_repair_instructions + "\n\n--- USER INPUT ---\n" + syntax_user,
                artifact_type="syntax_repair_prompt",
                iteration=1,
            )
            syntax_result = client.call(
                "syntax_repair",
                self.prompts.syntax_repair_instructions,
                syntax_user,
            )
            call_results.append(syntax_result)
            syntax_usage = syntax_result.usage
            logger.emit(
                "api_call_completed",
                role="syntax_repair",
                model=syntax_result.model,
                response_id=syntax_result.response_id,
                transport_attempts=syntax_result.transport_attempts,
                elapsed_ms=syntax_result.elapsed_ms,
                input_tokens=syntax_usage.get("input_tokens", ""),
                output_tokens=syntax_usage.get("output_tokens", ""),
                total_tokens=syntax_usage.get("total_tokens", ""),
                prompt_sha256=hash_text(self.prompts.syntax_repair_instructions + "\n" + syntax_user),
                response_sha256=hash_text(syntax_result.text),
                iteration=1,
                syntax_repair_attempt=syntax_repair_count,
            )
            logger.write_artifact(
                f"artifacts/attempt_01/syntax_repair_raw_{syntax_repair_count:02d}.txt",
                syntax_result.text,
                artifact_type="syntax_repair_raw_response",
                iteration=1,
            )
            candidate_response = syntax_result.text
            candidate_turtle, validation = self.static_validator.validate_raw(
                candidate_response, context
            )
            logger.emit(
                "syntax_repair_completed",
                iteration=1,
                syntax_repair_attempt=syntax_repair_count,
                syntax_valid=not self.static_validator.is_syntax_failure(validation),
                semantic_attempt_consumed=False,
            )

        candidate_path: Path | None = None
        if candidate_turtle:
            candidate_path = logger.write_artifact(
                "artifacts/attempt_01/candidate_shape.ttl",
                candidate_turtle,
                artifact_type="no_semantic_validator_candidate_shape",
                iteration=1,
            )
        if self.static_validator.is_syntax_failure(validation):
            status = "SYNTAX_REPAIR_EXHAUSTED"
        elif validation.valid:
            status = "NO_SEMANTIC_VALIDATOR_DETERMINISTIC_PASS"
        else:
            status = "NO_SEMANTIC_VALIDATOR_DETERMINISTIC_FAIL"

        diagnostics_payload = {
            "mode": "LUNA_NO_SEMANTIC_VALIDATOR",
            "semanticValidatorEnabled": False,
            "deterministicDiagnosticsAreTerminalNotRepairFeedback": True,
            "deterministicValidation": validation.to_dict(),
            "terminalStatus": status,
            "llmCallCounts": {
                "generator": 1,
                "validator": 0,
                "syntax_repair": syntax_repair_count,
                "vocabulary_matcher": 0,
                "regeneration": 0,
            },
        }
        diagnostics_path = logger.write_artifact(
            "artifacts/attempt_01/no_semantic_validator_diagnostics.json",
            json.dumps(diagnostics_payload, indent=2, ensure_ascii=True) + "\n",
            artifact_type="no_semantic_validator_diagnostics",
            iteration=1,
        )
        logger.emit("validation_completed", iteration=1, **validation.to_dict())
        logger.emit(
            "iteration_completed",
            iteration=1,
            static_valid=validation.valid,
            validator_accept=None,
            matcher_activated=False,
            decision=status,
            feedback="Semantic validator disabled; deterministic diagnostics were not used as repair feedback.",
            generator_elapsed_ms=generator_result.elapsed_ms,
            validator_elapsed_ms=0,
        )
        logger.emit(
            "run_finished",
            status=status,
            accepted=False,
            deterministic_valid=validation.valid,
            attempts=1,
            syntax_repair_calls=syntax_repair_count,
            final_shape="",
            candidate_shape=(
                str(candidate_path.relative_to(run_directory)) if candidate_path else ""
            ),
            final_feedback="Semantic validator disabled; no semantic acceptance judgement was made.",
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
                warning=f"Tracker export failed without changing the verdict: {type(exc).__name__}: {exc}",
            )

        total_input = sum(int(result.usage.get("input_tokens") or 0) for result in call_results)
        total_output = sum(int(result.usage.get("output_tokens") or 0) for result in call_results)
        total_tokens = sum(int(result.usage.get("total_tokens") or 0) for result in call_results)
        return NoSemanticValidatorRunResult(
            run_id=run_id,
            requirement_id=requirement_id,
            status=status,
            attempts=1,
            run_directory=run_directory,
            raw_response=raw_path,
            candidate_shape=candidate_path,
            diagnostics=diagnostics_path,
            deterministic_valid=validation.valid,
            generator_calls=1,
            validator_calls=0,
            syntax_repair_calls=syntax_repair_count,
            vocabulary_matcher_calls=0,
            regeneration_calls=0,
            physical_transport_attempts=sum(result.transport_attempts for result in call_results),
            input_tokens=total_input,
            output_tokens=total_output,
            total_tokens=total_tokens,
            elapsed_ms=sum(result.elapsed_ms for result in call_results),
            estimated_cost_usd=sum(estimate_call_cost(self.config, result) for result in call_results),
        )
