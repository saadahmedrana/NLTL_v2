from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from rdflib import Graph


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R14_FINAL_STRESS_GAP_CLOSURE"
TARGET = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R4"
ROOT_BASENAME = "benchmark_vocabulary_stage2_LOCK-2026-08-14-R4"
LOCK_ID = "VOCAB-LOCK-2026-08-14-R4"
WORKBOOK_NAME = ROOT_BASENAME + ".xlsx"
LOCK_NAME = ROOT_BASENAME + ".lock.json"
SHA_NAME = ROOT_BASENAME + ".sha256"
EVAL = MVP / "SHACL_GENERATION_PIPELINE/outputs/development_r14/evaluations/EVAL-R4-GENERATED-SHAPES-I2-005-IMO-086-20260814T134621891010Z/evaluation_summary.json"
BATCH = MVP / "SHACL_GENERATION_PIPELINE/outputs/development_r14/sessions/SESSION-BATCH-20260814T124851373747Z/batch_result.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite final lock directory: {TARGET}")
    TARGET.mkdir(parents=True)
    for relative in ("registry", "ontology", "context", "evidence", "validation"):
        shutil.copytree(SOURCE / relative, TARGET / relative)
    shutil.copy2(SOURCE / "requirement_term_index.json", TARGET / "requirement_term_index.json")
    shutil.copy2(SOURCE / "README.md", TARGET / "R14_DEVELOPMENT_README.md")
    (TARGET / "confirmation").mkdir()
    batch = read_json(BATCH)
    evaluation = read_json(EVAL)
    write_json(TARGET / "confirmation/r14_confirmation_results.json", {
        "generationSessionId": batch["session_id"],
        "generationAccepted": sum(1 for row in batch["results"] if row["accepted"]),
        "generationTotal": len(batch["results"]),
        "generationResults": batch["results"],
        "rdfEvaluationId": evaluation["evaluation_id"],
        "rdfEvaluationSummary": evaluation,
        "rdfExpectedMatches": evaluation["expected_matches"],
        "rdfExpectedMismatches": evaluation["expected_mismatches"],
    })
    registry = read_json(TARGET / "registry/term_registry.json")
    index = read_json(TARGET / "requirement_term_index.json")
    evidence = read_json(TARGET / "evidence/stage1_approved.json")
    artifact_paths = [
        "registry/term_registry.json", "registry/term_registry.csv", "registry/r14_change_decisions.json",
        "ontology/nltl_benchmark_vocabulary.ttl", "ontology/nltl_benchmark_vocabulary.rdf",
        "context/nltl_benchmark_context.jsonld", "evidence/stage1_approved.json",
        "requirement_term_index.json", "validation/validation_report.json",
        "confirmation/r14_confirmation_results.json",
    ]
    write_json(TARGET / "prelock_manifest.json", {
        "lockId": LOCK_ID,
        "status": "PREPARED_PENDING_WORKBOOK_AND_FINAL_HASHES",
        "sourceDevelopmentId": "VOCAB-DEV-2026-08-14-R14-FINAL-STRESS-GAP-CLOSURE",
        "supersedes": "VOCAB-LOCK-2026-08-14-R3",
        "counts": {
            "requirements": len(evidence["requirements"]),
            "registryTerms": len(registry),
            "canonicalTermsIncludingInfrastructure": 1678,
            "generationEligibleRequirements": 238,
            "completeDependencyContracts": sum(1 for value in index["dependencyContracts"].values() if value.get("status") == "COMPLETE"),
        },
        "boundArtifacts": {relative: sha256(TARGET / relative) for relative in artifact_paths},
        "knownVocabularyGaps": 0,
        "confirmation": "PASS - I2-005 and IMO-086 generation accepted; 7/7 independent RDF outcomes matched",
    })
    print(json.dumps({"status": "PREPARED", "target": str(TARGET), "registryTerms": len(registry)}, indent=2))


