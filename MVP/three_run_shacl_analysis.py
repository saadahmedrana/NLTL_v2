#!/usr/bin/env python3
"""
Full manual-evaluation tracker analysis.

This script reads Tracker.xlsx and analyzes all manually evaluated sheets:
  - Run1
  - Run2  -> displayed as "Reference run (Run 2)"
  - Run3  -> displayed as "Independent run 2"
  - With Ship context
  - Generator only_no_context

It is designed for thesis reporting:
  - clear reporting names
  - PNG figures only
  - simple CSV / Markdown / LaTeX tables
  - no complicated plot types
  - output-rate and accuracy among produced outputs
  - category-level accuracy among produced outputs
  - problem-category distribution from comments
  - comparison against the reference run
  - similarity of independent runs against the reference run

Install:
  pip install pandas numpy matplotlib openpyxl rapidfuzz rdflib

Run:
  python tracker_full_evaluation_analysis.py
"""

from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

try:
    from rapidfuzz.distance import Levenshtein
    HAS_RAPIDFUZZ = True
except Exception:
    import difflib
    HAS_RAPIDFUZZ = False

try:
    from rdflib import Graph
    from rdflib.compare import graph_diff, to_isomorphic
    HAS_RDFLIB = True
except Exception:
    HAS_RDFLIB = False


# =============================================================================
# 1. CONFIGURATION
# =============================================================================

OUTPUT_PARENT = Path(
    "/Users/sadisfaction570/Desktop/MASTER THESIS PIPELINE/thesis_mvp/"
    "data/output/experiments/FINALK RESUTLS"
)

TRACKER_XLSX = OUTPUT_PARENT / "Tracker.xlsx"

PROJECT_ROOT = Path("/Users/sadisfaction570/Desktop/MASTER THESIS PIPELINE/thesis_mvp")
FINAL_SHACL_FILENAME = "final_generated_shacl.ttl"

# CSV files are used only for locating generated SHACL files for similarity plots.
# The manual accuracy statistics still come from Tracker.xlsx.
RUN_CSVS_FOR_SIMILARITY = {
    "Independent run 1": OUTPUT_PARENT / "run1.csv",
    "Reference run (Run 2)": OUTPUT_PARENT / "results2.csv",
    "Independent run 2": OUTPUT_PARENT / "run3.csv",
}

REFERENCE_SIMILARITY_NAME = "Reference run (Run 2)"

OUTPUT_DIR = OUTPUT_PARENT / "tracker_full_evaluation_analysis"
TABLE_DIR = OUTPUT_DIR / "tables"
FIGURE_DIR = OUTPUT_DIR / "figures"

TOTAL_CASES_EXPECTED = 90
DPI = 220

# The script will search for these sheet names case-insensitively.
# reporting_name is what appears in tables/figures.
METHOD_SPECS = [
    {
        "key": "run1",
        "reporting_name": "Independent run 1",
        "sheet_aliases": ["Run1", "Run 1", "run1"],
    },
    {
        "key": "run2_reference",
        "reporting_name": "Reference run (Run 2)",
        "sheet_aliases": ["Run2", "Run 2", "results2", "Reference run", "Main run"],
    },
    {
        "key": "run3",
        "reporting_name": "Independent run 2",
        "sheet_aliases": ["Run3", "Run 3", "run3"],
    },
    {
        "key": "with_ship_context",
        "reporting_name": "Generator + ship context",
        "sheet_aliases": ["With Ship context", "With ship context", "Ship context", "with ship context"],
    },
    {
        "key": "generator_only_no_context",
        "reporting_name": "Generator only (no context)",
        "sheet_aliases": ["Generator only_no_context", "Generator only no context", "Generator only", "No context"],
    },
]

REFERENCE_METHOD_KEY = "run2_reference"

CATEGORY_ORDER = ["static", "static_calculation", "complex", "dynamic", "unknown"]


# =============================================================================
# 2. GENERAL HELPERS
# =============================================================================

def ensure_dirs() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    # Remove old figures that this newer version intentionally no longer creates.
    for old_name in ["output_rate_vs_accuracy.png", "output_rate_accuracy_tradeoff.png"]:
        old_path = FIGURE_DIR / old_name
        if old_path.exists():
            old_path.unlink()


