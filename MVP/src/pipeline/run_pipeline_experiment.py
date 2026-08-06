from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypeVar

from src.api.aalto_client_experiment import AaltoExperimentLLMClient
from src.processing.shacl_extractor import extract_shacl_block
from src.processing.shacl_runner import run_shacl_validation
from src.processing.syntax_checker import check_turtle_syntax
from src.processing.validator_parser import parse_validator_json
from src.utils.io import read_json, read_text, write_json, write_text
from src.utils.logger import log
from src.api.aalto_client_experiment_responses import AaltoExperimentResponsesClient


RESULT_COLUMNS = [
    "experiment_id",
    "timestamp",
    "model_name",
    "repeat_index",
    "case_id",
    "shape_name",
    "category",
    "requirement_type",
    "title",
    "test_kind",
    "ship_ttl",
    "input_filename",
    "input_relative_path",
    "category_folder",
    "status",
    "accepted",
    "accepted_iteration",
    "max_iterations",
    "aborted",
    "aborted_reason",
    "llm_final_decision",
    "llm_claimed_code_correct",
    "validator_confidence",
    "manifest_expected_outcome",
    "validator_expected_outcome",
    "actual_outcome",
    "manifest_outcome_match",
    "ship_behavior_correct",
    "reason_alignment",
    "applicability_handled_correctly",
    "syntax_valid",
    "ship_execution_ok",
    "issues_count",
    "llm_correct_on_final_decision",
    "final_shacl_hash",
    "artifact_mode",
    "run_folder",
    "error",
]


@dataclass(slots=True)
class ExperimentRunConfig:
    case_id: str
    ship_path: str | Path
    test_kind: str  # "pass_test" | "fail_test"
    manifest_expected_outcome: str
    model_name: str
    repeat_index: int
    experiment_id: str
    max_iterations: int
    artifact_mode: str  # "full" | "summary_only" | "none"

    shape_name: str = ""
    category: str = ""
    requirement_type: str = ""
    title: str = ""


def log_section(title: str) -> None:
    log("")
    log(f"=== {title} ===")


def short_status(label: str, value: str) -> None:
    log(f"{label}: {value}")


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12] if text else "NONE"


def normalize_outcome(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"pass", "fail", "not_applicable", "execution_error", "unknown"}:
        return text
    if text in {"non_conformant", "nonconformant"}:
        return "fail"
    return text or "unknown"


def load_fewshot_examples(fewshot_dir: Path, category: str) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    category_norm = str(category).strip().lower()

    for path in sorted(fewshot_dir.rglob("*.json")):
        item = read_json(path)
        item_category = str(item.get("category", "")).strip().lower()
        if item_category == category_norm:
            examples.append(item)

    return examples


def build_skipped_validation_result(reason: str) -> dict[str, Any]:
    return {
        "execution_ok": False,
        "conforms": None,
        "results_text": "",
        "error": reason,
    }


def hard_acceptance_passed(
    syntax_result: dict[str, Any],
    ship_result: dict[str, Any],
    validator_result: dict[str, Any],
) -> bool:
    syntax_valid = bool(syntax_result.get("syntax_valid"))
    ship_execution_ok = ship_result.get("execution_ok") is True
    validator_accepts = validator_result.get("decision") == "accept"
    return syntax_valid and ship_execution_ok and validator_accepts


def resolve_input_path(input_dir: Path, case_id: str) -> Path:
    input_path = next(input_dir.rglob(f"{case_id}.json"), None)
    if input_path is None:
        raise FileNotFoundError(f"Missing input file for case: {case_id}")
    return input_path


def resolve_ship_path(project_root: Path, ship_path: str | Path) -> Path:
    raw = Path(ship_path)
    if raw.is_absolute():
        resolved = raw
    else:
        resolved = project_root / "data" / "shipdesigns" / raw

    if not resolved.exists():
        raise FileNotFoundError(f"Missing ship file: {resolved}")
    return resolved


def get_run_id(prefix: str = "R") -> str:
    return f"{prefix}{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


