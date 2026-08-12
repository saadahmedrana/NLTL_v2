from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


MVP = Path(__file__).resolve().parents[2]
R2 = MVP / "BENCHMARK_VOCABULARY" / "STAGE2_R2"
LOCK_ID = "VOCAB-LOCK-2026-08-12-R2"
ROOT_WORKBOOK = MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-12-R2.xlsx"
LOCK_JSON = MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-12-R2.lock.json"
LOCK_SHA = MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-12-R2.sha256"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_hashes(directory: Path, names: list[str]) -> dict[str, str]:
    return {name: sha256(directory / name) for name in names}


def main() -> None:
    source_workbook = R2 / "benchmark_vocabulary_stage2_R2.xlsx"
    shutil.copy2(source_workbook, ROOT_WORKBOOK)
    workbook_hash = sha256(ROOT_WORKBOOK)
    machine_names = [
        "registry/term_registry.json",
        "context/nltl_benchmark_context.jsonld",
        "stage2_manifest.json",
        "validation/validation_report.json",
        "validation/workbook_verification.json",
        "validation/locked_workbook_verification.json",
        "ontology/nltl_benchmark_vocabulary.ttl",
        "shacl/schema_only_shapes.ttl",
        "mappings/haitham_exact_mappings.ttl",
        "evidence/external_uri_verification.json",
        "evidence/stage1_approved.json",
    ]
    profile_hashes = relative_hashes(R2 / "profiles", [
        "direct_deterministic.json", "evidence_and_deferred.json", "iacs_ur_i2.json",
        "imo_amend_2026.json", "imo_polar_code.json", "master.json", "traficom.json",
    ])
    manifest = json.loads((R2 / "stage2_manifest.json").read_text(encoding="utf-8"))
    lock = {
        "lockId": LOCK_ID,
        "status": "LOCKED_FOR_PIPELINE_INPUT",
        "lockedDate": "2026-08-12",
        "vocabularyVersion": manifest["version"],
        "revision": "R2",
        "supersedes": "VOCAB-LOCK-2026-08-12-R1",
        "workbook": ROOT_WORKBOOK.name,
        "workbookSha256": workbook_hash,
        "sourceWorkbook": "../BENCHMARK_VOCABULARY/STAGE2_R2/benchmark_vocabulary_stage2_R2.xlsx",
        "sourceWorkbookSha256": sha256(source_workbook),
        "lockMeaning": "R1 remains unchanged. R2 is content-locked by filename, version, and SHA-256 after a pilot-discovered IMO-057 structural vocabulary repair.",
        "pipelineBoundary": "R2 changes names, entity types, and an object path only. It contains no regulatory threshold, applicability outcome, SHACL answer logic, or expected pass/fail result.",
        "repair": {
            "requirementId": "IMO-057",
            "retiredActiveTerm": "containingCompartment (R1 xsd:string DatatypeProperty)",
            "replacementTerms": [
                "compartment", "hasContainingCompartment", "emergencyFirePump",
                "waterMistPump", "waterSprayPump",
            ],
            "engineeringReason": "The verified clause requires traversal from each pump to a compartment whose maintained temperature is checked; a string label cannot form that SHACL path.",
            "sourceReference": "IMO-057 | IMO_POLAR_CODE p.22 | 7.3.2.1",
        },
        "counts": {
            "requirements": 313,
            "stage1CandidateLineages": 823,
            "r2AddedConcepts": 4,
            "canonicalTerms": 825,
            "classes": 80,
            "datatypeProperties": 462,
            "objectProperties": 25,
            "quantityProperties": 258,
            "namingRefinementRows": 13,
            "semanticMerges": 1,
            "retiredOrRemodelledCandidates": 2,
        },
        "validation": {
            "stage2ChecksPassed": 45,
            "independentWorkbookChecksPassed": 18,
            "visualReview": "PASS - 16 renders covering all 14 sheets inspected",
            "formulaErrors": 0,
            "allCanonicalNamesAsciiLowerCamelCase": True,
            "requirementsReconciled": 313,
            "masterTermRowsReconciled": 825,
            "containsRegulatoryAnswerLogic": False,
        },
        "upstreamStage1": {
            "lockId": "LOCK-2026-08-11-R2",
            "workbook": "Input_regulations_3Sources.xlsx",
            "workbookSha256": "05eb02b0bce6fb7373329a92841a30171cd5c03c880ac570efbeb10b13700eaa",
        },
        "boundMachineReadableArtifacts": relative_hashes(R2, machine_names),
        "boundRequirementIndex": {
            "BENCHMARK_VOCABULARY/PIPELINE_CONTEXT/R2/requirement_term_index.json": sha256(
                MVP / "BENCHMARK_VOCABULARY" / "PIPELINE_CONTEXT" / "R2" / "requirement_term_index.json"
            )
        },
        "profileSha256": profile_hashes,
        "nonBlockingPublicationItems": [
            "The provisional w3id namespace is not registered; register or replace it before public release.",
            "ISO 19848 normative text remains unavailable; no ISO-specific definition or identifier is claimed.",
        ],
    }
    LOCK_JSON.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    LOCK_SHA.write_text(f"{workbook_hash}  {ROOT_WORKBOOK.name}\n", encoding="utf-8")
    print(json.dumps({
        "status": "LOCKED",
        "lockId": LOCK_ID,
        "workbook": str(ROOT_WORKBOOK),
        "workbookSha256": workbook_hash,
        "lock": str(LOCK_JSON),
    }, indent=2))


if __name__ == "__main__":
    main()
