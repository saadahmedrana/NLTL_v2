from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic


MVP = Path(__file__).resolve().parents[2]
PIPE = MVP / "SHACL_GENERATION_PIPELINE"
R8 = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R8"
R7 = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R7"
CANONICAL = "https://w3id.org/nltl/vocab#"
RECLASSIFIED = {
    "I2-008", "I2-015", "I2-022", "I2-023", "I2-024", "I2-030", "I2-040",
    "I2-041", "I2-043", "I2-050", "I2-053", "I2-054", "I2-064", "I2-065",
    "TRF-020", "TRF-022", "TRF-025", "TRF-026", "TRF-030", "TRF-034",
    "TRF-041", "TRF-051", "TRF-060", "TRF-116",
}
EXPECTED = {"Static": 151, "Static Calculation": 65, "Complex": 64,
            "Dynamic": 17, "Physical Test": 16}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors = []
    evidence = read(R8 / "evidence/stage1_approved.json")
    r7_evidence = read(R7 / "evidence/stage1_approved.json")
    index = read(R8 / "requirement_term_index.json")
    r7_index = read(R7 / "requirement_term_index.json")
    by_id = {row["id"]: row for row in evidence["requirements"]}
    r7_by_id = {row["id"]: row for row in r7_evidence["requirements"]}
    changed = {rid for rid in by_id if by_id[rid]["category"] != r7_by_id[rid]["category"]}
    if changed != RECLASSIFIED:
        errors.append(f"classification delta differs from approved 24: {sorted(changed ^ RECLASSIFIED)}")
    counts = dict(Counter(row["category"] for row in evidence["requirements"]))
    if counts != EXPECTED:
        errors.append(f"category counts differ: {counts}")

    for rid in RECLASSIFIED:
        if r7_by_id[rid]["category"] != "Static Calculation" or by_id[rid]["category"] != "Complex":
            errors.append(f"incorrect category transition: {rid}")
        old = r7_index["dependencyContracts"][rid]
        new = index["dependencyContracts"][rid]
        for field in ("formulaExpression", "comparisonModel", "tableModel", "applicabilityTerms", "modelPaths"):
            empty = [] if field in {"applicabilityTerms", "modelPaths"} else ""
            if old.get(field, empty) != new.get(field, empty):
                errors.append(f"source semantic field changed instead of being preserved: {rid}.{field}")
        if new.get("verificationMode") != "COMPLEX_READINESS":
            errors.append(f"missing COMPLEX_READINESS mode: {rid}")
        if new.get("formulaExecutionRequired") is not False:
            errors.append(f"complex formula execution was not disabled: {rid}")

    if (R7 / "registry/term_registry.json").read_bytes() != (R8 / "registry/term_registry.json").read_bytes():
        errors.append("registry vocabulary changed")
    if (R7 / "ontology/nltl_benchmark_vocabulary.ttl").read_bytes() != (R8 / "ontology/nltl_benchmark_vocabulary.ttl").read_bytes():
        errors.append("ontology Turtle changed")
    if (R7 / "ontology/nltl_benchmark_vocabulary.rdf").read_bytes() != (R8 / "ontology/nltl_benchmark_vocabulary.rdf").read_bytes():
        errors.append("ontology RDF/XML changed")
    ttl = Graph().parse(R8 / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(R8 / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf):
        errors.append("R8 Turtle/RDF/XML are not isomorphic")

    binding = read(R8 / "r8_prelock_binding.json")
    checked = 0
    for relative, expected in binding["boundMachineReadableArtifacts"].items():
        checked += 1
        path = R8 / relative
        if not path.exists() or digest(path) != expected:
            errors.append(f"prelock hash mismatch: {relative}")
    provenance = read(R8 / "provenance/r7_immutable_source_hashes.json")
    changed_r7 = [relative for relative, expected in provenance["files"].items()
                  if not (MVP / relative).exists() or digest(MVP / relative) != expected]
    if changed_r7:
        errors.append(f"R7 immutability failure: {changed_r7[:10]}")

    sys.path.insert(0, str(PIPE / "src"))
    from nltl_pipeline.config import PipelineConfig
    from nltl_pipeline.retrieval.context import VocabularyRepository
    vocabulary = VocabularyRepository(PipelineConfig.load(PIPE / "config/pipeline.r8-prelock-offline.json"))
    resolved = 0
    try:
        for rid in sorted(vocabulary.requirements):
            vocabulary.build_context_pack(rid)
            resolved += 1
    except Exception as exc:
        errors.append(f"context resolution failed after {resolved}: {exc}")

    complex_ids = {rid for rid, row in by_id.items() if row["category"] == "Complex"}
    complete_complex = {rid for rid in complex_ids
                        if index["dependencyContracts"][rid].get("status") == "COMPLETE"
                        and index["dependencyContracts"][rid].get("verificationMode") == "COMPLEX_READINESS"}
    eligible_complex = {rid for rid in complex_ids if vocabulary.is_generation_eligible(by_id[rid])}
    deferred_complex = complex_ids - eligible_complex
    if (len(complex_ids), len(complete_complex), len(eligible_complex), len(deferred_complex)) != (64, 23, 23, 41):
        errors.append("unexpected Complex total/complete/eligible/deferred counts")
    if "I2-008" not in eligible_complex:
        errors.append("I2-008 was not enabled for completed readiness")
    if "I2-053" not in deferred_complex or not index["dependencyContracts"]["I2-053"].get("deferredReason"):
        errors.append("I2-053 deferred decision/reason missing")

    generator = (PIPE / "prompts/generator.txt").read_text(encoding="utf-8")
    validator = (PIPE / "prompts/validator.txt").read_text(encoding="utf-8")
    if "COMPLEX_READINESS" not in generator or "do not reproduce the complete engineering numerical calculation" not in generator:
        errors.append("generator readiness routing missing")
    if "COMPLEX_READINESS" not in validator or "does not execute or reconstruct" not in validator:
        errors.append("validator readiness boundary missing")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "lockCandidate": "VOCAB-LOCK-2026-08-20-R8",
        "categoryCounts": counts,
        "reclassifiedCount": len(changed),
        "reclassifiedRequirementIds": sorted(changed),
        "requirements": len(by_id),
        "contextsResolved": resolved,
        "completeContracts": sum(c.get("status") == "COMPLETE" for c in index["dependencyContracts"].values()),
        "generationEligibleRequirements": sum(vocabulary.is_generation_eligible(row) for row in by_id.values()),
        "complex": {
            "total": len(complex_ids), "completeReadiness": len(complete_complex),
            "generationEligible": len(eligible_complex), "deferred": len(deferred_complex),
            "deferredRequirementIds": sorted(deferred_complex),
            "deferredReasons": {rid: index["dependencyContracts"][rid].get("deferredReason")
                                or index["dependencyContracts"][rid].get("status") for rid in sorted(deferred_complex)},
        },
        "ontologyChangedFromR7": False,
        "registryChangedFromR7": False,
        "boundHashesChecked": checked,
        "r7ImmutableFilesChecked": len(provenance["files"]),
        "canonicalVocabularyNamespace": CANONICAL,
        "errors": errors,
        "apiCalls": 0,
    }
    output = R8 / "validation/r8_namespace_policy_and_integrity_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