def write_iteration_artifacts(
    run_dir: Path,
    iter_tag: str,
    generator_raw: str,
    shacl_text: str,
    syntax_result: dict[str, Any],
    ship_result: dict[str, Any],
    validator_raw: str,
    validator_result: dict[str, Any],
    iteration_summary: dict[str, Any],
) -> None:
    write_text(run_dir / f"{iter_tag}_generator_raw.txt", generator_raw)
    write_text(run_dir / f"{iter_tag}_generated_shacl.ttl", shacl_text)
    write_json(run_dir / f"{iter_tag}_syntax_result.json", syntax_result)
    write_json(run_dir / f"{iter_tag}_ship_validation.json", ship_result)
    write_text(run_dir / f"{iter_tag}_validator_raw.txt", validator_raw)
    write_json(run_dir / f"{iter_tag}_validator_result.json", validator_result)
    write_json(run_dir / f"{iter_tag}_summary.json", iteration_summary)


def write_summary_only_artifacts(
    run_dir: Path,
    regulation: dict[str, Any],
    fewshot_examples: list[dict[str, Any]],
    final_summary: dict[str, Any],
    final_shacl_text: str,
    final_validator_result: dict[str, Any],
    final_ship_result: dict[str, Any],
    final_syntax_result: dict[str, Any],
    input_path: Path,
    ship_path: Path,
) -> None:
    write_json(run_dir / "input_regulation.json", regulation)
    write_json(run_dir / "fewshot_used.json", fewshot_examples)
    write_text(run_dir / "input_file.txt", str(input_path))
    write_text(run_dir / "ship_file.txt", str(ship_path))
    write_text(run_dir / "final_generated_shacl.ttl", final_shacl_text)
    write_json(run_dir / "final_validator_result.json", final_validator_result)
    write_json(run_dir / "final_ship_validation.json", final_ship_result)
    write_json(run_dir / "final_syntax_result.json", final_syntax_result)
    write_json(run_dir / "final_summary.json", final_summary)


def validator_fallback_result(
    exc: Exception,
    syntax_result: dict[str, Any],
    ship_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "decision": "retry",
        "confidence": 0.0,
        "semantic_match": False,
        "syntax_valid": syntax_result["syntax_valid"],
        "expected_outcome": "unknown",
        "actual_outcome": (
            "pass" if ship_result.get("conforms") is True
            else "fail" if ship_result.get("conforms") is False
            else "execution_error" if ship_result.get("execution_ok") is False
            else "unknown"
        ),
        "ship_behavior_correct": False,
        "reason_alignment": False,
        "applicability_handled_correctly": False,
        "facts_used": [],
        "regulation_interpretation": "",
        "applicability_explanation": "",
        "justification": "",
        "issues": [f"Validator output was not parseable JSON: {exc}"],
        "suggested_fix": "Return strict JSON only and judge expected vs actual outcome explicitly.",
    }


def compute_llm_correct_on_final_decision(
    llm_claimed_code_correct: bool,
    syntax_valid: bool,
    ship_execution_ok: bool,
    manifest_outcome_match: bool,
    ship_behavior_correct: bool,
    reason_alignment: bool,
    applicability_handled_correctly: bool,
) -> bool:
    should_accept = all(
        [
            syntax_valid,
            ship_execution_ok,
            manifest_outcome_match,
            ship_behavior_correct,
            reason_alignment,
            applicability_handled_correctly,
        ]
    )
    return llm_claimed_code_correct == should_accept


T = TypeVar("T")


def is_transient_api_error(exc: BaseException) -> bool:
    """Return True for infrastructure/API transport failures that should not count as experiment failures."""
    text = str(exc).lower()
    transient_markers = (
        "read timed out",
        "connect timeout",
        "connection timed out",
        "max retries exceeded",
        "connection aborted",
        "connection reset",
        "temporarily unavailable",
        "service unavailable",
        "gateway timeout",
        "bad gateway",
        "too many requests",
        "rate limit",
        "status 408",
        "status 429",
        "status 500",
        "status 502",
        "status 503",
        "status 504",
    )
    return any(marker in text for marker in transient_markers)


def call_llm_with_transport_retries(
    label: str,
    fn: Callable[[], T],
    *,
    max_retries: int = 8,
    initial_delay_seconds: float = 10.0,
    max_delay_seconds: float = 120.0,
) -> T:
    """Retry the same LLM call on transient transport failures without consuming a pipeline iteration."""
    attempt = 0
    delay = initial_delay_seconds

    while True:
        try:
            return fn()
        except Exception as exc:
            if not is_transient_api_error(exc):
                raise

            attempt += 1
            if attempt > max_retries:
                raise RuntimeError(
                    f"Transient API failure during {label} after {max_retries} retries: {exc}"
                ) from exc

            log(
                f"Transient API failure during {label}; retrying same example "
                f"({attempt}/{max_retries}) after {delay:.0f}s."
            )
            time.sleep(delay)
            delay = min(delay * 2, max_delay_seconds)


