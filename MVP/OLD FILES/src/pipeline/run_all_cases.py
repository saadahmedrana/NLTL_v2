import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from src.pipeline.run_pipeline import list_available_cases, run_case
from src.utils.logger import log


RESULT_COLUMNS = [
    "case_id",
    "input_filename",
    "input_relative_path",
    "category_folder",
    "run_id",
    "status",
    "accepted",
    "accepted_iteration",
    "validator_decision",
    "validator_confidence",
    "ship_conforms",
    "actual_outcome",
    "expected_outcome",
    "ship_behavior_correct",
    "reason_alignment",
    "applicability_handled_correctly",
    "syntax_valid",
    "ship_execution_ok",
    "issues_count",
    "run_folder",
    "error",
]


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in RESULT_COLUMNS})


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    input_dir = project_root / "data" / "input" / "input_all" / "static_calculation"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = project_root / "data" / "output" / "batch_runs" / f"batch_{timestamp}"
    results_csv = batch_dir / "results.csv"

    cases = list_available_cases(input_dir)
    if not cases:
        log("No cases found.")
        return

    log(f"Found {len(cases)} case(s).")
    log(f"Batch output folder: {batch_dir.relative_to(project_root)}")

    rows: list[dict[str, Any]] = []

    for idx, case_id in enumerate(cases, start=1):
        log("")
        log(f"### Batch case {idx}/{len(cases)}: {case_id}")

        try:
            row = run_case(case_id)
        except Exception as exc:
            row = {
                "case_id": case_id,
                "input_filename": f"{case_id}.json",
                "input_relative_path": "",
                "category_folder": "",
                "run_id": "",
                "status": "crashed",
                "accepted": False,
                "accepted_iteration": None,
                "validator_decision": "",
                "validator_confidence": "",
                "ship_conforms": "",
                "actual_outcome": "",
                "expected_outcome": "",
                "ship_behavior_correct": "",
                "reason_alignment": "",
                "applicability_handled_correctly": "",
                "syntax_valid": "",
                "ship_execution_ok": "",
                "issues_count": "",
                "run_folder": "",
                "error": str(exc),
            }
            log(f"Case crashed: {case_id}")
            log(f"Error: {exc}")

        rows.append(row)
        write_results_csv(results_csv, rows)
        log(f"Batch CSV updated: {results_csv.relative_to(project_root)}")

    log("")
    log("Batch run completed.")
    log(f"Final CSV: {results_csv.relative_to(project_root)}")


if __name__ == "__main__":
    main()