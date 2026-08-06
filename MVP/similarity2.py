#!/usr/bin/env python3
"""
Create two thesis-style similarity scatter figures:

1. Normalized character similarity to base run
2. General word-overlap similarity to base run

Comparison:
- Independent run 1 = run1.csv
- Base run = results2.csv
- Independent run 2 = run3.csv

Each row uses:
    run_folder/final_generated_shacl.ttl

Outputs are saved under:
    FINALK RESUTLS/tracker_similarity_analysis_v2/
"""

from __future__ import annotations

import re
import difflib
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import matplotlib.pyplot as plt


# =============================================================================
# CONFIG
# =============================================================================

PROJECT_ROOT = Path(
    "/Users/sadisfaction570/Desktop/MASTER THESIS PIPELINE/thesis_mvp"
)

OUTPUT_PARENT = PROJECT_ROOT / "data/output/experiments/FINALK RESUTLS"

RUN1_CSV = OUTPUT_PARENT / "run1.csv"
BASE_CSV = OUTPUT_PARENT / "results2.csv"
RUN3_CSV = OUTPUT_PARENT / "run3.csv"

FINAL_SHACL_FILENAME = "final_generated_shacl.ttl"

OUTPUT_DIR = OUTPUT_PARENT / "tracker_similarity_analysis_v2"
TABLE_DIR = OUTPUT_DIR / "tables"
FIGURE_DIR = OUTPUT_DIR / "figures"

DPI = 220


# =============================================================================
# TEXT NORMALIZATION + SIMILARITY
# =============================================================================