def run_case_experiment(config: ExperimentRunConfig) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]

    input_dir = project_root / "data" / "input" / "input_all"
    fewshot_dir = project_root / "data" / "fewshot"
    generator_prompt_path = project_root / "src" / "prompts" / "generator_prompt.txt"
    validator_prompt_path = project_root / "src" / "prompts" / "validator_prompt.txt"
    experiments_root = project_root / "data" / "output" / "experiments" / config.experiment_id / "runs"

    if config.test_kind not in {"pass_test", "fail_test", "feedback_ship"}:
        raise ValueError(f"Unsupported test_kind: {config.test_kind}")

    if config.artifact_mode not in {"full", "summary_only", "none"}:
        raise ValueError(f"Unsupported artifact_mode: {config.artifact_mode}")

    if config.max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")

    timestamp = datetime.now().isoformat(timespec="seconds")
    input_path = resolve_input_path(input_dir, config.case_id)
    ship_path = resolve_ship_path(project_root, config.ship_path)

    regulation = read_json(input_path)
    category = config.category or str(regulation.get("category") or "").strip()
    if not category:
        raise ValueError("Input regulation JSON is missing 'category'.")

    requirement_type = config.requirement_type or str(regulation.get("requirement_type") or "")
    title = config.title or str(regulation.get("title") or "")
    fewshot_examples = load_fewshot_examples(fewshot_dir, category)
    if not fewshot_examples:
        raise ValueError(f"No few-shot examples found for category '{category}'.")

    generator_prompt = read_text(generator_prompt_path)
    validator_prompt = read_text(validator_prompt_path)
    
    responses_models = {
    "gpt-5",
    "gpt-5.1",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5-2025-08-07",
    "gpt-5.1-2025-11-13",
    "gpt-5-mini-2025-08-07",
    "gpt-5-nano-2025-08-07",
}

    if config.model_name in responses_models:
        client = AaltoExperimentResponsesClient(model_name=config.model_name, debug=False)
    else:
        client = AaltoExperimentLLMClient(model_name=config.model_name, debug=False)


    run_id = get_run_id()
    run_folder_name = f"{config.case_id}__{config.test_kind}__{config.model_name.replace('/', '_')}__rep{config.repeat_index:02d}__{run_id}"

    temp_dir_obj: tempfile.TemporaryDirectory[str] | None = None
    deleted_temp_artifacts = False

    if config.artifact_mode in {"full", "summary_only"}:
        active_run_dir = experiments_root / run_folder_name
        active_run_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir_obj = tempfile.TemporaryDirectory(prefix=f"{run_folder_name}__")
        active_run_dir = Path(temp_dir_obj.name)

    repair_feedback = ""

    final_summary: dict[str, Any] = {
        "experiment_id": config.experiment_id,
        "timestamp": timestamp,
        "case_id": config.case_id,
        "run_id": run_id,
        "regulation_id": regulation.get("id"),
        "shape_name": config.shape_name,
        "category": category,
        "requirement_type": requirement_type,
        "title": title,
        "test_kind": config.test_kind,
        "model_name": config.model_name,
        "repeat_index": config.repeat_index,
        "input_file": input_path.name,
        "ship_file": ship_path.name,
        "max_iterations": config.max_iterations,
        "accepted": False,
        "accepted_iteration": None,
        "aborted": False,
        "aborted_reason": "",
        "artifact_mode": config.artifact_mode,
    }

    if config.artifact_mode in {"full", "summary_only"}:
        write_json(active_run_dir / "input_regulation.json", regulation)
        write_json(active_run_dir / "fewshot_used.json", fewshot_examples)
        write_text(active_run_dir / "case_id.txt", config.case_id)
        write_text(active_run_dir / "input_file.txt", str(input_path))
        write_text(active_run_dir / "ship_file.txt", str(ship_path))

    log_section(f"Starting experiment case {config.case_id}")
    short_status("Model", config.model_name)
    short_status("Repeat", str(config.repeat_index))
    short_status("Test kind", config.test_kind)
    short_status("Expected outcome", normalize_outcome(config.manifest_expected_outcome))
    short_status("Input file", input_path.name)
    short_status("Ship file", ship_path.name)

    last_validator_result: dict[str, Any] = {}
    last_ship_result: dict[str, Any] = {}
    last_syntax_result: dict[str, Any] = {}
    last_actual_outcome = "unknown"
    last_shacl_text = ""
    error_message = ""

    try:
        for iteration in range(1, config.max_iterations + 1):
            iter_tag = f"iter_{iteration:02d}"
            log_section(f"Iteration {iteration}/{config.max_iterations}")

            generator_raw = call_llm_with_transport_retries(
                "generator",
                lambda: client.call_generator_llm(
                    generator_instructions=generator_prompt,
                    regulation_json=regulation,
                    fewshot_examples=fewshot_examples,
                    repair_feedback=repair_feedback,
                ),
            )
            log("Generator response received.")

            try:
                shacl_text = extract_shacl_block(generator_raw)
                shacl_extract_error = ""
            except Exception as exc:
                shacl_text = ""
                shacl_extract_error = str(exc)

            if shacl_extract_error:
                log(f"SHACL extraction: failed - {shacl_extract_error}")
                syntax_result = {
                    "syntax_valid": False,
                    "errors": [f"SHACL extraction failed: {shacl_extract_error}"],
                    "warnings": [],
                }
            else:
                log("SHACL extraction: success")
                syntax_result = check_turtle_syntax(shacl_text)

            if syntax_result["syntax_valid"]:
                log("Syntax check: valid")
                ship_result = run_shacl_validation(shacl_text, ship_path)
            else:
                log("Syntax check: invalid")
                for err in syntax_result.get("errors", []):
                    log(f"  - {err}")
                ship_result = build_skipped_validation_result(
                    "Skipped because SHACL syntax/extraction failed."
                )

            if ship_result.get("execution_ok") is not True:
                actual_outcome = "execution_error"
                ship_label = "execution_error"
            elif ship_result.get("conforms") is True:
                actual_outcome = "pass"
                ship_label = "conforms"
            else:
                actual_outcome = "fail"
                ship_label = "non-conformant"

            log(f"Ship graph: {ship_label}")

            validator_raw = call_llm_with_transport_retries(
                "validator",
                lambda: client.call_validator_llm(
                    validator_instructions=validator_prompt,
                    regulation_json=regulation,
                    generated_shacl=shacl_text,
                    syntax_result=syntax_result,
                    validation_result=ship_result,
                    ship_graph_path=str(ship_path),
                    fewshot_examples=fewshot_examples,
                ),
            )

            try:
                validator_result = parse_validator_json(validator_raw)
            except Exception as exc:
                validator_result = validator_fallback_result(exc, syntax_result, ship_result)

            decision = validator_result.get("decision", "unknown")
            confidence = validator_result.get("confidence", 0.0)

            log(f"Validator decision: {decision} ({confidence:.2f})")
            log(f"Expected outcome: {validator_result.get('expected_outcome', 'unknown')}")
            log(f"Actual outcome: {validator_result.get('actual_outcome', actual_outcome)}")
            log(f"Ship behavior correct: {validator_result.get('ship_behavior_correct', False)}")
            log(f"Reason alignment: {validator_result.get('reason_alignment', False)}")

            if validator_result.get("issues"):
                log("Validator issues:")
                for issue in validator_result["issues"]:
                    log(f"  - {issue}")

            accepted = hard_acceptance_passed(
                syntax_result=syntax_result,
                ship_result=ship_result,
                validator_result=validator_result,
            )

            iteration_summary = {
                "case_id": config.case_id,
                "iteration": iteration,
                "syntax_valid": syntax_result.get("syntax_valid"),
                "ship_execution_ok": ship_result.get("execution_ok"),
                "ship_conforms": ship_result.get("conforms"),
                "actual_outcome": actual_outcome,
                "expected_outcome": validator_result.get("expected_outcome"),
                "ship_behavior_correct": validator_result.get("ship_behavior_correct"),
                "reason_alignment": validator_result.get("reason_alignment"),
                "applicability_handled_correctly": validator_result.get("applicability_handled_correctly"),
                "validator_decision": validator_result.get("decision"),
                "validator_confidence": validator_result.get("confidence"),
                "issues_count": len(validator_result.get("issues", [])),
                "accepted": accepted,
            }

            if config.artifact_mode == "full":
                write_iteration_artifacts(
                    run_dir=active_run_dir,
                    iter_tag=iter_tag,
                    generator_raw=generator_raw,
                    shacl_text=shacl_text,
                    syntax_result=syntax_result,
                    ship_result=ship_result,
                    validator_raw=validator_raw,
                    validator_result=validator_result,
                    iteration_summary=iteration_summary,
                )

            last_validator_result = validator_result
            last_ship_result = ship_result
            last_syntax_result = syntax_result
            last_actual_outcome = actual_outcome
            last_shacl_text = shacl_text

            if accepted:
                final_summary["accepted"] = True
                final_summary["accepted_iteration"] = iteration
                final_summary["final_validator_decision"] = validator_result.get("decision")
                final_summary["validator_expected_outcome"] = validator_result.get("expected_outcome")
                final_summary["actual_outcome"] = actual_outcome
                final_summary["final_shacl_hash"] = text_hash(shacl_text)

                if config.artifact_mode == "summary_only":
                    write_summary_only_artifacts(
                        run_dir=active_run_dir,
                        regulation=regulation,
                        fewshot_examples=fewshot_examples,
                        final_summary=final_summary,
                        final_shacl_text=last_shacl_text,
                        final_validator_result=last_validator_result,
                        final_ship_result=last_ship_result,
                        final_syntax_result=last_syntax_result,
                        input_path=input_path,
                        ship_path=ship_path,
                    )
                elif config.artifact_mode == "full":
                    write_json(active_run_dir / "final_summary.json", final_summary)

                manifest_expected_outcome = normalize_outcome(config.manifest_expected_outcome)
                validator_expected_outcome = normalize_outcome(validator_result.get("expected_outcome"))
                manifest_outcome_match = actual_outcome == manifest_expected_outcome
                llm_claimed_code_correct = validator_result.get("decision") == "accept"

                if config.artifact_mode == "none":
                    deleted_temp_artifacts = True
                    temp_path_str = str(active_run_dir)
                    temp_dir_obj.cleanup()
                    run_folder_value = f"{temp_path_str} (deleted temp artifacts)"
                else:
                    run_folder_value = str(active_run_dir.relative_to(project_root))

                return {
                    "experiment_id": config.experiment_id,
                    "timestamp": timestamp,
                    "model_name": config.model_name,
                    "repeat_index": config.repeat_index,
                    "case_id": config.case_id,
                    "shape_name": config.shape_name,
                    "category": category,
                    "requirement_type": requirement_type,
                    "title": title,
                    "test_kind": config.test_kind,
                    "ship_ttl": ship_path.name,
                    "input_filename": input_path.name,
                    "input_relative_path": str(input_path.relative_to(input_dir)),
                    "category_folder": str(input_path.parent.relative_to(input_dir)),
                    "status": "completed_accepted",
                    "accepted": True,
                    "accepted_iteration": iteration,
                    "max_iterations": config.max_iterations,
                    "aborted": False,
                    "aborted_reason": "",
                    "llm_final_decision": validator_result.get("decision"),
                    "llm_claimed_code_correct": llm_claimed_code_correct,
                    "validator_confidence": validator_result.get("confidence"),
                    "manifest_expected_outcome": manifest_expected_outcome,
                    "validator_expected_outcome": validator_expected_outcome,
                    "actual_outcome": actual_outcome,
                    "manifest_outcome_match": manifest_outcome_match,
                    "ship_behavior_correct": validator_result.get("ship_behavior_correct"),
                    "reason_alignment": validator_result.get("reason_alignment"),
                    "applicability_handled_correctly": validator_result.get("applicability_handled_correctly"),
                    "syntax_valid": syntax_result.get("syntax_valid"),
                    "ship_execution_ok": ship_result.get("execution_ok"),
                    "issues_count": len(validator_result.get("issues", [])),
                    "llm_correct_on_final_decision": compute_llm_correct_on_final_decision(
                        llm_claimed_code_correct=llm_claimed_code_correct,
                        syntax_valid=bool(syntax_result.get("syntax_valid")),
                        ship_execution_ok=ship_result.get("execution_ok") is True,
                        manifest_outcome_match=manifest_outcome_match,
                        ship_behavior_correct=bool(validator_result.get("ship_behavior_correct")),
                        reason_alignment=bool(validator_result.get("reason_alignment")),
                        applicability_handled_correctly=bool(
                            validator_result.get("applicability_handled_correctly")
                        ),
                    ),
                    "final_shacl_hash": text_hash(shacl_text),
                    "artifact_mode": config.artifact_mode,
                    "run_folder": run_folder_value,
                    "error": "",
                }

            repair_feedback = validator_result.get("suggested_fix", "")
            if validator_result.get("issues"):
                repair_feedback = (
                    repair_feedback
                    + "\n\nIssues:\n- "
                    + "\n- ".join(str(x) for x in validator_result["issues"])
                ).strip()

        final_summary["final_validator_decision"] = last_validator_result.get("decision")
        final_summary["accepted"] = False
        final_summary["aborted"] = True
        final_summary["aborted_reason"] = "max_iterations_reached"
        final_summary["validator_expected_outcome"] = last_validator_result.get("expected_outcome")
        final_summary["actual_outcome"] = last_actual_outcome
        final_summary["final_shacl_hash"] = text_hash(last_shacl_text)

        if config.artifact_mode == "summary_only":
            write_summary_only_artifacts(
                run_dir=active_run_dir,
                regulation=regulation,
                fewshot_examples=fewshot_examples,
                final_summary=final_summary,
                final_shacl_text=last_shacl_text,
                final_validator_result=last_validator_result,
                final_ship_result=last_ship_result,
                final_syntax_result=last_syntax_result,
                input_path=input_path,
                ship_path=ship_path,
            )
        elif config.artifact_mode == "full":
            write_json(active_run_dir / "final_summary.json", final_summary)

        log(f"Stopped after {config.max_iterations} iterations without acceptance")

    except Exception as exc:
        error_message = str(exc)
        log(f"Experiment case crashed: {config.case_id}")
        log(f"Error: {exc}")

        manifest_expected_outcome = normalize_outcome(config.manifest_expected_outcome)
        validator_expected_outcome = normalize_outcome(last_validator_result.get("expected_outcome"))
        manifest_outcome_match = last_actual_outcome == manifest_expected_outcome
        llm_claimed_code_correct = last_validator_result.get("decision") == "accept"

        if config.artifact_mode == "none":
            if temp_dir_obj is not None and not deleted_temp_artifacts:
                temp_path_str = str(active_run_dir)
                temp_dir_obj.cleanup()
                run_folder_value = f"{temp_path_str} (deleted temp artifacts)"
            else:
                run_folder_value = ""
        else:
            run_folder_value = str(active_run_dir.relative_to(project_root))

        return {
            "experiment_id": config.experiment_id,
            "timestamp": timestamp,
            "model_name": config.model_name,
            "repeat_index": config.repeat_index,
            "case_id": config.case_id,
            "shape_name": config.shape_name,
            "category": category,
            "requirement_type": requirement_type,
            "title": title,
            "test_kind": config.test_kind,
            "ship_ttl": ship_path.name if ship_path.exists() else str(config.ship_path),
            "input_filename": input_path.name if input_path.exists() else f"{config.case_id}.json",
            "input_relative_path": (
                str(input_path.relative_to(input_dir)) if input_path.exists() else ""
            ),
            "category_folder": (
                str(input_path.parent.relative_to(input_dir)) if input_path.exists() else ""
            ),
            "status": "crashed",
            "accepted": False,
            "accepted_iteration": None,
            "max_iterations": config.max_iterations,
            "aborted": False,
            "aborted_reason": "",
            "llm_final_decision": last_validator_result.get("decision"),
            "llm_claimed_code_correct": llm_claimed_code_correct,
            "validator_confidence": last_validator_result.get("confidence"),
            "manifest_expected_outcome": manifest_expected_outcome,
            "validator_expected_outcome": validator_expected_outcome,
            "actual_outcome": last_actual_outcome,
            "manifest_outcome_match": manifest_outcome_match,
            "ship_behavior_correct": last_validator_result.get("ship_behavior_correct"),
            "reason_alignment": last_validator_result.get("reason_alignment"),
            "applicability_handled_correctly": last_validator_result.get("applicability_handled_correctly"),
            "syntax_valid": last_syntax_result.get("syntax_valid"),
            "ship_execution_ok": last_ship_result.get("execution_ok"),
            "issues_count": len(last_validator_result.get("issues", [])),
            "llm_correct_on_final_decision": compute_llm_correct_on_final_decision(
                llm_claimed_code_correct=llm_claimed_code_correct,
                syntax_valid=bool(last_syntax_result.get("syntax_valid")),
                ship_execution_ok=last_ship_result.get("execution_ok") is True,
                manifest_outcome_match=manifest_outcome_match,
                ship_behavior_correct=bool(last_validator_result.get("ship_behavior_correct")),
                reason_alignment=bool(last_validator_result.get("reason_alignment")),
                applicability_handled_correctly=bool(
                    last_validator_result.get("applicability_handled_correctly")
                ),
            ),
            "final_shacl_hash": text_hash(last_shacl_text),
            "artifact_mode": config.artifact_mode,
            "run_folder": run_folder_value,
            "error": error_message,
        }

    manifest_expected_outcome = normalize_outcome(config.manifest_expected_outcome)
    validator_expected_outcome = normalize_outcome(last_validator_result.get("expected_outcome"))
    manifest_outcome_match = last_actual_outcome == manifest_expected_outcome
    llm_claimed_code_correct = last_validator_result.get("decision") == "accept"

    if config.artifact_mode == "none":
        if temp_dir_obj is not None and not deleted_temp_artifacts:
            temp_path_str = str(active_run_dir)
            temp_dir_obj.cleanup()
            run_folder_value = f"{temp_path_str} (deleted temp artifacts)"
        else:
            run_folder_value = ""
    else:
        run_folder_value = str(active_run_dir.relative_to(project_root))

    return {
        "experiment_id": config.experiment_id,
        "timestamp": timestamp,
        "model_name": config.model_name,
        "repeat_index": config.repeat_index,
        "case_id": config.case_id,
        "shape_name": config.shape_name,
        "category": category,
        "requirement_type": requirement_type,
        "title": title,
        "test_kind": config.test_kind,
        "ship_ttl": ship_path.name,
        "input_filename": input_path.name,
        "input_relative_path": str(input_path.relative_to(input_dir)),
        "category_folder": str(input_path.parent.relative_to(input_dir)),
        "status": "aborted_max_iterations",
        "accepted": False,
        "accepted_iteration": None,
        "max_iterations": config.max_iterations,
        "aborted": True,
        "aborted_reason": "max_iterations_reached",
        "llm_final_decision": last_validator_result.get("decision"),
        "llm_claimed_code_correct": llm_claimed_code_correct,
        "validator_confidence": last_validator_result.get("confidence"),
        "manifest_expected_outcome": manifest_expected_outcome,
        "validator_expected_outcome": validator_expected_outcome,
        "actual_outcome": last_actual_outcome,
        "manifest_outcome_match": manifest_outcome_match,
        "ship_behavior_correct": last_validator_result.get("ship_behavior_correct"),
        "reason_alignment": last_validator_result.get("reason_alignment"),
        "applicability_handled_correctly": last_validator_result.get("applicability_handled_correctly"),
        "syntax_valid": last_syntax_result.get("syntax_valid"),
        "ship_execution_ok": last_ship_result.get("execution_ok"),
        "issues_count": len(last_validator_result.get("issues", [])),
        "llm_correct_on_final_decision": compute_llm_correct_on_final_decision(
            llm_claimed_code_correct=llm_claimed_code_correct,
            syntax_valid=bool(last_syntax_result.get("syntax_valid")),
            ship_execution_ok=last_ship_result.get("execution_ok") is True,
            manifest_outcome_match=manifest_outcome_match,
            ship_behavior_correct=bool(last_validator_result.get("ship_behavior_correct")),
            reason_alignment=bool(last_validator_result.get("reason_alignment")),
            applicability_handled_correctly=bool(
                last_validator_result.get("applicability_handled_correctly")
            ),
        ),
        "final_shacl_hash": text_hash(last_shacl_text),
        "artifact_mode": config.artifact_mode,
        "run_folder": run_folder_value,
        "error": error_message,
    }
