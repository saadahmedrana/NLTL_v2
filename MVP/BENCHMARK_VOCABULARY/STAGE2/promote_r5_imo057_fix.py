from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R4"
TARGET = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R5"
ROOT_BASENAME = "benchmark_vocabulary_stage2_LOCK-2026-08-19-R5"
LOCK_ID = "VOCAB-LOCK-2026-08-19-R5"
WORKBOOK_NAME = ROOT_BASENAME + ".xlsx"
LOCK_NAME = ROOT_BASENAME + ".lock.json"
SHA_NAME = ROOT_BASENAME + ".sha256"
PREFLIGHT_SESSION = (
    MVP
    / "SHACL_GENERATION_PIPELINE/outputs/official_r4_pilot_5/sessions"
    / "SESSION-BATCH-20260814T164606431676Z/batch_result.json"
)
PREFLIGHT_RUN = (
    MVP
    / "SHACL_GENERATION_PIPELINE/outputs/official_r4_pilot_5/runs"
    / "RUN-IMO-057-20260814T164625387258Z"
)
CANONICAL = "https://w3id.org/nltl/vocab#"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {description} occurrence, found {count}")
    return text.replace(old, new, 1)


def patch_ontology() -> None:
    ttl_path = TARGET / "ontology/nltl_benchmark_vocabulary.ttl"
    ttl = ttl_path.read_text(encoding="utf-8")
    ttl = replace_once(
        ttl,
        "owl:versionIRI <https://w3id.org/nltl/vocab/2.8.1-dev-batch01-postconfirmation> ;\n"
        '    owl:versionInfo "2.14.0-dev-final-stress-gap-closure" ;\n'
        '    nltl:publicationStatus "Stage 2 draft; provisional w3id redirect not yet registered" .',
        "owl:versionIRI <https://w3id.org/nltl/vocab/2.15.0-stage2-final-r5> ;\n"
        '    owl:versionInfo "2.15.0-stage2-final-r5" ;\n'
        '    nltl:publicationStatus "Final R5 candidate; permanent W3ID namespace requested" .',
        "Turtle ontology-version block",
    )
    old_ttl_term = (
        "nltl:maintainedTemperature a owl:ObjectProperty ;\n"
        '    rdfs:label "Maintained temperature"@en ;\n'
        "    rdfs:domain nltl:benchmarkEntity ;\n"
        "    rdfs:range qudt:QuantityValue ;"
    )
    new_ttl_term = old_ttl_term.replace(
        "rdfs:domain nltl:benchmarkEntity", "rdfs:domain nltl:compartment"
    )
    ttl = replace_once(ttl, old_ttl_term, new_ttl_term, "maintainedTemperature Turtle block")
    ttl_path.write_text(ttl, encoding="utf-8")

    rdf_path = TARGET / "ontology/nltl_benchmark_vocabulary.rdf"
    rdf = rdf_path.read_text(encoding="utf-8")
    rdf = replace_once(
        rdf,
        '<owl:versionIRI rdf:resource="https://w3id.org/nltl/vocab/2.8.1-dev-batch01-postconfirmation"/>\n'
        "    <owl:versionInfo>2.14.0-dev-final-stress-gap-closure</owl:versionInfo>\n"
        "    <nltl:publicationStatus>Stage 2 draft; provisional w3id redirect not yet registered</nltl:publicationStatus>",
        '<owl:versionIRI rdf:resource="https://w3id.org/nltl/vocab/2.15.0-stage2-final-r5"/>\n'
        "    <owl:versionInfo>2.15.0-stage2-final-r5</owl:versionInfo>\n"
        "    <nltl:publicationStatus>Final R5 candidate; permanent W3ID namespace requested</nltl:publicationStatus>",
        "RDF/XML ontology-version block",
    )
    old_rdf_term = (
        '<rdf:Description rdf:about="https://w3id.org/nltl/vocab#maintainedTemperature">\n'
        '    <rdf:type rdf:resource="http://www.w3.org/2002/07/owl#ObjectProperty"/>\n'
        '    <rdfs:label xml:lang="en">Maintained temperature</rdfs:label>\n'
        '    <rdfs:domain rdf:resource="https://w3id.org/nltl/vocab#benchmarkEntity"/>\n'
        '    <rdfs:range rdf:resource="http://qudt.org/schema/qudt/QuantityValue"/>'
    )
    new_rdf_term = old_rdf_term.replace(
        f'{CANONICAL}benchmarkEntity', f'{CANONICAL}compartment'
    )
    rdf = replace_once(rdf, old_rdf_term, new_rdf_term, "maintainedTemperature RDF/XML block")
    rdf_path.write_text(rdf, encoding="utf-8")

    ttl_graph = Graph().parse(ttl_path, format="turtle")
    rdf_graph = Graph().parse(rdf_path, format="xml")
    if not isomorphic(ttl_graph, rdf_graph):
        raise RuntimeError("R5 Turtle and RDF/XML graphs are not isomorphic")


