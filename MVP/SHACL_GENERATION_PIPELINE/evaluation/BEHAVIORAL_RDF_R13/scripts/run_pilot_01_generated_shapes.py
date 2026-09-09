#!/usr/bin/env python3
"""Evaluate frozen Pilot 01 RDF fixtures against Luna RUN01 generated SHACL."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyshacl
from rdflib import Graph


REPO_ROOT = Path(__file__).resolve().parents[5]
MVP_ROOT = REPO_ROOT / "MVP"
PIPELINE_ROOT = MVP_ROOT / "SHACL_GENERATION_PIPELINE"
PILOT_ROOT = PIPELINE_ROOT / "evaluation" / "BEHAVIORAL_RDF_R13"
EXPERIMENT_ROOT = PIPELINE_ROOT / "experiments"
MANIFEST_PATH = PILOT_ROOT / "manifests" / "pilot_01_manifest.jsonl"
ONTOLOGY_PATH = MVP_ROOT / "BENCHMARK_VOCABULARY" / "FINAL_LOCK_R13" / "ontology" / "nltl_benchmark_vocabulary.ttl"
REPORT_DIR = PILOT_ROOT / "reports"
JSON_PATH = REPORT_DIR / "pilot_01_generated_shape_results.json"
CASES_CSV_PATH = REPORT_DIR / "pilot_01_generated_shape_cases.csv"
SUMMARY_CSV_PATH = REPORT_DIR / "pilot_01_generated_shape_summary.csv"
DIAGNOSTICS_PATH = REPORT_DIR / "pilot_01_generated_shape_diagnostics.txt"

REQUIREMENTS = ("I2-004", "I2-005", "I2-042")
ARCHITECTURES = {
    "FULL": {"directory": "FINAL_LUNA_MAIN", "selection": "final"},
    "NO_SEMANTIC": {"directory": "LUNA_NO_SEMANTIC_VALIDATOR", "selection": "no_semantic"},
    "SINGLESHOT": {"directory": "LUNA_CONTEXTUAL_SINGLESHOT", "selection": "singleshot"},
}
SETTINGS = {"inference": "rdfs", "meta_shacl": True, "advanced": True}

# Captured before generated SHACL was inspected. Any mismatch aborts evaluation.
FROZEN_SHA256 = {
    "manifests/pilot_01_manifest.jsonl": "95001b379c2501b17f3c82dc2c376ac682003208892b21b16bdb9f3cf939b03d",
    "rdf/I2/I2-004/I2-004-F01.ttl": "6c953c72de95b3c385a0b95a45cea50a845d208506f762f51a6d73b875c3a432",
    "rdf/I2/I2-004/I2-004-F02.ttl": "daf3080ae10eef1f0471f809cce4c81bd86a763fc66616c1cdbf4bee9b43075e",
    "rdf/I2/I2-004/I2-004-P01.ttl": "c8d1c9cd1df74f43b277deafaf2074b5d533ecf6eef03b568a19674cfd2638b6",
    "rdf/I2/I2-004/I2-004-P02.ttl": "d641d296c6e0bbd7196b99bfd60637e6049a6440cab929080030df92c9ea5102",
    "rdf/I2/I2-005/I2-005-F01.ttl": "2190b4cc77a6571a651f449f10a791203210c94446865e709e47bcd9125d8863",
    "rdf/I2/I2-005/I2-005-F02.ttl": "bd1df679eb612c82f566a912cc78453a9f6577aec0787e3d40335dc788caafd7",
    "rdf/I2/I2-005/I2-005-F03.ttl": "1c9402f1ddb4dda3d5b2fa9b36c1a17459afbca70e59245fed76e84f1d5242a0",
    "rdf/I2/I2-005/I2-005-P01.ttl": "88f6fdd78a044777abe2fc1b16a4fe3f4a73ca464a6b89ce556ffcaa2a308a95",
    "rdf/I2/I2-042/I2-042-F01.ttl": "384198748e8a8bc794ab1e0b64e19eea1e66073040b0a7522ec7ce7f4ed400fe",
    "rdf/I2/I2-042/I2-042-F02.ttl": "42e11d83f5470898ac323a1945cdc884758520895b7e1223a1882f05c561de4f",
    "rdf/I2/I2-042/I2-042-P01.ttl": "59a427ff4c917b63a5f35b490ad55635c812f87f1255edcf2ee6d7d0eea59203",
    "rdf/I2/I2-042/I2-042-P02.ttl": "c9d46d949bcc0a494e3968b9bf9e44efeeb9162277d9dc83d3f7828950654771",
    "specifications/I2/I2-004.json": "d6413dd4e8771118e455c3f5bb3eada70e141076660b250c777f37842301e823",
    "specifications/I2/I2-005.json": "c56a15e6b82ef593ae4cdcf2facd81cbe2713a57f5b18080ad5bd6b6bd4a7738",
    "specifications/I2/I2-042.json": "fc58412c4e17c02a7f522c80c1ccb0959fccf934afb04a0d98e3f416b386622e",
}


def relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_hashes() -> dict[str, str]:
    return {name: sha256(PILOT_ROOT / name) for name in FROZEN_SHA256}


def assert_frozen(hashes: dict[str, str], stage: str) -> None:
    mismatches = [
        f"{name}: expected {FROZEN_SHA256[name]}, found {digest}"
        for name, digest in hashes.items() if digest != FROZEN_SHA256[name]
    ]
    if mismatches:
        raise RuntimeError(f"Frozen Pilot fixture integrity failure ({stage}): " + "; ".join(mismatches))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_manifest() -> list[dict[str, Any]]:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    counts = Counter(row["requirement_id"] for row in rows)
    if len(rows) != 12 or counts != Counter({requirement: 4 for requirement in REQUIREMENTS}):
        raise RuntimeError(f"Frozen manifest must contain exactly 12 cases, four per requirement; found {dict(counts)}")
    if len({row["case_id"] for row in rows}) != 12:
        raise RuntimeError("Frozen manifest case IDs are not unique")
    for row in rows:
        if row["expected"] not in {"PASS", "FAIL"}:
            raise RuntimeError(f"Invalid manifest verdict for {row['case_id']}: {row['expected']!r}")
        rdf_path = PILOT_ROOT / row["rdf_path"]
        if not rdf_path.is_file():
            raise RuntimeError(f"Manifest RDF does not exist: {rdf_path}")
    return rows


def load_rationales() -> dict[str, str]:
    rationales: dict[str, str] = {}
    for requirement in REQUIREMENTS:
        spec_path = PILOT_ROOT / "specifications" / "I2" / f"{requirement}.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        for case in spec["cases"]:
            rationales[case["case_id"]] = case["rationale"]
    return rationales


def one(items: list[Any], description: str) -> Any:
    if len(items) != 1:
        raise RuntimeError(f"Ambiguous {description}: found {len(items)} candidates")
    return items[0]


def recorded_failure(diagnostics: dict[str, Any], mode: str) -> str | None:
    if mode == "no_semantic":
        validation = diagnostics.get("deterministicValidation", {})
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
    if mode == "singleshot":
        for key, stage in (
            ("extractionStatus", "EXTRACTION_FAILURE"),
            ("rdfParseStatus", "TURTLE_PARSE_FAILURE"),
            ("shaclValidationStatus", "META_SHACL_FAILURE"),
        ):
            if diagnostics.get(key) not in {None, "PASS"}:
                return stage
    return None


def select_artifact(architecture: str, requirement: str) -> dict[str, Any]:
    config = ARCHITECTURES[architecture]
    runs_root = EXPERIMENT_ROOT / config["directory"] / "RUN_01" / "runs"
    run_dir = one(sorted(runs_root.glob(f"RUN-{requirement}-*")), f"RUN01 directory for {architecture}/{requirement}")
    run_rows = [row for row in read_csv(run_dir / "tables" / "runs.csv") if row.get("REQUIREMENT_ID") == requirement]
    run_row = one(run_rows, f"runs.csv row for {architecture}/{requirement}")
    artifact_rows = read_csv(run_dir / "tables" / "artifacts.csv")
    mode = config["selection"]
    diagnostics_path: Path | None = None
    failure_stage: str | None = None

    if mode == "final":
        final_rel = run_row.get("FINAL_SHAPE", "").strip()
        matching = [row for row in artifact_rows if row.get("ARTIFACT_TYPE") == "final_accepted_shape"]
        artifact_row = one(matching, f"final accepted artifact for {architecture}/{requirement}")
        if not final_rel or artifact_row["ARTIFACT_PATH"] != final_rel:
            raise RuntimeError(f"Ambiguous final artifact metadata for {architecture}/{requirement}")
        shape_path = run_dir / final_rel
        if run_row.get("ACCEPTED", "").lower() != "true":
            failure_stage = run_row.get("FINAL_STATUS") or "GENERATION_FAILURE"
    else:
        artifact_type = (
            "no_semantic_validator_candidate_shape" if mode == "no_semantic"
            else "single_shot_extracted_shape"
        )
        artifact_row = one(
            [row for row in artifact_rows if row.get("ARTIFACT_TYPE") == artifact_type],
            f"{artifact_type} artifact for {architecture}/{requirement}",
        )
        shape_path = run_dir / artifact_row["ARTIFACT_PATH"]
        diagnostic_type = (
            "no_semantic_validator_diagnostics" if mode == "no_semantic"
            else "single_shot_diagnostics"
        )
        diagnostic_row = one(
            [row for row in artifact_rows if row.get("ARTIFACT_TYPE") == diagnostic_type],
            f"{diagnostic_type} artifact for {architecture}/{requirement}",
        )
        diagnostics_path = run_dir / diagnostic_row["ARTIFACT_PATH"]
        diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
        failure_stage = recorded_failure(diagnostics, mode)

    if not shape_path.is_file() and failure_stage is None:
        failure_stage = "NO_OUTPUT"
    return {
        "architecture": architecture,
        "architecture_directory": config["directory"],
        "run": "RUN01",
        "run_id": run_row["RUN_ID"],
        "requirement_id": requirement,
        "terminal_status": run_row.get("FINAL_STATUS", ""),
        "generated_shape_path": relative(shape_path) if shape_path.exists() else str(shape_path),
        "generated_shape_sha256": sha256(shape_path) if shape_path.is_file() else None,
        "selection_evidence": relative(run_dir / "tables" / "runs.csv"),
        "diagnostics_path": relative(diagnostics_path) if diagnostics_path else None,
        "recorded_failure_stage": failure_stage,
        "_shape_path": shape_path,
    }


def concise_report(report_text: str, conforms: bool | None, error: str = "") -> str:
    if error:
        return error
    if conforms is True:
        return "Conforms: true"
    messages = [
        line.split("Message:", 1)[1].strip()
        for line in report_text.splitlines() if "Message:" in line
    ]
    return "Conforms: false | " + (" | ".join(dict.fromkeys(messages)) if messages else "SHACL violation")


def evaluate_shape(
    selection: dict[str, Any], cases: list[dict[str, Any]], ontology: Graph, rationales: dict[str, str]
) -> list[dict[str, Any]]:
    shape_path: Path = selection["_shape_path"]
    failure_stage = selection["recorded_failure_stage"]
    shape_graph: Graph | None = None
    shape_text = shape_path.read_text(encoding="utf-8", errors="replace") if shape_path.is_file() else ""

    if failure_stage is None:
        try:
            shape_graph = Graph().parse(shape_path, format="turtle")
        except Exception as exc:
            failure_stage = "TURTLE_PARSE_FAILURE"
            preflight_error = f"{type(exc).__name__}: {exc}"
        else:
            preflight_error = ""
    else:
        preflight_error = f"Recorded pipeline failure: {failure_stage}"

    results: list[dict[str, Any]] = []
    for case in cases:
        rdf_path = PILOT_ROOT / case["rdf_path"]
        report_text = ""
        error = preflight_error
        actual: str | None = None
        case_failure = failure_stage
        execution_status = "UNUSABLE_SHAPE" if failure_stage else "PENDING"

        if shape_graph is not None and failure_stage is None:
            try:
                data_graph = Graph().parse(rdf_path, format="turtle")
                conforms, report_graph, report_text = pyshacl.validate(
                    data_graph,
                    shacl_graph=shape_graph,
                    ont_graph=ontology,
                    inference="rdfs",
                    meta_shacl=True,
                    advanced=True,
                )
                if not isinstance(report_graph, Graph):
                    raise RuntimeError(f"SHACL engine rejected the shape: {report_text}")
                actual = "PASS" if bool(conforms) else "FAIL"
                execution_status = "SUCCESS"
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                lowered = error.lower()
                case_failure = "META_SHACL_FAILURE" if "meta-shacl" in lowered or "shape" in lowered else "PYSHACL_EXECUTION_FAILURE"
                execution_status = "UNUSABLE_SHAPE"

        correct = execution_status == "SUCCESS" and actual == case["expected"]
        results.append({
            "architecture": selection["architecture"],
            "run": "RUN01",
            "run_id": selection["run_id"],
            "requirement_id": case["requirement_id"],
            "case_id": case["case_id"],
            "generated_shape_path": selection["generated_shape_path"],
            "generated_shape_sha256": selection["generated_shape_sha256"],
            "rdf_fixture_path": relative(rdf_path),
            "rdf_fixture_sha256": sha256(rdf_path),
            "expected": case["expected"],
            "actual": actual if actual is not None else "UNUSABLE",
            "correct": correct,
            "execution_status": execution_status,
            "failure_stage": case_failure,
            "validation_report_summary": concise_report(report_text, None if actual is None else actual == "PASS", error),
            "validation_report_text": report_text or error,
            "source_oracle_rationale": rationales[case["case_id"]],
            "_rdf_text": rdf_path.read_text(encoding="utf-8"),
            "_shape_text": shape_text,
        })
    return results


def summarize(cases: list[dict[str, Any]], selections: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    architecture_rows: list[dict[str, Any]] = []
    requirement_rows: list[dict[str, Any]] = []
    for architecture in ARCHITECTURES:
        arch_cases = [row for row in cases if row["architecture"] == architecture]
        exact = 0
        for requirement in REQUIREMENTS:
            req_cases = [row for row in arch_cases if row["requirement_id"] == requirement]
            correct = sum(row["correct"] for row in req_cases)
            success = correct == len(req_cases) == 4
            exact += success
            requirement_rows.append({
                "architecture": architecture,
                "requirement_id": requirement,
                "cases_correct": correct,
                "total": len(req_cases),
                "exact_success": success,
            })
        pass_cases = [row for row in arch_cases if row["expected"] == "PASS"]
        fail_cases = [row for row in arch_cases if row["expected"] == "FAIL"]
        unusable_requirements = {
            row["requirement_id"] for row in arch_cases if row["execution_status"] != "SUCCESS"
        }
        correct_total = sum(row["correct"] for row in arch_cases)
        architecture_rows.append({
            "architecture": architecture,
            "cases_correct": correct_total,
            "cases_total": 12,
            "case_accuracy": correct_total / 12,
            "exact_requirements": exact,
            "requirements_total": 3,
            "requirement_accuracy": exact / 3,
            "expected_pass_correct": sum(row["correct"] for row in pass_cases),
            "expected_pass_total": len(pass_cases),
            "expected_pass_accuracy": sum(row["correct"] for row in pass_cases) / len(pass_cases),
            "expected_fail_correct": sum(row["correct"] for row in fail_cases),
            "expected_fail_total": len(fail_cases),
            "expected_fail_accuracy": sum(row["correct"] for row in fail_cases) / len(fail_cases),
            "false_accepts": sum(row["expected"] == "FAIL" and row["actual"] == "PASS" for row in arch_cases),
            "false_rejects": sum(row["expected"] == "PASS" and row["actual"] == "FAIL" for row in arch_cases),
            "generation_execution_failure_count": len(unusable_requirements),
            "unusable_shapes": len(unusable_requirements),
            "cases_affected_by_unusable_shapes": sum(row["execution_status"] != "SUCCESS" for row in arch_cases),
        })
    return architecture_rows, requirement_rows


def markdown_tables(summary: list[dict[str, Any]], requirements: list[dict[str, Any]], cases: list[dict[str, Any]]) -> str:
    lines = [
        "Pilot 01 generated-shape behavioral evaluation",
        "",
        "| Architecture | Cases correct | Case accuracy | Exact requirements | Requirement accuracy | Expected PASS accuracy | Expected FAIL accuracy | False accepts | False rejects | Unusable shapes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['architecture']} | {row['cases_correct']}/12 | {row['case_accuracy']:.2%} | "
            f"{row['exact_requirements']}/3 | {row['requirement_accuracy']:.2%} | "
            f"{row['expected_pass_correct']}/{row['expected_pass_total']} ({row['expected_pass_accuracy']:.2%}) | "
            f"{row['expected_fail_correct']}/{row['expected_fail_total']} ({row['expected_fail_accuracy']:.2%}) | "
            f"{row['false_accepts']} | {row['false_rejects']} | {row['unusable_shapes']} |"
        )
    lines.extend([
        "",
        "| Architecture | Requirement | Cases correct | Total | Exact success |",
        "|---|---|---:|---:|---|",
    ])
    for row in requirements:
        lines.append(
            f"| {row['architecture']} | {row['requirement_id']} | {row['cases_correct']} | "
            f"{row['total']} | {'YES' if row['exact_success'] else 'NO'} |"
        )
    lines.extend([
        "",
        "| Architecture | Requirement | Case | Expected | Actual | Correct | Execution | Failure stage |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for row in cases:
        lines.append(
            f"| {row['architecture']} | {row['requirement_id']} | {row['case_id']} | {row['expected']} | "
            f"{row['actual']} | {'YES' if row['correct'] else 'NO'} | {row['execution_status']} | {row['failure_stage'] or ''} |"
        )
    return "\n".join(lines)


def diagnostics_text(cases: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for row in cases:
        fields = [
            f"architecture: {row['architecture']}",
            f"requirement_id: {row['requirement_id']}",
            f"case_id: {row['case_id']}",
            f"expected: {row['expected']}",
            f"actual: {row['actual']}",
            f"correct: {str(row['correct']).lower()}",
            f"generated_shape_path: {row['generated_shape_path']}",
            f"rdf_fixture_path: {row['rdf_fixture_path']}",
            f"execution_status: {row['execution_status']}",
            f"failure_stage: {row['failure_stage'] or ''}",
        ]
        if not row["correct"]:
            fields.extend([
                "source_oracle_rationale: " + row["source_oracle_rationale"],
                "--- RDF INPUT ---",
                row["_rdf_text"].rstrip(),
                "--- GENERATED SHACL ---",
                row["_shape_text"].rstrip() or "<NO USABLE SHACL ARTIFACT>",
                "--- PYSHACL REPORT ---",
                row["validation_report_text"].rstrip() or "<NO REPORT>",
                "--- EXPECTED ---",
                row["expected"],
                "--- ACTUAL ---",
                row["actual"],
            ])
        blocks.append("\n".join(fields))
    return "\n\n".join(blocks)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    initial_hashes = frozen_hashes()
    assert_frozen(initial_hashes, "before evaluation")
    manifest = load_manifest()
    rationales = load_rationales()
    ontology = Graph().parse(ONTOLOGY_PATH, format="turtle")

    selections: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for architecture in ARCHITECTURES:
        for requirement in REQUIREMENTS:
            selection = select_artifact(architecture, requirement)
            selections.append(selection)
            assigned = [row for row in manifest if row["requirement_id"] == requirement]
            cases.extend(evaluate_shape(selection, assigned, ontology, rationales))

    final_hashes = frozen_hashes()
    assert_frozen(final_hashes, "after evaluation")
    fixtures_modified = initial_hashes != final_hashes
    if fixtures_modified:
        raise RuntimeError("Pilot fixtures changed during evaluation")

    summary, requirement_summary = summarize(cases, selections)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    public_selections = [{key: value for key, value in item.items() if not key.startswith("_")} for item in selections]
    public_cases = [{key: value for key, value in item.items() if not key.startswith("_")} for item in cases]
    payload = {
        "pilot": "Pilot 01",
        "run": "RUN01",
        "pyshacl_version": pyshacl.__version__,
        "pyshacl_settings": SETTINGS,
        "expected_outcome_source": relative(MANIFEST_PATH),
        "pilot_fixtures_modified": fixtures_modified,
        "frozen_fixture_sha256": final_hashes,
        "artifact_selections": public_selections,
        "architecture_summary": summary,
        "requirement_summary": requirement_summary,
        "case_results": public_cases,
    }
    JSON_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(CASES_CSV_PATH, public_cases, [
        "architecture", "run", "run_id", "requirement_id", "case_id", "generated_shape_path",
        "generated_shape_sha256", "rdf_fixture_path", "rdf_fixture_sha256", "expected", "actual",
        "correct", "execution_status", "failure_stage", "validation_report_summary", "source_oracle_rationale",
    ])
    write_csv(SUMMARY_CSV_PATH, summary, list(summary[0].keys()))

    tables = markdown_tables(summary, requirement_summary, cases)
    diagnostics = diagnostics_text(cases)
    full_diagnostics = tables + "\n\nCASE DIAGNOSTICS\n\n" + diagnostics + "\n"
    DIAGNOSTICS_PATH.write_text(full_diagnostics, encoding="utf-8")
    print(full_diagnostics, end="")
    print("Pilot fixtures modified: NO")
    for row in summary:
        print(
            f"{row['architecture']}: {row['cases_correct']}/12 cases ({row['case_accuracy']:.2%}); "
            f"{row['exact_requirements']}/3 exact requirements ({row['requirement_accuracy']:.2%})"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"EVALUATION ABORTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
