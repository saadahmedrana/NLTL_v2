#!/usr/bin/env python3
"""Create the three manuscript figures from an existing offline report.

This program only reads saved reporting files. It does not execute SHACL,
regenerate constraints, call model APIs, alter RDF, relabel cases, or edit the
source workbook/report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import stat
import sys
import tempfile
import textwrap
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "nltl-matplotlib-cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np
import pandas as pd
from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
POLICY = "PROPOSED_RDF_EDIT_SENSITIVITY"
REQUIRED_INPUTS = (
    "summary_results.csv",
    "breakdowns.csv",
    "policy_case_outcomes.csv",
    "requirement_scores.csv",
    "manual_summary.csv",
    "referenced_files.csv",
)
WORKFLOW_ORDER = ("SINGLESHOT", "NO_SEMANTIC", "FULL_REPAIR_V2")
RETROSPECTIVE = "RETROSPECTIVE_V2_PLUS_REJECTED25"
WORKFLOW_LABELS = {
    "SINGLESHOT": "Single-shot",
    "NO_SEMANTIC": "Syntax repair without\nsemantic validation",
    "FULL_REPAIR_V2": "Full workflow",
    RETROSPECTIVE: "Including rejected\ncandidates",
}
WORKFLOW_COLORS = {
    "SINGLESHOT": "#0072B2",
    "NO_SEMANTIC": "#E69F00",
    "FULL_REPAIR_V2": "#009E73",
    RETROSPECTIVE: "#8A8A8A",
}
MODE_ORDER = ("DIRECT_STATIC", "DIRECT_CALCULATION", "COMPLEX_READINESS")
MODE_LABELS = {
    "DIRECT_STATIC": "Direct static",
    "DIRECT_CALCULATION": "Direct calculation",
    "COMPLEX_READINESS": "Complex readiness",
}
MODE_REQUIREMENTS = {"DIRECT_STATIC": 190, "DIRECT_CALCULATION": 41, "COMPLEX_READINESS": 37}
MODEL_ORDER = ("luna", "sol", "gemini", "gpt_oss")
MODEL_LABELS = {
    "luna": "GPT-5.6 Luna",
    "sol": "GPT-5.6 Sol",
    "gemini": "Gemini 3.5 Flash",
    "gpt_oss": "GPT-OSS 120B",
}
MODEL_IDS = {
    "luna": "gpt-5.6-luna-2026-07-09",
    "sol": "gpt-5.6-sol-2026-07-09",
    "gemini": "gemini-3.5-flash",
    "gpt_oss": "gpt-oss-120b",
}
STAGE_ORDER = ("FIRST_GENERATION", "SELF_REPAIR_FINAL")
STAGE_LABELS = {"FIRST_GENERATION": "First generated", "SELF_REPAIR_FINAL": "Final output"}
STAGE_COLORS = {"FIRST_GENERATION": "#0072B2", "SELF_REPAIR_FINAL": "#D55E00"}
EXPECTED_WORKFLOW = {
    "SINGLESHOT": 68.468680,
    "NO_SEMANTIC": 76.109101,
    "FULL_REPAIR_V2": 73.964709,
    RETROSPECTIVE: 80.651092,
}
EXPECTED_MODELS = {
    ("luna", "FIRST_GENERATION"): 72.422150,
    ("luna", "SELF_REPAIR_FINAL"): 72.032468,
    ("sol", "FIRST_GENERATION"): 88.757071,
    ("sol", "SELF_REPAIR_FINAL"): 82.193434,
    ("gemini", "FIRST_GENERATION"): 71.137013,
    ("gemini", "SELF_REPAIR_FINAL"): 73.537013,
    ("gpt_oss", "FIRST_GENERATION"): 52.057648,
    ("gpt_oss", "SELF_REPAIR_FINAL"): 47.041919,
}
SOURCE_LABELS = {
    "I2": "IACS I2",
    "TRAFICOM": "Traficom",
    "IMO": "Polar Code",
    "IMO26": "January 2026 supplement",
}
EXPECTED_SOURCES = {
    "I2": (45, 493),
    "TRAFICOM": (99, 737),
    "IMO": (109, 803),
    "IMO26": (15, 127),
}


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def safe_member(name: str) -> PurePosixPath:
    member = PurePosixPath(name.replace("\\", "/"))
    require(not member.is_absolute(), f"Unsafe absolute ZIP member: {name}")
    require(".." not in member.parts, f"Unsafe parent traversal in ZIP member: {name}")
    require(bool(member.parts), f"Unsafe empty ZIP member: {name}")
    return member


def safe_extract(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            member = safe_member(info.filename)
            mode = info.external_attr >> 16
            require(not stat.S_ISLNK(mode), f"Symbolic-link ZIP member rejected: {info.filename}")
            target = destination.joinpath(*member.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def locate_report_root(candidate: Path) -> Path:
    if all((candidate / name).is_file() for name in REQUIRED_INPUTS):
        return candidate
    matches = [p.parent for p in candidate.rglob("summary_results.csv") if all((p.parent / name).is_file() for name in REQUIRED_INPUTS)]
    require(len(matches) == 1, f"Expected exactly one report root in {candidate}; found {len(matches)}")
    return matches[0]


@contextmanager
def open_report(path: Path):
    path = path.expanduser().resolve()
    require(path.exists(), f"Report input does not exist: {path}")
    if path.is_dir():
        yield locate_report_root(path), {"kind": "directory", "path": str(path)}
        return
    require(path.is_file() and path.suffix.lower() == ".zip", "--report-dir must be a directory or ZIP")
    with tempfile.TemporaryDirectory(prefix="nltl-paper-report-") as temporary:
        destination = Path(temporary)
        safe_extract(path, destination)
        yield locate_report_root(destination), {"kind": "zip", "path": str(path), "sha256": sha256(path)}


def read_inputs(root: Path) -> tuple[dict[str, pd.DataFrame], list[dict[str, object]]]:
    data, manifest = {}, []
    for name in REQUIRED_INPUTS:
        path = root / name
        require(path.is_file(), f"Required report file missing: {path}")
        data[name] = pd.read_csv(path, low_memory=False)
        manifest.append({"name": name, "absolute_path": str(path.resolve()), "sha256": sha256(path), "rows": len(data[name]), "columns": list(data[name].columns)})
    return data, manifest


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.fillna(False).astype(str).str.strip().str.lower().map({"true": True, "false": False}).fillna(False)


def validate_and_recompute(data: dict[str, pd.DataFrame]) -> dict[str, object]:
    validations: list[dict[str, object]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        validations.append({"check": name, "passed": bool(condition), "detail": detail})
        require(condition, f"{name}: {detail}")

    summary_all = data["summary_results.csv"]
    breakdown_all = data["breakdowns.csv"]
    cases_all = data["policy_case_outcomes.csv"]
    req_all = data["requirement_scores.csv"]
    for frame_name, frame in [("summary_results", summary_all), ("breakdowns", breakdown_all), ("case outcomes", cases_all), ("requirement scores", req_all)]:
        check(f"{frame_name} contains selected policy", POLICY in set(frame["policy"].dropna()), f"policy={POLICY}")
    summary = summary_all[summary_all.policy.eq(POLICY)].copy()
    breakdown = breakdown_all[breakdown_all.policy.eq(POLICY)].copy()
    cases = cases_all[cases_all.policy.eq(POLICY)].copy()
    supplied_req = req_all[req_all.policy.eq(POLICY)].copy()

    expected_pairs = {(c, "RUN_01") for c in (*WORKFLOW_ORDER, RETROSPECTIVE)} | {(m, s) for m in MODEL_ORDER for s in STAGE_ORDER}
    actual_pairs = set(map(tuple, summary[["condition", "stage"]].itertuples(index=False, name=None)))
    check("selected condition/stage set", actual_pairs == expected_pairs, f"found={sorted(actual_pairs)}")
    check("no historical FULL", "FULL" not in set(cases.condition), "historical FULL excluded")
    check("unique case rows", not cases.duplicated(["condition", "stage", "case_id"]).any(), "condition/stage/case_id is unique")
    check("all evaluation records present", bool_series(cases.evaluation_row_present).all(), "missing evaluation rows are rejected")
    allowed_availability = {"RECORDED_ARTIFACT", "RECORDED_NO_OUTPUT", "UNKNOWN"}
    check("known availability states", set(cases.artifact_availability.dropna()) <= allowed_availability, str(sorted(set(cases.artifact_availability.dropna()))))
    check("no unknown availability", not cases.artifact_availability.eq("UNKNOWN").any(), "unavailable outputs remain RECORDED_NO_OUTPUT")
    check("binary correct values", set(cases.correct.dropna().astype(int)) <= {0, 1}, "correct is a 0/1 case score")
    check("expected labels", set(cases.expected.dropna()) == {"PASS", "FAIL"}, "PASS is the positive class")

    group_sizes = cases.groupby(["condition", "stage"], sort=False).agg(rows=("case_id", "size"), cases=("case_id", "nunique"), requirements=("requirement_id", "nunique"), evaluation_rows=("evaluation_row_present", lambda x: int(bool_series(x).sum())))
    for condition, stage in expected_pairs:
        row = group_sizes.loc[(condition, stage)]
        expected_cases, expected_requirements = (2160, 268) if stage == "RUN_01" else (373, 50)
        check(f"denominator {condition}/{stage}", int(row.rows) == int(row.cases) == int(row.evaluation_rows) == expected_cases and int(row.requirements) == expected_requirements, row.to_dict().__str__())

    keys = ["condition", "stage", "requirement_id", "verification_mode", "source_family"]
    req = cases.groupby(keys, dropna=False, sort=False).agg(cases=("case_id", "size"), correct=("correct", "sum"), verdicts=("observed", lambda x: int((x != "NO_VERDICT").sum())), evaluation_rows=("evaluation_row_present", lambda x: int(bool_series(x).sum())), artifact_availability=("artifact_availability", "first")).reset_index()
    req["requirement_accuracy"] = req.correct / req.cases
    req["policy"] = POLICY
    req["all_cases_have_verdicts"] = req.verdicts == req.cases
    req["all_cases_correct"] = req.correct == req.cases
    req = req[["policy", *keys, "cases", "correct", "verdicts", "evaluation_rows", "artifact_availability", "requirement_accuracy", "all_cases_have_verdicts", "all_cases_correct"]]
    check("one score per requirement and condition", not req.duplicated(["condition", "stage", "requirement_id"]).any(), "requirement aggregation unique")
    merged_req = req.merge(supplied_req, on=["policy", *keys], how="outer", suffixes=("_recomputed", "_supplied"), indicator=True)
    check("requirement score keys complete", (merged_req._merge == "both").all(), merged_req._merge.value_counts().to_dict().__str__())
    max_req_difference = float((merged_req.requirement_accuracy_recomputed - merged_req.requirement_accuracy_supplied).abs().max())
    check("requirement scores match", max_req_difference <= 1e-12, f"maximum absolute difference={max_req_difference:.3g}")

    summary_records = []
    for (condition, stage), group in cases.groupby(["condition", "stage"], sort=False):
        score_group = req[(req.condition == condition) & (req.stage == stage)]
        counts = group.scored_outcome.value_counts()
        summary_records.append({
            "condition": condition,
            "stage": stage,
            "requirements": len(score_group),
            "cases": len(group),
            "requirement_level_accuracy": float(score_group.requirement_accuracy.mean()),
            "supplementary_pooled_case_accuracy": float(group.correct.mean()),
            "correct": int(counts.get("CORRECT", 0)),
            "false_accept": int(counts.get("FALSE_ACCEPT", 0)),
            "false_reject": int(counts.get("FALSE_REJECT", 0)),
            "no_verdict": int(counts.get("NO_VERDICT", 0)),
            "requirements_with_all_verdicts": int(score_group.all_cases_have_verdicts.sum()),
            "requirements_with_any_no_verdict": int((~score_group.all_cases_have_verdicts).sum()),
            "recorded_output_requirements": int(score_group.artifact_availability.eq("RECORDED_ARTIFACT").sum()),
            "recorded_no_output_requirements": int(score_group.artifact_availability.eq("RECORDED_NO_OUTPUT").sum()),
            "recorded_artifact_case_rows": int(group.artifact_availability.eq("RECORDED_ARTIFACT").sum()),
            "recorded_unavailable_case_rows": int(group.artifact_availability.eq("RECORDED_NO_OUTPUT").sum()),
            "missing_evaluation_rows": int((~bool_series(group.evaluation_row_present)).sum()),
        })
    recomputed_summary = pd.DataFrame(summary_records)
    compare_summary = recomputed_summary.merge(summary, on=["condition", "stage"], suffixes=("_recomputed", "_supplied"), validate="one_to_one")
    max_summary_difference = float((compare_summary.requirement_level_accuracy_recomputed - compare_summary.requirement_level_accuracy_supplied).abs().max())
    check("overall summaries match", max_summary_difference <= 1e-12, f"maximum absolute difference={max_summary_difference:.3g}")

    mode_records = []
    for (condition, stage, mode), group in req.groupby(["condition", "stage", "verification_mode"], sort=False):
        mode_records.append({"condition": condition, "stage": stage, "verification_mode": mode, "requirements": len(group), "cases": int(group.cases.sum()), "requirement_level_accuracy": float(group.requirement_accuracy.mean())})
    modes = pd.DataFrame(mode_records)
    supplied_modes = breakdown[breakdown.dimension.eq("verification_mode")].rename(columns={"category": "verification_mode"})
    mode_check = modes.merge(supplied_modes, on=["condition", "stage", "verification_mode"], suffixes=("_recomputed", "_supplied"), validate="one_to_one")
    max_mode_difference = float((mode_check.requirement_level_accuracy_recomputed - mode_check.requirement_level_accuracy_supplied).abs().max())
    check("mode summaries match", max_mode_difference <= 1e-12, f"maximum absolute difference={max_mode_difference:.3g}")
    check("workflow mode requirement counts", all(int(modes[(modes.condition == "FULL_REPAIR_V2") & (modes.verification_mode == mode)].requirements.iloc[0]) == count for mode, count in MODE_REQUIREMENTS.items()), str(MODE_REQUIREMENTS))
    check("model mode requirement counts", all(int(modes[(modes.condition == "luna") & (modes.stage == "FIRST_GENERATION") & (modes.verification_mode == mode)].requirements.iloc[0]) == count for mode, count in {"DIRECT_STATIC": 20, "DIRECT_CALCULATION": 15, "COMPLEX_READINESS": 15}.items()), "20/15/15")

    for condition, expected in EXPECTED_WORKFLOW.items():
        value = 100 * float(recomputed_summary[(recomputed_summary.condition == condition) & (recomputed_summary.stage == "RUN_01")].requirement_level_accuracy.iloc[0])
        check(f"workflow check {condition}", abs(value - expected) <= 5e-7, f"recomputed={value:.6f}, expected={expected:.6f}")
    for key, expected in EXPECTED_MODELS.items():
        value = 100 * float(recomputed_summary[(recomputed_summary.condition == key[0]) & (recomputed_summary.stage == key[1])].requirement_level_accuracy.iloc[0])
        check(f"model check {key[0]}/{key[1]}", abs(value - expected) <= 5e-7, f"recomputed={value:.6f}, expected={expected:.6f}")

    workflow_reference = cases[(cases.condition == "FULL_REPAIR_V2") & (cases.stage == "RUN_01")]
    source_counts = workflow_reference.groupby("source_family").agg(requirements=("requirement_id", "nunique"), cases=("case_id", "size")).reset_index()
    for source, expected in EXPECTED_SOURCES.items():
        row = source_counts[source_counts.source_family == source].iloc[0]
        check(f"source count {SOURCE_LABELS[source]}", (int(row.requirements), int(row.cases)) == expected, f"found={(int(row.requirements), int(row.cases))}, expected={expected}")
    mode_counts = workflow_reference.groupby("verification_mode").agg(requirements=("requirement_id", "nunique"), cases=("case_id", "size")).reset_index()
    check("workflow source totals", int(source_counts.requirements.sum()) == 268 and int(source_counts.cases.sum()) == 2160, source_counts.to_dict("records").__str__())
    check("workflow mode totals", int(mode_counts.requirements.sum()) == 268 and int(mode_counts.cases.sum()) == 2160, mode_counts.to_dict("records").__str__())

    model_reference = cases[(cases.condition == "luna") & (cases.stage == "FIRST_GENERATION")]
    model_source_counts = model_reference.groupby("source_family").agg(requirements=("requirement_id", "nunique"), cases=("case_id", "size")).reset_index()
    model_mode_counts = model_reference.groupby("verification_mode").agg(requirements=("requirement_id", "nunique"), cases=("case_id", "size")).reset_index()
    check("model source totals", int(model_source_counts.requirements.sum()) == 50 and int(model_source_counts.cases.sum()) == 373, model_source_counts.to_dict("records").__str__())
    check("model mode totals", int(model_mode_counts.requirements.sum()) == 50 and int(model_mode_counts.cases.sum()) == 373, model_mode_counts.to_dict("records").__str__())

    print("Validation results")
    for result in validations:
        print(f"  PASS  {result['check']}: {result['detail']}")
    return {
        "cases": cases,
        "requirements": req,
        "summary": recomputed_summary,
        "modes": modes,
        "source_counts": source_counts,
        "mode_counts": mode_counts,
        "model_source_counts": model_source_counts,
        "model_mode_counts": model_mode_counts,
        "validations": validations,
    }


def configure_matplotlib() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9.0,
        "axes.titlesize": 10.0,
        "axes.labelsize": 9.5,
        "xtick.labelsize": 9.0,
        "ytick.labelsize": 9.0,
        "legend.fontsize": 9.0,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "axes.facecolor": "white",
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })


def save_figure(fig: plt.Figure, output: Path, stem: str) -> list[dict[str, object]]:
    records = []
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    canvas = fig.bbox
    outside = []
    for text in fig.findobj(matplotlib.text.Text):
        if text.get_visible() and text.get_text().strip():
            box = text.get_window_extent(renderer)
            if box.x0 < canvas.x0 - 1 or box.y0 < canvas.y0 - 1 or box.x1 > canvas.x1 + 1 or box.y1 > canvas.y1 + 1:
                outside.append(text.get_text())
    require(not outside, f"Text outside canvas in {stem}: {outside}")
    for extension in ("pdf", "svg", "png"):
        path = output / f"{stem}.{extension}"
        # Preserve the declared 180 mm canvas. Tight bounding boxes can shrink
        # a figure below its intended print width even when all content fits.
        fig.savefig(path, dpi=300)
        require(path.is_file() and path.stat().st_size > 1000, f"Figure export failed: {path}")
        records.append({"figure": stem, "format": extension, "absolute_path": str(path.resolve()), "sha256": sha256(path), "bytes": path.stat().st_size})
    with Image.open(output / f"{stem}.png") as image:
        require(image.width >= 1800 and image.height >= 900, f"PNG too small: {stem} {image.size}")
    plt.close(fig)
    return records


def rounded_box(ax, x, y, width, height, label, *, face="#EFF4F8", edge="#365B73", fontsize=8.4, weight="normal", radius=0.018, zorder=3):
    patch = FancyBboxPatch((x, y), width, height, boxstyle=f"round,pad=0.012,rounding_size={radius}", facecolor=face, edgecolor=edge, linewidth=1.0, zorder=zorder)
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height / 2, label, ha="center", va="center", fontsize=fontsize, weight=weight, color="#1D2A33", zorder=zorder + 1)
    return patch


def arrow(ax, start, end, *, color="#486B7A", connection="arc3", label=None, label_xy=None, style="-|>", width=1.1, zorder=2):
    patch = FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=10, linewidth=width, color=color, connectionstyle=connection, zorder=zorder)
    ax.add_patch(patch)
    if label:
        x, y = label_xy or ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        ax.text(x, y, label, fontsize=7.4, color=color, ha="center", va="center", bbox=dict(facecolor="white", edgecolor="none", pad=1.2), zorder=5)
    return patch


def make_pipeline(output: Path) -> list[dict[str, object]]:
    fig, ax = plt.subplots(figsize=(7.09, 8.65))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.02, 0.975, "a", fontsize=11, weight="bold", va="top")
    ax.text(0.075, 0.975, "Constraint generation and validation", fontsize=10.2, weight="bold", va="top")

    inputs = [
        (0.04, 0.865, 0.21, 0.06, "Requirement text"),
        (0.04, 0.775, 0.21, 0.06, "Relevant ontology\ncontext"),
        (0.04, 0.675, 0.21, 0.072, "Two synthetic\nformat examples"),
    ]
    for x, y, w, h, label in inputs:
        rounded_box(ax, x, y, w, h, label, face="#E8F3F8", edge="#4A7A91")
        arrow(ax, (x + w, y + h / 2), (0.32, 0.81), color="#4A7A91")
    rounded_box(ax, 0.32, 0.765, 0.22, 0.09, "Generate candidate\nconstraints", face="#D8ECF4", edge="#2A6F8E", weight="bold")
    arrow(ax, (0.54, 0.81), (0.61, 0.81))
    rounded_box(ax, 0.61, 0.765, 0.25, 0.09, "Extract candidate and\nparse Turtle", face="#EFF4F8")

    rounded_box(ax, 0.61, 0.625, 0.25, 0.085, "Syntax correction", face="#FFF1DA", edge="#B77A18", weight="bold")
    arrow(ax, (0.735, 0.765), (0.735, 0.71), color="#B77A18", label="extraction or\nparse failure", label_xy=(0.83, 0.738))
    arrow(ax, (0.61, 0.665), (0.535, 0.78), color="#B77A18", connection="arc3,rad=-0.25", label="corrected response", label_xy=(0.54, 0.69))

    rounded_box(ax, 0.32, 0.515, 0.54, 0.075, "", face="#EAF4E9", edge="#4D8050", weight="bold")
    ax.text(0.59, 0.565, "Deterministic checks", fontsize=8.4, weight="bold", ha="center", va="center", color="#274C2A")
    ax.text(0.59, 0.536, "structure  •  vocabulary  •  SPARQL\nmeta-validation  •  runtime smoke check", fontsize=7.5, ha="center", va="center", color="#274C2A")
    arrow(ax, (0.735, 0.765), (0.735, 0.59), color="#4D8050", label="parsed", label_xy=(0.705, 0.625))
    arrow(ax, (0.43, 0.515), (0.43, 0.465), color="#B77A18", label="revise", label_xy=(0.39, 0.49))
    rounded_box(ax, 0.32, 0.375, 0.26, 0.09, "Semantic validation", face="#E8E1F3", edge="#6C5A8C", weight="bold")
    arrow(ax, (0.59, 0.515), (0.45, 0.465), color="#6C5A8C", label="checks pass", label_xy=(0.54, 0.48))
    arrow(ax, (0.32, 0.42), (0.22, 0.61), color="#6C5A8C", connection="arc3,rad=-0.28", label="diagnostic feedback\nfor revision", label_xy=(0.20, 0.48))
    rounded_box(ax, 0.65, 0.39, 0.25, 0.07, "Accepted final\nconstraints", face="#DDF1E4", edge="#3B7D55", weight="bold")
    arrow(ax, (0.58, 0.42), (0.65, 0.425), color="#3B7D55", label="accept", label_xy=(0.615, 0.445))
    rounded_box(ax, 0.67, 0.275, 0.25, 0.08, "Unsuccessful-generation record\n(candidate retained as diagnostic)", face="#EFEFEF", edge="#777777", weight="bold", fontsize=7.7)
    arrow(ax, (0.50, 0.375), (0.67, 0.32), color="#777777", label="budget exhausted", label_xy=(0.60, 0.365))
    rounded_box(ax, 0.04, 0.275, 0.46, 0.075, "Budget: ≤4 generation attempts\n≤3 syntax corrections per attempt\n≤1 fresh-generation attempt within the budget", face="#FFF8E8", edge="#B7953E", fontsize=7.2)

    ax.plot([0.02, 0.98], [0.22, 0.22], color="#CDD5DA", lw=1)
    ax.text(0.02, 0.202, "b", fontsize=11, weight="bold", va="top")
    ax.text(0.075, 0.202, "Independent behavioural evaluation and manual assessment", fontsize=10.2, weight="bold", va="top")
    rounded_box(ax, 0.035, 0.07, 0.27, 0.08, "Independent RDF test\nconfigurations and expected\nPASS/FAIL labels", face="#F2ECF7", edge="#765A8E", fontsize=7.3)
    rounded_box(ax, 0.39, 0.07, 0.22, 0.08, "Behavioural\nevaluation", face="#DDEAF7", edge="#4878A8", weight="bold")
    rounded_box(ax, 0.69, 0.07, 0.25, 0.08, "Case outcomes and\nrequirement-level scores", face="#E9F1F6", edge="#4878A8", fontsize=7.7)
    arrow(ax, (0.305, 0.11), (0.39, 0.11), color="#4878A8")
    arrow(ax, (0.61, 0.11), (0.69, 0.11), color="#4878A8")
    arrow(ax, (0.775, 0.39), (0.52, 0.15), color="#3B7D55", connection="arc3,rad=0.1")
    arrow(ax, (0.795, 0.275), (0.83, 0.15), color="#777777", connection="arc3,rad=-0.1")
    ax.text(0.61, 0.235, "accepted → evaluation", fontsize=7.1, color="#3B7D55", ha="center")
    ax.text(0.865, 0.235, "unsuccessful → no verdict", fontsize=7.1, color="#666666", ha="center")
    rounded_box(ax, 0.69, 0.005, 0.25, 0.042, "Manual assessment", face="#FFF0E8", edge="#A9633B", weight="bold")
    arrow(ax, (0.775, 0.39), (0.79, 0.047), color="#A9633B", connection="arc3,rad=0.16", width=0.9)
    arrow(ax, (0.82, 0.07), (0.82, 0.047), color="#A9633B", width=0.9)
    ax.text(0.34, 0.012, "Benchmark outcomes do not feed generation or repair.", fontsize=7.3, color="#5D6870", ha="center", va="bottom", style="italic")
    return save_figure(fig, output, "pipeline")


def make_workflow_comparison(summary: pd.DataFrame, modes: pd.DataFrame, output: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, object]]]:
    overall = summary[(summary.stage == "RUN_01") & summary.condition.isin((*WORKFLOW_ORDER, RETROSPECTIVE))].copy()
    overall["condition_label"] = overall.condition.map(WORKFLOW_LABELS).str.replace("\n", " ", regex=False)
    overall["accuracy_percent"] = 100 * overall.requirement_level_accuracy
    overall["display_order"] = overall.condition.map({c: i for i, c in enumerate((*WORKFLOW_ORDER, RETROSPECTIVE))})
    overall = overall.sort_values("display_order")
    mode = modes[(modes.stage == "RUN_01") & modes.condition.isin(WORKFLOW_ORDER) & modes.verification_mode.isin(MODE_ORDER)].copy()
    mode["condition_label"] = mode.condition.map(WORKFLOW_LABELS).str.replace("\n", " ", regex=False)
    mode["mode_label"] = mode.verification_mode.map(MODE_LABELS)
    mode["accuracy_percent"] = 100 * mode.requirement_level_accuracy
    mode["condition_order"] = mode.condition.map({c: i for i, c in enumerate(WORKFLOW_ORDER)})
    mode["mode_order"] = mode.verification_mode.map({m: i for i, m in enumerate(MODE_ORDER)})
    mode = mode.sort_values(["mode_order", "condition_order"])

    fig, axes = plt.subplots(1, 2, figsize=(7.09, 4.05), gridspec_kw={"width_ratios": [1.05, 1.6]}, layout="constrained")
    ax = axes[0]
    ypos = np.array([3.3, 2.3, 1.3, 0.0])
    bars = ax.barh(ypos, overall.accuracy_percent, height=0.66, color=[WORKFLOW_COLORS[c] for c in overall.condition], edgecolor="white", linewidth=0.7)
    ax.bar_label(bars, labels=[f"{v:.2f}%" for v in overall.accuracy_percent], padding=3, fontsize=8.2)
    ax.set_yticks(ypos, [WORKFLOW_LABELS[c] for c in overall.condition])
    ax.axhline(0.65, color="#B9B9B9", lw=0.8, ls="--")
    ax.set_title("a  Overall (268 requirements)", loc="left", weight="bold")
    ax.set_xlabel("Requirement-level accuracy (%)")
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.55, 3.85)
    ax.grid(axis="x", color="#DADADA", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)

    ax = axes[1]
    group_x = np.arange(len(MODE_ORDER))
    width = 0.23
    for index, condition in enumerate(WORKFLOW_ORDER):
        values = mode[mode.condition == condition].set_index("verification_mode").reindex(MODE_ORDER).accuracy_percent
        bars = ax.bar(group_x + (index - 1) * width, values, width=width, color=WORKFLOW_COLORS[condition], label=WORKFLOW_LABELS[condition].replace("\n", " "), edgecolor="white", linewidth=0.5)
        ax.bar_label(bars, labels=[f"{v:.1f}" for v in values], padding=1, fontsize=6.8, rotation=90)
    short_mode_labels = {"DIRECT_STATIC": "Direct\nstatic", "DIRECT_CALCULATION": "Direct\ncalculation", "COMPLEX_READINESS": "Complex\nreadiness"}
    ax.set_xticks(group_x, [f"{short_mode_labels[m]}\n(n={MODE_REQUIREMENTS[m]})" for m in MODE_ORDER])
    ax.set_title("b  By verification mode", loc="left", weight="bold")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", color="#DADADA", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=1, frameon=False)
    records = save_figure(fig, output, "workflow_comparison")
    return overall, mode, records


def make_model_comparison(summary: pd.DataFrame, modes: pd.DataFrame, output: Path) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    records = []
    for model in MODEL_ORDER:
        for stage in STAGE_ORDER:
            row = summary[(summary.condition == model) & (summary.stage == stage)].iloc[0]
            records.append({"panel": "Overall", "verification_mode": "OVERALL", "requirements": 50, "cases": int(row.cases), "model_key": model, "model_label": MODEL_LABELS[model], "model_id": MODEL_IDS[model], "stage": stage, "stage_label": STAGE_LABELS[stage], "requirement_level_accuracy": row.requirement_level_accuracy, "accuracy_percent": 100 * row.requirement_level_accuracy})
            for mode in MODE_ORDER:
                value = modes[(modes.condition == model) & (modes.stage == stage) & (modes.verification_mode == mode)].iloc[0]
                records.append({"panel": MODE_LABELS[mode], "verification_mode": mode, "requirements": int(value.requirements), "cases": int(value.cases), "model_key": model, "model_label": MODEL_LABELS[model], "model_id": MODEL_IDS[model], "stage": stage, "stage_label": STAGE_LABELS[stage], "requirement_level_accuracy": value.requirement_level_accuracy, "accuracy_percent": 100 * value.requirement_level_accuracy})
    plot_data = pd.DataFrame(records)
    panels = [("Overall", "OVERALL", 50), ("Direct static", "DIRECT_STATIC", 20), ("Direct calculation", "DIRECT_CALCULATION", 15), ("Complex readiness", "COMPLEX_READINESS", 15)]
    fig, axes = plt.subplots(2, 2, figsize=(7.09, 7.35), sharex=True, sharey=True, layout="constrained")
    y = np.arange(len(MODEL_ORDER))[::-1]
    for letter, ax, (title, mode, n) in zip("abcd", axes.flat, panels):
        panel = plot_data[plot_data.verification_mode == mode]
        for ypos, model in zip(y, MODEL_ORDER):
            group = panel[panel.model_key == model].set_index("stage").reindex(STAGE_ORDER)
            values = group.accuracy_percent.to_numpy()
            ax.plot(values, [ypos, ypos], color="#A9A9A9", lw=1.4, zorder=1)
            for stage, value in zip(STAGE_ORDER, values):
                ax.scatter(value, ypos, s=42, color=STAGE_COLORS[stage], edgecolor="white", linewidth=0.6, zorder=3)
            left, right = values
            ax.text(left, ypos + 0.17, f"{left:.1f}", ha="center", va="bottom", fontsize=7.2, color=STAGE_COLORS[STAGE_ORDER[0]])
            ax.text(right, ypos - 0.17, f"{right:.1f}", ha="center", va="top", fontsize=7.2, color=STAGE_COLORS[STAGE_ORDER[1]])
        ax.set_title(f"{letter}  {title} (n={n})", loc="left", weight="bold")
        ax.set_yticks(y, [MODEL_LABELS[m] for m in MODEL_ORDER])
        ax.set_xlim(0, 100)
        ax.set_ylim(-0.48, 3.48)
        ax.set_xticks(np.arange(0, 101, 20))
        ax.grid(axis="x", color="#DADADA", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="y", length=0)
    for ax in axes[1]:
        ax.set_xlabel("Requirement-level accuracy (%)")
    handles = [Line2D([0], [0], marker="o", color="none", markerfacecolor=STAGE_COLORS[s], markeredgecolor="white", markersize=7, label=STAGE_LABELS[s]) for s in STAGE_ORDER]
    fig.legend(handles=handles, loc="outside lower center", ncol=2, frameon=False)
    output_records = save_figure(fig, output, "model_comparison")
    return plot_data, output_records


def pipeline_plot_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes = [
        ("requirement", "Requirement text", "generation input"), ("ontology", "Relevant ontology context", "generation input"),
        ("examples", "Two synthetic format examples", "generation input"), ("generate", "Generate candidate constraints", "generation"),
        ("parse", "Extract candidate and parse Turtle", "deterministic"), ("syntax", "Syntax correction", "repair"),
        ("checks", "Structure, vocabulary, SPARQL, meta-validation and runtime smoke checks", "deterministic"),
        ("semantic", "Semantic validation", "semantic"), ("accepted", "Accepted final constraints", "result"),
        ("unsuccessful", "Unsuccessful-generation record; last candidate may remain diagnostic evidence", "result"),
        ("fixtures", "Independently prepared RDF configurations and expected PASS/FAIL labels", "evaluation input"),
        ("evaluation", "Behavioural evaluation", "evaluation"), ("outcomes", "Case outcomes and requirement-level scores", "evaluation result"),
        ("manual", "Manual assessment", "manual review"),
    ]
    edges = [
        ("requirement", "generate", "input"), ("ontology", "generate", "input"), ("examples", "generate", "input"),
        ("generate", "parse", "candidate"), ("parse", "syntax", "extraction/parsing failure"), ("syntax", "parse", "corrected response"),
        ("parse", "checks", "parsed candidate"), ("checks", "generate", "deterministic diagnostic feedback"),
        ("checks", "semantic", "checks pass"), ("semantic", "generate", "diagnostic feedback for revision"),
        ("semantic", "accepted", "accept"), ("semantic", "unsuccessful", "budget exhausted"),
        ("fixtures", "evaluation", "independent benchmark"), ("accepted", "evaluation", "generated constraints"),
        ("unsuccessful", "outcomes", "record without verdicts"), ("evaluation", "outcomes", "case outcomes"),
        ("accepted", "manual", "generated output"), ("outcomes", "manual", "evaluation evidence"),
    ]
    return pd.DataFrame(nodes, columns=["node_id", "label", "role"]), pd.DataFrame(edges, columns=["source", "target", "relationship"])


def source_mode_export(results: dict[str, object]) -> pd.DataFrame:
    frames = []
    for experiment, source, mode in [
        ("manuscript_dataset", results["source_counts"], results["mode_counts"]),
        ("model_sample", results["model_source_counts"], results["model_mode_counts"]),
    ]:
        a = source.copy()
        a["experiment"] = experiment
        a["dimension"] = "source"
        a["category"] = a.source_family
        a["category_label"] = a.source_family.map(SOURCE_LABELS)
        frames.append(a[["experiment", "dimension", "category", "category_label", "requirements", "cases"]])
        b = mode.copy()
        b["experiment"] = experiment
        b["dimension"] = "verification_mode"
        b["category"] = b.verification_mode
        b["category_label"] = b.verification_mode.map(MODE_LABELS)
        frames.append(b[["experiment", "dimension", "category", "category_label", "requirements", "cases"]])
    return pd.concat(frames, ignore_index=True)


def make_readme(output: Path, report_source: dict[str, object], validations: list[dict[str, object]], input_manifest: list[dict[str, object]], zip_path: Path) -> str:
    source_lines = "\n".join(f"- `{item['absolute_path']}` (SHA-256 `{item['sha256']}`)" for item in input_manifest)
    count_lines = "\n".join(f"- {SOURCE_LABELS[key]}: {req} requirements / {cases} configurations" for key, (req, cases) in EXPECTED_SOURCES.items())
    command = f'cd "{SCRIPT_DIR}"\npython make_paper_figures.py --report-dir outputs/report_02 --output-dir outputs/paper_figures'
    return f"""# Ocean Engineering manuscript figures

