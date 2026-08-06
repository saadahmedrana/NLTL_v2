from __future__ import annotations

import hashlib
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypeVar

from src.api.aalto_client_experiment import AaltoExperimentLLMClient
from src.processing.shacl_extractor import extract_shacl_block
from src.utils.io import read_json, read_text, write_json, write_text
from src.utils.logger import log


# Same columns as the normal experiment runner, so analysis scripts can read
# validator and no-validator CSVs with the same schema.
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
    test_kind: str
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


def resolve_input_path(input_dir: Path, case_id: str) -> Path:
    input_path = next(input_dir.rglob(f"{case_id}.json"), None)
    if input_path is None:
        raise FileNotFoundError(f"Missing input file for case: {case_id}")
    return input_path


def resolve_ship_path(project_root: Path, ship_path: str | Path) -> Path:
    # Kept only for compatibility with the normal experiment manifest and CSV.
    # The no-validator ablation does not parse or validate this ship graph.
    raw = Path(ship_path)
    if raw.is_absolute():
        resolved = raw
    else:
        resolved = project_root / "data" / "shipdesigns" / raw

    if not resolved.exists():
        raise FileNotFoundError(f"Missing ship file: {resolved}")
    return resolved


def get_run_id(prefix: str = "NV") -> str:
    return f"{prefix}{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


def write_no_validator_artifacts(
    run_dir: Path,
    regulation: dict[str, Any],
    fewshot_examples: list[dict[str, Any]],
    generator_raw: str,
    extracted_shacl_text: str,
    extraction_error: str,
    final_summary: dict[str, Any],
    input_path: Path,
    ship_path: Path,
) -> None:
    write_json(run_dir / "input_regulation.json", regulation)
    write_json(run_dir / "fewshot_used.json", fewshot_examples)
    write_text(run_dir / "input_file.txt", str(input_path))
    write_text(run_dir / "ship_file.txt", str(ship_path))
    write_text(run_dir / "generator_raw.txt", generator_raw)

    # Store whatever we can extract for convenience, but extraction failure does
    # not make the run fail because this ablation measures generator output.
    write_text(run_dir / "final_generated_shacl.ttl", extracted_shacl_text)
    if extraction_error:
        write_text(run_dir / "shacl_extraction_error.txt", extraction_error)

    write_json(run_dir / "final_summary.json", final_summary)


T = TypeVar("T")


def is_transient_api_error(exc: BaseException) -> bool:
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


def make_row(
    *,
    config: ExperimentRunConfig,
    timestamp: str,
    category: str,
    requirement_type: str,
    title: str,
    input_dir: Path,
    input_path: Path,
    ship_path: Path,
    status: str,
    run_folder_value: str,
    shacl_text: str,
    error: str,
) -> dict[str, Any]:
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
        "input_relative_path": str(input_path.relative_to(input_dir)) if input_path.exists() else "",
        "category_folder": str(input_path.parent.relative_to(input_dir)) if input_path.exists() else "",
        "status": status,

        # No validator, so these acceptance/judgment fields are intentionally blank.
        "accepted": "",
        "accepted_iteration": "",
        "max_iterations": 1,
        "aborted": False,
        "aborted_reason": "",
        "llm_final_decision": "no_validator_generator_only",
        "llm_claimed_code_correct": "",
        "validator_confidence": "",
        "manifest_expected_outcome": normalize_outcome(config.manifest_expected_outcome),
        "validator_expected_outcome": "",
        "actual_outcome": "",
        "manifest_outcome_match": "",
        "ship_behavior_correct": "",
        "reason_alignment": "",
        "applicability_handled_correctly": "",
        "syntax_valid": "",
        "ship_execution_ok": "",
        "issues_count": "",
        "llm_correct_on_final_decision": "",
        "final_shacl_hash": text_hash(shacl_text),
        "artifact_mode": config.artifact_mode,
        "run_folder": run_folder_value,
        "error": error,
    }


