from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar

from ..config import PIPELINE_ROOT, PipelineConfig
from ..errors import ConfigurationError, ResponseContractError
from ..matching.search import CandidateSearcher
from ..models import ApiCallResult, ContextPack, MatcherDecision, PipelineRunResult, ValidatorDecision
from ..prompts import PromptFactory
from ..reporting.tracker import TrackerExporter
from ..retrieval.context import VocabularyRepository
from ..retrieval.fewshot import FewShotSelector
from ..telemetry.events import EventLogger
from ..validation.contracts import parse_matcher_decision, parse_validator_decision
from ..validation.shacl import ShaclStaticValidator


class LLMClient(Protocol):
    telemetry: Callable[[str, dict[str, Any]], None]

    def call(self, role: str, developer_prompt: str, user_prompt: str) -> ApiCallResult: ...


ParsedT = TypeVar("ParsedT")


def identifier(prefix: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}-{now}"


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PipelineRunner:
    def __init__(
        self,
        config: PipelineConfig,
        vocabulary: VocabularyRepository | None = None,
        *,
        live_progress: bool = False,
    ) -> None:
        self.config = config
        self.vocabulary = vocabulary or VocabularyRepository(config)
        self.few_shots = FewShotSelector(config.path("few_shot_jsonl"))
        self.prompts = PromptFactory()
        self.static_validator = ShaclStaticValidator(self.vocabulary)
        self.searcher = CandidateSearcher(self.vocabulary)
        self.tracker = TrackerExporter(config, self.vocabulary)
        self.live_progress = live_progress

    def _call_and_parse(
        self,
        *,
        client: LLMClient,
        logger: EventLogger,
        role: str,
        developer_prompt: str,
        user_prompt: str,
        parser: Callable[[str], ParsedT],
        artifact_prefix: str,
        iteration: int,
    ) -> tuple[ParsedT, ApiCallResult]:
        maximum_retries = int(self.config.raw["api"].get("contract_response_retries", 2))
        correction = ""
        last_error: ResponseContractError | None = None
        for contract_attempt in range(1, maximum_retries + 2):
            actual_user = user_prompt + correction
            logger.write_artifact(
                f"artifacts/attempt_{iteration:02d}/{artifact_prefix}_prompt_{contract_attempt:02d}.txt",
                developer_prompt + "\n\n--- USER INPUT ---\n" + actual_user,
                artifact_type=f"{artifact_prefix}_prompt",
                iteration=iteration,
            )
            result = client.call(role, developer_prompt, actual_user)
            usage = result.usage
            logger.emit(
                "api_call_completed",
                role=role,
                model=result.model,
                response_id=result.response_id,
                transport_attempts=result.transport_attempts,
                elapsed_ms=result.elapsed_ms,
                input_tokens=usage.get("input_tokens", ""),
                output_tokens=usage.get("output_tokens", ""),
                total_tokens=usage.get("total_tokens", ""),
                prompt_sha256=hash_text(developer_prompt + "\n" + actual_user),
                response_sha256=hash_text(result.text),
                iteration=iteration,
                contract_attempt=contract_attempt,
            )
            logger.write_artifact(
                f"artifacts/attempt_{iteration:02d}/{artifact_prefix}_raw_{contract_attempt:02d}.txt",
                result.text,
                artifact_type=f"{artifact_prefix}_raw_response",
                iteration=iteration,
            )
            try:
                return parser(result.text), result
            except ResponseContractError as exc:
                last_error = exc
                logger.emit(
                    "response_contract_error",
                    role=role,
                    iteration=iteration,
                    contract_attempt=contract_attempt,
                    error=str(exc),
                    retrying=contract_attempt <= maximum_retries,
                )
                correction = (
                    "\n\nYour previous response violated the required one-line JSON contract: "
                    + str(exc)
                    + " Return the required JSON object only."
                )
        raise ResponseContractError(f"{role} response contract failed: {last_error}")

    def _log_context(self, logger: EventLogger, context: ContextPack, iteration_added: int) -> None:
        for term in context.terms:
            logger.emit(
                "term_retrieved",
                local_name=term["localName"],
                iri=term["iri"],
                kind=term["kind"],
                datatype=term.get("datatype") or "",
                range=term.get("range") or "",
                recommended_unit=term.get("recommendedUnit") or "",
                selection_reason=term.get("selectionReason", ""),
                iteration_added=iteration_added,
            )

    def run_requirement(
        self,
        requirement_id: str,
        client: LLMClient,
        *,
        allow_deferred: bool = False,
        session_id: str | None = None,
    ) -> PipelineRunResult:
        requirement = self.vocabulary.requirement(requirement_id)
        if not allow_deferred and not self.vocabulary.is_generation_eligible(requirement):
            raise ConfigurationError(
                f"{requirement_id} is not in the direct/deterministic generation queue: "
                f"{requirement.get('activeStatus')}. Use an explicit review override only for development."
            )

        session_id = session_id or identifier("SESSION")
        run_id = identifier(f"RUN-{requirement_id}")
        output_root = self.config.path("outputs") / "runs"
        run_directory = output_root / run_id
        logger = EventLogger(
            run_directory,
            session_id,
            run_id,
            requirement_id,
            live_progress=self.live_progress,
        )
        run_directory = logger.run_directory
        client.telemetry = lambda event, payload: logger.emit(event, payload)

        pipeline_version = str(self.config.raw["pipeline_version"])
        context = self.vocabulary.build_context_pack(requirement_id)
        selected_few_shots = self.few_shots.select(
            context,
            count=int(self.config.raw["generation"]["few_shot_count"]),
        )
        logger.emit(
            "run_started",
            pipeline_version=pipeline_version,
            vocabulary_lock_id=context.source_lock["lock_id"],
            requirement_category=requirement.get("category", ""),
            eligibility=context.selection["eligibleForGeneration"],
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

        maximum_attempts = int(self.config.raw["generation"]["maximum_semantic_attempts"])
        generated_namespace = str(self.config.raw["generation"]["generated_shape_namespace"])
        repair_feedback = ""
        repair_feedback_items: list[str] = []
        additional_terms: set[str] = set()
        final_status = "MAX_ATTEMPTS_REACHED"
        final_feedback = "Maximum semantic generation attempts reached."
        final_shape: Path | None = None
        attempts_used = 0

        try:
            for iteration in range(1, maximum_attempts + 1):
                attempts_used = iteration
                if additional_terms:
                    context = self.vocabulary.build_context_pack(requirement_id, additional_terms)
                    logger.write_artifact(
                        f"artifacts/attempt_{iteration:02d}/context_pack_expanded.json",
                        json.dumps(context.to_dict(), indent=2, ensure_ascii=True) + "\n",
                        artifact_type="expanded_context_pack",
                        iteration=iteration,
                    )
                    self._log_context(logger, context, iteration)

                generator_user = self.prompts.generator_user(
                    context,
                    selected_few_shots,
                    repair_feedback,
                    generated_namespace,
                )
                logger.write_artifact(
                    f"artifacts/attempt_{iteration:02d}/generator_prompt.txt",
                    self.prompts.generator_instructions + "\n\n--- USER INPUT ---\n" + generator_user,
                    artifact_type="generator_prompt",
                    iteration=iteration,
                )
                generator_result = client.call("generator", self.prompts.generator_instructions, generator_user)
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
                    prompt_sha256=hash_text(self.prompts.generator_instructions + "\n" + generator_user),
                    response_sha256=hash_text(generator_result.text),
                    iteration=iteration,
                )
                logger.write_artifact(
                    f"artifacts/attempt_{iteration:02d}/generator_raw.txt",
                    generator_result.text,
                    artifact_type="generator_raw_response",
                    iteration=iteration,
                )
                candidate_turtle, validation = self.static_validator.validate_raw(generator_result.text, context)
                if candidate_turtle:
                    logger.write_artifact(
                        f"artifacts/attempt_{iteration:02d}/candidate_shape.ttl",
                        candidate_turtle,
                        artifact_type="candidate_shape",
                        iteration=iteration,
                    )
                logger.write_artifact(
                    f"artifacts/attempt_{iteration:02d}/deterministic_validation.json",
                    json.dumps(validation.to_dict(), indent=2, ensure_ascii=True) + "\n",
                    artifact_type="deterministic_validation",
                    iteration=iteration,
                )
                logger.emit("validation_completed", iteration=iteration, **validation.to_dict())

                suspicious = sorted(set(
                    validation.unknown_canonical_iris + validation.out_of_scope_canonical_iris
                ))
                mismatch_candidates = self.searcher.search(
                    " | ".join(validation.errors),
                    suspicious,
                    limit=int(self.config.raw["generation"]["matcher_candidate_limit"]),
                    minimum_score=float(self.config.raw["generation"]["matcher_minimum_score"]),
                ) if suspicious else []
                used_canonical_terms = self.vocabulary.compact_terms_for_iris(
                    validation.used_canonical_iris
                )
                validator_user = self.prompts.validator_user(
                    context,
                    candidate_turtle,
                    validation,
                    used_canonical_terms,
                    mismatch_candidates,
                )
                validator_decision, validator_result = self._call_and_parse(
                    client=client,
                    logger=logger,
                    role="validator",
                    developer_prompt=self.prompts.validator_instructions,
                    user_prompt=validator_user,
                    parser=parse_validator_decision,
                    artifact_prefix="validator",
                    iteration=iteration,
                )

                accepted = validation.valid and validator_decision.accept
                matcher_activated = False
                decision_label = "ACCEPT" if accepted else "REVISE"
                semantic_feedback = validator_decision.feedback
                feedback = semantic_feedback
                final_feedback = feedback
                if not validation.valid:
                    deterministic_feedback = (
                        "Deterministic validation prevents acceptance. Fix: "
                        + " | ".join(validation.errors)
                    )
                    feedback = (
                        deterministic_feedback
                        + ("\nSemantic validator feedback: " + feedback if feedback else "")
                    )
                    decision_label = "REVISE_STATIC_GATE"

                if accepted:
                    final_status = "GENERATION_ACCEPTED"
                    final_feedback = validator_decision.feedback
                    final_shape = logger.write_artifact(
                        "final/final_shape.ttl",
                        candidate_turtle,
                        artifact_type="final_accepted_shape",
                        iteration=iteration,
                    )
                    logger.emit(
                        "iteration_completed",
                        iteration=iteration,
                        static_valid=validation.valid,
                        validator_accept=True,
                        matcher_activated=False,
                        decision="ACCEPT",
                        feedback=feedback,
                        generator_elapsed_ms=generator_result.elapsed_ms,
                        validator_elapsed_ms=validator_result.elapsed_ms,
                    )
                    break

                if validator_decision.activate_variable_matcher:
                    matcher_activated = True
                    candidates = self.searcher.search(
                        semantic_feedback,
                        suspicious,
                        limit=int(self.config.raw["generation"]["matcher_candidate_limit"]),
                        minimum_score=float(self.config.raw["generation"]["matcher_minimum_score"]),
                    )
                    logger.emit(
                        "matcher_search",
                        iteration=iteration,
                        query_feedback=feedback,
                        candidate_count=len(candidates),
                        suspicious_iris=suspicious,
                    )
                    logger.write_artifact(
                        f"artifacts/attempt_{iteration:02d}/matcher_candidates.json",
                        json.dumps(candidates, indent=2, ensure_ascii=True) + "\n",
                        artifact_type="matcher_candidates",
                        iteration=iteration,
                    )
                    if not candidates:
                        final_status = "TERM_RESOLUTION_UNRESOLVED"
                        final_feedback = "Deterministic search found no plausible canonical candidate. " + feedback
                        logger.emit(
                            "unresolved_issue",
                            iteration=iteration,
                            issue_type="TERM_RESOLUTION_UNRESOLVED",
                            detail=final_feedback,
                            status="OPEN",
                        )
                        decision_label = "STOP_TERM_RESOLUTION"
                    else:
                        matcher_user = self.prompts.matcher_user(context, semantic_feedback, suspicious, candidates)
                        allowed_candidates = {(item["localName"], item["iri"]) for item in candidates}

                        def parse_verified_matcher(raw: str) -> MatcherDecision:
                            decision = parse_matcher_decision(raw)
                            if decision.match_found and (
                                decision.canonical_local_name,
                                decision.canonical_iri,
                            ) not in allowed_candidates:
                                raise ResponseContractError(
                                    "Vocabulary matcher selected an IRI outside its supplied candidate list"
                                )
                            return decision

                        matcher_decision, _matcher_result = self._call_and_parse(
                            client=client,
                            logger=logger,
                            role="vocabulary_matcher",
                            developer_prompt=self.prompts.matcher_instructions,
                            user_prompt=matcher_user,
                            parser=parse_verified_matcher,
                            artifact_prefix="vocabulary_matcher",
                            iteration=iteration,
                        )
                        logger.emit(
                            "matcher_decision",
                            iteration=iteration,
                            match_found=matcher_decision.match_found,
                            canonical_local_name=matcher_decision.canonical_local_name,
                            canonical_iri=matcher_decision.canonical_iri,
                            feedback_appendix=matcher_decision.feedback_appendix,
                        )
                        if not matcher_decision.match_found:
                            final_status = "TERM_RESOLUTION_UNRESOLVED"
                            final_feedback = matcher_decision.feedback_appendix or feedback
                            logger.emit(
                                "unresolved_issue",
                                iteration=iteration,
                                issue_type="TERM_RESOLUTION_UNRESOLVED",
                                detail=final_feedback,
                                status="OPEN",
                            )
                            decision_label = "STOP_TERM_RESOLUTION"
                        else:
                            additional_terms.add(matcher_decision.canonical_local_name)
                            current_repair = (
                                feedback
                                + "\nCanonical vocabulary resolution: "
                                + matcher_decision.feedback_appendix
                                + f" Use exactly {matcher_decision.canonical_iri}."
                            ).strip()
                            if current_repair not in repair_feedback_items:
                                repair_feedback_items.append(current_repair)
                            repair_feedback = "\n\n".join(
                                f"{index}. {item}" for index, item in enumerate(repair_feedback_items, start=1)
                            )
                            decision_label = "REVISE_WITH_MATCH"
                else:
                    if feedback not in repair_feedback_items:
                        repair_feedback_items.append(feedback)
                    repair_feedback = "\n\n".join(
                        f"{index}. {item}" for index, item in enumerate(repair_feedback_items, start=1)
                    )

                logger.emit(
                    "iteration_completed",
                    iteration=iteration,
                    static_valid=validation.valid,
                    validator_accept=validator_decision.accept,
                    matcher_activated=matcher_activated,
                    decision=decision_label,
                    feedback=feedback,
                    generator_elapsed_ms=generator_result.elapsed_ms,
                    validator_elapsed_ms=validator_result.elapsed_ms,
                )
                if final_status == "TERM_RESOLUTION_UNRESOLVED":
                    break
            else:
                logger.emit(
                    "unresolved_issue",
                    iteration=attempts_used,
                    issue_type="MAX_ATTEMPTS_REACHED",
                    detail=final_feedback,
                    status="OPEN",
                )
        except KeyboardInterrupt:
            final_status = "INTERRUPTED"
            final_feedback = "Run interrupted by operator; completed events and artifacts are preserved."
            logger.emit(
                "unresolved_issue",
                iteration=attempts_used,
                issue_type="INTERRUPTED",
                detail=final_feedback,
                status="OPEN",
            )
            raise
        except Exception as exc:
            final_status = "PIPELINE_ERROR"
            final_feedback = f"{type(exc).__name__}: {exc}"
            logger.emit(
                "unresolved_issue",
                iteration=attempts_used,
                issue_type="PIPELINE_ERROR",
                detail=final_feedback,
                status="OPEN",
            )
            raise
        finally:
            accepted_final = final_status == "GENERATION_ACCEPTED"
            logger.emit(
                "run_finished",
                status=final_status,
                accepted=accepted_final,
                attempts=attempts_used,
                final_shape=str(final_shape.relative_to(run_directory)) if final_shape else "",
                final_feedback=final_feedback,
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
            except Exception as reporting_exc:
                logger.emit(
                    "reporting_warning",
                    warning=f"Tracker export failed without changing the run verdict: {type(reporting_exc).__name__}: {reporting_exc}",
                )

        return PipelineRunResult(
            run_id=run_id,
            requirement_id=requirement_id,
            status=final_status,
            accepted=final_status == "GENERATION_ACCEPTED",
            attempts=attempts_used,
            run_directory=run_directory,
            final_shape=final_shape,
            final_feedback=final_feedback,
        )