This directory contains the three principal publication figures generated from the existing `report_02` reporting data. The program did not rerun generation or evaluation and did not modify the report, ontology, RDF graphs, labels, or source workbook.

## Rerun

```bash
{command}
```

`--report-dir` accepts either a report directory or a ZIP. ZIP members are validated against absolute paths, parent traversal, and symbolic links before extraction. A completed output created by this script is replaced atomically on rerun.

## Verified data

Internal behavioural policy: `{POLICY}`. This identifier is recorded in provenance and is omitted from figure labels.

- Manuscript dataset: 268 requirements / 2,160 configurations.
- Model sample: 50 requirements / 373 configurations.
{count_lines}
- Verification modes: Direct static 190 requirements; Direct calculation 41; Complex readiness 37.
- Accuracy is the unweighted mean of requirement-level correct-case fractions. Cases without executable verdicts remain in each requirement denominator with zero credit.
- All expected evaluation rows were present and unique. Recorded unavailable outputs remain explicit and are distinct from missing evaluation records.
- Recomputed per-requirement, overall, and mode-level values matched the supplied report summaries. All {len(validations)} validation checks passed.

## Principal figures

- `pipeline.pdf`, `.svg`, `.png`: generation, validation, independent behavioural evaluation, and separate manual assessment.
- `workflow_comparison.pdf`, `.svg`, `.png`: principal workflow comparison with retrospective results visually separated.
- `model_comparison.pdf`, `.svg`, `.png`: paired first-generated and final-output accuracy for four models.

