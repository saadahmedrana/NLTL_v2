from __future__ import annotations

import argparse
import csv
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.pipeline.run_pipeline_experiment_no_validator import (
    RESULT_COLUMNS,
    ExperimentRunConfig,
    run_case_experiment,
)
from src.utils.logger import log


DEFAULT_EXCEL = "data/input/input_all/Input sheet for making jsons.xlsx"

SHEET_TO_FOLDER = {
    "Static": "static",
    "Static Calculation": "static_calculation",
    "Complex": "complex",
    "Dynamic": "dynamic",
}

REQUIRED_MANIFEST_COLUMNS = [
    "id",
    "shape_name",
    "requirement_type",
    "title",
    "pass_test_ship_ttl",
    "pass_expected_outcome",
    "fail_test_ship_ttl",
    "fail_expected_outcome",
]


@dataclass(slots=True)
class ManifestRow:
    sheet_name: str
    category_folder: str
    case_id: str
    shape_name: str
    requirement_type: str
    title: str
    pass_test_ship_ttl: str
    pass_expected_outcome: str
    fail_test_ship_ttl: str
    fail_expected_outcome: str


@dataclass(slots=True)
class ExperimentJob:
    case_id: str
    shape_name: str
    category: str
    requirement_type: str
    title: str
    test_kind: str
    ship_ttl: str
    manifest_expected_outcome: str


def normalize_header(header: object) -> str:
    if header is None:
        return ""
    return " ".join(str(header).strip().lower().replace("\n", " ").split())


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_name(text: str) -> str:
    return " ".join(str(text or "").strip().lower().replace("_", " ").split())


def parse_csv_arg(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def normalize_outcome(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"pass", "fail", "not_applicable", "execution_error", "unknown"}:
        return text
    if text in {"non_conformant", "nonconformant"}:
        return "fail"
    return text or "unknown"


def build_column_map(df: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for col in df.columns:
        mapping[normalize_header(col)] = col
    return mapping


def require_columns(df: pd.DataFrame, required: list[str], sheet_name: str) -> dict[str, str]:
    colmap = build_column_map(df)
    resolved: dict[str, str] = {}
    missing: list[str] = []

    for required_name in required:
        normalized = normalize_header(required_name)
        if normalized not in colmap:
            missing.append(required_name)
        else:
            resolved[required_name] = colmap[normalized]

    if missing:
        raise ValueError(
            f"Sheet '{sheet_name}' is missing required columns: {missing}. "
            f"Available columns: {list(df.columns)}"
        )

    return resolved


def read_manifest_rows(excel_path: Path, allowed_sheets: list[str] | None = None) -> list[ManifestRow]:
    workbook = pd.read_excel(excel_path, sheet_name=None)
    rows: list[ManifestRow] = []

    allowed_sheet_norms = {normalize_name(s) for s in (allowed_sheets or [])}

    for sheet_name, category_folder in SHEET_TO_FOLDER.items():
        if allowed_sheet_norms and normalize_name(sheet_name) not in allowed_sheet_norms:
            continue
        if sheet_name not in workbook:
            continue

        df = workbook[sheet_name].copy()
        df = df.dropna(how="all")
        if df.empty:
            continue

        cols = require_columns(df, REQUIRED_MANIFEST_COLUMNS, sheet_name)

        for _, row in df.iterrows():
            case_id = clean_text(row.get(cols["id"], ""))
            if not case_id:
                continue

            rows.append(
                ManifestRow(
                    sheet_name=sheet_name,
                    category_folder=category_folder,
                    case_id=case_id,
                    shape_name=clean_text(row.get(cols["shape_name"], "")),
                    requirement_type=clean_text(row.get(cols["requirement_type"], "")),
                    title=clean_text(row.get(cols["title"], "")),
                    pass_test_ship_ttl=clean_text(row.get(cols["pass_test_ship_ttl"], "")),
                    pass_expected_outcome=normalize_outcome(row.get(cols["pass_expected_outcome"], "")),
                    fail_test_ship_ttl=clean_text(row.get(cols["fail_test_ship_ttl"], "")),
                    fail_expected_outcome=normalize_outcome(row.get(cols["fail_expected_outcome"], "")),
                )
            )

    return rows


def build_jobs(rows: list[ManifestRow]) -> list[ExperimentJob]:
    jobs: list[ExperimentJob] = []

    for row in rows:
        # Match the current experiment design: one representative feedback ship per case.
        # The no-validator ablation changes only the pipeline behavior, not the dataset split.
        ship_ttl = row.pass_test_ship_ttl or "master_ship_1.ttl"

        jobs.append(
            ExperimentJob(
                case_id=row.case_id,
                shape_name=row.shape_name,
                category=row.category_folder,
                requirement_type=row.requirement_type,
                title=row.title,
                test_kind="feedback_ship",
                ship_ttl=ship_ttl,
                manifest_expected_outcome="unknown",
            )
        )

    return jobs


def filter_jobs(
    jobs: list[ExperimentJob],
    sheets: list[str] | None = None,
    categories: list[str] | None = None,
    case_ids: list[str] | None = None,
    shape_names: list[str] | None = None,
    manifest_rows_by_case: dict[str, ManifestRow] | None = None,
) -> list[ExperimentJob]:
    sheet_norms = {normalize_name(x) for x in (sheets or [])}
    category_norms = {normalize_name(x) for x in (categories or [])}
    case_id_set = {x.strip() for x in (case_ids or []) if x.strip()}
    shape_name_norms = {normalize_name(x) for x in (shape_names or [])}

    filtered: list[ExperimentJob] = []

    for job in jobs:
        manifest_row = manifest_rows_by_case[job.case_id] if manifest_rows_by_case else None

        if sheet_norms and manifest_row and normalize_name(manifest_row.sheet_name) not in sheet_norms:
            continue

        if category_norms and normalize_name(job.category) not in category_norms:
            continue

        if case_id_set and job.case_id not in case_id_set:
            continue

        if shape_name_norms and normalize_name(job.shape_name) not in shape_name_norms:
            continue

        filtered.append(job)

    return filtered


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in RESULT_COLUMNS})


