from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from rdflib import Graph, Namespace, RDFS
from rdflib.compare import isomorphic


MVP = Path(__file__).resolve().parents[2]
PIPE = MVP / "SHACL_GENERATION_PIPELINE"
R10 = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R10"
R9 = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R9"
NLTL = Namespace("https://w3id.org/nltl/vocab#")
EXPECTED = {"Static": 194, "Static Calculation": 43, "Complex": 42,
            "Dynamic": 19, "Physical Test": 15}
EXPECTED_STATUS = {"Static": (194, 194, 194, 0), "Static Calculation": (43, 41, 41, 2),
                   "Complex": (42, 34, 34, 8), "Dynamic": (19, 0, 0, 19),
                   "Physical Test": (15, 0, 0, 15)}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors: list[str] = []
    evidence, before = read(R10 / "evidence/stage1_approved.json"), read(R9 / "evidence/stage1_approved.json")
    index, old_index = read(R10 / "requirement_term_index.json"), read(R9 / "requirement_term_index.json")
    by_id = {r["id"]: r for r in evidence["requirements"]}
    before_by_id = {r["id"]: r for r in before["requirements"]}
    changed = {rid for rid in by_id if by_id[rid]["category"] != before_by_id[rid]["category"]}
    if changed != {"TRF-056", "TRF-128"}: errors.append(f"category delta differs: {sorted(changed)}")
    counts = dict(Counter(r["category"] for r in evidence["requirements"]))
    if counts != EXPECTED: errors.append(f"category counts differ: {counts}")

    old_registry = {t["localName"]: t for t in read(R9 / "registry/term_registry.json")}
    registry = {t["localName"]: t for t in read(R10 / "registry/term_registry.json")}
    if set(registry) - set(old_registry) != {"tableLookupPropellerLocation"}:
        errors.append("registry new-term delta is not exactly tableLookupPropellerLocation")
    if set(old_registry) - set(registry): errors.append("R10 removed registry terms")
    changed_existing = {name for name in old_registry if registry[name] != old_registry[name]}
    if changed_existing != {"sectionCalculationCaseStructuralMember"}:
        errors.append(f"unexpected changed existing registry terms: {sorted(changed_existing)}")
    if len(registry) != len(set(registry)): errors.append("registry local names are not unique")

    ttl = Graph().parse(R10 / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(R10 / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf): errors.append("ontology Turtle/RDFXML are not isomorphic")
    if (NLTL.sectionCalculationCaseStructuralMember, RDFS.domain, NLTL.calculationCase) not in ttl:
        errors.append("sectionCalculationCaseStructuralMember domain is not calculationCase")
    if (NLTL.sectionCalculationCaseStructuralMember, RDFS.domain, NLTL.localFrameSectionCalculationCase) in ttl:
        errors.append("retired sectionCalculationCaseStructuralMember domain remains")
    if (NLTL.tableLookupPropellerLocation, RDFS.domain, NLTL.tableLookupCase) not in ttl or \
       (NLTL.tableLookupPropellerLocation, RDFS.range, NLTL.propellerLocationValue) not in ttl:
        errors.append("tableLookupPropellerLocation domain/range is incorrect")

    binding = read(R10 / "r10_prelock_binding.json")
    bound_checked = 0
    for relative, expected in binding["boundMachineReadableArtifacts"].items():
        bound_checked += 1
        path = R10 / relative
        if not path.exists() or digest(path) != expected: errors.append(f"prelock hash mismatch: {relative}")
    provenance = read(R10 / "provenance/r9_immutable_source_hashes.json")
    changed_r9 = [rel for rel, expected in provenance["files"].items()
                  if not (MVP / rel).exists() or digest(MVP / rel) != expected]
    if changed_r9: errors.append(f"R9 immutability failure: {changed_r9[:10]}")

    sys.path.insert(0, str(PIPE / "src"))
    from nltl_pipeline.config import PipelineConfig
    from nltl_pipeline.retrieval.context import VocabularyRepository
    config = PipelineConfig.load(PIPE / "config/pipeline.r10-prelock-offline.json")
    vocabulary = VocabularyRepository(config)
    resolved = 0
    for rid in sorted(vocabulary.requirements):
        try: vocabulary.build_context_pack(rid); resolved += 1
        except Exception as exc: errors.append(f"context resolution failed for {rid}: {exc}")
    category_status = {}
    for category, expected in EXPECTED_STATUS.items():
        ids = {rid for rid, row in by_id.items() if row["category"] == category}
        complete = {rid for rid in ids if index["dependencyContracts"][rid].get("status") == "COMPLETE"}
        eligible = {rid for rid in ids if vocabulary.is_generation_eligible(by_id[rid])}
        actual = (len(ids), len(complete), len(eligible), len(ids - eligible))
        if actual != expected: errors.append(f"unexpected {category} status: {actual} vs {expected}")
        category_status[category] = {"total": actual[0], "complete": actual[1],
            "generationEligible": actual[2], "deferred": actual[3],
            "deferredRequirementIds": sorted(ids - eligible)}

    i2029 = index["dependencyContracts"]["I2-029"]
    if i2029["relationshipTerms"] != ["hasCalculationCase", "sectionCalculationCaseStructuralMember"]:
        errors.append("I2-029 relationship terms are incorrect")
    if "hasStructuralMember" in index["requirements"]["I2-029"]:
        errors.append("I2-029 still permits an arbitrary ship structural member")
    trf078 = index["dependencyContracts"]["TRF-078"]
    if "tableLookupPropellerLocation" not in trf078["relationshipTerms"] or "iceClass" not in trf078["relationshipTerms"]:
        errors.append("TRF-078 lookup selection paths are incomplete")
    trf128 = index["dependencyContracts"]["TRF-128"]
    if trf128["verificationMode"] != "DIRECT_STATIC" or trf128.get("formulaExpression"):
        errors.append("TRF-128 is not a formula-free DIRECT_STATIC contract")
    if "airReceiverCapacity" in index["requirements"]["TRF-128"] or "airCompressorCapacity" in vocabulary.all_terms:
        errors.append("TRF-128 retains or introduces forbidden capacity semantics")
    trf028 = index["dependencyContracts"]["TRF-028"]
    if "shipPerformanceExperienceEvidence" in trf028["evidenceTerms"] or \
       "shipPerformanceExperienceEvidence" not in index["requirements"]["TRF-028"]:
        errors.append("TRF-028 mandatory/general evidence scope is incorrect")
    if index["dependencyContracts"]["TRF-056"]["verificationMode"] != "DIRECT_STATIC":
        errors.append("TRF-056 is not DIRECT_STATIC")
    for key in ("requirements", "termOwners", "requirementTargetOwner", "semanticObligations"):
        if index[key].get("TRF-048") != old_index[key].get("TRF-048"):
            errors.append(f"TRF-048 changed in {key}")
    if index["dependencyContracts"]["TRF-048"] != old_index["dependencyContracts"]["TRF-048"]:
        errors.append("TRF-048 contract changed")

    workbook = read(R10 / "validation/final_lock_workbook_verification.json")
    if workbook.get("status") != "PASS" or not workbook.get("visualReview", "").startswith("PASS"):
        errors.append("workbook verification or visual review incomplete")
    final_lock_path = R10 / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R10.lock.json"
    final_sha_path = R10 / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R10.sha256"
    checksum_entries = 0
    if final_lock_path.exists() or final_sha_path.exists():
        if not final_lock_path.exists() or not final_sha_path.exists(): errors.append("final lock/checksum pair incomplete")
        else:
            if read(final_lock_path).get("lockId") != "VOCAB-LOCK-2026-08-20-R10": errors.append("final lock ID mismatch")
            for line in final_sha_path.read_text(encoding="utf-8").splitlines():
                expected, relative = line.split("  ", 1); checksum_entries += 1
                if not (R10 / relative).exists() or digest(R10 / relative) != expected:
                    errors.append(f"final checksum mismatch: {relative}")
            for name in (final_lock_path.name, final_sha_path.name, read(final_lock_path)["workbook"]):
                if not (MVP / name).exists() or (MVP / name).read_bytes() != (R10 / name).read_bytes():
                    errors.append(f"root R10 artifact mismatch: {name}")

    report = {"status": "PASS" if not errors else "FAIL", "lockCandidate": "VOCAB-LOCK-2026-08-20-R10",
        "requirements": len(by_id), "contextsResolved": resolved, "categoryChanges": len(changed),
        "categoryCounts": counts, "categoryStatus": category_status,
        "completeContracts": sum(c.get("status") == "COMPLETE" for c in index["dependencyContracts"].values()),
        "generationEligibleRequirements": sum(vocabulary.is_generation_eligible(row) for row in by_id.values()),
        "registryTerms": len(registry), "newCanonicalTerms": ["tableLookupPropellerLocation"],
        "modifiedCanonicalTerms": ["sectionCalculationCaseStructuralMember"],
        "boundHashesChecked": bound_checked, "finalChecksumEntriesChecked": checksum_entries,
        "r9ImmutableFilesChecked": len(provenance["files"]), "r9ImmutableAggregateSha256": provenance["aggregateSha256"],
        "apiCalls": 0, "errors": errors}
    output = R10 / "validation/r10_namespace_policy_and_integrity_report.json"
    if not final_lock_path.exists(): output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__": raise SystemExit(main())
