from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic


MVP = Path(__file__).resolve().parents[2]
LOCK_DIR = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R7"
BASE = "benchmark_vocabulary_stage2_LOCK-2026-08-20-R7"
LOCK_ID = "VOCAB-LOCK-2026-08-20-R7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> None:
    workbook = LOCK_DIR / f"{BASE}.xlsx"
    workbook_check = LOCK_DIR / "validation/final_lock_workbook_verification.json"
    offline = LOCK_DIR / "validation/r7_offline_validation.json"
    integrity = LOCK_DIR / "validation/r7_namespace_and_integrity_report.json"
    provenance = LOCK_DIR / "provenance/r6_immutable_source_hashes.json"
    for path in (workbook, workbook_check, offline, integrity, provenance):
        if not path.exists():
            raise FileNotFoundError(path)
    if read(workbook_check).get("status") != "PASS" or not read(workbook_check).get("visualReview", "").startswith("PASS"):
        raise RuntimeError("R7 workbook programmatic/visual verification is incomplete")
    if read(offline).get("status") != "PASS" or read(integrity).get("status") != "PASS":
        raise RuntimeError("R7 offline verification is not PASS")
    ttl = Graph().parse(LOCK_DIR / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(LOCK_DIR / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf):
        raise RuntimeError("R7 Turtle and RDF/XML are not isomorphic")

    prelock = read(LOCK_DIR / "prelock_manifest.json")
    bound = {relative: sha(LOCK_DIR / relative) for relative in prelock["boundArtifacts"]}
    for relative in (
        "validation/final_lock_workbook_verification.json",
        "validation/r7_offline_validation.json",
        "validation/r7_namespace_and_integrity_report.json",
    ):
        bound[relative] = sha(LOCK_DIR / relative)

    prompts = {
        name: sha(MVP / "SHACL_GENERATION_PIPELINE/prompts" / name)
        for name in ("generator.txt", "validator.txt", "vocabulary_matcher.txt", "syntax_repair.txt")
    }
    pipeline_sources = {
        relative: sha(MVP / "SHACL_GENERATION_PIPELINE" / relative)
        for relative in (
            "src/nltl_pipeline/orchestration/runner.py",
            "src/nltl_pipeline/validation/shacl.py",
            "src/nltl_pipeline/prompts.py",
            "src/nltl_pipeline/api/client.py",
            "src/nltl_pipeline/config.py",
        )
    }
    r6_lock = read(MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-19-R6.lock.json")
    if prompts != r6_lock["promptSha256"]:
        raise RuntimeError("Prompt hashes changed during R7 vocabulary-only promotion")
    pipeline_matches_r6 = pipeline_sources == r6_lock["pipelineSourceSha256"]

    registry = read(LOCK_DIR / "registry/term_registry.json")
    index = read(LOCK_DIR / "requirement_term_index.json")
    evidence = read(LOCK_DIR / "evidence/r7_source_grounded_corrections.json")
    r6_provenance = read(provenance)
    lock = {
        "lockId": LOCK_ID,
        "status": "LOCKED_SOURCE_GROUNDED_R7",
        "lockedDate": "2026-08-20",
        "revision": "R7",
        "vocabularyVersion": "2.17.0-stage2-final-r7",
        "supersedes": "VOCAB-LOCK-2026-08-19-R6",
        "canonicalVocabularyNamespace": "https://w3id.org/nltl/vocab#",
        "workbook": workbook.name,
        "workbookSha256": sha(workbook),
        "counts": {
            "requirements": 313,
            "generationEligibleRequirements": 238,
            "completeDependencyContracts": sum(c.get("status") == "COMPLETE" for c in index["dependencyContracts"].values()),
            "registryTerms": len(registry),
            "canonicalTermsIncludingInfrastructure": 1692,
            "newVocabularyTerms": len(evidence["newCanonicalTerms"]),
            "implementedRequirementCorrections": len(evidence["implementedRequirementIds"]),
            "humanReviewUnchanged": len(evidence["intentionallyUnchangedHumanReview"]),
        },
        "newCanonicalTerms": evidence["newCanonicalTerms"],
        "implementedRequirementIds": evidence["implementedRequirementIds"],
        "intentionallyUnchangedHumanReview": evidence["intentionallyUnchangedHumanReview"],
        "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {"requirement_term_index.json": bound["requirement_term_index.json"]},
        "promptSha256": prompts,
        "promptHashesUnchangedFromR6": True,
        "pipelineSourceSha256": pipeline_sources,
        "pipelineSourceHashesUnchangedFromR6": pipeline_matches_r6,
        "pipelineSourceNote": "Current hardened pipeline sources are hash-bound as found and were not edited by the R7 vocabulary task; runner, prompt assembly and SHACL validation already differed from the earlier R6 lock before this task.",
        "fewShotJsonlSha256": sha(MVP / "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/few_shot_pairs.jsonl"),
        "r6ImmutableSource": {
            "fileCount": r6_provenance["fileCount"],
            "aggregateSha256": r6_provenance["aggregateSha256"],
        },
        "offlineVerification": read(offline),
        "apiCallsDuringPromotion": 0,
    }
    lock_path = LOCK_DIR / f"{BASE}.lock.json"
    sha_path = LOCK_DIR / f"{BASE}.sha256"
    if lock_path.exists() or sha_path.exists():
        raise FileExistsError("Refusing to overwrite an existing finalized R7 lock")
    write(lock_path, lock)
    lines = [f"{sha(workbook)}  {workbook.name}", f"{sha(lock_path)}  {lock_path.name}"]
    lines.extend(f"{value}  {relative}" for relative, value in sorted(bound.items()))
    sha_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for source in (workbook, lock_path, sha_path):
        target = MVP / source.name
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite existing root artifact: {target}")
        shutil.copy2(source, target)
    print(json.dumps({
        "status": "LOCKED", "lockId": LOCK_ID,
        "workbookSha256": lock["workbookSha256"],
        "registrySha256": bound["registry/term_registry.json"],
        "ontologySha256": bound["ontology/nltl_benchmark_vocabulary.ttl"],
        "requirementIndexSha256": bound["requirement_term_index.json"],
        "r6ImmutableAggregateSha256": r6_provenance["aggregateSha256"],
        "rootArtifacts": [str((MVP / name).relative_to(MVP)) for name in (workbook.name, lock_path.name, sha_path.name)],
        "apiCalls": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
