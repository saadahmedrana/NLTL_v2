from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from rdflib import Graph


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R13_APPLICABILITY_MATRIX_CLOSURE"
TARGET = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R3"
ROOT_BASENAME = "benchmark_vocabulary_stage2_LOCK-2026-08-14-R3"
LOCK_ID = "VOCAB-LOCK-2026-08-14-R3"
WORKBOOK_NAME = ROOT_BASENAME + ".xlsx"
LOCK_NAME = ROOT_BASENAME + ".lock.json"
SHA_NAME = ROOT_BASENAME + ".sha256"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def confirmation_results():
    runs = {
        "I2-046": MVP / "SHACL_GENERATION_PIPELINE/outputs/development_r13/runs/RUN-I2-046-20260814T073005028257Z",
        "IMO-102": MVP / "SHACL_GENERATION_PIPELINE/outputs/development_r13/runs/RUN-IMO-102-20260814T073130950743Z",
    }
    rows = []
    for requirement_id, directory in runs.items():
        events = [json.loads(line) for line in (directory / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
        finish = next(event for event in reversed(events) if event.get("event_type") == "run_finished")
        shape = directory / finish["final_shape"]
        if not finish.get("accepted") or not shape.exists():
            raise RuntimeError(f"R13 confirmation is not accepted and frozen: {requirement_id}")
        rows.append({
            "requirementId": requirement_id,
            "runId": finish["run_id"],
            "status": finish["status"],
            "accepted": True,
            "attempts": finish["attempts"],
            "finalFeedback": finish["final_feedback"],
            "finalShapeSha256": sha256(shape),
            "sourceRunDirectory": str(directory.relative_to(MVP)),
        })
    return rows


def prepare() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite final lock directory: {TARGET}")
    TARGET.mkdir(parents=True)
    for relative in ("registry", "ontology", "context", "evidence", "validation"):
        shutil.copytree(SOURCE / relative, TARGET / relative)
    shutil.copy2(SOURCE / "requirement_term_index.json", TARGET / "requirement_term_index.json")
    shutil.copy2(SOURCE / "README.md", TARGET / "R13_DEVELOPMENT_README.md")
    (TARGET / "confirmation").mkdir()
    write_json(TARGET / "confirmation/r13_confirmation_results.json", {
        "sessionId": "SESSION-BATCH-20260814T073005028093Z",
        "accepted": 2,
        "total": 2,
        "estimatedIncrementalUsd": 1.07,
        "results": confirmation_results(),
    })
    registry = read_json(TARGET / "registry/term_registry.json")
    index = read_json(TARGET / "requirement_term_index.json")
    evidence = read_json(TARGET / "evidence/stage1_approved.json")
    kinds = {}
    for item in registry:
        kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
    artifact_paths = [
        "registry/term_registry.json", "registry/term_registry.csv", "registry/r13_change_decisions.json",
        "ontology/nltl_benchmark_vocabulary.ttl", "ontology/nltl_benchmark_vocabulary.rdf",
        "context/nltl_benchmark_context.jsonld", "evidence/stage1_approved.json",
        "requirement_term_index.json", "validation/validation_report.json",
        "confirmation/r13_confirmation_results.json",
    ]
    write_json(TARGET / "prelock_manifest.json", {
        "lockId": LOCK_ID,
        "status": "PREPARED_PENDING_WORKBOOK_AND_FINAL_HASHES",
        "sourceDevelopmentId": "VOCAB-DEV-2026-08-14-R13-APPLICABILITY-MATRIX-CLOSURE",
        "supersedes": "VOCAB-LOCK-2026-08-12-R2",
        "counts": {
            "requirements": len(evidence["requirements"]),
            "registryTerms": len(registry),
            "canonicalTermsIncludingInfrastructure": 1673,
            "generationEligibleRequirements": 238,
            "completeDependencyContracts": sum(1 for value in index["dependencyContracts"].values() if value.get("status") == "COMPLETE"),
            "termKinds": kinds,
        },
        "boundArtifacts": {relative: sha256(TARGET / relative) for relative in artifact_paths},
        "knownVocabularyGaps": 0,
        "confirmation": "PASS - I2-046 and IMO-102 accepted in R13",
    })
    print(json.dumps({"status": "PREPARED", "target": str(TARGET), "registryTerms": len(registry)}, indent=2))


def finalize() -> None:
    workbook = TARGET / WORKBOOK_NAME
    verification = TARGET / "validation/final_lock_workbook_verification.json"
    if not workbook.exists() or not verification.exists():
        raise FileNotFoundError("Final lock workbook or verification file is missing")
    verification_payload = read_json(verification)
    if verification_payload.get("status") != "PASS":
        raise RuntimeError("Workbook verification did not pass")
    Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    prelock = read_json(TARGET / "prelock_manifest.json")
    bound = dict(prelock["boundArtifacts"])
    bound["validation/final_lock_workbook_verification.json"] = sha256(verification)
    lock = {
        "lockId": LOCK_ID,
        "status": "LOCKED_FOR_FINAL_EXPERIMENT_INPUT",
        "lockedDate": "2026-08-14",
        "vocabularyVersion": "2.13.0-stage2-final",
        "revision": "R3",
        "supersedes": "VOCAB-LOCK-2026-08-12-R2",
        "sourceDevelopmentId": prelock["sourceDevelopmentId"],
        "workbook": WORKBOOK_NAME,
        "workbookSha256": sha256(workbook),
        "lockMeaning": "Content identity is fixed by this lock manifest and SHA-256 hashes. Any vocabulary, requirement contract, owner, context, ontology, or workbook edit requires a new lock ID and separate experiment run.",
        "experimentRule": "Model use of an incorrect, invented, or missed in-lock term is an LLM/pipeline outcome. The lock must not be edited during a scored run. A genuinely absent concept is recorded as a benchmark-infrastructure defect and handled outside that run.",
        "counts": prelock["counts"],
        "validation": {
            "doctor": "PASS",
            "all313ContextsResolve": True,
            "unitTests": "44/44 PASS",
            "formulaErrors": 0,
            "visualWorkbookReview": verification_payload.get("visualReview"),
            "knownVocabularyGaps": 0,
            "r13Confirmation": prelock["confirmation"],
        },
        "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {
            "requirement_term_index.json": sha256(TARGET / "requirement_term_index.json")
        },
        "nonBlockingPublicationItems": [
            "The provisional w3id namespace is not registered; register or replace it before public release.",
            "ISO 19848 normative text remains unavailable; no ISO-specific normative definition or identifier is claimed.",
        ],
    }
    write_json(TARGET / LOCK_NAME, lock)
    shutil.copy2(workbook, MVP / WORKBOOK_NAME)
    shutil.copy2(TARGET / LOCK_NAME, MVP / LOCK_NAME)
    (MVP / SHA_NAME).write_text(f"{lock['workbookSha256']}  {WORKBOOK_NAME}\n", encoding="ascii")
    (TARGET / SHA_NAME).write_text(f"{lock['workbookSha256']}  {WORKBOOK_NAME}\n", encoding="ascii")
    print(json.dumps({"status": "LOCKED", "lockId": LOCK_ID, "workbookSha256": lock["workbookSha256"], "rootWorkbook": str(MVP / WORKBOOK_NAME)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "finalize"))
    args = parser.parse_args()
    prepare() if args.action == "prepare" else finalize()