def write_results_xlsx(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.reindex(columns=RESULT_COLUMNS)
    else:
        df = pd.DataFrame(columns=RESULT_COLUMNS)
    df.to_excel(path, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", type=str, default=DEFAULT_EXCEL)
    parser.add_argument("--models", type=str, required=True, help="Comma-separated model names")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--artifact-mode", type=str, default="summary_only", choices=["full", "summary_only", "none"])
    parser.add_argument("--experiment-id", type=str, default="")
    parser.add_argument("--sheets", type=str, default="")
    parser.add_argument("--categories", type=str, default="")
    parser.add_argument("--case-ids", type=str, default="")
    parser.add_argument("--shape-names", type=str, default="")
    return parser.parse_args()


def is_transient_error_text(text: object) -> bool:
    lowered = str(text or "").lower()
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
        "transient api failure",
    )
    return any(marker in lowered for marker in transient_markers)


def is_auth_error_text(text: object) -> bool:
    lowered = str(text or "").lower()
    return (
        "missing subscription key" in lowered
        or "access denied" in lowered
        or "error 401" in lowered
        or "status 401" in lowered
        or "error 403" in lowered
        or "status 403" in lowered
    )


def cleanup_failed_run_folder(project_root: Path, run_folder: object) -> None:
    text = str(run_folder or "").strip()
    if not text or "deleted temp artifacts" in text:
        return

    path = Path(text)
    if not path.is_absolute():
        path = project_root / path

    try:
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
    except Exception as exc:
        log(f"Warning: could not clean failed transient run folder {path}: {exc}")


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    args = parse_args()

    excel_path = Path(args.excel)
    if not excel_path.is_absolute():
        excel_path = project_root / excel_path

    if not excel_path.exists():
        raise FileNotFoundError(f"Excel manifest not found: {excel_path}")

    models = parse_csv_arg(args.models)
    if not models:
        raise ValueError("At least one model must be provided via --models")

    if args.repeats < 1:
        raise ValueError("--repeats must be >= 1")

    experiment_id = args.experiment_id.strip() or f"abl_no_validator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    experiment_root = project_root / "data" / "output" / "experiments" / experiment_id
    results_csv = experiment_root / "results.csv"
    results_xlsx = experiment_root / "results.xlsx"

    selected_sheets = parse_csv_arg(args.sheets)
    selected_categories = parse_csv_arg(args.categories)
    selected_case_ids = parse_csv_arg(args.case_ids)
    selected_shape_names = parse_csv_arg(args.shape_names)

    manifest_rows = read_manifest_rows(excel_path, allowed_sheets=selected_sheets or None)
    if not manifest_rows:
        raise ValueError("No manifest rows found after sheet filtering.")

    manifest_rows_by_case = {row.case_id: row for row in manifest_rows}
    jobs = build_jobs(manifest_rows)
    jobs = filter_jobs(
        jobs,
        sheets=selected_sheets or None,
        categories=selected_categories or None,
        case_ids=selected_case_ids or None,
        shape_names=selected_shape_names or None,
        manifest_rows_by_case=manifest_rows_by_case,
    )

    if not jobs:
        raise ValueError("No jobs remain after applying filters.")

    log(f"NO-VALIDATOR ablation experiment id: {experiment_id}")
    log(f"Excel: {excel_path}")
    log(f"Models: {models}")
    log(f"Repeats: {args.repeats}")
    log("Validator: DISABLED")
    log("Generator calls per case: 1")
    log(f"Artifact mode: {args.artifact_mode}")
    log(f"Jobs: {len(jobs)}")

    rows: list[dict[str, Any]] = []
    total_runs = len(models) * args.repeats * len(jobs)
    run_counter = 0

    for model_name in models:
        for repeat_index in range(1, args.repeats + 1):
            for job in jobs:
                run_counter += 1
                log("")
                log(
                    f"### No-validator run {run_counter}/{total_runs}: "
                    f"{job.case_id} | {job.test_kind} | model={model_name} | repeat={repeat_index}"
                )

                config = ExperimentRunConfig(
                    case_id=job.case_id,
                    ship_path=job.ship_ttl,
                    test_kind=job.test_kind,
                    manifest_expected_outcome=job.manifest_expected_outcome,
                    model_name=model_name,
                    repeat_index=repeat_index,
                    experiment_id=experiment_id,
                    max_iterations=1,
                    artifact_mode=args.artifact_mode,
                    shape_name=job.shape_name,
                    category=job.category,
                    requirement_type=job.requirement_type,
                    title=job.title,
                )

                case_attempt = 0
                while True:
                    case_attempt += 1
                    row = run_case_experiment(config)

                    if row.get("status") == "crashed" and is_auth_error_text(row.get("error")):
                        rows.append(row)
                        write_results_csv(results_csv, rows)
                        write_results_xlsx(results_xlsx, rows)
                        raise RuntimeError(
                            "Authentication/API configuration error. Stopping instead of filling "
                            f"the CSV with crashed rows. Last error: {row.get('error')}"
                        )

                    if row.get("status") == "crashed" and is_transient_error_text(row.get("error")):
                        cleanup_failed_run_folder(project_root, row.get("run_folder"))
                        delay = min(60 * case_attempt, 300)
                        log(
                            f"Transient API crash for {job.case_id}; retrying same example "
                            f"without writing a CSV/XLSX row (attempt {case_attempt}, wait {delay}s)."
                        )
                        time.sleep(delay)
                        continue

                    break

                rows.append(row)

                write_results_csv(results_csv, rows)
                write_results_xlsx(results_xlsx, rows)

                log(f"Updated CSV: {results_csv.relative_to(project_root)}")
                log(f"Updated XLSX: {results_xlsx.relative_to(project_root)}")

    log("")
    log("No-validator ablation run completed.")
    log(f"Final CSV: {results_csv.relative_to(project_root)}")
    log(f"Final XLSX: {results_xlsx.relative_to(project_root)}")


if __name__ == "__main__":
    main()
