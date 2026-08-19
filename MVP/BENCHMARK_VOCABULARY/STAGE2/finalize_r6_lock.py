from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic


MVP = Path(__file__).resolve().parents[2]
LOCK_DIR = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R6"
BASE = "benchmark_vocabulary_stage2_LOCK-2026-08-19-R6"
LOCK_ID = "VOCAB-LOCK-2026-08-19-R6"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> None:
    workbook = LOCK_DIR / f"{BASE}.xlsx"
    workbook_check = LOCK_DIR / "validation/final_lock_workbook_verification.json"
    offline = LOCK_DIR / "validation/r6_offline_validation.json"
    integrity = LOCK_DIR / "validation/r6_namespace_and_integrity_report.json"
    for path in (workbook, workbook_check, offline, integrity):
        if not path.exists():
            raise FileNotFoundError(path)
    if read(workbook_check).get("status") != "PASS" or not read(workbook_check).get("visualReview", "").startswith("PASS"):
        raise RuntimeError("R6 workbook programmatic/visual verification is incomplete")
    if read(offline).get("status") != "PASS" or read(integrity).get("status") != "PASS":
        raise RuntimeError("R6 offline verification is not PASS")
    ttl = Graph().parse(LOCK_DIR / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(LOCK_DIR / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf):
        raise RuntimeError("R6 ontology serializations are not isomorphic")

    prelock = read(LOCK_DIR / "prelock_manifest.json")
    bound = {relative: sha(LOCK_DIR / relative) for relative in prelock["boundArtifacts"]}
    for relative in (
        "validation/final_lock_workbook_verification.json",
        "validation/r6_offline_validation.json",
        "validation/r6_namespace_and_integrity_report.json",
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
    registry = read(LOCK_DIR / "registry/term_registry.json")
    index = read(LOCK_DIR / "requirement_term_index.json")
    audit = read(LOCK_DIR / "validation/global_consistency_audit/r6_global_consistency_audit.json")
    lock = {
        "lockId": LOCK_ID,
        "status": "LOCKED_FOR_DEVELOPMENT_TERRA_CONFIRMATION",
        "lockedDate": "2026-08-19",
        "revision": "R6",
        "vocabularyVersion": "2.16.0-stage2-final-r6",
        "supersedes": "VOCAB-LOCK-2026-08-19-R5",
        "canonicalVocabularyNamespace": "https://w3id.org/nltl/vocab#",
        "workbook": workbook.name,
        "workbookSha256": sha(workbook),
        "counts": {
            "requirements": 313,
            "generationEligibleRequirements": 238,
            "completeDependencyContracts": 238,
            "registryTerms": len(registry),
            "canonicalTermsIncludingInfrastructure": 1682,
            "newVocabularyTerms": 4,
        },
        "globalAudit": {
            "contractsAudited": audit["contractsAudited"],
            "flagged": audit["flagged"],
            "confirmedDefective": audit["confirmedDefective"],
            "falsePositives": audit["falsePositives"],
        },
        "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {"requirement_term_index.json": bound["requirement_term_index.json"]},
        "promptSha256": prompts,
        "pipelineSourceSha256": pipeline_sources,
        "fewShotJsonlSha256": sha(MVP / "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/few_shot_pairs.jsonl"),
        "offlineVerification": read(offline),
        "apiCallsDuringPromotion": 0,
    }
    lock_path = LOCK_DIR / f"{BASE}.lock.json"
    sha_path = LOCK_DIR / f"{BASE}.sha256"
    write(lock_path, lock)
    lines = [f"{sha(workbook)}  {workbook.name}", f"{sha(lock_path)}  {lock_path.name}"]
    lines.extend(f"{value}  {relative}" for relative, value in sorted(bound.items()))
    sha_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for source in (workbook, lock_path, sha_path):
        target = MVP / source.name
        if target.exists():
            if "2026-08-19-R6" not in target.name:
                raise FileExistsError(f"Refusing to overwrite non-R6 root artifact: {target}")
        shutil.copy2(source, target)
    print(json.dumps({
        "status": "LOCKED",
        "lockId": LOCK_ID,
        "workbookSha256": lock["workbookSha256"],
        "registrySha256": bound["registry/term_registry.json"],
        "ontologySha256": bound["ontology/nltl_benchmark_vocabulary.ttl"],
        "requirementIndexSha256": bound["requirement_term_index.json"],
        "rootArtifacts": [str((MVP / name).relative_to(MVP)) for name in (workbook.name, lock_path.name, sha_path.name)],
    }, indent=2))


if __name__ == "__main__":
    main()