PDF and SVG retain vector graphics and editable text. PNG files are exported at 300 dpi. Figures contain no manuscript captions.

## Reusable data

- `pipeline_nodes.csv`, `pipeline_edges.csv`
- `workflow_overall_plot_data.csv`, `workflow_by_mode_plot_data.csv`
- `model_comparison_plot_data.csv`
- `per_requirement_behavioural_scores.csv`
- `coverage_error_table.csv`
- `source_mode_dataset_counts.csv`
- `manual_review_summary.csv`
- `referenced_files.csv`
- `validation_results.csv`
- `provenance_manifest.json`

The detailed heatmaps, confusion matrices, rubric heatmaps, and failure plots remain available in the existing report and are not part of this principal figure set. No maritime worked example is invented here.

## Paths

- Report source: `{report_source['path']}` ({report_source['kind']})
- Output directory: `{output.resolve()}`
- Shareable ZIP: `{zip_path.resolve()}`

Exact consumed files:

{source_lines}
"""


def atomic_publish(staging: Path, output: Path, zip_staging: Path, zip_path: Path) -> None:
    if output.exists():
        marker = output / "provenance_manifest.json"
        require(marker.is_file(), f"Refusing to replace unrecognized output directory: {output}")
        try:
            prior = json.loads(marker.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValidationError(f"Refusing to replace output with unreadable provenance: {marker}: {exc}") from exc
        require(prior.get("generator") == Path(__file__).name, f"Refusing to replace output not created by {Path(__file__).name}")
        shutil.rmtree(output)
    staging.replace(output)
    if zip_path.exists():
        zip_path.unlink()
    zip_staging.replace(zip_path)


def build(args: argparse.Namespace) -> tuple[Path, Path]:
    report_arg = args.report_dir.expanduser().resolve()
    output = args.output_dir.expanduser().resolve()
    zip_path = output.parent / f"{output.name}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    configure_matplotlib()
    with open_report(report_arg) as (report_root, report_source):
        data, input_manifest = read_inputs(report_root)
        results = validate_and_recompute(data)

        parent = output.parent
        with tempfile.TemporaryDirectory(prefix=f".{output.name}-build-", dir=parent) as temporary:
            staging = Path(temporary) / output.name
            staging.mkdir()
            figure_manifest = []
            figure_manifest += make_pipeline(staging)
            workflow_overall, workflow_modes, figure_records = make_workflow_comparison(results["summary"], results["modes"], staging)
            figure_manifest += figure_records
            model_plot, figure_records = make_model_comparison(results["summary"], results["modes"], staging)
            figure_manifest += figure_records

            pipeline_nodes, pipeline_edges = pipeline_plot_data()
            pipeline_nodes.to_csv(staging / "pipeline_nodes.csv", index=False)
            pipeline_edges.to_csv(staging / "pipeline_edges.csv", index=False)
            workflow_overall.to_csv(staging / "workflow_overall_plot_data.csv", index=False)
            workflow_modes.to_csv(staging / "workflow_by_mode_plot_data.csv", index=False)
            model_plot.to_csv(staging / "model_comparison_plot_data.csv", index=False)
            results["requirements"].sort_values(["condition", "stage", "requirement_id"]).to_csv(staging / "per_requirement_behavioural_scores.csv", index=False)
            results["summary"].sort_values(["condition", "stage"]).to_csv(staging / "coverage_error_table.csv", index=False)
            source_mode_export(results).to_csv(staging / "source_mode_dataset_counts.csv", index=False)
            data["manual_summary.csv"].to_csv(staging / "manual_review_summary.csv", index=False)
            data["referenced_files.csv"].to_csv(staging / "referenced_files.csv", index=False)
            pd.DataFrame(results["validations"]).to_csv(staging / "validation_results.csv", index=False)

            implementation_sources = []
            for relative, role in [
                ("SHACL_GENERATION_PIPELINE/src/nltl_pipeline/orchestration/runner.py", "implemented full-workflow control flow"),
                ("SHACL_GENERATION_PIPELINE/src/nltl_pipeline/validation/shacl.py", "implemented deterministic checks"),
                ("SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/execution.py", "independent behavioural evaluation"),
                ("SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/CONFIGS/pipeline.full-repair-v2-run01.json", "implemented attempt budgets"),
                ("RELEVANT FILES/HAITHAMSOCEANENGINEERINGJOURNAL.pdf", "available manuscript workflow context"),
            ]:
                path = PROJECT_ROOT / relative
                if path.is_file():
                    implementation_sources.append({"role": role, "absolute_path": str(path.resolve()), "sha256": sha256(path)})

            generation_sources = []
            for model in MODEL_ORDER:
                for stage in STAGE_ORDER:
                    path = report_root / f"generation_{model}_{stage}.csv"
                    require(path.is_file(), f"Model provenance input missing: {path}")
                    frame = pd.read_csv(path, low_memory=False)
                    ids = sorted(frame.model_identifier.dropna().unique())
                    require(ids == [MODEL_IDS[model]], f"Unexpected model identifier for {model}/{stage}: {ids}")
                    generation_sources.append({"model_key": model, "stage": stage, "model_id": ids[0], "absolute_path": str(path.resolve()), "sha256": sha256(path)})

            provenance = {
                "generator": Path(__file__).name,
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "report_source": report_source,
                "selected_policy": POLICY,
                "policy_figure_label": None,
                "metric_definition": "For each requirement, correct included cases divided by all included cases assigned to that requirement; the plotted accuracy is the unweighted mean across included requirements. No-verdict cases receive zero credit and stay in the denominator.",
                "stage_mapping": STAGE_LABELS,
                "condition_mapping": {**{key: WORKFLOW_LABELS[key].replace("\n", " ") for key in (*WORKFLOW_ORDER, RETROSPECTIVE)}, **MODEL_LABELS},
                "model_identifiers": MODEL_IDS,
                "counts": {
                    "manuscript": {"requirements": 268, "configurations": 2160, "sources": {SOURCE_LABELS[k]: {"requirements": v[0], "configurations": v[1]} for k, v in EXPECTED_SOURCES.items()}, "modes": {MODE_LABELS[k]: v for k, v in MODE_REQUIREMENTS.items()}},
                    "model_sample": {"requirements": 50, "configurations": 373, "modes": {"Direct static": 20, "Direct calculation": 15, "Complex readiness": 15}},
                },
                "attempt_budget": {"generation_attempts": 4, "syntax_corrections_per_generation_attempt": 3, "fresh_generation_attempts_within_budget": 1},
                "input_files": input_manifest,
                "model_generation_sources": generation_sources,
                "implementation_and_manuscript_sources": implementation_sources,
                "validation": results["validations"],
                "figures": figure_manifest,
            }
            write_json(staging / "provenance_manifest.json", provenance)
            shutil.copy2(Path(__file__), staging / Path(__file__).name)
            dependencies = SCRIPT_DIR / "requirements-paper-figures.txt"
            require(dependencies.is_file(), f"Dependency file missing: {dependencies}")
            shutil.copy2(dependencies, staging / dependencies.name)

            readme = make_readme(output, report_source, results["validations"], input_manifest, zip_path)
            (staging / "README.md").write_text(readme, encoding="utf-8")
            zip_staging = Path(temporary) / f"{output.name}.zip"
            with zipfile.ZipFile(zip_staging, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(staging.rglob("*")):
                    if path.is_file():
                        archive.write(path, Path(output.name) / path.relative_to(staging))
            require(zip_staging.stat().st_size > 1000, "ZIP packaging failed")
            atomic_publish(staging, output, zip_staging, zip_path)
    return output, zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=Path("outputs/report_02"), help="Existing report directory or ZIP")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/paper_figures"), help="Destination for figures and reusable plot data")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        output, zip_path = build(args)
    except Exception as exc:
        print(f"Paper figure build failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
    print(f"All validations passed.\nOutput directory: {output}\nShareable ZIP: {zip_path}")


if __name__ == "__main__":
    main()