def run_case_experiment(config: ExperimentRunConfig) -> dict[str, Any]:
    """Run one generator-only ablation case.

    Intentional behavior:
    - exactly one generator call
    - no repair loop
    - no syntax checker
    - no pySHACL run on master/feedback ship
    - no validator LLM
    - store raw generator output and extracted SHACL if available
    """
    project_root = Path(__file__).resolve().parents[2]

    input_dir = project_root / "data" / "input" / "input_all"
    fewshot_dir = project_root / "data" / "fewshot"
    generator_prompt_path = project_root / "src" / "prompts" / "generator_prompt_withshipctx.txt"
    experiments_root = project_root / "data" / "output" / "experiments" / config.experiment_id / "runs"

    if config.test_kind not in {"pass_test", "fail_test", "feedback_ship"}:
        raise ValueError(f"Unsupported test_kind: {config.test_kind}")

    if config.artifact_mode not in {"full", "summary_only", "none"}:
        raise ValueError(f"Unsupported artifact_mode: {config.artifact_mode}")

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

    # Important: use the same working experiment client as the validator-based
    # experiment runner's normal path. Do not route GPT-5.1 to a separate
    # Responses endpoint here.
    client = AaltoExperimentLLMClient(model_name=config.model_name, debug=False)

    run_id = get_run_id()
    run_folder_name = (
        f"{config.case_id}__{config.test_kind}__{config.model_name.replace('/', '_')}"
        f"__rep{config.repeat_index:02d}__{run_id}__NO_VALIDATOR"
    )

    temp_dir_obj: tempfile.TemporaryDirectory[str] | None = None
    deleted_temp_artifacts = False

    if config.artifact_mode in {"full", "summary_only"}:
        active_run_dir = experiments_root / run_folder_name
        active_run_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir_obj = tempfile.TemporaryDirectory(prefix=f"{run_folder_name}__")
        active_run_dir = Path(temp_dir_obj.name)

    log_section(f"Starting NO-VALIDATOR ablation case {config.case_id}")
    short_status("Model", config.model_name)
    short_status("Repeat", str(config.repeat_index))
    short_status("Test kind", config.test_kind)
    short_status("Input file", input_path.name)
    short_status("Ship file", ship_path.name)
    short_status("Validator", "DISABLED")
    short_status("Syntax checker", "DISABLED")
    short_status("pySHACL ship run", "DISABLED")

    generator_raw = ""
    shacl_text = ""
    extraction_error = ""

    try:
        log_section("Generator-only pass 1/1")
        generator_raw = call_llm_with_transport_retries(
            "generator",
            lambda: client.call_generator_llm(
                generator_instructions=generator_prompt,
                regulation_json=regulation,
                fewshot_examples=fewshot_examples,
                repair_feedback="NONE",
            ),
        )
        log("Generator response received.")

        try:
            shacl_text = extract_shacl_block(generator_raw)
            log("SHACL extraction: success")
        except Exception as exc:
            extraction_error = str(exc)
            shacl_text = ""
            log(f"SHACL extraction: failed - {extraction_error}")

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
            "ablation": "no_validator_generator_only",
            "max_iterations": 1,
            "validator_enabled": False,
            "syntax_checker_enabled": False,
            "ship_validation_enabled": False,
            "shacl_extraction_ok": not bool(extraction_error),
            "shacl_extraction_error": extraction_error,
            "final_shacl_hash": text_hash(shacl_text),
            "artifact_mode": config.artifact_mode,
            "error": "",
        }

        if config.artifact_mode in {"full", "summary_only"}:
            write_no_validator_artifacts(
                run_dir=active_run_dir,
                regulation=regulation,
                fewshot_examples=fewshot_examples,
                generator_raw=generator_raw,
                extracted_shacl_text=shacl_text,
                extraction_error=extraction_error,
                final_summary=final_summary,
                input_path=input_path,
                ship_path=ship_path,
            )

        status = "completed_generator_only"
        error_message = extraction_error

    except Exception as exc:
        status = "crashed"
        error_message = str(exc)
        log(f"No-validator experiment case crashed: {config.case_id}")
        log(f"Error: {exc}")

    if config.artifact_mode == "none":
        if temp_dir_obj is not None and not deleted_temp_artifacts:
            temp_path_str = str(active_run_dir)
            temp_dir_obj.cleanup()
            run_folder_value = f"{temp_path_str} (deleted temp artifacts)"
        else:
            run_folder_value = ""
    else:
        run_folder_value = str(active_run_dir.relative_to(project_root))

    return make_row(
        config=config,
        timestamp=timestamp,
        category=category,
        requirement_type=requirement_type,
        title=title,
        input_dir=input_dir,
        input_path=input_path,
        ship_path=ship_path,
        status=status,
        run_folder_value=run_folder_value,
        shacl_text=shacl_text,
        error=error_message,
    )
