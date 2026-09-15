#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ARCHITECTURES = ("V2_FALLBACK25", "NO_SEMANTIC", "SINGLESHOT")
SEED_EXPECTED = "NLTL-MANUAL-AUDIT-20260915-v1"
BASELINE_RUN_ID = "BEHAVIORAL-R13-20260911T080233539977Z"
V2_RUN_ID = "BEHAVIORAL-R13-FULL-REPAIR-V2-RUN01-20260915T144116505813Z"
V2_A4_RUN_ID = "BEHAVIORAL-R13-FULL-REPAIR-V2-REJECTED-A4-RUN01-20260915T155743340362Z"
SOURCE_LEDGER_HASHES = {
    "historical_three": "41a92cd847032c84c78bbb8558736483201fad34b93e85fe100fe5db28e654f7",
    "full_repair_v2": "657a34b991f826a0bc589c932eca040a148625fb080cc50b599d7a88bca87c8a",
    "rejected_attempt4": "34648dc6c4f63167c8eadf47ce3a8e0b58d1af77d2b601479d44b1c948f487a5",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def csv_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def actual_verdict(row: dict[str, Any] | None) -> str:
    if not row or row.get("execution_status") != "EXECUTED":
        return "NO_VERDICT"
    value = row.get("actual_conforms")
    return "PASS" if value is True else "FAIL" if value is False else "NO_VERDICT"


def source_pdf(repo: Path, family: str) -> Path | None:
    choices = {
        "I2": repo / "MVP/RELEVANT FILES/ur-i2rev4.pdf",
        "TRAFICOM": repo / "MVP/RELEVANT FILES/TRAFICOM.pdf",
        "IMO": repo / "MVP/RELEVANT FILES/MSC.385(94).pdf",
        "IMO26": repo / "MVP/OLD FILES/Haitham_Data/2Q191E_Supplement_January2026_EBK.pdf",
    }
    candidate = choices.get(family)
    return candidate if candidate and candidate.is_file() else None


def find_deterministic_evidence(repo: Path, record: dict[str, Any]) -> dict[str, Any]:
    run_metadata = repo / record["run_metadata_path"]
    artifact_metadata = repo / record["artifact_metadata_path"]
    run = csv_rows(run_metadata)[0]
    artifacts = csv_rows(artifact_metadata)
    shape_path = record.get("shape_path")
    attempt_match = re.search(r"attempt_(\d+)", shape_path or "")
    attempt = int(attempt_match.group(1)) if attempt_match else int(run.get("ATTEMPTS") or 0) or None
    evidence_path: Path | None = None
    payload: dict[str, Any] = {}
    if attempt is not None:
        artifact_types = (
            "deterministic_validation",
            "no_semantic_validator_diagnostics",
            "single_shot_diagnostics",
        )
        matches = [
            row for row in artifacts
            if row.get("ARTIFACT_TYPE") in artifact_types
            and (not row.get("ITERATION") or int(row["ITERATION"]) == attempt)
        ]
        if matches:
            chosen = matches[-1]
            evidence_path = artifact_metadata.parent.parent / chosen["ARTIFACT_PATH"]
            if evidence_path.is_file() and sha256(evidence_path) == chosen["SHA256"]:
                payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    validation = payload.get("deterministicValidation", payload)
    valid = validation.get("valid")
    if valid is None and validation:
        checks = [
            validation.get("extraction_valid"), validation.get("turtle_valid"),
            validation.get("shacl_structure_valid"), validation.get("meta_shacl_valid"),
            validation.get("vocabulary_valid"), validation.get("datatype_unit_valid"),
            validation.get("target_path_valid"),
        ]
        present = [value for value in checks if isinstance(value, bool)]
        valid = all(present) if present else None
    if valid is True:
        status = "PASS"
    elif valid is False:
        status = "FAIL"
    else:
        status = record.get("deterministic_status") or "UNAVAILABLE"
    semantic_review_ran = False
    if record["architecture"] == "V2_FALLBACK25" and attempt is not None:
        semantic_review_ran = any(
            row.get("ARTIFACT_TYPE") == "validator_raw_response"
            and row.get("ITERATION") and int(row["ITERATION"]) == attempt
            for row in artifacts
        )
    return {
        "generation_pipeline_run_id": run["RUN_ID"],
        "candidate_attempt": attempt,
        "deterministic_status": status,
        "deterministic_validation_path": str(evidence_path.relative_to(repo)) if evidence_path else None,
        "deterministic_validation_sha256": sha256(evidence_path) if evidence_path else None,
        "deterministic_findings": {
            "valid": valid,
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", []),
            "extraction_valid": validation.get("extraction_valid", payload.get("extractionStatus")),
            "turtle_valid": validation.get("turtle_valid", payload.get("rdfParseStatus")),
            "shacl_structure_valid": validation.get("shacl_structure_valid", payload.get("shaclValidationStatus")),
            "meta_shacl_valid": validation.get("meta_shacl_valid"),
            "vocabulary_valid": validation.get("vocabulary_valid", payload.get("vocabularyDiagnosticStatus")),
            "datatype_unit_valid": validation.get("datatype_unit_valid"),
            "target_path_valid": validation.get("target_path_valid"),
        },
        "semantic_review_ran_for_selected_attempt": semantic_review_ran,
        "semantic_review_note": (
            "A preserved validator response exists for this V2 attempt."
            if semantic_review_ran else
            "No semantic-review response exists for this selected attempt; deterministic routing is not an LLM review."
            if record["architecture"] == "V2_FALLBACK25" else
            "This architecture disables semantic-review calls."
        ),
    }


def inventory_eligible_pools(results_root: Path) -> dict[str, list[str]]:
    pools = {architecture: [] for architecture in ARCHITECTURES}
    historical = json.loads((results_root / BASELINE_RUN_ID / "run_manifest.json").read_text(encoding="utf-8"))
    if historical.get("status") == "COMPLETE" and historical.get("selected_requirements") == 268 and historical.get("selected_cases") == 2186:
        pools["NO_SEMANTIC"].append("RUN_01")
        pools["SINGLESHOT"].append("RUN_01")
    v2 = json.loads((results_root / V2_RUN_ID / "run_manifest.json").read_text(encoding="utf-8"))
    a4 = json.loads((results_root / V2_A4_RUN_ID / "run_manifest.json").read_text(encoding="utf-8"))
    if (
        v2.get("status") == "COMPLETE"
        and v2.get("selected_requirements") == 268
        and v2.get("selected_cases") == 2186
        and a4.get("status") == "COMPLETE"
        and a4.get("diagnostic_only") is True
        and a4.get("expected_case_rows") == 199
    ):
        pools["V2_FALLBACK25"].append("RUN_01")
    return pools


def chosen_run(seed: str, architecture: str, requirement_id: str, pool: list[str]) -> str:
    if not pool:
        raise RuntimeError(f"No eligible evaluated run for {architecture}")
    return min(
        pool,
        key=lambda run: hashlib.sha256(f"{seed}|RUN|{architecture}|{requirement_id}|{run}".encode()).hexdigest(),
    )


def render_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def packet_requirement(
    repo: Path,
    requirement_record: dict[str, Any],
    architecture_records: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> str:
    requirement_id = requirement_record["requirement_id"]
    context = json.loads((repo / requirement_record["context_path"]).read_text(encoding="utf-8"))
    requirement = context["requirement"]
    pdf = source_pdf(repo, requirement_record["source_family"])
    lines = [
        "=" * 100,
        f"REQUIREMENT {requirement_record['order']:03d}: {requirement_id}",
        "=" * 100,
        "",
        "A. STABLE IDENTITY AND SOURCE EVIDENCE",
        f"Audit order: {requirement_record['order']}",
        f"Batch: {requirement_record['batch']}",
        f"Requirement ID: {requirement_id}",
        f"Source family: {requirement_record['source_family']}",
        f"Verification mode: {requirement_record['verification_mode']}",
        f"Source document: {requirement.get('source')}",
        f"Source revision: {requirement.get('edition')}",
        f"Clause / section / page: {requirement.get('clause')} / {requirement.get('section')} / {requirement.get('page')}",
        f"Source URL: {requirement.get('sourceUrl')}",
        f"Local source PDF: {pdf.relative_to(repo) if pdf else 'MISSING'}",
        f"Local source PDF SHA-256: {sha256(pdf) if pdf else 'UNAVAILABLE'}",
        f"Locked context path: {requirement_record['context_path']}",
        f"Original source text:\n{requirement.get('sourceText')}",
        f"Normalized requirement:\n{requirement.get('normalizedRequirement')}",
        f"Required inputs: {requirement.get('requiredInputs')}",
        "",
        "Locked context, definitions, ownership, units, and dependency contract:",
        render_json({
            "terms": context.get("terms", []),
            "node_patterns": context.get("node_patterns", []),
            "dependency_contract": context.get("selection", {}).get("dependencyContract"),
            "semantic_obligations": context.get("selection", {}).get("semanticObligations", []),
            "exclusive_property_groups": context.get("selection", {}).get("exclusivePropertyGroups", []),
            "source_lock": context.get("source_lock"),
        }),
        "",
        "B. SHARED SAMPLED RDF SCENARIOS",
        f"Total frozen RDF cases for this requirement: {requirement_record['total_case_count']}",
        "The following fixed cases are shared across all three architectures. The sample is not the full case set.",
    ]
    for case in cases:
        lines.extend([
            "",
            f"CASE {case['case_id']}",
            f"Original expected verdict: {case['expected_outcome']}",
            f"Original rationale: {case.get('source_oracle_rationale')}",
            f"Source clause: {case.get('source_clause')}",
            f"Test pattern: {case.get('test_pattern') or 'UNSPECIFIED'}",
            f"RDF path: {case['rdf_path_full']}",
            f"RDF SHA-256: {case['rdf_sha256']}",
            "Full unmodified RDF Turtle:",
            "```turtle",
            case["rdf_text"],
            "```",
        ])
    unreviewed = requirement_record.get("unreviewed_case_inventory", [])
    lines.extend(["", "Unreviewed frozen case inventory:", render_json(unreviewed)])

    for record in architecture_records:
        lines.extend([
            "",
            f"C. ARCHITECTURE SPECIMEN: {record['architecture']}",
            f"Selected generation run: {record['generation_run']}",
            f"Original generation pipeline run ID: {record.get('generation_pipeline_run_id')}",
            f"Output-selection policy: {record.get('output_selection_policy')}",
            f"Original generation status: {record.get('original_generation_status')}",
            f"Output origin/status: {record.get('output_origin')}",
            f"Candidate attempt: {record.get('candidate_attempt') or 'UNKNOWN'}",
            f"Candidate path: {record.get('shape_path') or 'MISSING'}",
            f"Candidate SHA-256: {record.get('shape_sha256') or 'UNAVAILABLE'}",
            f"Artifact hash verified: {record.get('artifact_hash_verified')}",
            f"Recorded Turtle parse status: {record.get('parse_status')}",
            f"Deterministic status: {record.get('deterministic_status')}",
            f"Deterministic evidence path: {record.get('deterministic_validation_path') or 'UNAVAILABLE'}",
            f"Semantic review ran for selected attempt: {record.get('semantic_review_ran_for_selected_attempt')}",
            f"Semantic review note: {record.get('semantic_review_note')}",
            "Deterministic findings:",
            render_json(record.get("deterministic_findings")),
            "Context and dependency evidence:",
            f"Context path: {record.get('context_path')}",
            render_json({
                "dependency_contract": context.get("selection", {}).get("dependencyContract"),
                "usage_policy": context.get("usage_policy"),
            }),
            "Full unmodified selected SHACL:",
            "```turtle",
            record.get("shape_text") if record.get("shape_text") is not None else "MISSING — no selected specimen exists under this architecture policy.",
            "```",
            "",
            f"D. RECORDED CASE OBSERVATIONS FOR {record['architecture']}",
        ])
        for observation in record["selected_observations"]:
            lines.extend([
                "",
                f"Case ID: {observation['case_id']}",
                f"Original expected verdict: {observation['expected_outcome']}",
                f"Recorded actual verdict: {observation['actual_verdict']}",
                f"Execution status: {observation['execution_status']}",
                f"Original behavioural match: {observation['behavioral_match']}",
                f"Original outcome class: {observation['outcome_class']}",
                f"Focus nodes: {render_json(observation['focus_nodes'])}",
                f"Constraint components: {render_json(observation['constraint_components'])}",
                f"Result paths: {render_json(observation['result_paths'])}",
                f"Report messages: {render_json(observation['result_messages'])}",
                f"Exception: {observation['exception_type'] or 'NONE'}: {observation['exception_message'] or ''}",
                f"Source ledger: {observation['source_ledger_path']}",
                f"Report graph path: {observation['report_graph_full_path'] or 'UNAVAILABLE'}",
                f"Report text path: {observation['report_text_full_path'] or 'UNAVAILABLE'}",
                f"Observation already recorded: {observation['already_recorded']}",
            ])
        lines.extend([
            "",
            "E. LOCAL PROVENANCE",
            f"Source evaluation run ID: {record.get('source_evaluation_run_id')}",
            f"Source ledger: {record.get('source_ledger_path')}",
            f"Artifact path/hash: {record.get('shape_path') or 'MISSING'} / {record.get('shape_sha256') or 'UNAVAILABLE'}",
            f"Run metadata: {record.get('run_metadata_path')}",
            f"Artifact metadata: {record.get('artifact_metadata_path')}",
            "These are recorded observations. No evaluation was executed while packaging.",
        ])
    lines.extend([
        "",
        "F. MANUAL REVIEW CHECKLIST — DO NOT PREFILL GRADES",
        "Q1 Applicability: Does the shape activate for the correct ships, conditions, and scope?",
        "Q2 Ownership / paths: Are target ownership and property paths correct?",
        "Q3 Required constraints: Are all mandatory obligations represented?",
        "Q4 Units / calculation: Are quantities, units, formulae, and comparisons correct?",
        "Q5 Branches / boundaries: Are alternatives, exceptions, equality boundaries, and conditionals correct?",
        "Q6 No extra restrictions: Does the shape avoid requirements not supported by the source?",
        "Q7 Traceability / clarity: Is the implementation understandable and traceable to the cited evidence?",
        "Record grades, reviewer identity, evidence, and notes in the workbook. Do not infer full-requirement correctness from these two cases.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproduce the frozen NLTL manual-audit evidence package")
    parser.add_argument("--audit-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    audit_root = args.audit_root.resolve()
    repo = audit_root.parents[4]
    evaluation = repo / "MVP/SHACL_GENERATION_PIPELINE/evaluation"
    results_root = evaluation / "experiment_results"
    originals = audit_root / "originals"
    batches_dir = audit_root / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)

    original_selection_path = originals / "audit_selection.json"
    selection = json.loads(original_selection_path.read_text(encoding="utf-8"))
    if selection["seed"] != SEED_EXPECTED or len(selection["requirements"]) != 268:
        raise RuntimeError("Unexpected audit seed or requirement population")
    if len(set(selection["requirements"])) != 268:
        raise RuntimeError("Duplicate requirement in frozen audit order")

    ledger_paths = {
        "historical_three": results_root / BASELINE_RUN_ID / "raw_case_results.jsonl",
        "full_repair_v2": results_root / V2_RUN_ID / "raw_case_results.jsonl",
        "rejected_attempt4": results_root / V2_A4_RUN_ID / "raw_case_results.jsonl",
    }
    for name, path in ledger_paths.items():
        actual = sha256(path)
        if actual != SOURCE_LEDGER_HASHES[name]:
            raise RuntimeError(f"Source ledger identity mismatch: {path}: {actual}")
    historical_rows = load_jsonl(ledger_paths["historical_three"])
    v2_rows = load_jsonl(ledger_paths["full_repair_v2"])
    a4_rows = load_jsonl(ledger_paths["rejected_attempt4"])
    pools = inventory_eligible_pools(results_root)
    if any(pool != ["RUN_01"] for pool in pools.values()):
        raise RuntimeError(f"Eligible run pools differ from frozen no-review state: {pools}")

    historical_index = {
        (row.get("generation_run", "RUN_01"), row["configuration"], row["requirement_id"], row["case_id"]): row
        for row in historical_rows
    }
    v2_index = {(row["generation_run"], row["requirement_id"], row["case_id"]): row for row in v2_rows}
    a4_index = {(row["generation_run"], row["requirement_id"], row["case_id"]): row for row in a4_rows}
    historical_by_requirement: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in historical_rows:
        historical_by_requirement[(row.get("generation_run", "RUN_01"), row["configuration"], row["requirement_id"])].append(row)
    v2_by_requirement: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in v2_rows:
        v2_by_requirement[(row["generation_run"], row["requirement_id"])].append(row)
    a4_by_requirement: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in a4_rows:
        a4_by_requirement[(row["generation_run"], row["requirement_id"])].append(row)
    case_index: dict[str, dict[str, Any]] = {}
    cases_by_requirement: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in v2_rows:
        case_index[row["case_id"]] = row
        cases_by_requirement[row["requirement_id"]].append(row)

    records_by_key = {(row["architecture"], row["requirement_id"]): dict(row) for row in selection["records"]}
    missing: list[str] = []
    enriched_records: list[dict[str, Any]] = []
    for requirement_id in selection["requirements"]:
        selected_cases = selection["cases_per_requirement"][requirement_id]
        if len(selected_cases) > 2 or any(case not in case_index for case in selected_cases):
            raise RuntimeError(f"Invalid frozen case selection for {requirement_id}")
        expected_classes = {case_index[case]["expected_outcome"] for case in selected_cases}
        if expected_classes != {"PASS", "FAIL"}:
            raise RuntimeError(f"Frozen selection does not contain PASS and FAIL for {requirement_id}")
        for architecture in ARCHITECTURES:
            record = records_by_key[(architecture, requirement_id)]
            selected_run = chosen_run(selection["seed"], architecture, requirement_id, pools[architecture])
            if record["generation_run"] != selected_run:
                raise RuntimeError(f"Existing selected run changed for {architecture} {requirement_id}")
            deterministic = find_deterministic_evidence(repo, record)
            record.update(deterministic)
            record["available_evaluated_runs"] = sorted(pools[architecture])
            record["selected_generation_run"] = selected_run
            record["run_choice_digest"] = hashlib.sha256(
                f"{selection['seed']}|RUN|{architecture}|{requirement_id}|{selected_run}".encode()
            ).hexdigest()
            record["output_selection_policy"] = (
                "Official accepted FULL_REPAIR_V2 final shape; otherwise only the preserved final attempt-4 candidate recorded by the rejected-attempt-4 diagnostic."
                if architecture == "V2_FALLBACK25" else
                "The single generated candidate from the no-semantic architecture, including explicit failed or unavailable generation outcomes."
                if architecture == "NO_SEMANTIC" else
                "The one-shot extracted candidate, including explicit failed or unavailable generation outcomes."
            )
            shape_path = repo / record["shape_path"] if record.get("shape_path") else None
            record["artifact_hash_verified"] = bool(
                shape_path and shape_path.is_file() and sha256(shape_path) == record.get("shape_sha256")
            )
            if shape_path and shape_path.is_file():
                if not record["artifact_hash_verified"]:
                    raise RuntimeError(f"Artifact hash mismatch: {record['shape_path']}")
                record["shape_text"] = shape_path.read_text(encoding="utf-8")
            else:
                record["shape_text"] = None
                missing.append(f"MISSING SHACL | {architecture} | {requirement_id} | status={record['original_generation_status']} | locator={record.get('shape_path')}")
            record["total_case_count"] = len(cases_by_requirement[requirement_id])
            observations = []
            source_ledger_name = "historical_three"
            source_eval_id = BASELINE_RUN_ID
            for case_id in selected_cases:
                if architecture == "V2_FALLBACK25":
                    if record["output_origin"] == "REJECTED_ATTEMPT_04":
                        row = a4_index.get((selected_run, requirement_id, case_id))
                        source_ledger_name, source_eval_id = "rejected_attempt4", V2_A4_RUN_ID
                    else:
                        row = v2_index.get((selected_run, requirement_id, case_id))
                        source_ledger_name, source_eval_id = "full_repair_v2", V2_RUN_ID
                else:
                    config = "NO_SEMANTIC" if architecture == "NO_SEMANTIC" else "SINGLESHOT"
                    row = historical_index.get((selected_run, config, requirement_id, case_id))
                if row is None:
                    missing.append(f"NOT_EVALUATED | {architecture} | {requirement_id} | {case_id}")
                ledger_path = ledger_paths[source_ledger_name]
                result_base = ledger_path.parent
                report_graph = row.get("report_graph_path") if row else None
                report_text = row.get("report_text_path") if row else None
                observations.append({
                    "case_id": case_id,
                    "expected_outcome": case_index[case_id]["expected_outcome"],
                    "actual_verdict": actual_verdict(row),
                    "execution_status": row.get("execution_status", "NOT_EVALUATED") if row else "NOT_EVALUATED",
                    "behavioral_match": row.get("behavioral_match") if row else None,
                    "outcome_class": row.get("outcome_class", "NOT_EVALUATED") if row else "NOT_EVALUATED",
                    "focus_nodes": row.get("focus_nodes", []) if row else [],
                    "constraint_components": row.get("constraint_components", []) if row else [],
                    "result_paths": row.get("result_paths", []) if row else [],
                    "result_messages": row.get("result_messages", []) if row else [],
                    "exception_type": row.get("exception_type") if row else None,
                    "exception_message": row.get("exception_message") if row else "Observation absent",
                    "source_ledger_path": str(ledger_path.relative_to(repo)),
                    "source_ledger_sha256": SOURCE_LEDGER_HASHES[source_ledger_name],
                    "report_graph_full_path": str((result_base / report_graph).relative_to(repo)) if report_graph else None,
                    "report_text_full_path": str((result_base / report_text).relative_to(repo)) if report_text else None,
                    "already_recorded": row is not None,
                })
            record["source_ledger_path"] = observations[0]["source_ledger_path"]
            record["source_ledger_sha256"] = observations[0]["source_ledger_sha256"]
            record["source_evaluation_run_id"] = source_eval_id
            record["selected_observations"] = observations
            if architecture == "V2_FALLBACK25":
                full_rows = (
                    a4_by_requirement[(selected_run, requirement_id)]
                    if record["output_origin"] == "REJECTED_ATTEMPT_04"
                    else v2_by_requirement[(selected_run, requirement_id)]
                )
            else:
                config = "NO_SEMANTIC" if architecture == "NO_SEMANTIC" else "SINGLESHOT"
                full_rows = historical_by_requirement[(selected_run, config, requirement_id)]
            if len(full_rows) != record["total_case_count"]:
                raise RuntimeError(
                    f"Full-set observation mismatch for {architecture} {requirement_id}: "
                    f"{len(full_rows)} != {record['total_case_count']}"
                )
            executed = sum(row.get("execution_status") == "EXECUTED" for row in full_rows)
            correct = sum(row.get("behavioral_match") is True for row in full_rows)
            record["full_case_metrics"] = {
                "cases_executed": executed,
                "cases_total": record["total_case_count"],
                "cases_correct": correct,
                "every_case_correct": int(correct == record["total_case_count"]),
            }
            enriched_records.append(record)

    enriched_by_key = {(row["architecture"], row["requirement_id"]): row for row in enriched_records}
    packet_files = []
    for batch_number in range(1, 28):
        batch = f"BATCH_{batch_number:02d}"
        batch_requirements = [req for req in selection["requirements"] if records_by_key[("V2_FALLBACK25", req)]["batch"] == batch]
        expected_count = 8 if batch_number == 27 else 10
        if len(batch_requirements) != expected_count:
            raise RuntimeError(f"{batch} has {len(batch_requirements)} requirements")
        text_parts = [
            f"NLTL MANUAL AUDIT EVIDENCE — {batch}",
            f"Seed: {selection['seed']}",
            f"Requirements: {', '.join(batch_requirements)}",
            "Architecture specimens: V2_FALLBACK25, NO_SEMANTIC, SINGLESHOT",
            "This packet contains recorded evidence only. It assigns no manual grades and executes no evaluation.",
            "",
        ]
        metadata_records = []
        for requirement_id in batch_requirements:
            base = enriched_by_key[("V2_FALLBACK25", requirement_id)]
            selected_cases = []
            for case_id in selection["cases_per_requirement"][requirement_id]:
                row = case_index[case_id]
                rdf_path = evaluation / "BEHAVIORAL_RDF_R13" / row["rdf_path"]
                if sha256(rdf_path) != row["rdf_sha256"]:
                    raise RuntimeError(f"RDF hash mismatch: {rdf_path}")
                selected_cases.append({
                    "case_id": case_id,
                    "expected_outcome": row["expected_outcome"],
                    "source_oracle_rationale": row.get("source_oracle_rationale"),
                    "source_clause": row.get("source_clause"),
                    "test_pattern": row.get("test_pattern"),
                    "rdf_path_full": str(rdf_path.relative_to(repo)),
                    "rdf_sha256": row["rdf_sha256"],
                    "rdf_text": rdf_path.read_text(encoding="utf-8"),
                })
            base["unreviewed_case_inventory"] = [
                {"case_id": row["case_id"], "expected": row["expected_outcome"], "pattern": row.get("test_pattern")}
                for row in sorted(cases_by_requirement[requirement_id], key=lambda item: item["case_id"])
                if row["case_id"] not in selection["cases_per_requirement"][requirement_id]
            ]
            architecture_records = [enriched_by_key[(architecture, requirement_id)] for architecture in ARCHITECTURES]
            text_parts.append(packet_requirement(repo, base, architecture_records, selected_cases))
            metadata_records.append({
                "order": base["order"],
                "batch": batch,
                "requirement_id": requirement_id,
                "source_id": base["source_id"],
                "source_family": base["source_family"],
                "verification_mode": base["verification_mode"],
                "selected_cases": [{key: case[key] for key in ("case_id", "expected_outcome", "rdf_path_full", "rdf_sha256")} for case in selected_cases],
                "architectures": [
                    {key: record.get(key) for key in (
                        "architecture", "generation_run", "generation_pipeline_run_id", "output_origin",
                        "original_generation_status", "candidate_attempt", "shape_path", "shape_sha256",
                        "artifact_hash_verified", "deterministic_status", "deterministic_validation_path",
                        "semantic_review_ran_for_selected_attempt", "source_evaluation_run_id", "source_ledger_path",
                    )}
                    for record in architecture_records
                ],
            })
        text_path = batches_dir / f"{batch}.txt"
        json_path = batches_dir / f"{batch}.json"
        text_path.write_text("\n".join(text_parts), encoding="utf-8")
        json_path.write_text(json.dumps({"batch": batch, "requirements": metadata_records}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        packet_files.extend([text_path, json_path])

    selection["run_selection"] = {
        "algorithm": "Choose the run with minimum SHA256(seed + '|RUN|' + architecture + '|' + requirement_id + '|' + generation_run).",
        "eligible_run_pools": pools,
        "pool_result": "Only RUN_01 has a completed compatible 268-requirement / 2,186-case evaluation for each architecture.",
        "failed_generation_jobs_included": True,
        "performance_filtering_used": False,
    }
    selection["architecture_verification"] = {
        "V2_FALLBACK25": {
            "description": "FULL_REPAIR_V2 permits up to four semantic attempts and up to three syntax-only repairs inside each semantic attempt. Deterministic routing can trigger repair; semantic validator calls occur only after routing permits them. The audit policy adds exactly the 25 preserved rejected attempt-4 candidates without promoting them to accepted outputs.",
            "configuration_path": "MVP/SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/CONFIGS/pipeline.full-repair-v2-run01.json",
            "orchestration_path": "MVP/SHACL_GENERATION_PIPELINE/src/nltl_pipeline/orchestration/runner.py",
            "discrepancy": "V2_FALLBACK25 is a retrospective audit policy, not the pipeline's official accepted-output policy.",
        },
        "NO_SEMANTIC": {
            "description": "One generator call with up to three syntax-only repair calls. Semantic validator, vocabulary matcher, and semantic regeneration are disabled; deterministic diagnostics are terminal and do not feed regeneration.",
            "configuration_path": "MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_NO_SEMANTIC_VALIDATOR/CONFIGS/pipeline.luna-no-semantic-validator-run01.json",
            "orchestration_path": "MVP/SHACL_GENERATION_PIPELINE/src/nltl_pipeline/orchestration/no_semantic_validator.py",
            "discrepancy": "The shared config still lists validator/matcher models and generic maximum_semantic_attempts, but the ablation flags and runner disable those calls and execute one semantic attempt.",
        },
        "SINGLESHOT": {
            "description": "Exactly one contextual generator call followed by read-only deterministic diagnostics. No syntax repair, semantic validator, matcher, or regeneration calls occur.",
            "configuration_path": "MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/CONFIGS/pipeline.luna-contextual-singleshot-run01.json",
            "orchestration_path": "MVP/SHACL_GENERATION_PIPELINE/src/nltl_pipeline/orchestration/singleshot.py",
            "discrepancy": "The shared config retains unused syntax-repair/validator/matcher model fields and generic generation limits; the SingleShot ablation and runner override them with one generator call and zero downstream LLM calls.",
        },
    }
    selection["local_source_ledgers"] = [
        {"identity": key, "path": str(path.relative_to(repo)), "sha256": SOURCE_LEDGER_HASHES[key]}
        for key, path in ledger_paths.items()
    ]
    selection["records"] = [
        {key: value for key, value in record.items() if key not in {"shape_text", "unreviewed_case_inventory"}}
        for record in enriched_records
    ]
    selection_path = audit_root / "audit_selection.json"
    selection_path.write_text(json.dumps(selection, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    missing_path = audit_root / "missing_evidence.txt"
    header = [
        "NLTL MANUAL AUDIT — MISSING OR UNRESOLVED EVIDENCE",
        "",
        f"Missing selected SHACL specimens or observations: {len(missing)}",
        "These entries remain explicit. No candidate was substituted and no evaluation was executed.",
        "No optional evaluation command is supplied: these gaps are absent generation artifacts, and behavioural evaluation cannot create them. Filling them would require a separately authorized generation run.",
        "",
    ]
    missing_path.write_text("\n".join(header + missing) + "\n", encoding="utf-8")

    readme = audit_root / "README.txt"
    readme.write_text(
        "NLTL manual audit package\n\n"
        "Send one batches/BATCH_XX.txt file together with NLTL_Manual_Audit_ready.xlsx for review. "
        "Record Q1-Q7 grades and evidence only in the workbook's amber manual-input cells. "
        "Use filters; do not sort or delete rows in CaseReview, RawResults, or RequirementScores.\n\n"
        "The same two frozen RDF cases are shown for all three architectures. Two cases do not validate the full requirement. "
        "V2_FALLBACK25 is retrospective audit evidence and does not alter official V2 results.\n\n"
        "Eligible run pools: V2_FALLBACK25=[RUN_01], NO_SEMANTIC=[RUN_01], SINGLESHOT=[RUN_01]. "
        "No later run had a complete compatible 268-requirement / 2,186-case evaluation.\n\n"
        "Architecture discrepancies are recorded in audit_selection.json. Reproduce packets with:\n"
        "MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/scripts/package_audit.py\n\n"
        "The 25 explicit gaps are absent generated SHACL specimens. No evaluation command is provided because evaluation cannot create a missing generation artifact.\n",
        encoding="utf-8",
    )

    packet_manifest = {
        "audit_version": selection["audit_version"],
        "seed": selection["seed"],
        "requirements": 268,
        "batches": 27,
        "architecture_slots": 804,
        "selected_case_ids": sum(len(value) for value in selection["cases_per_requirement"].values()),
        "files": [],
    }
    manifest_inputs = [selection_path, missing_path, readme, *packet_files]
    manifest_inputs.extend(sorted(path for path in originals.rglob("*") if path.is_file()))
    manifest_inputs.extend(sorted(
        path for path in (audit_root / "scripts").glob("*")
        if path.is_file() and path.suffix in {".py", ".mjs", ".png"}
    ))
    ready_workbook = audit_root / "NLTL_Manual_Audit_ready.xlsx"
    if ready_workbook.is_file():
        manifest_inputs.append(ready_workbook)
    for path in sorted(manifest_inputs):
        packet_manifest["files"].append({
            "path": str(path.relative_to(audit_root)),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    (audit_root / "packet_manifest.json").write_text(json.dumps(packet_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "eligible_run_pools": pools,
        "records": len(enriched_records),
        "artifacts_available": dict(Counter(
            record["architecture"] for record in enriched_records if record["artifact_hash_verified"]
        )),
        "artifacts_missing": dict(Counter(
            record["architecture"] for record in enriched_records if not record["artifact_hash_verified"]
        )),
        "batches": 27,
        "selected_cases": packet_manifest["selected_case_ids"],
        "missing_evidence_entries": len(missing),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
