import argparse
import re
from pathlib import Path
from typing import Any

from src.api.aalto_client import AaltoLLMClient
from src.processing.shacl_extractor import extract_shacl_block
from src.processing.shacl_runner import run_shacl_validation
from src.processing.syntax_checker import check_turtle_syntax
from src.processing.validator_parser import parse_validator_json
from src.utils.io import read_text, read_json, write_text, write_json
from src.utils.logger import log


MAX_ITERATIONS = 10


def log_section(title: str) -> None:
    log("")
    log(f"=== {title} ===")


def short_status(label: str, value: str) -> None:
    log(f"{label}: {value}")


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


def list_available_cases(input_dir: Path) -> list[str]:
    return sorted(path.stem for path in input_dir.rglob("*.json"))


def choose_case_interactively(input_dir: Path) -> str:
    cases = list_available_cases(input_dir)

    if not cases:
        raise ValueError(f"No case files found in {input_dir}")

    print("\nAvailable cases:")
    for idx, case_id in enumerate(cases, start=1):
        print(f"  {idx}. {case_id}")

    while True:
        raw = input("\nEnter case number or case id (e.g. 1 or C04): ").strip()

        if raw in cases:
            return raw

        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(cases):
                return cases[index - 1]

        print("Invalid selection. Try again.")


def resolve_case_paths(project_root: Path, input_dir: Path, case_id: str) -> tuple[Path, Path]:
    input_path = next(input_dir.rglob(f"{case_id}.json"), None)
    if input_path is None:
        raise FileNotFoundError(f"Missing input file for case: {case_id}")

    ship_path = project_root / "data" / "shipdesigns" / "master_ship_1.ttl"

    if not input_path.exists():
        raise FileNotFoundError(f"Missing input file: {input_path}")
    if not ship_path.exists():
        raise FileNotFoundError(f"Missing ship file: {ship_path}")

    return input_path, ship_path


def get_next_run_dir(runs_root: Path, case_id: str) -> tuple[str, Path]:
    case_runs_dir = runs_root / case_id
    case_runs_dir.mkdir(parents=True, exist_ok=True)

    existing_nums: list[int] = []
    pattern = re.compile(r"R(\d+)$")

    for path in case_runs_dir.iterdir():
        if not path.is_dir():
            continue
        match = pattern.fullmatch(path.name)
        if match:
            existing_nums.append(int(match.group(1)))

    next_num = max(existing_nums, default=0) + 1
    run_id = f"R{next_num:02d}"
    run_dir = case_runs_dir / run_id
    return run_id, run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=str, help="Case id to run")
    parser.add_argument("--list", action="store_true", help="List available case files and exit")
    return parser.parse_args()