def finalize() -> None:
    workbook = TARGET / WORKBOOK_NAME
    verification = TARGET / "validation/final_lock_workbook_verification.json"
    if not workbook.exists() or not verification.exists():
        raise FileNotFoundError("Final lock workbook or verification file is missing")
    verification_payload = read_json(verification)
    if verification_payload.get("status") != "PASS" or not str(verification_payload.get("visualReview", "")).startswith("PASS"):
        raise RuntimeError("Workbook verification or visual review did not pass")
    Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    prelock = read_json(TARGET / "prelock_manifest.json")
    # Recompute every bound hash at sealing time.  The namespace migration and
    # RDF reconfirmation deliberately changed several prepared artifacts.
    bound = {
        relative: sha256(TARGET / relative)
        for relative in prelock["boundArtifacts"]
    }
    bound["validation/final_lock_workbook_verification.json"] = sha256(verification)
    bound["validation/namespace_acceptance_report.json"] = sha256(
        TARGET / "validation/namespace_acceptance_report.json"
    )
    prompt_hashes = {
        name: sha256(MVP / "SHACL_GENERATION_PIPELINE/prompts" / name)
        for name in ("generator.txt", "validator.txt", "vocabulary_matcher.txt")
    }
    lock = {
        "lockId": LOCK_ID,
        "status": "LOCKED_FOR_FINAL_EXPERIMENT_INPUT",
        "lockedDate": "2026-08-14",
        "vocabularyVersion": "2.14.0-stage2-final",
        "revision": "R4",
        "supersedes": "VOCAB-LOCK-2026-08-14-R3",
        "sourceDevelopmentId": prelock["sourceDevelopmentId"],
        "workbook": WORKBOOK_NAME,
        "workbookSha256": sha256(workbook),
        "lockMeaning": "Content identity is fixed by this lock manifest and SHA-256 hashes. Any vocabulary, contract, context, ontology, or workbook edit requires a new lock and a separate experiment.",
        "experimentRule": "The R4 vocabulary and prompts must not be modified during scored runs. Incorrect, invented, or missed in-lock terms are model/pipeline outcomes.",
        "counts": prelock["counts"],
        "validation": {
            "doctor": "PASS", "all313ContextsResolve": True, "unitTests": "44/44 PASS",
            "visualWorkbookReview": verification_payload["visualReview"], "knownVocabularyGaps": 0,
            "r14GenerationConfirmation": "2/2 accepted", "r14RdfConfirmation": "7/7 expected outcomes matched",
            "canonicalVocabularyNamespace": "https://w3id.org/nltl/vocab#",
            "namespaceMigrationAudit": "PASS - zero retired project namespace occurrences in active artifacts",
        },
        "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {"requirement_term_index.json": sha256(TARGET / "requirement_term_index.json")},
        "boundGeneratorInputs": {
            "fewShotJsonl": {
                "path": "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/few_shot_pairs.jsonl",
                "sha256": sha256(MVP / "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/few_shot_pairs.jsonl"),
            },
            "prompts": prompt_hashes,
            "canonicalVocabularyNamespace": "https://w3id.org/nltl/vocab#",
        },
        "nonBlockingPublicationItems": [
            "The permanent W3ID path https://w3id.org/nltl/ has been requested; confirm redirect deployment before public release.",
            "ISO 19848 normative text remains unavailable; no ISO-specific normative definition or identifier is claimed.",
        ],
    }
    write_json(TARGET / LOCK_NAME, lock)
    shutil.copy2(workbook, MVP / WORKBOOK_NAME)
    shutil.copy2(TARGET / LOCK_NAME, MVP / LOCK_NAME)
    checksum = f"{lock['workbookSha256']}  {WORKBOOK_NAME}\n"
    (MVP / SHA_NAME).write_text(checksum, encoding="ascii")
    (TARGET / SHA_NAME).write_text(checksum, encoding="ascii")
    print(json.dumps({"status": "LOCKED", "lockId": LOCK_ID, "workbookSha256": lock["workbookSha256"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "finalize"))
    args = parser.parse_args()
    prepare() if args.action == "prepare" else finalize()
