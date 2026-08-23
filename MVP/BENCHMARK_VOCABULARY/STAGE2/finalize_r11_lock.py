from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic


MVP = Path(__file__).resolve().parents[2]
LOCK_DIR = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R11"
BASE = "benchmark_vocabulary_stage2_LOCK-2026-08-21-R11"
LOCK_ID = "VOCAB-LOCK-2026-08-21-R11"


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path: Path): return json.loads(path.read_text(encoding="utf-8"))
def write(path: Path, value): path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> None:
    workbook = LOCK_DIR / f"{BASE}.xlsx"
    workbook_check = LOCK_DIR / "validation/final_lock_workbook_verification.json"
    offline = LOCK_DIR / "validation/r11_offline_validation.json"
    integrity = LOCK_DIR / "validation/r11_namespace_policy_and_integrity_report.json"
    provenance = LOCK_DIR / "provenance/r10_immutable_source_hashes.json"
    for path in (workbook, workbook_check, offline, integrity, provenance):
        if not path.exists(): raise FileNotFoundError(path)
    if read(workbook_check).get("status") != "PASS" or not read(workbook_check).get("visualReview", "").startswith("PASS"):
        raise RuntimeError("R11 workbook verification incomplete")
    if read(offline).get("status") != "PASS" or read(integrity).get("status") != "PASS":
        raise RuntimeError("R11 offline verification incomplete")
    ttl = Graph().parse(LOCK_DIR / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(LOCK_DIR / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf): raise RuntimeError("R11 ontology serializations not isomorphic")

    prelock = read(LOCK_DIR / "prelock_manifest.json")
    bound = {relative: sha(LOCK_DIR / relative) for relative in prelock["boundArtifacts"]}
    for relative in ("validation/final_lock_workbook_verification.json",
                     "validation/r11_namespace_policy_and_integrity_report.json",
                     "validation/r11_offline_validation.json"):
        bound[relative] = sha(LOCK_DIR / relative)
    pipeline = MVP / "SHACL_GENERATION_PIPELINE"
    prompt_paths = ("r11/generator.txt", "r11/validator.txt", "vocabulary_matcher.txt", "control_v1_3/syntax_repair.txt")
    prompts = {name: sha(pipeline / "prompts" / name) for name in prompt_paths}
    source_paths = ("src/nltl_pipeline/retrieval/context.py", "src/nltl_pipeline/retrieval/fewshot.py",
                    "src/nltl_pipeline/validation/shacl.py", "src/nltl_pipeline/prompts.py",
                    "src/nltl_pipeline/orchestration/runner.py", "src/nltl_pipeline/api/client.py",
                    "src/nltl_pipeline/config.py")
    sources = {relative: sha(pipeline / relative) for relative in source_paths}
    report, integrity_report, registry, provenance_payload = read(offline), read(integrity), \
        read(LOCK_DIR / "registry/term_registry.json"), read(provenance)
    decisions = read(LOCK_DIR / "registry/r11_source_grounded_change_decisions.json")
    lock = {"lockId": LOCK_ID, "status": "LOCKED_SOURCE_GROUNDED_CORRECTIONS_R11",
        "lockedDate": "2026-08-21", "revision": "R11", "vocabularyVersion": "2.21.0-stage2-final-r11",
        "supersedes": "VOCAB-LOCK-2026-08-20-R10", "canonicalVocabularyNamespace": "https://w3id.org/nltl/vocab#",
        "workbook": workbook.name, "workbookSha256": sha(workbook),
        "counts": {"requirements": 313, "generationEligibleRequirements": report["generationEligibleRequirements"],
            "completeDependencyContracts": report["completeContracts"], "registryTerms": len(registry),
            "canonicalTermsIncludingInfrastructure": 1718, "categoryChanges": 6,
            "fewShotExamples": 22, "newVocabularyTerms": 25, "modifiedVocabularyTerms": 1},
        "categoryCounts": report["categoryCounts"], "categoryStatus": report["categoryStatus"],
        "newCanonicalTerms": decisions["newCanonicalTerms"],
        "modifiedCanonicalTerms": decisions["modifiedCanonicalTerms"],
        "affectedRequirements": sorted(set(decisions["categoryChanges"]) | set(decisions["contractOnlyChanges"]) |
                                       {"I2-002", "I2-018", "I2-048", "IMO-002", "IMO-011", "IMO-101",
                                        "IMO-117", "IMO-123", "TRF-043", "TRF-048", "TRF-063", "TRF-075", "TRF-109"}),
        "directCalculationDiagnostic": {"count": 23, "reportOnly": True},
        "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {"requirement_term_index.json": bound["requirement_term_index.json"]},
        "promptSha256": prompts, "pipelineSourceSha256": sources,
        "r10ImmutableSource": {"fileCount": provenance_payload["fileCount"],
                              "aggregateSha256": provenance_payload["aggregateSha256"]},
        "offlineVerification": report, "apiCallsDuringPromotion": 0}
    lock_path, sha_path = LOCK_DIR / f"{BASE}.lock.json", LOCK_DIR / f"{BASE}.sha256"
    if lock_path.exists() or sha_path.exists(): raise FileExistsError("Refusing to overwrite finalized R11 lock")
    write(lock_path, lock)
    lines = [f"{sha(workbook)}  {workbook.name}", f"{sha(lock_path)}  {lock_path.name}"]
    lines.extend(f"{value}  {relative}" for relative, value in sorted(bound.items()))
    sha_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for source in (workbook, lock_path, sha_path):
        target = MVP / source.name
        if target.exists(): raise FileExistsError(f"Refusing to overwrite root R11 artifact: {target}")
        shutil.copy2(source, target)
    print(json.dumps({"status": "LOCKED", "lockId": LOCK_ID, "workbookSha256": lock["workbookSha256"],
        "lockJsonSha256": sha(lock_path), "checksumManifestSha256": sha(sha_path),
        "registrySha256": bound["registry/term_registry.json"],
        "ontologyTurtleSha256": bound["ontology/nltl_benchmark_vocabulary.ttl"],
        "ontologyRdfXmlSha256": bound["ontology/nltl_benchmark_vocabulary.rdf"],
        "requirementIndexSha256": bound["requirement_term_index.json"],
        "requirementEvidenceSha256": bound["evidence/stage1_approved.json"],
        "verificationPolicySha256": bound["evidence/verification_policy_r11.json"],
        "r10ImmutableAggregateSha256": provenance_payload["aggregateSha256"], "apiCalls": 0}, indent=2))


if __name__ == "__main__": main()