def normalize_for_character_similarity(text: str) -> str:
    """
    Keeps the code structure, but removes comments and normalizes whitespace.
    This still captures structural/textual similarity.
    """
    text = re.sub(r"#.*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def normalized_character_similarity(a: str, b: str) -> float:
    """
    Normalized character-level similarity.
    1 = identical, 0 = completely different.

    Uses difflib so no extra package is required.
    """
    a_norm = normalize_for_character_similarity(a)
    b_norm = normalize_for_character_similarity(b)

    if not a_norm and not b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0

    return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()


def general_word_set(text: str) -> set[str]:
    """
    General word overlap.
    This ignores order and position.

    Example:
    If two files use the same words but in different places,
    this metric still gives high similarity.
    """
    text = re.sub(r"#.*", " ", text)
    text = text.lower()

    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_]*", text)

    # Optional tiny stopword removal.
    # Keep code-relevant words like prefix names, variable names, FILTER terms, etc.
    stopwords = {
        "a", "an", "the", "and", "or", "to", "of", "in", "for", "with",
        "is", "are", "be", "as", "by", "on", "this", "that"
    }

    return {w for w in words if len(w) >= 2 and w not in stopwords}


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    """
    Set overlap similarity.
    1 = same words, 0 = no shared words.
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def general_word_overlap_similarity(a: str, b: str) -> float:
    return jaccard_similarity(general_word_set(a), general_word_set(b))


# =============================================================================
# FILE LOADING
# =============================================================================

def ensure_dirs() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)


def case_number_from_case_id(case_id: str) -> Optional[int]:
    """
    Extracts the leading case number:
      13_static_existing_ib_ic_min_power_740 -> 13
    """
    match = re.match(r"^(\d+)", str(case_id).strip())
    if not match:
        return None
    return int(match.group(1))


def resolve_run_folder_path(run_folder_value: str) -> Path:
    """
    CSV run_folder is usually relative to PROJECT_ROOT, e.g.

    data/output/experiments/full_feedback_test_3repeats/runs/...
    """
    p = Path(str(run_folder_value).strip())

    if p.is_absolute():
        return p

    return PROJECT_ROOT / p


def load_outputs_from_csv(csv_path: Path) -> Dict[str, Dict[str, object]]:
    """
    Returns:
      case_id -> {
          case_number,
          text,
          ttl_path,
          status,
          accepted
      }
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    required_cols = ["case_id", "run_folder"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in {csv_path}")

    outputs: Dict[str, Dict[str, object]] = {}

    for _, row in df.iterrows():
        case_id = str(row["case_id"]).strip()
        if not case_id or case_id.lower() == "nan":
            continue

        case_number = case_number_from_case_id(case_id)
        if case_number is None:
            continue

        run_folder = row.get("run_folder")
        if pd.isna(run_folder):
            continue

        run_folder_path = resolve_run_folder_path(str(run_folder))
        ttl_path = run_folder_path / FINAL_SHACL_FILENAME

        if not ttl_path.exists():
            continue

        text = ttl_path.read_text(encoding="utf-8", errors="ignore")

        outputs[case_id] = {
            "case_number": case_number,
            "text": text,
            "ttl_path": str(ttl_path),
            "status": row.get("status", ""),
            "accepted": row.get("accepted", ""),
        }

    return outputs


# =============================================================================
# ANALYSIS
# =============================================================================

def compare_to_base(
    run_label: str,
    run_outputs: Dict[str, Dict[str, object]],
    base_outputs: Dict[str, Dict[str, object]],
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []

    common_cases = sorted(
        set(run_outputs.keys()) & set(base_outputs.keys()),
        key=lambda x: case_number_from_case_id(x) or 999999,
    )

    for case_id in common_cases:
        run_text = str(run_outputs[case_id]["text"])
        base_text = str(base_outputs[case_id]["text"])

        char_sim = normalized_character_similarity(run_text, base_text)
        word_sim = general_word_overlap_similarity(run_text, base_text)

        rows.append(
            {
                "run": run_label,
                "case_id": case_id,
                "case_number": run_outputs[case_id]["case_number"],
                "normalized_character_similarity": char_sim,
                "general_word_overlap_similarity": word_sim,
                "run_ttl_path": run_outputs[case_id]["ttl_path"],
                "base_ttl_path": base_outputs[case_id]["ttl_path"],
                "run_status": run_outputs[case_id]["status"],
                "base_status": base_outputs[case_id]["status"],
                "run_accepted": run_outputs[case_id]["accepted"],
                "base_accepted": base_outputs[case_id]["accepted"],
            }
        )

    return rows


# =============================================================================
# FIGURES
# =============================================================================

def save_similarity_scatter(
    df: pd.DataFrame,
    metric_col: str,
    title: str,
    ylabel: str,
    filename: str,
) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 6.4))

    run1_label = "Independent run 1 (run1.csv) compared to base run (run2.csv)"
    run3_label = "Independent run 2 (run3.csv) compared to base run (run2.csv)"

    run1 = df[df["run"] == run1_label].copy()
    run3 = df[df["run"] == run3_label].copy()

    ax.scatter(
        run1["case_number"],
        run1[metric_col],
        marker="o",
        s=46,
        alpha=0.85,
        label="Independent run 1 (run1.csv) compared to base run (run2.csv)",
    )

    ax.scatter(
        run3["case_number"],
        run3[metric_col],
        marker="^",
        s=52,
        alpha=0.85,
        label="Independent run 2 (run3.csv) compared to base run (run2.csv)",
    )

    ax.set_title(title, fontsize=14, fontweight="bold", pad=14)
    ax.set_xlabel("Case number", fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)

    ax.set_ylim(0, 1.05)
    ax.set_xlim(0, 91)

    ax.set_xticks(list(range(1, 91, 5)))
    ax.grid(axis="y", alpha=0.25)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
        ncol=2,
        frameon=False,
        fontsize=10,
    )

    fig.subplots_adjust(bottom=0.26)
    fig.savefig(FIGURE_DIR / filename, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    ensure_dirs()

    run1_outputs = load_outputs_from_csv(RUN1_CSV)
    base_outputs = load_outputs_from_csv(BASE_CSV)
    run3_outputs = load_outputs_from_csv(RUN3_CSV)

    run1_label = "Independent run 1 (run1.csv) compared to base run (run2.csv)"
    run3_label = "Independent run 2 (run3.csv) compared to base run (run2.csv)"

    rows = []
    rows.extend(compare_to_base(run1_label, run1_outputs, base_outputs))
    rows.extend(compare_to_base(run3_label, run3_outputs, base_outputs))

    if not rows:
        raise RuntimeError(
            "No comparable TTL files were found. "
            "Check that run_folder/final_generated_shacl.ttl exists."
        )

    detail_df = pd.DataFrame(rows)
    detail_df = detail_df.sort_values(["run", "case_number"])

    summary_df = (
        detail_df
        .groupby("run", as_index=False)
        .agg(
            compared_cases=("case_id", "count"),
            mean_normalized_character_similarity=("normalized_character_similarity", "mean"),
            median_normalized_character_similarity=("normalized_character_similarity", "median"),
            mean_general_word_overlap_similarity=("general_word_overlap_similarity", "mean"),
            median_general_word_overlap_similarity=("general_word_overlap_similarity", "median"),
        )
    )

    detail_df.to_csv(TABLE_DIR / "similarity_detail.csv", index=False)
    summary_df.to_csv(TABLE_DIR / "similarity_summary.csv", index=False)

    with open(TABLE_DIR / "similarity_summary.md", "w", encoding="utf-8") as f:
        f.write(summary_df.to_markdown(index=False))

    save_similarity_scatter(
        detail_df,
        metric_col="normalized_character_similarity",
        title="Normalized character similarity to base run by case",
        ylabel="Normalized character similarity",
        filename="normalized_character_similarity_to_base_run_by_case.png",
    )

    save_similarity_scatter(
        detail_df,
        metric_col="general_word_overlap_similarity",
        title="General word-overlap similarity to base run by case",
        ylabel="General word-overlap similarity",
        filename="general_word_overlap_similarity_to_base_run_by_case.png",
    )


if __name__ == "__main__":
    main()