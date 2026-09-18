from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar

from ..config import PipelineConfig
from ..errors import ConfigurationError, ResponseContractError
from ..matching.search import CandidateSearcher
from ..models import ApiCallResult, ContextPack, MatcherDecision, PipelineRunResult, ValidatorDecision, ValidatorIssue
from ..prompts import PromptFactory
from ..reporting.tracker import TrackerExporter
from ..retrieval.context import VocabularyRepository
from ..retrieval.fewshot import FewShotSelector
from ..telemetry.events import EventLogger
from ..validation.contracts import normalize_validator_response, parse_matcher_decision, parse_validator_decision
from ..validation.shacl import ShaclStaticValidator
from .repair import RepairMemory, format_issues, issue_key, issues_payload, packet_sha256, rdf_identity, repair_diff, static_issues


ARCHITECTURE = "FULL_REPAIR_V2"


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
    def __init__(self, config: PipelineConfig, vocabulary: VocabularyRepository | None = None, *, live_progress: bool = False) -> None:
        self.config = config
        self.vocabulary = vocabulary or VocabularyRepository(config)
        self.few_shots = FewShotSelector(config.path("few_shot_jsonl"))
        prompt_directory = config.path("prompt_directory") if config.raw.get("paths", {}).get("prompt_directory") else None
        self.prompts = PromptFactory(prompt_directory)
        self.static_validator = ShaclStaticValidator(self.vocabulary)
        self.searcher = CandidateSearcher(self.vocabulary)
        self.tracker = TrackerExporter(config, self.vocabulary)
        self.live_progress = live_progress

    def _call_and_parse(self, *, client: LLMClient, logger: EventLogger, role: str, developer_prompt: str,
                        user_prompt: str, parser: Callable[[str], ParsedT], artifact_prefix: str,
                        iteration: int, maximum_retries: int | None = None) -> tuple[ParsedT, ApiCallResult]:
        retries = int(self.config.raw["api"].get("contract_response_retries", 2)) if maximum_retries is None else maximum_retries
        correction = ""
        last_error: ResponseContractError | None = None
        for contract_attempt in range(1, retries + 2):
            actual_user = user_prompt + correction
            logger.write_artifact(f"artifacts/attempt_{iteration:02d}/{artifact_prefix}_prompt_{contract_attempt:02d}.txt",
                                  developer_prompt + "\n\n--- USER INPUT ---\n" + actual_user,
                                  artifact_type=f"{artifact_prefix}_prompt", iteration=iteration)
            result = client.call(role, developer_prompt, actual_user)
            self._log_api(logger, role, result, developer_prompt, actual_user, iteration, contract_attempt=contract_attempt)
            logger.write_artifact(f"artifacts/attempt_{iteration:02d}/{artifact_prefix}_raw_{contract_attempt:02d}.txt",
                                  result.text, artifact_type=f"{artifact_prefix}_raw_response", iteration=iteration)
            if role == "validator":
                normalization = normalize_validator_response(result.text)
                observation = normalization.to_dict()
                logger.write_artifact(
                    f"artifacts/attempt_{iteration:02d}/{artifact_prefix}_formatting_{contract_attempt:02d}.json",
                    json.dumps(observation, indent=2, ensure_ascii=True) + "\n",
                    artifact_type="validator_formatting_observation", iteration=iteration,
                )
                logger.emit(
                    "validator_formatting_observed", iteration=iteration, contract_attempt=contract_attempt,
                    has_text_outside_decision_block=normalization.text_outside_decision_block,
                    multiple_candidate_decision_blocks=normalization.multiple_candidate_decision_blocks,
                    candidate_decision_block_count=normalization.candidate_decision_block_count,
                    normalization_error=normalization.error or "",
                )
            try:
                return parser(result.text), result
            except ResponseContractError as exc:
                last_error = exc
                logger.emit("response_contract_error", role=role, iteration=iteration,
                            contract_attempt=contract_attempt, error=str(exc), retrying=contract_attempt <= retries,
                            semantic_attempt_consumed=False)
                correction = "\n\nYour previous response violated the required one-line JSON contract: " + str(exc) + " Return the required JSON object only."
        raise ResponseContractError(f"{role} response contract failed: {last_error}")

    @staticmethod
    def _log_api(logger: EventLogger, role: str, result: ApiCallResult, developer: str, user: str,
                 iteration: int, **extra: Any) -> None:
        usage = result.usage
        logger.emit("api_call_completed", role=role, model=result.model, response_id=result.response_id,
                    transport_attempts=result.transport_attempts, elapsed_ms=result.elapsed_ms,
                    input_tokens=usage.get("input_tokens", ""), output_tokens=usage.get("output_tokens", ""),
                    total_tokens=usage.get("total_tokens", ""), prompt_sha256=hash_text(developer + "\n" + user),
                    response_sha256=hash_text(result.text), iteration=iteration, **extra)

    def _log_context(self, logger: EventLogger, context: ContextPack, iteration_added: int) -> None:
        for term in context.terms:
            logger.emit("term_retrieved", local_name=term["localName"], iri=term["iri"], kind=term["kind"],
                        datatype=term.get("datatype") or "", range=term.get("range") or "",
                        recommended_unit=term.get("recommendedUnit") or "",
                        selection_reason=term.get("selectionReason", ""), iteration_added=iteration_added)

    def _generate(self, client: LLMClient, logger: EventLogger, iteration: int, mode: str, user: str,
                  developer: str, prefix: str) -> ApiCallResult:
        logger.write_artifact(f"artifacts/attempt_{iteration:02d}/{prefix}_prompt.txt",
                              developer + "\n\n--- USER INPUT ---\n" + user,
                              artifact_type=f"{prefix}_prompt", iteration=iteration)
        result = client.call("generator", developer, user)
        self._log_api(logger, "generator", result, developer, user, iteration, mode=mode)
        logger.write_artifact(f"artifacts/attempt_{iteration:02d}/{prefix}_raw.txt", result.text,
                              artifact_type=f"{prefix}_raw_response", iteration=iteration)
        return result

    def _search_matcher(self, issues: list[ValidatorIssue], suspicious: list[str], limit: int, minimum: float,
                        context: ContextPack | None = None) -> tuple[list[dict[str, Any]], bool]:
        query = " | ".join(f"{i.problem} {i.required_change}" for i in issues if i.needs_vocabulary_resolution)
        if context is not None:
            query += " | " + json.dumps(context.requirement, sort_keys=True)
        strict = self.searcher.search(query, suspicious, limit=limit, minimum_score=minimum)
        if strict:
            return strict, False
        return self.searcher.search(query, suspicious, limit=limit, minimum_score=0.0), True

    def run_requirement(self, requirement_id: str, client: LLMClient, *, allow_deferred: bool = False,
                        session_id: str | None = None) -> PipelineRunResult:
        requirement = self.vocabulary.requirement(requirement_id)
        if not allow_deferred and not self.vocabulary.is_generation_eligible(requirement):
            raise ConfigurationError(f"{requirement_id} is not in the direct/deterministic generation queue: {requirement.get('activeStatus')}. Use an explicit review override only for development.")
        if bool(self.config.raw["generation"].get("require_complete_dependency_contracts", False)):
            contract = self.vocabulary.dependency_contracts.get(requirement_id, {})
            if contract.get("status") != "COMPLETE":
                raise ConfigurationError(f"{requirement_id} is blocked from API generation because its dependency contract is {contract.get('status', 'MISSING')}, not COMPLETE.")

        session_id = session_id or identifier("SESSION")
        run_id = identifier(f"RUN-{requirement_id}")
        logger = EventLogger(self.config.path("outputs") / "runs" / run_id, session_id, run_id, requirement_id,
                             live_progress=self.live_progress)
        run_directory = logger.run_directory
        client.telemetry = lambda event, payload: logger.emit(event, payload)
        context = self.vocabulary.build_context_pack(requirement_id)
        few_shots = self.few_shots.select(context, count=int(self.config.raw["generation"]["few_shot_count"]))
        generation_run = str(self.config.raw.get("generation_run", "UNSPECIFIED"))
        logger.emit("run_started", pipeline_version=str(self.config.raw["pipeline_version"]), architecture=ARCHITECTURE,
                    generation_run=generation_run, vocabulary_lock_id=context.source_lock["lock_id"],
                    requirement_category=requirement.get("category", ""), eligibility=context.selection["eligibleForGeneration"])
        logger.write_artifact("artifacts/context_pack_initial.json", json.dumps(context.to_dict(), indent=2, ensure_ascii=True) + "\n", artifact_type="initial_context_pack")
        logger.write_artifact("artifacts/few_shots_selected.json", json.dumps(few_shots, indent=2, ensure_ascii=True) + "\n", artifact_type="few_shot_selection")
        self._log_context(logger, context, 0)
        for item in few_shots:
            logger.emit("few_shot_selected", example_id=item["exampleId"], case_id=item["caseId"],
                        score=item["selectionScore"], matched_tags=item["selectionReasons"], status=item["status"])

        max_attempts = int(self.config.raw["generation"]["maximum_semantic_attempts"])
        max_syntax = int(self.config.raw["generation"].get("maximum_syntax_repairs_per_semantic_attempt", 2))
        namespace = str(self.config.raw["generation"]["generated_shape_namespace"])
        memory = RepairMemory()
        additional_terms: set[str] = set()
        previous_turtle: str | None = None
        previous_validation_valid: bool | None = None
        raw_hashes: list[str] = []
        rdf_hashes: list[str | None] = []
        surviving: dict[str, int] = {}
        escape_used = False
        escape_next = False
        next_mode = "INITIAL_GENERATION"
        matcher_status = "NOT_REQUESTED"
        last_raw = ""
        last_turtle: str | None = None
        last_attempt = 0
        last_mode = "INITIAL_GENERATION"
        last_validation: Any = None
        final_status, final_feedback, final_shape = "MAX_ATTEMPTS_REACHED", "Maximum candidate-generation attempts reached.", None

        try:
            for iteration in range(1, max_attempts + 1):
                last_attempt = iteration
                matcher_status = "NOT_REQUESTED"
                if additional_terms:
                    context = self.vocabulary.build_context_pack(requirement_id, additional_terms)
                    logger.write_artifact(f"artifacts/attempt_{iteration:02d}/context_pack_expanded.json",
                                          json.dumps(context.to_dict(), indent=2, ensure_ascii=True) + "\n",
                                          artifact_type="expanded_context_pack", iteration=iteration)
                mode = next_mode
                if escape_next and not escape_used:
                    mode, escape_used, escape_next = "FRESH_REGENERATION_ESCAPE_HATCH", True, False
                last_mode = mode
                if iteration == 1:
                    user = self.prompts.generator_user(context, few_shots, "", namespace)
                    developer, prefix = self.prompts.generator_instructions, "generator"
                elif mode == "FRESH_REGENERATION_ESCAPE_HATCH":
                    user = self.prompts.escape_hatch_user(context, few_shots, memory.current_issues, memory.guards, namespace)
                    developer, prefix = self.prompts.escape_hatch_instructions, "escape_hatch"
                else:
                    if previous_turtle is None:
                        raise RuntimeError("Semantic/static repair requires exactly one previous parseable candidate")
                    user = self.prompts.semantic_repair_user(context, previous_turtle, memory.current_issues, memory.guards, namespace)
                    developer, prefix = self.prompts.semantic_repair_instructions, "semantic_repair"
                result = self._generate(client, logger, iteration, mode, user, developer, prefix)
                last_raw = candidate_response = result.text
                candidate_turtle, validation = self.static_validator.validate_raw(candidate_response, context)
                last_validation = validation
                syntax_repairs = 0
                while self.static_validator.is_syntax_failure(validation) and syntax_repairs < max_syntax:
                    syntax_repairs += 1
                    diagnostics = self.static_validator.syntax_repair_diagnostics(candidate_response, candidate_turtle, validation)
                    syntax_user = self.prompts.syntax_repair_user(candidate_response, diagnostics, namespace)
                    logger.write_artifact(f"artifacts/attempt_{iteration:02d}/syntax_repair_prompt_{syntax_repairs:02d}.txt",
                                          self.prompts.syntax_repair_instructions + "\n\n--- USER INPUT ---\n" + syntax_user,
                                          artifact_type="syntax_repair_prompt", iteration=iteration)
                    syntax_result = client.call("syntax_repair", self.prompts.syntax_repair_instructions, syntax_user)
                    self._log_api(logger, "syntax_repair", syntax_result, self.prompts.syntax_repair_instructions,
                                  syntax_user, iteration, syntax_repair_attempt=syntax_repairs)
                    logger.write_artifact(f"artifacts/attempt_{iteration:02d}/syntax_repair_raw_{syntax_repairs:02d}.txt",
                                          syntax_result.text, artifact_type="syntax_repair_raw_response", iteration=iteration)
                    last_raw = candidate_response = syntax_result.text
                    candidate_turtle, validation = self.static_validator.validate_raw(candidate_response, context)
                    last_validation = validation

                if candidate_turtle:
                    last_turtle = candidate_turtle
                    logger.write_artifact(f"artifacts/attempt_{iteration:02d}/candidate_shape.ttl", candidate_turtle,
                                          artifact_type="candidate_shape", iteration=iteration)
                logger.write_artifact(f"artifacts/attempt_{iteration:02d}/deterministic_validation.json",
                                      json.dumps(validation.to_dict(), indent=2, ensure_ascii=True) + "\n",
                                      artifact_type="deterministic_validation", iteration=iteration)
                logger.emit("validation_completed", iteration=iteration, **validation.to_dict())
                if self.static_validator.is_syntax_failure(validation):
                    final_status = "SYNTAX_REPAIR_EXHAUSTED"
                    final_feedback = "Syntax-only repair budget exhausted: " + " | ".join(self.static_validator.syntax_errors(validation))
                    break

                assert candidate_turtle
                raw_id, rdf_id = hash_text(candidate_turtle), rdf_identity(candidate_turtle)
                equivalent_previous = bool(previous_turtle and (raw_id == raw_hashes[-1] or (rdf_id and rdf_id == rdf_hashes[-1])))
                equivalent_two_back = bool(len(raw_hashes) >= 2 and (raw_id == raw_hashes[-2] or (rdf_id and rdf_id == rdf_hashes[-2])))
                if previous_turtle:
                    logger.write_artifact(f"artifacts/attempt_{iteration:02d}/repair_diff.json",
                                          json.dumps(repair_diff(previous_turtle, candidate_turtle), indent=2, ensure_ascii=True) + "\n",
                                          artifact_type="repair_diff", iteration=iteration)
                raw_hashes.append(raw_id); rdf_hashes.append(rdf_id)

                validator_result: ApiCallResult | None = None
                if not validation.valid:
                    new_issues = static_issues(validation.errors)
                    memory.transition(new_issues)
                    next_mode = "STATIC_REPAIR"
                    decision = "REVISE_STATIC_GATE"
                    suspicious = sorted(set(validation.unknown_canonical_iris + validation.out_of_scope_canonical_iris))
                    vocab_issues = [i for i in new_issues if i.needs_vocabulary_resolution]
                    if vocab_issues:
                        candidates, fallback = self._search_matcher(vocab_issues, suspicious,
                            int(self.config.raw["generation"]["matcher_candidate_limit"]),
                            float(self.config.raw["generation"]["matcher_minimum_score"]), context)
                        matcher_status = "FALLBACK_CANDIDATES" if fallback else "STRICT_CANDIDATES"
                        logger.write_artifact(f"artifacts/attempt_{iteration:02d}/matcher_candidates.json",
                            json.dumps(candidates, indent=2, ensure_ascii=True) + "\n", artifact_type="matcher_candidates", iteration=iteration)
                        if candidates:
                            matcher_user = self.prompts.matcher_user(context, vocab_issues, suspicious, candidates)
                            allowed = {(c["localName"], c["iri"]) for c in candidates}
                            def verified_static_match(raw: str) -> MatcherDecision:
                                found = parse_matcher_decision(raw)
                                if found.match_found and (found.canonical_local_name, found.canonical_iri) not in allowed:
                                    raise ResponseContractError("Vocabulary matcher selected an IRI outside its supplied candidate list")
                                return found
                            found, _ = self._call_and_parse(client=client, logger=logger, role="vocabulary_matcher",
                                developer_prompt=self.prompts.matcher_instructions, user_prompt=matcher_user,
                                parser=verified_static_match, artifact_prefix="vocabulary_matcher", iteration=iteration)
                            if found.match_found:
                                additional_terms.add(found.canonical_local_name)
                                for issue in vocab_issues:
                                    issue.required_change += f" Locked resolution: use exactly {found.canonical_iri}."
                                    issue.source = "MATCHER"
                                matcher_status, next_mode, decision = "MATCH_FOUND", "MATCHER_ASSISTED_REPAIR", "REVISE_STATIC_WITH_MATCH"
                            else:
                                matcher_status = "MATCHER_NO_MATCH"
                        else:
                            matcher_status = "MATCHER_NO_MATCH"
                else:
                    suspicious = sorted(set(validation.unknown_canonical_iris + validation.out_of_scope_canonical_iris))
                    mismatch, _ = self._search_matcher(memory.current_issues, suspicious,
                        int(self.config.raw["generation"]["matcher_candidate_limit"]),
                        float(self.config.raw["generation"]["matcher_minimum_score"]), context) if suspicious else ([], False)
                    validator_user = self.prompts.validator_user(context, candidate_turtle, validation,
                        self.vocabulary.compact_terms_for_iris(validation.used_canonical_iris), mismatch, memory.guards)
                    try:
                        validator_decision, validator_result = self._call_and_parse(
                            client=client, logger=logger, role="validator", developer_prompt=self.prompts.validator_instructions,
                            user_prompt=validator_user, parser=parse_validator_decision, artifact_prefix="validator", iteration=iteration,
                            maximum_retries=int(self.config.raw["api"].get("validator_response_retries", self.config.raw["api"].get("contract_response_retries", 2))))
                    except ResponseContractError as exc:
                        final_status = "VALIDATOR_RESPONSE_RETRY_EXHAUSTED"
                        final_feedback = f"Validator response contract budget exhausted: {exc}"
                        break
                    memory.transition(validator_decision.current_issues)
                    if validator_decision.accept:
                        final_status, final_feedback = "GENERATION_ACCEPTED", format_issues([])
                        final_shape = logger.write_artifact("final/final_shape.ttl", candidate_turtle,
                            artifact_type="final_accepted_shape", iteration=iteration)
                        decision = "ACCEPT"
                    else:
                        decision, next_mode = "REVISE", "SEMANTIC_CANDIDATE_REPAIR"
                        vocab_issues = [i for i in memory.current_issues if i.blocking and i.needs_vocabulary_resolution]
                        matcher_status = "NOT_REQUESTED"
                        if validator_decision.activate_variable_matcher and vocab_issues:
                            candidates, fallback = self._search_matcher(vocab_issues, suspicious,
                                int(self.config.raw["generation"]["matcher_candidate_limit"]),
                                float(self.config.raw["generation"]["matcher_minimum_score"]), context)
                            matcher_status = "FALLBACK_CANDIDATES" if fallback else "STRICT_CANDIDATES"
                            logger.write_artifact(f"artifacts/attempt_{iteration:02d}/matcher_candidates.json",
                                json.dumps(candidates, indent=2, ensure_ascii=True) + "\n", artifact_type="matcher_candidates", iteration=iteration)
                            if candidates:
                                matcher_user = self.prompts.matcher_user(context, vocab_issues, suspicious, candidates)
                                allowed = {(c["localName"], c["iri"]) for c in candidates}
                                def verified(raw: str) -> MatcherDecision:
                                    found = parse_matcher_decision(raw)
                                    if found.match_found and (found.canonical_local_name, found.canonical_iri) not in allowed:
                                        raise ResponseContractError("Vocabulary matcher selected an IRI outside its supplied candidate list")
                                    return found
                                found, _ = self._call_and_parse(client=client, logger=logger, role="vocabulary_matcher",
                                    developer_prompt=self.prompts.matcher_instructions, user_prompt=matcher_user, parser=verified,
                                    artifact_prefix="vocabulary_matcher", iteration=iteration)
                                if found.match_found:
                                    additional_terms.add(found.canonical_local_name)
                                    for issue in vocab_issues:
                                        issue.required_change += f" Locked resolution: use exactly {found.canonical_iri}."
                                        issue.source = "MATCHER"
                                    matcher_status, next_mode, decision = "MATCH_FOUND", "MATCHER_ASSISTED_REPAIR", "REVISE_WITH_MATCH"
                                else:
                                    matcher_status = "MATCHER_NO_MATCH"
                            else:
                                matcher_status = "MATCHER_NO_MATCH"

                # Persist authoritative issue/memory state after routing.
                issue_data = issues_payload(memory.current_issues)
                has_blocking = any(issue.blocking for issue in memory.current_issues)
                stalled = equivalent_previous and has_blocking
                oscillation = equivalent_two_back and has_blocking
                logger.write_artifact(f"artifacts/attempt_{iteration:02d}/structured_current_issues.json",
                    json.dumps(issue_data, indent=2, ensure_ascii=True) + "\n", artifact_type="structured_current_issues", iteration=iteration)
                logger.write_artifact(f"artifacts/attempt_{iteration:02d}/past_mistakes_to_avoid.json",
                    json.dumps(memory.guards, indent=2, ensure_ascii=True) + "\n", artifact_type="past_mistakes_to_avoid", iteration=iteration)
                prior_open = set(surviving)
                current_keys = {issue_key(i) for i in memory.current_issues if i.blocking}
                surviving = {key: surviving.get(key, 0) + 1 for key in current_keys if key in prior_open} | {key: 0 for key in current_keys if key not in prior_open}
                repeated_twice = any(count >= 2 for count in surviving.values())
                if (stalled or oscillation or repeated_twice) and memory.current_issues and iteration == max_attempts - 1 and not escape_used:
                    escape_next = True
                final_feedback = format_issues(memory.current_issues)
                attempt_calls = [event for event in logger.read_events()
                                 if event.get("event_type") == "api_call_completed" and event.get("iteration") == iteration]
                def token_total(name: str) -> int:
                    return sum(int(event.get(name) or 0) for event in attempt_calls)
                metadata = {
                    "architecture": ARCHITECTURE, "generation_run": generation_run, "requirement_id": requirement_id,
                    "run_id": run_id, "candidate_attempt": iteration, "mode": mode,
                    "previous_candidate_present": previous_turtle is not None,
                    "previous_candidate_sha256": hash_text(previous_turtle) if previous_turtle else None,
                    "candidate_sha256": raw_id, "current_issue_count": len(memory.current_issues),
                    "blocking_issue_count": sum(i.blocking for i in memory.current_issues),
                    "current_issue_packet_sha256": packet_sha256(issue_data), "past_mistake_count": len(memory.guards),
                    "regression_guard_sha256": packet_sha256(memory.guards),
                    "deterministic_valid_before": previous_validation_valid,
                    "deterministic_valid_after": validation.valid, "matcher_status": matcher_status,
                    "stalled": stalled, "oscillation_detected": oscillation,
                    "input_tokens": token_total("input_tokens"), "output_tokens": token_total("output_tokens"),
                    "total_tokens": token_total("total_tokens"), "decision": decision,
                }
                logger.write_artifact(f"artifacts/attempt_{iteration:02d}/attempt_metadata.json",
                                      json.dumps(metadata, indent=2, ensure_ascii=True) + "\n",
                                      artifact_type="attempt_metadata", iteration=iteration)
                logger.emit("iteration_completed", iteration=iteration, architecture=ARCHITECTURE, generation_run=generation_run,
                            mode=mode, static_valid=validation.valid, validator_accept=decision == "ACCEPT",
                            matcher_activated=matcher_status not in {"NOT_REQUESTED", "MATCHER_NO_MATCH"},
                            decision=decision, feedback=final_feedback, stalled=stalled,
                            oscillation_detected=oscillation, current_issues=issue_data,
                            generator_elapsed_ms=result.elapsed_ms,
                            validator_elapsed_ms=validator_result.elapsed_ms if validator_result else 0)
                previous_turtle, previous_validation_valid = candidate_turtle, validation.valid
                if final_status == "GENERATION_ACCEPTED":
                    break
            if final_status == "MAX_ATTEMPTS_REACHED" and any(i.needs_vocabulary_resolution and i.blocking for i in memory.current_issues):
                final_status = "TERM_RESOLUTION_UNRESOLVED"
        except KeyboardInterrupt:
            final_status, final_feedback = "INTERRUPTED", "Run interrupted; completed artifacts are preserved."
            raise
        except Exception as exc:
            final_status, final_feedback = "PIPELINE_ERROR", f"{type(exc).__name__}: {exc}"
            raise
        finally:
            accepted = final_status == "GENERATION_ACCEPTED"
            attempt_dir = run_directory / f"artifacts/attempt_{last_attempt:02d}" if last_attempt else None
            if attempt_dir is not None and not (attempt_dir / "attempt_metadata.json").exists():
                issue_data = issues_payload(memory.current_issues)
                if not (attempt_dir / "structured_current_issues.json").exists():
                    logger.write_artifact(f"artifacts/attempt_{last_attempt:02d}/structured_current_issues.json",
                        json.dumps(issue_data, indent=2, ensure_ascii=True) + "\n",
                        artifact_type="structured_current_issues", iteration=last_attempt)
                if not (attempt_dir / "past_mistakes_to_avoid.json").exists():
                    logger.write_artifact(f"artifacts/attempt_{last_attempt:02d}/past_mistakes_to_avoid.json",
                        json.dumps(memory.guards, indent=2, ensure_ascii=True) + "\n",
                        artifact_type="past_mistakes_to_avoid", iteration=last_attempt)
                fallback_calls = [event for event in logger.read_events()
                                  if event.get("event_type") == "api_call_completed" and event.get("iteration") == last_attempt]
                fallback_tokens = lambda name: sum(int(event.get(name) or 0) for event in fallback_calls)
                fallback_metadata = {
                    "architecture": ARCHITECTURE, "generation_run": generation_run,
                    "requirement_id": requirement_id, "run_id": run_id,
                    "candidate_attempt": last_attempt, "mode": last_mode,
                    "previous_candidate_present": previous_turtle is not None,
                    "previous_candidate_sha256": hash_text(previous_turtle) if previous_turtle else None,
                    "candidate_sha256": hash_text(last_turtle) if last_turtle else None,
                    "current_issue_count": len(memory.current_issues),
                    "blocking_issue_count": sum(issue.blocking for issue in memory.current_issues),
                    "current_issue_packet_sha256": packet_sha256(issue_data),
                    "past_mistake_count": len(memory.guards),
                    "regression_guard_sha256": packet_sha256(memory.guards),
                    "deterministic_valid_before": previous_validation_valid,
                    "deterministic_valid_after": last_validation.valid if last_validation is not None else None,
                    "matcher_status": matcher_status, "stalled": False,
                    "oscillation_detected": False, "input_tokens": fallback_tokens("input_tokens"),
                    "output_tokens": fallback_tokens("output_tokens"),
                    "total_tokens": fallback_tokens("total_tokens"), "decision": final_status,
                }
                logger.write_artifact(f"artifacts/attempt_{last_attempt:02d}/attempt_metadata.json",
                    json.dumps(fallback_metadata, indent=2, ensure_ascii=True) + "\n",
                    artifact_type="attempt_metadata", iteration=last_attempt)
            if last_raw:
                logger.write_artifact("diagnostics/last_candidate_raw.txt", last_raw, artifact_type="last_candidate_raw")
            source = None
            if last_turtle:
                logger.write_artifact("diagnostics/last_candidate.ttl", last_turtle, artifact_type="last_candidate_diagnostic")
                source = f"artifacts/attempt_{last_attempt:02d}/candidate_shape.ttl"
            diagnostic_metadata = {
                "requirement_id": requirement_id, "run_id": run_id, "architecture": ARCHITECTURE,
                "generation_run": generation_run, "accepted": accepted, "final_status": final_status,
                "last_candidate_attempt": last_attempt or None,
                "last_candidate_sha256": hash_text(last_turtle) if last_turtle else None,
                "source_candidate_artifact": source, "official_final_shape": False,
                "accepted_final_shape": "final/final_shape.ttl" if accepted and final_shape is not None else None,
            }
            logger.write_artifact("diagnostics/last_candidate_metadata.json",
                json.dumps(diagnostic_metadata, indent=2, ensure_ascii=True) + "\n", artifact_type="last_candidate_metadata")
            if not accepted:
                logger.emit("unresolved_issue", iteration=last_attempt, issue_type=final_status,
                            detail=final_feedback, status="OPEN", current_issues=issues_payload(memory.current_issues))
            logger.emit("run_finished", status=final_status, accepted=accepted, attempts=last_attempt,
                        architecture=ARCHITECTURE, generation_run=generation_run,
                        final_shape=str(final_shape.relative_to(run_directory)) if final_shape else "", final_feedback=final_feedback)
            try:
                workbook, warnings = self.tracker.export(run_directory)
                for warning in warnings: logger.emit("reporting_warning", warning=warning)
                if workbook: logger.emit("reporting_completed", workbook=str(workbook.relative_to(run_directory)), sha256=hashlib.sha256(workbook.read_bytes()).hexdigest())
            except Exception as exc:
                logger.emit("reporting_warning", warning=f"Tracker export failed without changing verdict: {type(exc).__name__}: {exc}")

        return PipelineRunResult(run_id=run_id, requirement_id=requirement_id, status=final_status,
            accepted=final_status == "GENERATION_ACCEPTED", attempts=last_attempt,
            run_directory=run_directory, final_shape=final_shape, final_feedback=final_feedback)