def save_png(fig: plt.Figure, filename: str) -> None:
    fig.savefig(FIGURE_DIR / f"{filename}.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def style_axis(ax: plt.Axes, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def legend_below(fig: plt.Figure, ax: plt.Axes, ncol: int = 3, bottom: float = 0.28) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        fig.legend(
            handles,
            labels,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.015),
            ncol=ncol,
            frameon=False,
            fontsize=9,
        )
        fig.subplots_adjust(bottom=bottom)


def wrap_label(value: str, width: int = 18) -> str:
    """Wrap long tick labels so figure text does not overlap."""
    return "\n".join(textwrap.wrap(str(value), width=width, break_long_words=False))
def wrap_labels(values: Iterable[str], width: int = 18) -> List[str]:
    return [wrap_label(v, width=width) for v in values]


def normalize_text(value) -> str:
    return str(value).strip() if not pd.isna(value) else ""


def normalize_col_name(col) -> str:
    return str(col).strip().replace(" ", "_").replace("-", "_").lower()


def normalize_sheet_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def pct(x: float) -> str:
    if pd.isna(x):
        return ""
    return f"{100 * x:.1f}%"


def fmt_float(x: float, digits: int = 3) -> str:
    if pd.isna(x):
        return ""
    return f"{x:.{digits}f}"


def ordered_categories(values: Iterable[str]) -> List[str]:
    available = {str(v) for v in values if pd.notna(v)}
    ordered = [c for c in CATEGORY_ORDER if c in available]
    return ordered + sorted(available - set(ordered))


