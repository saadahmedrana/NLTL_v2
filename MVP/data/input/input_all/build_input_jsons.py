from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


# =========================
# CONFIG
# =========================

EXCEL_FILENAME = "data/input/input_all/Input sheet for making jsons.xlsx"
OUTPUT_ROOT = Path(".")

SHEET_TO_FOLDER = {
    "Static": "static",
    "Static Calculation": "static_calculation",
    "Complex": "complex",
    "Dynamic": "dynamic",
    "meta_optional": "meta",
}

REQUIRED_FIELDS = [
    "id",
    "category",
    "requirement_type",
    "title",
    "regulation_source",
    "regulation_text",
]


# =========================
# HELPERS
# =========================

def normalize_header(header: object) -> str:
    if header is None:
        return ""
    text = str(header).strip().lower()
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def build_column_map(df: pd.DataFrame) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for col in df.columns:
        mapping[normalize_header(col)] = col
    return mapping


def find_column(colmap: Dict[str, str], candidates: List[str]) -> Optional[str]:
    for cand in candidates:
        norm = normalize_header(cand)
        if norm in colmap:
            return colmap[norm]
    return None


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def row_to_payload(
    row: pd.Series,
    columns: Dict[str, str],
    sheet_name: str,
) -> Optional[Dict[str, str]]:
    id_col = columns["id"]
    case_id = clean_text(row.get(id_col, ""))

    if not case_id:
        return None

    category_col = columns["category"]
    category_value = ""
    if category_col != "__sheet_fallback__":
        category_value = clean_text(row.get(category_col, ""))

    payload = {
        "id": case_id,
        "category": category_value or sheet_name,
        "requirement_type": clean_text(row.get(columns["requirement_type"], "")),
        "title": clean_text(row.get(columns["title"], "")),
        "regulation_source": clean_text(row.get(columns["regulation_source"], "")),
        "regulation_text": clean_text(row.get(columns["regulation_text"], "")),
    }

    return payload


def validate_payload(payload: Dict[str, str], sheet_name: str, row_number: int) -> List[str]:
    errors: List[str] = []
    for field in REQUIRED_FIELDS:
        if not payload.get(field):
            errors.append(f"[{sheet_name}] row {row_number}: missing '{field}'")
    return errors


# =========================
# MAIN
# =========================

def main() -> None:
    excel_path = Path(EXCEL_FILENAME)

    if not excel_path.exists():
        raise FileNotFoundError(
            f"Could not find Excel file: {excel_path.resolve()}\n"
            f"Put this script in the same folder as '{EXCEL_FILENAME}' or update EXCEL_FILENAME."
        )

    workbook = pd.read_excel(excel_path, sheet_name=None)

    all_errors: List[str] = []
    files_written = 0

    for sheet_name, out_folder_name in SHEET_TO_FOLDER.items():
        if sheet_name not in workbook:
            print(f"Skipping missing sheet: {sheet_name}")
            continue

        df = workbook[sheet_name].copy()
        df = df.dropna(how="all")

        if df.empty:
            print(f"Skipping empty sheet: {sheet_name}")
            continue

        colmap = build_column_map(df)

        id_col = find_column(colmap, ["id"])
        category_col = find_column(colmap, ["category"])
        req_type_col = find_column(colmap, ["requirement_type", "requirement type"])
        title_col = find_column(colmap, ["title"])

        # Here is the important fix:
        reg_source_col = find_column(colmap, [
            "regulation_source",
            "regulation source",
            "filename"
        ])

        reg_text_col = find_column(colmap, ["regulation_text", "regulation text"])

        missing_headers = []
        if not id_col:
            missing_headers.append("id")
        if not req_type_col:
            missing_headers.append("requirement_type")
        if not title_col:
            missing_headers.append("title")
        if not reg_source_col:
            missing_headers.append("regulation_source (or filename)")
        if not reg_text_col:
            missing_headers.append("regulation_text")

        if not category_col:
            category_col = "__sheet_fallback__"

        if missing_headers:
            print(f"\nSheet '{sheet_name}' is missing required headers: {missing_headers}")
            print("Available headers:", list(df.columns))
            continue

        columns = {
            "id": id_col,
            "category": category_col,
            "requirement_type": req_type_col,
            "title": title_col,
            "regulation_source": reg_source_col,
            "regulation_text": reg_text_col,
        }

        out_dir = OUTPUT_ROOT / out_folder_name
        ensure_output_dir(out_dir)

        for excel_row_idx, (_, row) in enumerate(df.iterrows(), start=2):
            payload = row_to_payload(row, columns, sheet_name)
            if payload is None:
                continue

            errors = validate_payload(payload, sheet_name, excel_row_idx)
            if errors:
                all_errors.extend(errors)
                continue

            filename = f"{payload['id']}.json"
            out_path = out_dir / filename

            with out_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            files_written += 1

    print(f"\nDone. Wrote {files_written} JSON file(s).")

    if all_errors:
        print("\nValidation issues found:")
        for err in all_errors:
            print(" -", err)
    else:
        print("No validation errors.")


if __name__ == "__main__":
    main()