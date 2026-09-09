#!/usr/bin/env python3
"""Evaluate frozen Pilot 02 RDF fixtures against Luna RUN01 generated SHACL."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pyshacl
from rdflib import Graph


REPO_ROOT = Path(__file__).resolve().parents[5]
MVP_ROOT = REPO_ROOT / "MVP"
PIPELINE_ROOT = MVP_ROOT / "SHACL_GENERATION_PIPELINE"
PILOT_ROOT = PIPELINE_ROOT / "evaluation" / "BEHAVIORAL_RDF_R13"
EXPERIMENT_ROOT = PIPELINE_ROOT / "experiments"
MANIFEST_PATH = PILOT_ROOT / "manifests" / "pilot_02_manifest.jsonl"
ONTOLOGY_PATH = MVP_ROOT / "BENCHMARK_VOCABULARY" / "FINAL_LOCK_R13" / "ontology" / "nltl_benchmark_vocabulary.ttl"
REPORT_DIR = PILOT_ROOT / "reports"
JSON_PATH = REPORT_DIR / "pilot_02_generated_shape_results.json"
CASES_CSV_PATH = REPORT_DIR / "pilot_02_generated_shape_cases.csv"
REQUIREMENT_CSV_PATH = REPORT_DIR / "pilot_02_generated_shape_requirement_summary.csv"
SUMMARY_CSV_PATH = REPORT_DIR / "pilot_02_generated_shape_summary.csv"
DIAGNOSTICS_PATH = REPORT_DIR / "pilot_02_generated_shape_diagnostics.txt"

REQUIREMENTS = (
    "I2-014", "I2-015", "I2-021", "I2-041", "I2-046",
    "I2-047", "I2-048", "I2-066", "IMO26-007", "IMO26-011",
)
ARCHITECTURES = {
    "FULL": {"directory": "FINAL_LUNA_MAIN", "selection": "final"},
    "NO_SEMANTIC": {"directory": "LUNA_NO_SEMANTIC_VALIDATOR", "selection": "no_semantic"},
    "SINGLESHOT": {"directory": "LUNA_CONTEXTUAL_SINGLESHOT", "selection": "singleshot"},
}
SETTINGS = {"inference": "rdfs", "meta_shacl": True, "advanced": True}

# Match the project's deterministic bulk evaluator registration behavior.
sys.path.insert(0, str(PIPELINE_ROOT / "src"))
from nltl_pipeline.validation.sparql_extensions import register_math_functions  # noqa: E402

register_math_functions()


def rel_repo(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def rel_pilot(path: Path) -> str:
    return path.resolve().relative_to(PILOT_ROOT.resolve()).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def exactly_one(items: list[Any], description: str) -> Any:
    if len(items) != 1:
        raise RuntimeError(f"Expected exactly one {description}; found {len(items)}")
    return items[0]


def load_manifest() -> list[dict[str, Any]]:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    counts = Counter(row.get("requirement_id") for row in rows)
    if len(rows) != 65 or set(counts) != set(REQUIREMENTS):
        raise RuntimeError(f"Frozen manifest inventory mismatch: rows={len(rows)}, requirements={dict(counts)}")
    if len({row.get("case_id") for row in rows}) != 65:
        raise RuntimeError("Frozen manifest case IDs are not unique")
    for row in rows:
        if row.get("expected") not in {"PASS", "FAIL"}:
            raise RuntimeError(f"Invalid frozen expected verdict for {row.get('case_id')}: {row.get('expected')!r}")
        fixture = PILOT_ROOT / row["rdf_path"]
        if not fixture.is_file():
            raise RuntimeError(f"Frozen fixture is missing: {fixture}")
    return rows


def specification_path(requirement: str) -> Path:
    family = "IMO26" if requirement.startswith("IMO26-") else "I2"
    return PILOT_ROOT / "specifications" / family / f"{requirement}.json"


def frozen_paths(manifest: list[dict[str, Any]]) -> list[Path]:
    paths = [MANIFEST_PATH]
    paths.extend(specification_path(requirement) for requirement in REQUIREMENTS)
    paths.extend(PILOT_ROOT / row["rdf_path"] for row in manifest)
    unique = sorted(set(path.resolve() for path in paths), key=str)
    missing = [str(path) for path in unique if not path.is_file()]
    if missing:
        raise RuntimeError(f"Frozen files missing: {missing}")
    return unique


def hash_inventory(paths: list[Path]) -> dict[str, str]:
    return {rel_pilot(path): sha256(path) for path in paths}


def classify_diagnostics(diagnostics: dict[str, Any], mode: str) -> str | None:
    validation = diagnostics.get("deterministicValidation", {})
    if mode == "singleshot":
        if diagnostics.get("extractionStatus") not in {None, "PASS"}:
            return "EXTRACTION_FAILURE"
        if diagnostics.get("rdfParseStatus") not in {None, "PASS"}:
            return "TURTLE_PARSE_FAILURE"
        if diagnostics.get("shaclValidationStatus") not in {None, "PASS"}:
            return "META_SHACL_FAILURE"
    if validation.get("valid") is True:
        return None
    for key, stage in (
        ("extraction_valid", "EXTRACTION_FAILURE"),
        ("turtle_valid", "TURTLE_PARSE_FAILURE"),
        ("shacl_structure_valid", "SHACL_STRUCTURE_FAILURE"),
        ("meta_shacl_valid", "META_SHACL_FAILURE"),
        ("vocabulary_valid", "VOCABULARY_FAILURE"),
        ("datatype_unit_valid", "DATATYPE_UNIT_FAILURE"),
        ("target_path_valid", "TARGET_PATH_FAILURE"),
    ):
        if validation.get(key) is False:
            return stage
    return "DETERMINISTIC_VALIDITY_FAILURE"


def latest_candidate(run_dir: Path, artifact_rows: list[dict[str, str]]) -> dict[str, Any]:
    candidates = [row for row in artifact_rows if row.get("ARTIFACT_TYPE") == "candidate_shape"]
    if not candidates:
        return {"path": None, "sha256": None}
    candidates.sort(key=lambda row: int(row.get("ITERATION") or 0))
    row = candidates[-1]
    path = run_dir / row["ARTIFACT_PATH"]
    return {
        "path": rel_repo(path) if path.exists() else row["ARTIFACT_PATH"],
        "sha256": sha256(path) if path.is_file() else row.get("SHA256") or None,
    }


def select_artifact(architecture: str, requirement: str) -> dict[str, Any]:
    config = ARCHITECTURES[architecture]
    runs_root = EXPERIMENT_ROOT / config["directory"] / "RUN_01" / "runs"
    run_dir = exactly_one(
        sorted(runs_root.glob(f"RUN-{requirement}-*")),
        f"RUN01 run directory for {architecture}/{requirement}",
    )
    run_row = exactly_one(
        [row for row in read_csv(run_dir / "tables" / "runs.csv") if row.get("REQUIREMENT_ID") == requirement],
        f"runs.csv row for {architecture}/{requirement}",
    )
    artifact_rows = read_csv(run_dir / "tables" / "artifacts.csv")
    mode = config["selection"]
    shape_path: Path | None = None
    diagnostics_path: Path | None = None
    failure_stage: str | None = None
    failure_detail = ""

    if mode == "final":
        accepted = run_row.get("ACCEPTED", "").strip().lower() == "true"
        final_rel = run_row.get("FINAL_SHAPE", "").strip()
        final_rows = [row for row in artifact_rows if row.get("ARTIFACT_TYPE") == "final_accepted_shape"]
        if accepted:
            final_row = exactly_one(final_rows, f"final accepted artifact for {architecture}/{requirement}")
            if not final_rel or final_row.get("ARTIFACT_PATH") != final_rel:
                raise RuntimeError(f"Ambiguous final artifact metadata for {architecture}/{requirement}")
            shape_path = run_dir / final_rel
            if not shape_path.is_file():
                failure_stage = "NO_OUTPUT"
                failure_detail = "runs.csv identifies an accepted final shape, but the file is absent"
        else:
            if final_rel or final_rows:
                raise RuntimeError(f"Conflicting rejected/final artifact metadata for {architecture}/{requirement}")
            failure_stage = run_row.get("FINAL_STATUS") or "GENERATION_FAILURE"
            failure_detail = run_row.get("FINAL_FEEDBACK", "")
    else:
        artifact_type = "no_semantic_validator_candidate_shape" if mode == "no_semantic" else "single_shot_extracted_shape"
        artifact_row = exactly_one(
            [row for row in artifact_rows if row.get("ARTIFACT_TYPE") == artifact_type],
            f"{artifact_type} artifact for {architecture}/{requirement}",
        )
        shape_path = run_dir / artifact_row["ARTIFACT_PATH"]
        diagnostic_type = "no_semantic_validator_diagnostics" if mode == "no_semantic" else "single_shot_diagnostics"
        diagnostic_row = exactly_one(
            [row for row in artifact_rows if row.get("ARTIFACT_TYPE") == diagnostic_type],
            f"{diagnostic_type} artifact for {architecture}/{requirement}",
        )
        diagnostics_path = run_dir / diagnostic_row["ARTIFACT_PATH"]
        diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
        failure_stage = classify_diagnostics(diagnostics, mode)
        if failure_stage:
            errors = diagnostics.get("deterministicValidation", {}).get("errors", [])
            failure_detail = " | ".join(str(error) for error in errors) or run_row.get("FINAL_STATUS", "")
        if not shape_path.is_file() and failure_stage is None:
            failure_stage = "NO_OUTPUT"
            failure_detail = "Recorded generated artifact file is absent"

    evidence = latest_candidate(run_dir, artifact_rows)
    selected_path = rel_repo(shape_path) if shape_path and shape_path.exists() else None
    selected_sha = sha256(shape_path) if shape_path and shape_path.is_file() else None
    return {
        "architecture": architecture,
        "architecture_directory": config["directory"],
        "run": "RUN01",
        "run_id": run_row["RUN_ID"],
        "requirement_id": requirement,
        "terminal_status": run_row.get("FINAL_STATUS", ""),
        "generated_shape_path": selected_path,
        "generated_shape_sha256": selected_sha,
        "failure_stage": failure_stage,
        "failure_detail": failure_detail,
        "selection_evidence_path": rel_repo(run_dir / "tables" / "runs.csv"),
        "diagnostics_path": rel_repo(diagnostics_path) if diagnostics_path else None,
        "last_generated_candidate_path": evidence["path"],
        "last_generated_candidate_sha256": evidence["sha256"],
        "_shape_path": shape_path,
        "_run_dir": run_dir,
    }


def report_summary(conforms: bool | None, report_text: str, error: str) -> str:
    if error:
        return error.replace("\n", " ")
    if conforms is True:
        return "Conforms: true"
    messages = [
        line.split("Message:", 1)[1].strip()
        for line in report_text.splitlines() if "Message:" in line
    ]
    detail = " | ".join(dict.fromkeys(messages)) if messages else "SHACL violation"
    return f"Conforms: false | {detail}"


def mechanical_reason(expected: str, actual: str, summary: str, failure_stage: str | None) -> str:
    if failure_stage:
        return f"Generated shape was unusable at {failure_stage}; the requirement's cases are incorrect end-to-end."
    if expected == "FAIL" and actual == "PASS":
        return "False acceptance: pySHACL returned conforms=true, so the generated shape produced no violation for this frozen negative case."
    if expected == "PASS" and actual == "FAIL":
        return f"False rejection: pySHACL returned conforms=false. {summary}"
    return ""


def evaluate_requirement(
    selection: dict[str, Any], assigned_cases: list[dict[str, Any]], ontology: Graph
) -> list[dict[str, Any]]:
    shape_path: Path | None = selection["_shape_path"]
    failure_stage = selection["failure_stage"]
    error = selection["failure_detail"] if failure_stage else ""
    shape_graph: Graph | None = None
    shape_text = ""
    diagnostic_shape_path = selection["generated_shape_path"]
    diagnostic_shape_sha = selection["generated_shape_sha256"]

    if shape_path and shape_path.is_file():
        shape_text = shape_path.read_text(encoding="utf-8", errors="replace")
    elif selection["last_generated_candidate_path"]:
        last_path = REPO_ROOT / selection["last_generated_candidate_path"]
        if last_path.is_file():
            shape_text = last_path.read_text(encoding="utf-8", errors="replace")
            diagnostic_shape_path = selection["last_generated_candidate_path"] + " (last candidate; not evaluated as final)"
            diagnostic_shape_sha = selection["last_generated_candidate_sha256"]

    if failure_stage is None and shape_path:
        try:
            shape_graph = Graph().parse(shape_path, format="turtle")
        except Exception as exc:
            failure_stage = "TURTLE_PARSE_FAILURE"
            error = f"{type(exc).__name__}: {exc}"

    results: list[dict[str, Any]] = []
    for case in assigned_cases:
        fixture_path = PILOT_ROOT / case["rdf_path"]
        actual = "UNUSABLE"
        execution_status = "UNUSABLE_SHAPE"
        case_failure = failure_stage
        case_error = error
        report_text = ""
        conforms: bool | None = None

        if shape_graph is not None and failure_stage is None:
            try:
                data_graph = Graph().parse(fixture_path, format="turtle")
                conforms_value, report_graph, report_text_value = pyshacl.validate(
                    data_graph,
                    shacl_graph=shape_graph,
                    ont_graph=ontology,
                    inference="rdfs",
                    meta_shacl=True,
                    advanced=True,
                )
                if not isinstance(report_graph, Graph):
                    raise RuntimeError(f"SHACL engine rejected the graph: {report_text_value}")
                conforms = bool(conforms_value)
                actual = "PASS" if conforms else "FAIL"
                execution_status = "SUCCESS"
                case_failure = None
                case_error = ""
                report_text = str(report_text_value)
            except Exception as exc:
                case_error = f"{type(exc).__name__}: {exc}"
                lowered = case_error.lower()
                case_failure = "META_SHACL_FAILURE" if "meta-shacl" in lowered else "PYSHACL_EXECUTION_FAILURE"

        summary = report_summary(conforms, report_text, case_error)
        correct = execution_status == "SUCCESS" and actual == case["expected"]
        results.append({
            "architecture": selection["architecture"],
            "run": "RUN01",
            "run_id": selection["run_id"],
            "requirement_id": case["requirement_id"],
            "case_id": case["case_id"],
            "generated_shape_path": selection["generated_shape_path"],
            "generated_shape_sha256": selection["generated_shape_sha256"],
            "rdf_fixture_path": rel_repo(fixture_path),
            "rdf_fixture_sha256": sha256(fixture_path),
            "expected": case["expected"],
            "actual": actual,
            "correct": correct,
            "execution_status": execution_status,
            "failure_stage": case_failure,
            "validation_report_summary": summary,
            "validation_report_text": report_text or case_error,
            "source_oracle_rationale": case.get("rationale", case.get("source_oracle", "")),
            "mechanical_mismatch_reason": mechanical_reason(case["expected"], actual, summary, case_failure) if not correct else "",
            "diagnostic_shape_path": diagnostic_shape_path,
            "diagnostic_shape_sha256": diagnostic_shape_sha,
            "_rdf_text": fixture_path.read_text(encoding="utf-8"),
            "_shape_text": shape_text,
        })
    return results


def summarize(cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requirement_rows: list[dict[str, Any]] = []
    architecture_rows: list[dict[str, Any]] = []
    for architecture in ARCHITECTURES:
        arch_cases = [row for row in cases if row["architecture"] == architecture]
        exact_requirements = 0
        for requirement in REQUIREMENTS:
            rows = [row for row in arch_cases if row["requirement_id"] == requirement]
            pass_rows = [row for row in rows if row["expected"] == "PASS"]
            fail_rows = [row for row in rows if row["expected"] == "FAIL"]
            correct = sum(bool(row["correct"]) for row in rows)
            exact = bool(rows) and correct == len(rows)
            exact_requirements += int(exact)
            unusable = any(row["execution_status"] != "SUCCESS" for row in rows)
            requirement_rows.append({
                "architecture": architecture,
                "requirement_id": requirement,
                "cases_correct": correct,
                "cases_total": len(rows),
                "case_accuracy": correct / len(rows),
                "exact_success": exact,
                "expected_pass_correct": sum(bool(row["correct"]) for row in pass_rows),
                "expected_pass_total": len(pass_rows),
                "expected_fail_correct": sum(bool(row["correct"]) for row in fail_rows),
                "expected_fail_total": len(fail_rows),
                "false_accepts": sum(row["expected"] == "FAIL" and row["actual"] == "PASS" for row in rows),
                "false_rejects": sum(row["expected"] == "PASS" and row["actual"] == "FAIL" for row in rows),
                "unusable_shape": unusable,
                "generation_execution_failure_count": int(unusable),
            })
        pass_rows = [row for row in arch_cases if row["expected"] == "PASS"]
        fail_rows = [row for row in arch_cases if row["expected"] == "FAIL"]
        unusable_requirements = {row["requirement_id"] for row in arch_cases if row["execution_status"] != "SUCCESS"}
        correct = sum(bool(row["correct"]) for row in arch_cases)
        pass_correct = sum(bool(row["correct"]) for row in pass_rows)
        fail_correct = sum(bool(row["correct"]) for row in fail_rows)
        architecture_rows.append({
            "architecture": architecture,
            "cases_correct": correct,
            "cases_total": len(arch_cases),
            "case_accuracy": correct / len(arch_cases),
            "exact_requirements": exact_requirements,
            "requirements_total": len(REQUIREMENTS),
            "requirement_accuracy": exact_requirements / len(REQUIREMENTS),
            "expected_pass_correct": pass_correct,
            "expected_pass_total": len(pass_rows),
            "expected_pass_accuracy": pass_correct / len(pass_rows),
            "expected_fail_correct": fail_correct,
            "expected_fail_total": len(fail_rows),
            "expected_fail_accuracy": fail_correct / len(fail_rows),
            "false_accepts": sum(row["expected"] == "FAIL" and row["actual"] == "PASS" for row in arch_cases),
            "false_rejects": sum(row["expected"] == "PASS" and row["actual"] == "FAIL" for row in arch_cases),
            "generation_execution_failure_count": len(unusable_requirements),
            "unusable_shapes": len(unusable_requirements),
            "cases_affected_by_unusable_shapes": sum(row["execution_status"] != "SUCCESS" for row in arch_cases),
        })
    return requirement_rows, architecture_rows


def diagnostics_text(cases: list[dict[str, Any]]) -> str:
    blocks = [
        "Pilot 02 RUN01 incorrect-case diagnostics",
        "Generated artifacts and frozen fixtures were read only. No LLM or repair was used.",
    ]
    for row in cases:
        if row["correct"]:
            continue
        blocks.extend([
            "",
            "=" * 80,
            f"architecture: {row['architecture']}",
            f"requirement: {row['requirement_id']}",
            f"case: {row['case_id']}",
            f"expected: {row['expected']}",
            f"actual: {row['actual']}",
            f"shape path: {row['generated_shape_path'] or '<NO USABLE SELECTED SHAPE>'}",
            f"shape SHA256: {row['generated_shape_sha256'] or '<NONE>'}",
            f"fixture path: {row['rdf_fixture_path']}",
            f"execution status: {row['execution_status']}",
            f"failure stage: {row['failure_stage'] or ''}",
            f"source-oracle rationale: {row['source_oracle_rationale']}",
            f"mechanical reason: {row['mechanical_mismatch_reason']}",
            "--- RELEVANT RDF INPUT ---",
            row["_rdf_text"].rstrip(),
            "--- RELEVANT GENERATED SHACL/SPARQL ---",
            f"artifact evidence: {row['diagnostic_shape_path'] or '<NONE>'}",
            f"artifact evidence SHA256: {row['diagnostic_shape_sha256'] or '<NONE>'}",
            row["_shape_text"].rstrip() or "<NO GENERATED SHACL TEXT AVAILABLE>",
            "--- PYSHACL REPORT ---",
            row["validation_report_text"].rstrip() or "<NO PYSHACL REPORT: SHAPE UNUSABLE BEFORE EXECUTION>",
        ])
    return "\n".join(blocks) + "\n"


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def print_summary(architecture_rows: list[dict[str, Any]], requirement_rows: list[dict[str, Any]], modified: bool) -> None:
    print("Pilot 02 RUN01 behavioral evaluation")
    for row in architecture_rows:
        print()
        print(row["architecture"])
        print(f"Cases: {row['cases_correct']}/{row['cases_total']}")
        print(f"Case accuracy: {row['case_accuracy']:.2%}")
        print(f"Exact requirements: {row['exact_requirements']}/{row['requirements_total']}")
        print(f"False accepts: {row['false_accepts']}")
        print(f"False rejects: {row['false_rejects']}")
        print(f"Unusable shapes: {row['unusable_shapes']}")
    print()
    print("| Architecture | Requirement | Cases correct | Total | Case accuracy | Exact success | False accepts | False rejects | Unusable shape |")
    print("|---|---|---:|---:|---:|---|---:|---:|---|")
    for row in requirement_rows:
        print(
            f"| {row['architecture']} | {row['requirement_id']} | {row['cases_correct']} | {row['cases_total']} | "
            f"{row['case_accuracy']:.2%} | {'YES' if row['exact_success'] else 'NO'} | {row['false_accepts']} | "
            f"{row['false_rejects']} | {'YES' if row['unusable_shape'] else 'NO'} |"
        )
    print()
    print(f"Pilot fixtures modified: {'YES' if modified else 'NO'}")
    print("New LLM calls made: NO")


def main() -> int:
    manifest = load_manifest()
    locked_paths = frozen_paths(manifest)
    hashes_before = hash_inventory(locked_paths)
    ontology = Graph().parse(ONTOLOGY_PATH, format="turtle")

    selections = [
        select_artifact(architecture, requirement)
        for architecture in ARCHITECTURES
        for requirement in REQUIREMENTS
    ]
    cases: list[dict[str, Any]] = []
    for selection in selections:
        assigned = [row for row in manifest if row["requirement_id"] == selection["requirement_id"]]
        cases.extend(evaluate_requirement(selection, assigned, ontology))

    hashes_after = hash_inventory(locked_paths)
    modified = hashes_before != hashes_after
    if modified:
        changed = sorted(name for name in hashes_before if hashes_before[name] != hashes_after.get(name))
        raise RuntimeError(f"Frozen Pilot 02 inputs changed during evaluation: {changed}")
    if len(cases) != 195:
        raise RuntimeError(f"Expected 195 case executions; produced {len(cases)}")

    requirement_rows, architecture_rows = summarize(cases)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    public_cases = [{key: value for key, value in row.items() if not key.startswith("_")} for row in cases]
    public_selections = [{key: value for key, value in row.items() if not key.startswith("_")} for row in selections]
    payload = {
        "pilot": "Pilot 02",
        "scope": "RUN01 diagnostic evaluation only",
        "scientific_global_comparison_claimed": False,
        "new_llm_calls_made": False,
        "pilot_fixtures_modified": modified,
        "pyshacl_version": pyshacl.__version__,
        "pyshacl_settings": SETTINGS,
        "ontology_path": rel_repo(ONTOLOGY_PATH),
        "expected_outcome_source": rel_repo(MANIFEST_PATH),
        "frozen_hashes_before": hashes_before,
        "frozen_hashes_after": hashes_after,
        "artifact_selections": public_selections,
        "architecture_summary": architecture_rows,
        "requirement_summary": requirement_rows,
        "case_results": public_cases,
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(CASES_CSV_PATH, public_cases, [
        "architecture", "run", "run_id", "requirement_id", "case_id", "generated_shape_path",
        "generated_shape_sha256", "rdf_fixture_path", "rdf_fixture_sha256", "expected", "actual", "correct",
        "execution_status", "failure_stage", "validation_report_summary", "source_oracle_rationale",
        "mechanical_mismatch_reason",
    ])
    write_csv(REQUIREMENT_CSV_PATH, requirement_rows, [
        "architecture", "requirement_id", "cases_correct", "cases_total", "case_accuracy", "exact_success",
        "expected_pass_correct", "expected_pass_total", "expected_fail_correct", "expected_fail_total",
        "false_accepts", "false_rejects", "unusable_shape", "generation_execution_failure_count",
    ])
    write_csv(SUMMARY_CSV_PATH, architecture_rows, [
        "architecture", "cases_correct", "cases_total", "case_accuracy", "exact_requirements",
        "requirements_total", "requirement_accuracy", "expected_pass_correct", "expected_pass_total",
        "expected_pass_accuracy", "expected_fail_correct", "expected_fail_total", "expected_fail_accuracy",
        "false_accepts", "false_rejects", "generation_execution_failure_count", "unusable_shapes",
        "cases_affected_by_unusable_shapes",
    ])
    DIAGNOSTICS_PATH.write_text(diagnostics_text(cases), encoding="utf-8")
    print_summary(architecture_rows, requirement_rows, modified)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"EVALUATION ABORTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
