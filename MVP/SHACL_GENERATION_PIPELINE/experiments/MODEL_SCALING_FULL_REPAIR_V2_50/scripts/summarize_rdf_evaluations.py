#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from rdf_evaluation_common import FINAL_CASES, MODES, MODELS, SMOKE_CASES, output_directory


METRICS = (
    "tp", "tn", "fp_false_accept", "fn_false_reject", "correct_cases", "total_cases",
    "end_to_end_accuracy", "executable_accuracy", "precision", "recall", "specificity", "f1",
    "artifact_coverage", "no_verdict_count", "exact_requirement_success_count",
    "exact_requirement_total", "exact_requirement_success_rate",
)


def load_complete(scope: str, mode: str, model: str) -> dict[str, Any]:
    output = output_directory(EXPERIMENT, scope, mode, model)
    manifest_path = output / "run_manifest.json"
    summary_path = output / "summary.json"
    if not manifest_path.is_file() or not summary_path.is_file():
        raise RuntimeError(f"Evaluation output is incomplete: {scope}/{mode}/{model}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    expected = SMOKE_CASES if scope == "smoke" else FINAL_CASES
    if manifest.get("status") != "COMPLETE" or summary.get("total_cases") != expected:
        raise RuntimeError(f"Evaluation did not complete with {expected} rows: {scope}/{mode}/{model}")
    return summary


def write_workbook(path: Path, rows: list[dict[str, Any]], title: str) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "comparison"
    headers = ["scope", "evaluation_mode", "model", "model_id", *METRICS]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([row.get(header) for header in headers])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    sheet.column_dimensions["A"].width = 12
    sheet.column_dimensions["B"].width = 24
    sheet.column_dimensions["C"].width = 12
    sheet.column_dimensions["D"].width = 30
    notes = workbook.create_sheet("provenance")
    notes.append(["title", title])
    notes.append(["source", "Completed immutable RDF evaluation summaries"])
    notes.append(["modes", ", ".join(MODES)])
    notes.append(["models", ", ".join(MODELS)])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    workbook.save(temporary)
    temporary.replace(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    all_rows: list[dict[str, Any]] = []
    for scope in ("smoke", "final"):
        for mode in MODES:
            group = [load_complete(scope, mode, model) for model in MODELS]
            all_rows.extend(group)
            directory = output_directory(EXPERIMENT, scope, mode, MODELS[0]).parent
            write_json(directory / "combined_summary.json", {"scope": scope, "evaluation_mode": mode, "models": group})
            write_workbook(directory / "comparison.xlsx", group, f"{scope} / {mode}")
    root = EXPERIMENT / "OUTPUTS/RDF_EVALUATION"
    write_json(root / "combined_summary.json", {"evaluations": all_rows})
    write_workbook(root / "comparison.xlsx", all_rows, "FULL_REPAIR_V2 model-scaling RDF comparison")
    print(json.dumps({"status": "COMPLETE", "evaluations": len(all_rows), "comparison": str(root / "comparison.xlsx")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