def patch_requirement_index() -> None:
    path = TARGET / "requirement_term_index.json"
    payload = read_json(path)
    requirement_id = "IMO-057"
    indexed = list(payload["requirements"][requirement_id])
    if "hasComponent" not in indexed:
        indexed.append("hasComponent")
    payload["requirements"][requirement_id] = sorted(indexed)
    payload.setdefault("requirementTargetOwner", {})[requirement_id] = "ship"
    payload.setdefault("termOwners", {})[requirement_id] = {
        "hasComponent": "ship",
        "hasContainingCompartment": "firePump",
        "maintainedTemperature": "compartment",
    }
    old_contract = dict(payload["dependencyContracts"][requirement_id])
    payload["dependencyContracts"][requirement_id] = {
        "status": "COMPLETE",
        "schemaVersion": 2,
        "engineeringDecision": "R5_IMO057_COMPARTMENT_TEMPERATURE_PATH_CONFIRMED",
        "observedFailureStatus": "R4_PREFLIGHT_TERM_RESOLUTION_UNRESOLVED_DUE_TO_OWNER_METADATA",
        "ownerClasses": ["ship", "shipComponent", "firePump", "compartment"],
        "applicabilityTerms": [],
        "operandTerms": ["maintainedTemperature"],
        "resultTerms": [],
        "comparisonTerms": [],
        "relationshipTerms": ["hasComponent", "hasContainingCompartment"],
        "timeTerms": [],
        "controlledValueTerms": [],
        "evidenceTerms": [],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasComponent", "toOwner": "shipComponent"},
            {"fromOwner": "firePump", "via": "hasContainingCompartment", "toOwner": "compartment"},
        ],
        "nodeTypeRequirements": [
            {
                "pathOwner": "shipComponent",
                "requiredClass": "firePump",
                "includedSubclasses": ["emergencyFirePump", "waterMistPump", "waterSprayPump"],
            }
        ],
        "comparisonModel": old_contract["comparisonModel"],
        "tableModel": "",
        "encodingPattern": old_contract["encodingPattern"],
        "requiredModelFields": [
            "ownerClasses",
            "operandTerms",
            "relationshipTerms",
            "modelPaths",
            "nodeTypeRequirements",
            "comparisonModel",
        ],
        "auditFlags": [],
        "legacyIndexedTerms": old_contract["legacyIndexedTerms"],
    }
    write_json(path, payload)


