from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic


MVP = Path(__file__).resolve().parents[2]
LOCK_DIR = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R9"
BASE = "benchmark_vocabulary_stage2_LOCK-2026-08-20-R9"
LOCK_ID = "VOCAB-LOCK-2026-08-20-R9"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> None:
    workbook = LOCK_DIR / f"{BASE}.xlsx"
    workbook_check = LOCK_DIR / "validation/final_lock_workbook_verification.json"
    offline = LOCK_DIR / "validation/r9_offline_validation.json"
    integrity = LOCK_DIR / "validation/r9_namespace_policy_and_integrity_report.json"
    provenance = LOCK_DIR / "provenance/r8_immutable_source_hashes.json"
    for path in (workbook, workbook_check, offline, integrity, provenance):
        if not path.exists():
            raise FileNotFoundError(path)
    if read(workbook_check).get("status") != "PASS" or not read(workbook_check).get("visualReview", "").startswith("PASS"):
        raise RuntimeError("R9 workbook verification incomplete")
    if read(offline).get("status") != "PASS" or read(integrity).get("status") != "PASS":
        raise RuntimeError("R9 offline verification is not PASS")
    ttl = Graph().parse(LOCK_DIR / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(LOCK_DIR / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf):
        raise RuntimeError("R9 ontology serializations are not isomorphic")

    prelock = read(LOCK_DIR / "prelock_manifest.json")
    bound = {relative: sha(LOCK_DIR / relative) for relative in prelock["boundArtifacts"]}
    for relative in (
        "validation/final_lock_workbook_verification.json",
        "validation/r9_namespace_policy_and_integrity_report.json",
        "validation/r9_offline_validation.json",
    ):
        bound[relative] = sha(LOCK_DIR / relative)

    pipeline = MVP / "SHACL_GENERATION_PIPELINE"
    prompts = {
        "generator.txt": sha(pipeline / "prompts/generator.txt"),
        "validator.txt": sha(pipeline / "prompts/validator.txt"),
        "vocabulary_matcher.txt": sha(pipeline / "prompts/vocabulary_matcher.txt"),
        "control_v1_3/syntax_repair.txt": sha(pipeline / "prompts/control_v1_3/syntax_repair.txt"),
    }
    sources = {relative: sha(pipeline / relative) for relative in (
        "src/nltl_pipeline/retrieval/context.py",
        "src/nltl_pipeline/retrieval/fewshot.py",
        "src/nltl_pipeline/validation/shacl.py",
        "src/nltl_pipeline/prompts.py",
        "src/nltl_pipeline/orchestration/runner.py",
        "src/nltl_pipeline/api/client.py",
        "src/nltl_pipeline/config.py",
    )}
    report = read(offline)
    integrity_report = read(integrity)
    registry = read(LOCK_DIR / "registry/term_registry.json")
    provenance_payload = read(provenance)
    fewshot_validation = read(LOCK_DIR / "few_shots/validation_report.json")
    lock = {
        "lockId": LOCK_ID,
        "status": "LOCKED_CLASSIFICATION_AND_FEWSHOTS_R9",
        "lockedDate": "2026-08-20", "revision": "R9",
        "vocabularyVersion": "2.19.0-stage2-final-r9",
        "supersedes": "VOCAB-LOCK-2026-08-20-R8",
        "canonicalVocabularyNamespace": "https://w3id.org/nltl/vocab#",
        "workbook": workbook.name, "workbookSha256": sha(workbook),
        "counts": {
            "requirements": 313,
            "generationEligibleRequirements": report["generationEligibleRequirements"],
            "completeDependencyContracts": report["completeContracts"],
            "registryTerms": len(registry),
            "canonicalTermsIncludingInfrastructure": 1692,
            "categoryChanges": integrity_report["categoryChanges"],
            "fewShotExamples": fewshot_validation["exampleCount"],
            "newVocabularyTerms": 0,
        },
        "categoryCounts": report["categoryCounts"],
        "categoryStatus": report["categoryStatus"],
        "changedRequirementVocabularyBlockers": report["changedRequirementVocabularyBlockers"],
        "verificationPolicyBasis": (
            "The category policy is based on the source requirement and intrinsic verification method. "
            "It is independent of whether any particular LLM model previously succeeded or failed to generate a SHACL shape."
        ),
        "newCanonicalTerms": [], "ontologyChangedFromR8": False, "registryChangedFromR8": False,
        "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {"requirement_term_index.json": bound["requirement_term_index.json"]},
        "promptSha256": prompts, "pipelineSourceSha256": sources,
        "fewShotJsonlSha256": sha(LOCK_DIR / "few_shots/few_shot_pairs.jsonl"),
        "fewShotNewExampleIds": ["FS-COMPLEX-READINESS-01", "FS-COMPLEX-READINESS-02"],
        "r8ImmutableSource": {"fileCount": provenance_payload["fileCount"],
                              "aggregateSha256": provenance_payload["aggregateSha256"]},
        "offlineVerification": report, "apiCallsDuringPromotion": 0,
    }
    lock_path = LOCK_DIR / f"{BASE}.lock.json"
    sha_path = LOCK_DIR / f"{BASE}.sha256"
    if lock_path.exists() or sha_path.exists():
        raise FileExistsError("Refusing to overwrite an existing finalized R9 lock")
    write(lock_path, lock)
    lines = [f"{sha(workbook)}  {workbook.name}", f"{sha(lock_path)}  {lock_path.name}"]
    lines.extend(f"{value}  {relative}" for relative, value in sorted(bound.items()))
    sha_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for source in (workbook, lock_path, sha_path):
        target = MVP / source.name
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite root artifact: {target}")
        shutil.copy2(source, target)
    print(json.dumps({
        "status": "LOCKED", "lockId": LOCK_ID,
        "workbookSha256": lock["workbookSha256"], "lockJsonSha256": sha(lock_path),
        "registrySha256": bound["registry/term_registry.json"],
        "ontologySha256": bound["ontology/nltl_benchmark_vocabulary.ttl"],
        "requirementIndexSha256": bound["requirement_term_index.json"],
        "requirementEvidenceSha256": bound["evidence/stage1_approved.json"],
        "verificationPolicySha256": bound["evidence/verification_policy_r9.json"],
        "fewShotJsonlSha256": lock["fewShotJsonlSha256"],
        "r8ImmutableAggregateSha256": provenance_payload["aggregateSha256"],
        "apiCalls": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
