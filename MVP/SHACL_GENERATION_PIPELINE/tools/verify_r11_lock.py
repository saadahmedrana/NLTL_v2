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
R11 = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R11"
R10 = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R10"
NLTL = Namespace("https://w3id.org/nltl/vocab#")
EXPECTED = {"Static": 190, "Static Calculation": 44, "Complex": 45,
            "Dynamic": 19, "Physical Test": 15}
EXPECTED_STATUS = {"Static": (190, 189, 189, 1), "Static Calculation": (44, 42, 42, 2),
                   "Complex": (45, 37, 37, 8), "Dynamic": (19, 0, 0, 19),
                   "Physical Test": (15, 0, 0, 15)}
EXPECTED_CHANGED = {"I2-017", "IMO-011", "TRF-012", "TRF-080", "TRF-084", "TRF-086"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors: list[str] = []
    evidence, before = read(R11 / "evidence/stage1_approved.json"), read(R10 / "evidence/stage1_approved.json")
    index, old_index = read(R11 / "requirement_term_index.json"), read(R10 / "requirement_term_index.json")
    by_id = {r["id"]: r for r in evidence["requirements"]}
    before_by_id = {r["id"]: r for r in before["requirements"]}
    changed = {rid for rid in by_id if by_id[rid]["category"] != before_by_id[rid]["category"]}
    if changed != EXPECTED_CHANGED: errors.append(f"category delta differs: {sorted(changed)}")
    counts = dict(Counter(r["category"] for r in evidence["requirements"]))
    if counts != EXPECTED: errors.append(f"category counts differ: {counts}")

    old_registry = {t["localName"]: t for t in read(R10 / "registry/term_registry.json")}
    registry = {t["localName"]: t for t in read(R11 / "registry/term_registry.json")}
    decisions = read(R11 / "registry/r11_source_grounded_change_decisions.json")
    expected_new = set(decisions["newCanonicalTerms"])
    if set(registry) - set(old_registry) != expected_new:
        errors.append("registry new-term delta differs from the approved 25-term R11 set")
    if set(old_registry) - set(registry): errors.append("R11 removed registry terms")
    changed_existing = {name for name in old_registry if registry[name] != old_registry[name]}
    if changed_existing != {"frameBoundaryConditionType"}:
        errors.append(f"unexpected changed existing registry terms: {sorted(changed_existing)}")
    if len(registry) != len(set(registry)): errors.append("registry local names are not unique")

    ttl = Graph().parse(R11 / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(R11 / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf): errors.append("ontology Turtle/RDFXML are not isomorphic")
    if (NLTL.frameBoundaryConditionType, RDFS.domain, NLTL.frame) not in ttl:
        errors.append("frameBoundaryConditionType domain is not frame")
    if (NLTL.frameBoundaryConditionType, RDFS.domain, NLTL.transverseFrame) in ttl:
        errors.append("retired frameBoundaryConditionType domain remains")
    for local in expected_new:
        if not any(ttl.triples((NLTL[local], None, None))): errors.append(f"new R11 term absent from ontology: {local}")

    binding = read(R11 / "r11_prelock_binding.json")
    bound_checked = 0
    for relative, expected in binding["boundMachineReadableArtifacts"].items():
        bound_checked += 1
        path = R11 / relative
        if not path.exists() or digest(path) != expected: errors.append(f"prelock hash mismatch: {relative}")
    provenance = read(R11 / "provenance/r10_immutable_source_hashes.json")
    changed_R10 = [rel for rel, expected in provenance["files"].items()
                  if not (MVP / rel).exists() or digest(MVP / rel) != expected]
    if changed_R10: errors.append(f"R10 immutability failure: {changed_R10[:10]}")

    sys.path.insert(0, str(PIPE / "src"))
    from nltl_pipeline.config import PipelineConfig
    from nltl_pipeline.retrieval.context import VocabularyRepository
    config = PipelineConfig.load(PIPE / "config/pipeline.r11-prelock-offline.json")
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

    if index["dependencyContracts"]["I2-002"].get("status") != "DEFERRED_SCOPE_ONLY":
        errors.append("I2-002 is not DEFERRED_SCOPE_ONLY")
    if index["dependencyContracts"]["I2-023"].get("operandTerms") != ["averageIcePressure","frameSpacing","frameSpan","framingAngleOmega","loadPatchHeight","peakPressureFactor","selectedHullAreaFactor","yieldStrength"]:
        errors.append("I2-023 operand cleanup differs")
    if index["dependencyContracts"]["I2-035"].get("resultTerms") != ["requiredLongitudinalFrameShearArea"]:
        errors.append("I2-035 result cleanup differs")
    if "steelGradeRequirementCasePlating" not in index["dependencyContracts"]["I2-048"].get("relationshipTerms", []):
        errors.append("I2-048 case-to-plating path is missing")
    if "searchlightContinuousUseSuitabilityStatus" not in index["requirements"]["IMO-072"] or "continuousUseSuitabilityStatus" in index["requirements"]["IMO-072"]:
        errors.append("IMO-072 stale-term replacement differs")
    if index["dependencyContracts"]["IMO-101"].get("relationshipTerms") != ["hasPolarRoutePlan"]:
        errors.append("IMO-101 polar-route-plan path differs")
    if "strengtheningEnvelopeBoundary" not in index["dependencyContracts"]["TRF-063"].get("relationshipTerms", []):
        errors.append("TRF-063 envelope boundary relation is missing")
    if set(index["dependencyContracts"]["TRF-075"].get("relationshipTerms", [])) != {"hasPropellerBladeLoadCase","propellerBladeLoadCaseBlade","propellerBladeLoadCaseIceBlock"}:
        errors.append("TRF-075 load-case relationships differ")
    diagnostic = read(R11 / "validation/r11_direct_calculation_completeness_diagnostic.json")
    if diagnostic.get("diagnosticCount") != 23 or diagnostic.get("contractsModified") or diagnostic.get("eligibilityModified"):
        errors.append("DIRECT_CALCULATION diagnostic is not the approved report-only result")

    workbook = read(R11 / "validation/final_lock_workbook_verification.json")
    if workbook.get("status") != "PASS" or not workbook.get("visualReview", "").startswith("PASS"):
        errors.append("workbook verification or visual review incomplete")
    final_lock_path = R11 / "benchmark_vocabulary_stage2_LOCK-2026-08-21-R11.lock.json"
    final_sha_path = R11 / "benchmark_vocabulary_stage2_LOCK-2026-08-21-R11.sha256"
    checksum_entries = 0
    if final_lock_path.exists() or final_sha_path.exists():
        if not final_lock_path.exists() or not final_sha_path.exists(): errors.append("final lock/checksum pair incomplete")
        else:
            if read(final_lock_path).get("lockId") != "VOCAB-LOCK-2026-08-21-R11": errors.append("final lock ID mismatch")
            for line in final_sha_path.read_text(encoding="utf-8").splitlines():
                expected, relative = line.split("  ", 1); checksum_entries += 1
                if not (R11 / relative).exists() or digest(R11 / relative) != expected:
                    errors.append(f"final checksum mismatch: {relative}")
            for name in (final_lock_path.name, final_sha_path.name, read(final_lock_path)["workbook"]):
                if not (MVP / name).exists() or (MVP / name).read_bytes() != (R11 / name).read_bytes():
                    errors.append(f"root R11 artifact mismatch: {name}")

    report = {"status": "PASS" if not errors else "FAIL", "lockCandidate": "VOCAB-LOCK-2026-08-21-R11",
        "requirements": len(by_id), "contextsResolved": resolved, "categoryChanges": len(changed),
        "categoryCounts": counts, "categoryStatus": category_status,
        "completeContracts": sum(c.get("status") == "COMPLETE" for c in index["dependencyContracts"].values()),
        "generationEligibleRequirements": sum(vocabulary.is_generation_eligible(row) for row in by_id.values()),
        "registryTerms": len(registry), "newCanonicalTerms": sorted(expected_new),
        "modifiedCanonicalTerms": ["frameBoundaryConditionType"],
        "boundHashesChecked": bound_checked, "finalChecksumEntriesChecked": checksum_entries,
        "r10ImmutableFilesChecked": len(provenance["files"]), "r10ImmutableAggregateSha256": provenance["aggregateSha256"],
        "apiCalls": 0, "errors": errors}
    output = R11 / "validation/r11_namespace_policy_and_integrity_report.json"
    if not final_lock_path.exists(): output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__": raise SystemExit(main())