def write_evidence_and_audit() -> None:
    batch = read_json(PREFLIGHT_SESSION)
    imo_result = next(row for row in batch["results"] if row["requirement_id"] == "IMO-057")
    source_pdf = MVP / "RELEVANT FILES/MSC.385(94).pdf"
    evidence = {
        "classification": "NON_SCORED_R4_PREFLIGHT_DEVELOPMENT_EVIDENCE",
        "sessionId": batch["session_id"],
        "sessionResultPath": str(PREFLIGHT_SESSION.relative_to(MVP)),
        "sessionResultSha256": sha256(PREFLIGHT_SESSION),
        "requirementId": "IMO-057",
        "runId": imo_result["run_id"],
        "status": imo_result["status"],
        "accepted": imo_result["accepted"],
        "finalFeedback": imo_result["final_feedback"],
        "candidateShape": {
            "path": str((PREFLIGHT_RUN / "artifacts/attempt_01/candidate_shape.ttl").relative_to(MVP)),
            "sha256": sha256(PREFLIGHT_RUN / "artifacts/attempt_01/candidate_shape.ttl"),
            "deterministicValidation": "PASS",
        },
        "validatorRawSha256": sha256(PREFLIGHT_RUN / "artifacts/attempt_01/validator_raw_01.txt"),
        "matcherRawSha256": sha256(PREFLIGHT_RUN / "artifacts/attempt_01/vocabulary_matcher_raw_01.txt"),
        "confirmedDefect": "maintainedTemperature was presented as ship-owned because its ontology domain was benchmarkEntity and IMO-057 lacked explicit compartment ownership/path metadata.",
        "sourceEvidence": {
            "document": "MSC.385(94).pdf",
            "sha256": sha256(source_pdf),
            "pdfPage": 22,
            "printedPage": 21,
            "clause": "7.3.2.1",
            "verifiedExcerpt": "fire pumps, including emergency fire pumps, water mist and water spray pumps, shall be located in compartments maintained above freezing",
        },
    }
    write_json(TARGET / "evidence/r4_preflight_imo057_defect.json", evidence)

    registry = read_json(TARGET / "registry/term_registry.json")
    index = read_json(TARGET / "requirement_term_index.json")
    term = next(row for row in registry if row["localName"] == "maintainedTemperature")
    affected = sorted(
        requirement_id
        for requirement_id, terms in index["requirements"].items()
        if "maintainedTemperature" in terms
    )
    audit = {
        "status": "PASS",
        "term": "maintainedTemperature",
        "canonicalIri": term["iri"],
        "registryRequirementLinks": term["requirements"],
        "indexedRequirementContexts": affected,
        "affectedContexts": ["IMO-057"],
        "otherAffectedContexts": [],
        "newVocabularyTerms": 0,
        "canonicalLocalNamesChanged": 0,
        "promptsChanged": False,
        "fewShotsChanged": False,
        "conclusion": "The same ownership defect affects no other requirement context because maintainedTemperature is linked only to IMO-057.",
    }
    write_json(TARGET / "validation/maintained_temperature_scope_audit.json", audit)
    write_json(
        TARGET / "registry/r5_change_decisions.json",
        [
            {
                "requirementId": "IMO-057",
                "term": "maintainedTemperature",
                "action": "NARROW_DOMAIN_AND_COMPLETE_EXISTING_PATH_METADATA",
                "oldDomain": f"{CANONICAL}benchmarkEntity",
                "newDomain": f"{CANONICAL}compartment",
                "newTerms": 0,
                "localNameChanged": False,
                "rationale": "Polar Code 7.3.2.1 attaches the above-freezing condition to the compartments containing the listed pumps.",
            }
        ],
    )


def artifact_paths() -> list[str]:
    return [
        "registry/term_registry.json",
        "registry/term_registry.csv",
        "registry/r5_change_decisions.json",
        "ontology/nltl_benchmark_vocabulary.ttl",
        "ontology/nltl_benchmark_vocabulary.rdf",
        "context/nltl_benchmark_context.jsonld",
        "evidence/stage1_approved.json",
        "evidence/r4_preflight_imo057_defect.json",
        "requirement_term_index.json",
        "validation/maintained_temperature_scope_audit.json",
    ]


def prepare() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite R5 directory: {TARGET}")
    TARGET.mkdir(parents=True)
    for relative in ("registry", "ontology", "context", "evidence"):
        shutil.copytree(SOURCE / relative, TARGET / relative)
    shutil.copy2(SOURCE / "requirement_term_index.json", TARGET / "requirement_term_index.json")
    (TARGET / "validation").mkdir()
    patch_ontology()
    patch_requirement_index()
    write_evidence_and_audit()

    registry = read_json(TARGET / "registry/term_registry.json")
    index = read_json(TARGET / "requirement_term_index.json")
    evidence = read_json(TARGET / "evidence/stage1_approved.json")
    bound = {relative: sha256(TARGET / relative) for relative in artifact_paths()}
    prelock = {
        "lockId": LOCK_ID,
        "status": "PREPARED_PENDING_OFFLINE_VALIDATION_AND_WORKBOOK",
        "sourceLockId": "VOCAB-LOCK-2026-08-14-R4",
        "supersedes": "VOCAB-LOCK-2026-08-14-R4",
        "scope": "IMO-057 ownership/domain/dependency-path metadata only",
        "counts": {
            "requirements": len(evidence["requirements"]),
            "registryTerms": len(registry),
            "canonicalTermsIncludingInfrastructure": 1678,
            "generationEligibleRequirements": 238,
            "completeDependencyContracts": sum(
                value.get("status") == "COMPLETE"
                for value in index["dependencyContracts"].values()
            ),
            "newVocabularyTerms": 0,
        },
        "boundArtifacts": bound,
        "knownVocabularyGaps": 0,
        "preflightEvidencePreserved": str(PREFLIGHT_SESSION.relative_to(MVP)),
    }
    write_json(TARGET / "prelock_manifest.json", prelock)
    write_json(
        TARGET / "r5_prelock_binding.json",
        {
            "lockId": LOCK_ID,
            "status": "PRELOCK_OFFLINE_VALIDATION_ONLY",
            "workbook": "Pending R5 workbook",
            "workbookSha256": "",
            "boundMachineReadableArtifacts": bound,
            "boundRequirementIndex": {
                "requirement_term_index.json": bound["requirement_term_index.json"]
            },
        },
    )
    print(
        json.dumps(
            {
                "status": "PREPARED",
                "target": str(TARGET),
                "registryTerms": len(registry),
                "newVocabularyTerms": 0,
            },
            indent=2,
        )
    )