def latex_escape(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    bs = chr(92)
    replacements = {
        bs: bs + "textbackslash{}",
        "&": bs + "&",
        "%": bs + "%",
        "$": bs + "$",
        "#": bs + "#",
        "_": bs + "_",
        "{": bs + "{",
        "}": bs + "}",
        "~": bs + "textasciitilde{}",
        "^": bs + "textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def dataframe_to_simple_markdown(df: pd.DataFrame, index: bool = False) -> str:
    out = df.copy()
    if index:
        out = out.reset_index()
    cols = list(out.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |"]
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for _, row in out.iterrows():
        vals = [str(row[c]) if not pd.isna(row[c]) else "" for c in cols]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def dataframe_to_simple_latex(df: pd.DataFrame, index: bool = False) -> str:
    out = df.copy()
    if index:
        out = out.reset_index()
    cols = list(out.columns)
    bs = chr(92)
    alignment = "l" * len(cols)
    lines = []
    lines.append(bs + "begin{tabular}{" + alignment + "}")
    lines.append(bs + "hline")
    lines.append(" & ".join(latex_escape(c) for c in cols) + " " + bs + bs)
    lines.append(bs + "hline")
    for _, row in out.iterrows():
        vals = [latex_escape(row[c]) for c in cols]
        lines.append(" & ".join(vals) + " " + bs + bs)
    lines.append(bs + "hline")
    lines.append(bs + "end{tabular}")
    lines.append("")
    return "\n".join(lines)


def export_table(df: pd.DataFrame, name: str, index: bool = False) -> None:
    df.to_csv(TABLE_DIR / f"{name}.csv", index=index)
    with open(TABLE_DIR / f"{name}.md", "w", encoding="utf-8") as f:
        f.write(dataframe_to_simple_markdown(df, index=index))
    with open(TABLE_DIR / f"{name}.tex", "w", encoding="utf-8") as f:
        f.write(dataframe_to_simple_latex(df, index=index))


def find_sheet(workbook_sheets: List[str], aliases: List[str]) -> Optional[str]:
    normalized_map = {normalize_sheet_name(s): s for s in workbook_sheets}
    for alias in aliases:
        norm_alias = normalize_sheet_name(alias)
        if norm_alias in normalized_map:
            return normalized_map[norm_alias]
    # More forgiving contains match.
    for alias in aliases:
        norm_alias = normalize_sheet_name(alias)
        for norm_sheet, original in normalized_map.items():
            if norm_alias in norm_sheet or norm_sheet in norm_alias:
                return original
    return None


# =============================================================================
# 3. NORMALIZATION AND ISSUE CLASSIFICATION
# =============================================================================

def normalize_correct(value) -> Optional[int]:
    """Correct Code: 1 = correct, 0 = incorrect, blank = no produced/evaluated code."""
    if pd.isna(value):
        return None
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "correct", "good", "pass"}:
            return 1
        if v in {"0", "false", "no", "n", "incorrect", "bad", "fail"}:
            return 0
        return None
    try:
        iv = int(value)
        if iv in {0, 1}:
            return iv
    except Exception:
        return None
    return None


def case_to_category(case_id: str) -> str:
    cid = str(case_id).strip().lower()
    if "staticcalculation" in cid or "static_calculation" in cid or "static calculation" in cid:
        return "static_calculation"
    if "_static_" in cid or re.match(r"^\d+_static_", cid):
        return "static"
    if "_complex_" in cid or re.match(r"^\d+_complex_", cid):
        return "complex"
    if "_dynamic_" in cid or re.match(r"^\d+_dynamic_", cid):
        return "dynamic"
    return "unknown"


def extract_main_issue_type(comment: str) -> Optional[str]:
    text = str(comment or "")
    m = re.search(r"main_issue_type\s*:\s*([^;\n]+)", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip().lower().replace(" ", "_")
    return None


def broad_issue_category(correct_code: Optional[int], comment: str) -> str:
    if correct_code == 1:
        return "Correct / acceptable"

    text = str(comment or "").lower()
    main_issue = extract_main_issue_type(text)

    if main_issue in {"syntax_problem", "syntax", "execution_error", "invalid_sparql", "invalid_turtle"}:
        return "Syntax or execution problem"
    if main_issue in {"wrong_path", "wrong_target", "wrong_property", "wrong_prefix", "wrong_rdf_path"}:
        return "Wrong RDF path or target"
    if main_issue in {"incomplete_logic", "missing_logic", "no_comparison", "partial", "too_weak"}:
        return "Incomplete validation logic"
    if main_issue in {"missing_edge_case", "applicability", "false_pass", "loophole"}:
        return "Applicability or edge-case gap"
    if main_issue in {"wrong_formula", "formula_error", "math_error", "wrong_table_value", "calculation_error"}:
        return "Formula/table calculation problem"

    if any(k in text for k in ["syntax", "invalid", "not executable", "parse", "missing prefix", "sparql error"]):
        return "Syntax or execution problem"
    if any(k in text for k in ["wrong path", "wrong rdf", "wrong target", "wrong property", "invented", "nonexistent", "never binds", "does not match model"]):
        return "Wrong RDF path or target"
    if any(k in text for k in ["does not validate", "doesn't validate", "only checks", "never compares", "no comparison", "incomplete", "too weak", "missing constraint"]):
        return "Incomplete validation logic"
    if any(k in text for k in ["edge case", "false pass", "falsely pass", "applicability", "does not apply", "missing value"]):
        return "Applicability or edge-case gap"
    if any(k in text for k in ["formula", "calculation", "recalculate", "table", "threshold", "coefficient", "wrong value"]):
        return "Formula/table calculation problem"

    if correct_code == 0:
        return "Other / manual review"
    return "No output / not evaluated"


# =============================================================================
# 4. LOAD TRACKER
# =============================================================================

def load_tracker_sheet(excel_path: Path, sheet_name: str, spec: Dict) -> pd.DataFrame:
    """
    Load one tracker sheet.

    Supports both formats:
      A) header row: case_number | correct_code | more_comments
      B) no header row: first column = case_id, second = correct_code, third+ = comments

    Your Run1 sheet appears to be format B, because pandas read the first data row
    as column names: ['02_static_cmu_minimum', '1'].
    """
    raw = pd.read_excel(excel_path, sheet_name=sheet_name)
    raw.columns = [normalize_col_name(c) for c in raw.columns]

    case_col_candidates = ["case_number", "case", "case_id", "input_filename"]
    correct_col_candidates = ["correct_code", "correct", "is_correct", "manual_correct"]
    comment_col_candidates = ["more_comments", "comments", "comment", "notes", "manual_notes"]

    case_col = next((c for c in case_col_candidates if c in raw.columns), None)
    correct_col = next((c for c in correct_col_candidates if c in raw.columns), None)
    comment_col = next((c for c in comment_col_candidates if c in raw.columns), None)

    # Fallback for sheets without headers.
    if case_col is None or correct_col is None:
        raw = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
        if raw.shape[1] < 2:
            raise ValueError(
                f"Sheet '{sheet_name}' needs at least two columns: case_id and correct_code. "
                f"Found shape={raw.shape}"
            )

        raw = raw.dropna(how="all").copy()
        raw = raw.rename(columns={0: "case_id", 1: "correct_code"})

        if raw.shape[1] >= 3:
            comment_cols = [c for c in raw.columns if c not in {"case_id", "correct_code"}]
            raw["more_comments"] = raw[comment_cols].fillna("").astype(str).agg(" ".join, axis=1).str.strip()
        else:
            raw["more_comments"] = ""

        # Remove header row if header=None accidentally captured it as data.
        if len(raw):
            first_case = str(raw.iloc[0]["case_id"]).strip().lower()
            first_correct = str(raw.iloc[0]["correct_code"]).strip().lower()
            if first_case in {"case", "case_id", "case_number", "input_filename"} or first_correct in {"correct", "correct_code", "is_correct"}:
                raw = raw.iloc[1:].copy()

        case_col = "case_id"
        correct_col = "correct_code"
        comment_col = "more_comments"
    else:
        if comment_col is None:
            raw["more_comments"] = ""
            comment_col = "more_comments"

    out = pd.DataFrame(
        {
            "method_key": spec["key"],
            "method": spec["reporting_name"],
            "sheet_name": sheet_name,
            "case_id": raw[case_col].map(normalize_text),
            "correct_code": raw[correct_col].map(normalize_correct),
            "comment": raw[comment_col].fillna("").astype(str),
        }
    )
    out = out[out["case_id"].str.strip() != ""].copy()
    out = out[out["case_id"].str.lower() != "nan"].copy()
    out["category"] = out["case_id"].map(case_to_category)
    out["produced_code"] = out["correct_code"].notna()
    out["correct"] = out["correct_code"] == 1
    out["incorrect"] = out["correct_code"] == 0
    out["issue_category"] = out.apply(lambda r: broad_issue_category(r["correct_code"], r["comment"]), axis=1)
    return out


def load_tracker(excel_path: Path) -> pd.DataFrame:
    if not excel_path.exists():
        raise FileNotFoundError(f"Tracker not found: {excel_path}")

    xls = pd.ExcelFile(excel_path)
    available_sheets = xls.sheet_names
    print("Available sheets:", available_sheets)

    frames = []
    for spec in METHOD_SPECS:
        sheet = find_sheet(available_sheets, spec["sheet_aliases"])
        if sheet is None:
            print(f"WARNING: no sheet found for {spec['reporting_name']} aliases={spec['sheet_aliases']}")
            continue
        print(f"Using sheet '{sheet}' for {spec['reporting_name']}")
        frames.append(load_tracker_sheet(excel_path, sheet, spec))

    if not frames:
        raise RuntimeError("No matching sheets were found in Tracker.xlsx")

    df = pd.concat(frames, ignore_index=True)

    # Case number is only for plotting, not replacing original case_id.
    unique_cases = sorted(df["case_id"].unique())
    df["case_number"] = df["case_id"].map({case_id: i + 1 for i, case_id in enumerate(unique_cases)})
    return df


# =============================================================================
# 5. TABLES
# =============================================================================

def make_method_summary(df: pd.DataFrame) -> pd.DataFrame:
    total_cases = max(TOTAL_CASES_EXPECTED, df["case_id"].nunique())
    rows = []
    for method_key, g in df.groupby("method_key", sort=False):
        method = g["method"].iloc[0]
        produced = int(g["produced_code"].sum())
        correct = int(g["correct"].sum())
        incorrect = int(g["incorrect"].sum())
        missing = total_cases - produced
        rows.append(
            {
                "Method": method,
                "Total_cases": total_cases,
                "Correct_outputs": correct,
                "Incorrect_outputs": incorrect,
                "Not_produced_or_not_evaluated": missing,
                "Produced_outputs": produced,
                "Output_rate": produced / total_cases if total_cases else np.nan,
                "Accuracy_among_produced": correct / produced if produced else np.nan,
                "Overall_correct_rate": correct / total_cases if total_cases else np.nan,
            }
        )
    return pd.DataFrame(rows)


def make_category_accuracy(df: pd.DataFrame) -> pd.DataFrame:
    all_cases = df[["case_id", "category"]].drop_duplicates()
    total_by_category = all_cases.groupby("category").size().to_dict()

    rows = []
    for (method_key, category), g in df.groupby(["method_key", "category"], sort=False):
        method = g["method"].iloc[0]
        total = int(total_by_category.get(category, len(g)))
        produced = int(g["produced_code"].sum())
        correct = int(g["correct"].sum())
        incorrect = int(g["incorrect"].sum())
        missing = total - produced
        rows.append(
            {
                "Method": method,
                "Category": category,
                "Total_cases": total,
                "Correct_outputs": correct,
                "Incorrect_outputs": incorrect,
                "Not_produced_or_not_evaluated": missing,
                "Produced_outputs": produced,
                "Output_rate": produced / total if total else np.nan,
                "Accuracy_among_produced": correct / produced if produced else np.nan,
                "Overall_correct_rate": correct / total if total else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    out["Category"] = pd.Categorical(out["Category"], categories=ordered_categories(out["Category"]), ordered=True)
    return out.sort_values(["Category", "Method"]).reset_index(drop=True)


def make_case_wide_status(df: pd.DataFrame) -> pd.DataFrame:
    meta = df[["case_id", "case_number", "category"]].drop_duplicates("case_id").sort_values("case_number")
    out = meta.copy()

    for spec in METHOD_SPECS:
        method_key = spec["key"]
        method_df = df[df["method_key"] == method_key].set_index("case_id")
        if method_df.empty:
            continue
        status_col = f"status_{method_key}"
        code_col = f"correct_code_{method_key}"
        out[code_col] = out["case_id"].map(method_df["correct_code"])
        out[status_col] = out[code_col].map({1: "correct", 0: "incorrect"}).fillna("not produced")

    return out


def make_reference_comparison(case_wide: pd.DataFrame) -> pd.DataFrame:
    ref_col = f"correct_code_{REFERENCE_METHOD_KEY}"
    if ref_col not in case_wide.columns:
        return pd.DataFrame()

    rows = []
    for spec in METHOD_SPECS:
        method_key = spec["key"]
        if method_key == REFERENCE_METHOD_KEY:
            continue
        method_col = f"correct_code_{method_key}"
        if method_col not in case_wide.columns:
            continue

        for _, row in case_wide.iterrows():
            ref = row[ref_col]
            other = row[method_col]
            if pd.isna(ref) and pd.isna(other):
                comparison = "both not produced"
            elif ref == 1 and other == 1:
                comparison = "both correct"
            elif ref == 0 and other == 0:
                comparison = "both incorrect"
            elif ref == 0 and other == 1:
                comparison = "improved over reference"
            elif ref == 1 and other == 0:
                comparison = "regressed from reference"
            elif pd.isna(ref) and other == 1:
                comparison = "other correct, reference missing"
            elif pd.isna(ref) and other == 0:
                comparison = "other incorrect, reference missing"
            elif ref == 1 and pd.isna(other):
                comparison = "reference correct, other missing"
            elif ref == 0 and pd.isna(other):
                comparison = "reference incorrect, other missing"
            else:
                comparison = "other"

            rows.append(
                {
                    "Compared_method": spec["reporting_name"],
                    "case_id": row["case_id"],
                    "case_number": row["case_number"],
                    "category": row["category"],
                    "Reference_status": "correct" if ref == 1 else "incorrect" if ref == 0 else "not produced",
                    "Compared_status": "correct" if other == 1 else "incorrect" if other == 0 else "not produced",
                    "Comparison": comparison,
                }
            )
    return pd.DataFrame(rows)


def make_problem_distribution(df: pd.DataFrame) -> pd.DataFrame:
    bad = df[df["incorrect"]].copy()
    if bad.empty:
        return pd.DataFrame(columns=["Method", "Issue_category", "Bad_cases", "Share_of_bad_cases"])
    out = bad.groupby(["method", "issue_category"]).size().reset_index(name="Bad_cases")
    totals = bad.groupby("method").size().rename("Total_bad_cases")
    out = out.merge(totals, on="method", how="left")
    out["Share_of_bad_cases"] = out["Bad_cases"] / out["Total_bad_cases"]
    out = out.rename(columns={"method": "Method", "issue_category": "Issue_category"})
    return out.sort_values(["Method", "Bad_cases"], ascending=[True, False])


def make_pretty(table: pd.DataFrame) -> pd.DataFrame:
    out = table.copy()
    for col in out.columns:
        lower = col.lower()
        if "rate" in lower or "share" in lower or "accuracy" in lower:
            out[col] = out[col].map(pct)
        elif pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda x: fmt_float(x, 3))
    return out


# =============================================================================
# 6. FIGURES
# =============================================================================

def figure_correct_incorrect_missing(method_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    x = np.arange(len(method_summary))

    correct = method_summary["Correct_outputs"].values
    incorrect = method_summary["Incorrect_outputs"].values
    missing = method_summary["Not_produced_or_not_evaluated"].values

    ax.bar(x, correct, label="Correct outputs")
    ax.bar(x, incorrect, bottom=correct, label="Incorrect outputs")
    ax.bar(x, missing, bottom=correct + incorrect, label="Not produced / not evaluated")

    ax.set_xticks(x)
    ax.set_xticklabels(wrap_labels(method_summary["Method"], width=16), rotation=0, ha="center")
    ax.set_ylim(0, TOTAL_CASES_EXPECTED + 5)
    style_axis(ax, "Correct, incorrect, and missing outputs by method", "Method", "Number of cases")
    for i, total in enumerate(correct + incorrect + missing):
        ax.text(i, total + 1, str(int(total)), ha="center", fontsize=8)
    legend_below(fig, ax, ncol=3, bottom=0.30)
    save_png(fig, "correct_incorrect_missing_by_method")


def figure_category_overall_correct_rate(category_accuracy: pd.DataFrame) -> None:
    categories = ordered_categories(category_accuracy["Category"])
    methods = category_accuracy["Method"].drop_duplicates().tolist()

    fig, ax = plt.subplots(figsize=(13.5, 6.2))
    x = np.arange(len(categories))
    width = min(0.16, 0.75 / max(1, len(methods)))

    for idx, method in enumerate(methods):
        sub = category_accuracy[category_accuracy["Method"] == method].set_index("Category").reindex(categories)
        offset = (idx - (len(methods) - 1) / 2) * width
        ax.bar(x + offset, sub["Overall_correct_rate"], width, label=method)

    ax.set_xticks(x)
    ax.set_xticklabels(wrap_labels(categories, width=18), rotation=0, ha="center")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylim(0, 1.05)
    style_axis(ax, "Overall correct rate by requirement category", "Category", "Correct / total cases")
    legend_below(fig, ax, ncol=2, bottom=0.34)
    save_png(fig, "category_overall_correct_rate")


def figure_category_accuracy_among_produced(category_accuracy: pd.DataFrame) -> None:
    categories = ordered_categories(category_accuracy["Category"])
    methods = category_accuracy["Method"].drop_duplicates().tolist()

    fig, ax = plt.subplots(figsize=(13.5, 6.2))
    x = np.arange(len(categories))
    width = min(0.16, 0.75 / max(1, len(methods)))

    for idx, method in enumerate(methods):
        sub = category_accuracy[category_accuracy["Method"] == method].set_index("Category").reindex(categories)
        offset = (idx - (len(methods) - 1) / 2) * width
        ax.bar(x + offset, sub["Accuracy_among_produced"], width, label=method)

    ax.set_xticks(x)
    ax.set_xticklabels(wrap_labels(categories, width=18), rotation=0, ha="center")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylim(0, 1.05)
    style_axis(ax, "Accuracy among produced outputs by requirement category", "Category", "Accuracy among produced")
    legend_below(fig, ax, ncol=2, bottom=0.34)
    save_png(fig, "category_accuracy_among_produced")


def figure_reference_comparison_counts(reference_comparison: pd.DataFrame) -> None:
    if reference_comparison.empty:
        return
    counts = reference_comparison.groupby(["Compared_method", "Comparison"]).size().reset_index(name="Cases")
    comparisons = counts.groupby("Comparison")["Cases"].sum().sort_values(ascending=False).index.tolist()
    methods = counts["Compared_method"].drop_duplicates().tolist()

    fig, ax = plt.subplots(figsize=(13.5, 6.8))
    x = np.arange(len(comparisons))
    width = min(0.18, 0.75 / max(1, len(methods)))

    for idx, method in enumerate(methods):
        sub = counts[counts["Compared_method"] == method].set_index("Comparison").reindex(comparisons).fillna(0)
        offset = (idx - (len(methods) - 1) / 2) * width
        ax.bar(x + offset, sub["Cases"], width, label=method)

    ax.set_xticks(x)
    ax.set_xticklabels(wrap_labels(comparisons, width=20), rotation=0, ha="center")
    style_axis(ax, "Case-level comparison against Reference run (Run 2)", "Comparison type", "Number of cases")
    legend_below(fig, ax, ncol=2, bottom=0.34)
    save_png(fig, "comparison_against_reference_run")


def figure_problem_distribution(problem_dist: pd.DataFrame) -> None:
    if problem_dist.empty:
        return
    issue_order = problem_dist.groupby("Issue_category")["Bad_cases"].sum().sort_values(ascending=False).index.tolist()
    methods = problem_dist["Method"].drop_duplicates().tolist()

    fig, ax = plt.subplots(figsize=(13.5, 6.2))
    x = np.arange(len(issue_order))
    width = min(0.16, 0.75 / max(1, len(methods)))

    for idx, method in enumerate(methods):
        sub = problem_dist[problem_dist["Method"] == method].set_index("Issue_category").reindex(issue_order).fillna(0)
        offset = (idx - (len(methods) - 1) / 2) * width
        ax.bar(x + offset, sub["Bad_cases"], width, label=method)

    ax.set_xticks(x)
    ax.set_xticklabels(wrap_labels(issue_order, width=20), rotation=0, ha="center")
    style_axis(ax, "Broad problem categories among incorrect outputs", "Problem category", "Incorrect outputs")
    legend_below(fig, ax, ncol=2, bottom=0.34)
    save_png(fig, "problem_category_distribution")


# =============================================================================
# 7. MAIN
# =============================================================================

def main() -> None:
    ensure_dirs()

    print("Loading manual evaluation tracker...")
    df = load_tracker(TRACKER_XLSX)
    print(f"Loaded {len(df)} rows across {df['method'].nunique()} methods and {df['case_id'].nunique()} unique cases.")

    print("Building tables...")
    method_summary = make_method_summary(df)
    category_accuracy = make_category_accuracy(df)
    case_wide = make_case_wide_status(df)
    reference_comparison = make_reference_comparison(case_wide)
    problem_dist = make_problem_distribution(df)

    tables = {
        "table_1_method_summary": method_summary,
        "table_2_category_accuracy": category_accuracy,
        "table_3_case_status_wide": case_wide,
        "table_4_comparison_against_reference_run": reference_comparison,
        "table_5_problem_distribution": problem_dist,
    }

    print("Saving tables...")
    for name, table in tables.items():
        export_table(make_pretty(table), name)
        table.to_csv(TABLE_DIR / f"raw_{name}.csv", index=False)

    print("Creating figures...")
    figure_correct_incorrect_missing(method_summary)
    figure_category_overall_correct_rate(category_accuracy)
    figure_category_accuracy_among_produced(category_accuracy)
    figure_reference_comparison_counts(reference_comparison)
    figure_problem_distribution(problem_dist)

    print("\nDone.")
    print(f"Tables:  {TABLE_DIR}")
    print(f"Figures: {FIGURE_DIR}")

    print("\nMethod summary:")
    print(make_pretty(method_summary).to_string(index=False))

    print("\nCategory accuracy:")
    print(make_pretty(category_accuracy).to_string(index=False))

    if not problem_dist.empty:
        print("\nProblem distribution:")
        print(make_pretty(problem_dist).to_string(index=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