def run_case(case_id: str) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]

    input_dir = project_root / "data" / "input" / "input_all"
    fewshot_dir = project_root / "data" / "fewshot"
    runs_root = project_root / "data" / "output" / "runs"
    generator_prompt_path = project_root / "src" / "prompts" / "generator_prompt.txt"
    validator_prompt_path = project_root / "src" / "prompts" / "validator_prompt.txt"

    input_path, ship_path = resolve_case_paths(project_root, input_dir, case_id)

    regulation = read_json(input_path)
    category = regulation.get("category")
    if not category:
        raise ValueError("Input regulation JSON is missing 'category'.")

    fewshot_examples = load_fewshot_examples(fewshot_dir, category)
    if not fewshot_examples:
        raise ValueError(f"No few-shot examples found for category '{category}'.")

    run_id, run_dir = get_next_run_dir(runs_root, case_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    generator_prompt = read_text(generator_prompt_path)
    validator_prompt = read_text(validator_prompt_path)

    client = AaltoLLMClient(debug=False)

    write_json(run_dir / "input_regulation.json", regulation)
    write_json(run_dir / "fewshot_used.json", fewshot_examples)
    write_text(run_dir / "case_id.txt", case_id)
    write_text(run_dir / "input_file.txt", str(input_path))
    write_text(run_dir / "ship_file.txt", str(ship_path))

    repair_feedback = ""

    log_section(f"Starting case {case_id}")
    short_status("Input file", input_path.name)
    short_status("Ship file", ship_path.name)
    short_status("Run folder", str(run_dir.relative_to(project_root)))

    final_summary: dict[str, Any] = {
        "case_id": case_id,
        "run_id": run_id,
        "regulation_id": regulation.get("id"),
        "category": category,
        "input_file": input_path.name,
        "ship_file": ship_path.name,
        "max_iterations": MAX_ITERATIONS,
        "accepted": False,
        "accepted_iteration": None,
    }

    last_validator_result: dict[str, Any] = {}
    last_ship_result: dict[str, Any] = {}
    last_syntax_result: dict[str, Any] = {}
    last_actual_outcome = "unknown"

    for iteration in range(1, MAX_ITERATIONS + 1):
        iter_tag = f"iter_{iteration:02d}"
        log_section(f"Iteration {iteration}/{MAX_ITERATIONS}")

        generator_raw = client.call_generator_llm(
            generator_instructions=generator_prompt,
            regulation_json=regulation,
            fewshot_examples=fewshot_examples,
            repair_feedback=repair_feedback,
        )
        log("Generator response received.")
        write_text(run_dir / f"{iter_tag}_generator_raw.txt", generator_raw)

        try:
            shacl_text = extract_shacl_block(generator_raw)
            shacl_extract_error = ""
        except Exception as exc:
            shacl_text = ""
            shacl_extract_error = str(exc)

        write_text(run_dir / f"{iter_tag}_generated_shacl.ttl", shacl_text)

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

        write_json(run_dir / f"{iter_tag}_syntax_result.json", syntax_result)

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

        write_json(run_dir / f"{iter_tag}_ship_validation.json", ship_result)

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

        validator_raw = client.call_validator_llm(
            validator_instructions=validator_prompt,
            regulation_json=regulation,
            generated_shacl=shacl_text,
            syntax_result=syntax_result,
            validation_result=ship_result,
            ship_graph_path=str(ship_path),
            fewshot_examples=fewshot_examples,
        )
        write_text(run_dir / f"{iter_tag}_validator_raw.txt", validator_raw)

        try:
            validator_result = parse_validator_json(validator_raw)
        except Exception as exc:
            validator_result = {
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

        write_json(run_dir / f"{iter_tag}_validator_result.json", validator_result)

        decision = validator_result.get("decision", "unknown")
        confidence = validator_result.get("confidence", 0.0)
        log(f"Validator decision: {decision} ({confidence:.2f})")
        log(f"Expected outcome: {validator_result.get('expected_outcome', 'unknown')}")
        log(f"Actual outcome: {validator_result.get('actual_outcome', actual_outcome)}")
        log(f"Ship behavior correct: {validator_result.get('ship_behavior_correct', False)}")
        log(f"Reason alignment: {validator_result.get('reason_alignment', False)}")

        if validator_result.get("facts_used"):
            log("Facts used:")
            for fact in validator_result["facts_used"]:
                log(f"  - {fact}")

        if validator_result.get("regulation_interpretation"):
            log(f"Regulation interpretation: {validator_result['regulation_interpretation']}")

        if validator_result.get("applicability_explanation"):
            log(f"Applicability: {validator_result['applicability_explanation']}")

        if validator_result.get("justification"):
            log(f"Justification: {validator_result['justification']}")

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
            "case_id": case_id,
            "run_id": run_id,
            "iteration": iteration,
            "syntax_valid": syntax_result.get("syntax_valid"),
            "ship_execution_ok": ship_result.get("execution_ok"),
            "ship_conforms": ship_result.get("conforms"),
            "actual_outcome": actual_outcome,
            "expected_outcome": validator_result.get("expected_outcome"),
            "ship_behavior_correct": validator_result.get("ship_behavior_correct"),
            "reason_alignment": validator_result.get("reason_alignment"),
            "applicability_handled_correctly": validator_result.get("applicability_handled_correctly"),
            "facts_used": validator_result.get("facts_used"),
            "regulation_interpretation": validator_result.get("regulation_interpretation"),
            "applicability_explanation": validator_result.get("applicability_explanation"),
            "justification": validator_result.get("justification"),
            "validator_decision": validator_result.get("decision"),
            "validator_confidence": validator_result.get("confidence"),
            "accepted": accepted,
        }
        write_json(run_dir / f"{iter_tag}_summary.json", iteration_summary)

        last_validator_result = validator_result
        last_ship_result = ship_result
        last_syntax_result = syntax_result
        last_actual_outcome = actual_outcome

        if accepted:
            final_summary["accepted"] = True
            final_summary["accepted_iteration"] = iteration
            final_summary["final_validator_decision"] = validator_result.get("decision")
            write_json(run_dir / "final_summary.json", final_summary)
            log(f"Accepted at iteration {iteration}")
            log(f"Results saved to: {run_dir.relative_to(project_root)}")

            return {
                "case_id": case_id,
                "input_filename": input_path.name,
                "input_relative_path": str(input_path.relative_to(input_dir)),
                "category_folder": str(input_path.parent.relative_to(input_dir)),
                "run_id": run_id,
                "status": "completed_accepted",
                "accepted": True,
                "accepted_iteration": iteration,
                "validator_decision": validator_result.get("decision"),
                "validator_confidence": validator_result.get("confidence"),
                "ship_conforms": ship_result.get("conforms"),
                "actual_outcome": actual_outcome,
                "expected_outcome": validator_result.get("expected_outcome"),
                "ship_behavior_correct": validator_result.get("ship_behavior_correct"),
                "reason_alignment": validator_result.get("reason_alignment"),
                "applicability_handled_correctly": validator_result.get("applicability_handled_correctly"),
                "syntax_valid": syntax_result.get("syntax_valid"),
                "ship_execution_ok": ship_result.get("execution_ok"),
                "issues_count": len(validator_result.get("issues", [])),
                "run_folder": str(run_dir.relative_to(project_root)),
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
    write_json(run_dir / "final_summary.json", final_summary)
    log(f"Stopped after {MAX_ITERATIONS} iterations without acceptance")
    log(f"Results saved to: {run_dir.relative_to(project_root)}")

    return {
        "case_id": case_id,
        "input_filename": input_path.name,
        "input_relative_path": str(input_path.relative_to(input_dir)),
        "category_folder": str(input_path.parent.relative_to(input_dir)),
        "run_id": run_id,
        "status": "completed_not_accepted",
        "accepted": False,
        "accepted_iteration": None,
        "validator_decision": last_validator_result.get("decision"),
        "validator_confidence": last_validator_result.get("confidence"),
        "ship_conforms": last_ship_result.get("conforms"),
        "actual_outcome": last_actual_outcome,
        "expected_outcome": last_validator_result.get("expected_outcome"),
        "ship_behavior_correct": last_validator_result.get("ship_behavior_correct"),
        "reason_alignment": last_validator_result.get("reason_alignment"),
        "applicability_handled_correctly": last_validator_result.get("applicability_handled_correctly"),
        "syntax_valid": last_syntax_result.get("syntax_valid"),
        "ship_execution_ok": last_ship_result.get("execution_ok"),
        "issues_count": len(last_validator_result.get("issues", [])),
        "run_folder": str(run_dir.relative_to(project_root)),
        "error": "",
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    input_dir = project_root / "data" / "input" / "input_all"

    args = parse_args()

    if args.list:
        cases = list_available_cases(input_dir)
        if not cases:
            print("No cases found.")
            return
        print("\nAvailable cases:")
        for case_id in cases:
            print(f" - {case_id}")
        return

    case_id = args.case.strip() if args.case else choose_case_interactively(input_dir)
    run_case(case_id)


if __name__ == "__main__":
    main()