def finalize() -> None:
    workbook = TARGET / WORKBOOK_NAME
    workbook_verification = TARGET / "validation/final_lock_workbook_verification.json"
    offline_validation = TARGET / "validation/r5_offline_validation.json"
    for required in (workbook, workbook_verification, offline_validation):
        if not required.exists():
            raise FileNotFoundError(f"Missing R5 finalization input: {required}")
    workbook_check = read_json(workbook_verification)
    offline_check = read_json(offline_validation)
    if workbook_check.get("status") != "PASS" or not str(
        workbook_check.get("visualReview", "")
    ).startswith("PASS"):
        raise RuntimeError("R5 workbook verification or visual review did not pass")
    if offline_check.get("status") != "PASS":
        raise RuntimeError("R5 offline validation did not pass")
    Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    prelock = read_json(TARGET / "prelock_manifest.json")
    bound = {
        relative: sha256(TARGET / relative)
        for relative in prelock["boundArtifacts"]
    }
    bound["validation/final_lock_workbook_verification.json"] = sha256(workbook_verification)
    bound["validation/r5_offline_validation.json"] = sha256(offline_validation)
    bound["validation/r5_namespace_and_scope_report.json"] = sha256(
        TARGET / "validation/r5_namespace_and_scope_report.json"
    )
    prompt_hashes = {
        name: sha256(MVP / "SHACL_GENERATION_PIPELINE/prompts" / name)
        for name in ("generator.txt", "validator.txt", "vocabulary_matcher.txt")
    }
    lock = {
        "lockId": LOCK_ID,
        "status": "LOCKED_FOR_IMO057_CONFIRMATION",
        "lockedDate": "2026-08-19",
        "vocabularyVersion": "2.15.0-stage2-final-r5",
        "revision": "R5",
        "supersedes": "VOCAB-LOCK-2026-08-14-R4",
        "changeScope": "Only the confirmed IMO-057 maintainedTemperature ownership/domain/dependency-path defect.",
        "workbook": WORKBOOK_NAME,
        "workbookSha256": sha256(workbook),
        "lockMeaning": "Content identity is fixed by this manifest and SHA-256 hashes. R4 remains preserved as preflight evidence.",
        "counts": prelock["counts"],
        "validation": offline_check,
        "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {
            "requirement_term_index.json": sha256(TARGET / "requirement_term_index.json")
        },
        "boundGeneratorInputs": {
            "canonicalVocabularyNamespace": CANONICAL,
            "fewShotJsonl": {
                "path": "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/few_shot_pairs.jsonl",
                "sha256": sha256(
                    MVP / "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/few_shot_pairs.jsonl"
                ),
            },
            "prompts": prompt_hashes,
        },
        "nonBlockingPublicationItems": [
            "Confirm the requested https://w3id.org/nltl/ redirect before public release.",
            "ISO 19848 normative text remains unavailable; no ISO-specific normative claim is made.",
        ],
    }
    write_json(TARGET / LOCK_NAME, lock)
    shutil.copy2(workbook, MVP / WORKBOOK_NAME)
    shutil.copy2(TARGET / LOCK_NAME, MVP / LOCK_NAME)
    checksum = f"{lock['workbookSha256']}  {WORKBOOK_NAME}\n"
    (MVP / SHA_NAME).write_text(checksum, encoding="ascii")
    (TARGET / SHA_NAME).write_text(checksum, encoding="ascii")
    print(
        json.dumps(
            {
                "status": "LOCKED",
                "lockId": LOCK_ID,
                "workbookSha256": lock["workbookSha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "finalize"))
    args = parser.parse_args()
    prepare() if args.action == "prepare" else finalize()
