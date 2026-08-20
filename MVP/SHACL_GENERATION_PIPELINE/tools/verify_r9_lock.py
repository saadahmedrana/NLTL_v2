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
R9 = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R9"
R8 = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R8"
EXPECTED = {"Static": 192, "Static Calculation": 45, "Complex": 42,
            "Dynamic": 19, "Physical Test": 15}
EXPECTED_STATUS = {
    "Static": (192, 192, 192, 0),
    "Static Calculation": (45, 43, 43, 2),
    "Complex": (42, 34, 34, 8),
    "Dynamic": (19, 0, 0, 19),
    "Physical Test": (15, 0, 0, 15),
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors: list[str] = []
    evidence = read(R9 / "evidence/stage1_approved.json")
    before = read(R8 / "evidence/stage1_approved.json")
    index = read(R9 / "requirement_term_index.json")
    decisions = read(R9 / "registry/r9_classification_change_decisions.json")
    by_id = {row["id"]: row for row in evidence["requirements"]}
    before_by_id = {row["id"]: row for row in before["requirements"]}
    changed = {rid for rid in by_id if by_id[rid]["category"] != before_by_id[rid]["category"]}
    approved = {row["requirementId"] for row in decisions["changes"]}
    if len(changed) != 62 or changed != approved:
        errors.append("classification delta is not exactly the approved 62 requirements")
    counts = dict(Counter(row["category"] for row in evidence["requirements"]))
    if counts != EXPECTED:
        errors.append(f"category counts differ: {counts}")

    if (R8 / "registry/term_registry.json").read_bytes() != (R9 / "registry/term_registry.json").read_bytes():
        errors.append("registry changed from R8")
    if (R8 / "ontology/nltl_benchmark_vocabulary.ttl").read_bytes() != (R9 / "ontology/nltl_benchmark_vocabulary.ttl").read_bytes():
        errors.append("ontology Turtle changed from R8")
    if (R8 / "ontology/nltl_benchmark_vocabulary.rdf").read_bytes() != (R9 / "ontology/nltl_benchmark_vocabulary.rdf").read_bytes():
        errors.append("ontology RDF/XML changed from R8")
    ttl = Graph().parse(R9 / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(R9 / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf):
        errors.append("R9 ontology serializations are not isomorphic")

    binding = read(R9 / "r9_prelock_binding.json")
    bound_checked = 0
    for relative, expected in binding["boundMachineReadableArtifacts"].items():
        bound_checked += 1
        path = R9 / relative
        if not path.exists() or digest(path) != expected:
            errors.append(f"prelock hash mismatch: {relative}")
    provenance = read(R9 / "provenance/r8_immutable_source_hashes.json")
    changed_r8 = [relative for relative, expected in provenance["files"].items()
                  if not (MVP / relative).exists() or digest(MVP / relative) != expected]
    if changed_r8:
        errors.append(f"R8 immutability failure: {changed_r8[:10]}")

    sys.path.insert(0, str(PIPE / "src"))
    from nltl_pipeline.config import PipelineConfig
    from nltl_pipeline.retrieval.context import VocabularyRepository
    from nltl_pipeline.retrieval.fewshot import FewShotSelector
    config = PipelineConfig.load(PIPE / "config/pipeline.r9-prelock-offline.json")
    vocabulary = VocabularyRepository(config)
    resolved = 0
    for rid in sorted(vocabulary.requirements):
        try:
            vocabulary.build_context_pack(rid)
            resolved += 1
        except Exception as exc:
            errors.append(f"context resolution failed for {rid}: {exc}")

    category_status = {}
    for category, expected in EXPECTED_STATUS.items():
        ids = {rid for rid, row in by_id.items() if row["category"] == category}
        complete = {rid for rid in ids if index["dependencyContracts"][rid].get("status") == "COMPLETE"}
        eligible = {rid for rid in ids if vocabulary.is_generation_eligible(by_id[rid])}
        actual = (len(ids), len(complete), len(eligible), len(ids - eligible))
        category_status[category] = {
            "total": actual[0], "complete": actual[1], "generationEligible": actual[2],
            "deferred": actual[3], "deferredRequirementIds": sorted(ids - eligible),
            "deferredReasons": {rid: index["dependencyContracts"][rid].get("deferredReason")
                                or index["dependencyContracts"][rid].get("status") for rid in sorted(ids - eligible)},
        }
        if actual != expected:
            errors.append(f"unexpected {category} status counts: {actual}, expected {expected}")

    insufficient = {row["requirementId"] for row in decisions["changes"] if not row["vocabularySufficient"]}
    if insufficient != {"I2-003", "TRF-039"}:
        errors.append(f"unexpected changed-case vocabulary blockers: {sorted(insufficient)}")
    available = set(vocabulary.all_terms)
    for rid in approved:
        missing = sorted(set(index["requirements"][rid]) - available)
        if missing:
            errors.append(f"changed requirement has absent indexed terms: {rid} {missing}")

    catalog = read(R9 / "few_shots/catalog.json")
    few_validation = read(R9 / "few_shots/validation_report.json")
    if catalog.get("exampleCount") != 22 or not few_validation.get("allChecksPassed"):
        errors.append("R9 few-shot snapshot is not 22/22 validated")
    selector = FewShotSelector(config.path("few_shot_jsonl"))
    picks = selector.select(vocabulary.build_context_pack("I2-030"), 2)
    selected_ids = [row["exampleId"] for row in picks]
    if selected_ids != ["FS-COMPLEX-READINESS-01", "FS-COMPLEX-READINESS-02"]:
        errors.append(f"Complex selection did not prefer readiness examples: {selected_ids}")

    generator = (PIPE / "prompts/generator.txt").read_text(encoding="utf-8")
    validator = (PIPE / "prompts/validator.txt").read_text(encoding="utf-8")
    for token in ("DIRECT_STATIC", "DIRECT_CALCULATION", "COMPLEX_READINESS", "Dynamic", "Physical Test"):
        if token not in generator or token not in validator:
            errors.append(f"five-category prompt routing token missing: {token}")

    workbook = read(R9 / "validation/final_lock_workbook_verification.json")
    if workbook.get("status") != "PASS" or not workbook.get("visualReview", "").startswith("PASS"):
        errors.append("workbook verification or visual review is incomplete")

    final_lock_path = R9 / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R9.lock.json"
    final_sha_path = R9 / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R9.sha256"
    checksum_entries = 0
    if final_lock_path.exists() or final_sha_path.exists():
        if not final_lock_path.exists() or not final_sha_path.exists():
            errors.append("R9 final lock/checksum pair is incomplete")
        else:
            final_lock = read(final_lock_path)
            if final_lock.get("lockId") != "VOCAB-LOCK-2026-08-20-R9":
                errors.append("R9 final lock identity mismatch")
            for line in final_sha_path.read_text(encoding="utf-8").splitlines():
                expected, relative = line.split("  ", 1)
                path = R9 / relative
                checksum_entries += 1
                if not path.exists() or digest(path) != expected:
                    errors.append(f"final checksum mismatch: {relative}")
            for name in (final_lock["workbook"], final_lock_path.name, final_sha_path.name):
                root_copy = MVP / name
                lock_copy = R9 / name
                if not root_copy.exists() or root_copy.read_bytes() != lock_copy.read_bytes():
                    errors.append(f"root R9 artifact mismatch: {name}")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "lockCandidate": "VOCAB-LOCK-2026-08-20-R9",
        "requirements": len(by_id), "contextsResolved": resolved,
        "categoryChanges": len(changed), "categoryCounts": counts,
        "categoryStatus": category_status,
        "completeContracts": sum(c.get("status") == "COMPLETE" for c in index["dependencyContracts"].values()),
        "generationEligibleRequirements": sum(vocabulary.is_generation_eligible(row) for row in by_id.values()),
        "changedRequirementVocabularyBlockers": sorted(insufficient),
        "ontologyChangedFromR8": False, "registryChangedFromR8": False,
        "fewShots": {"count": catalog.get("exampleCount"), "validation": "PASS",
                     "complexSelection": selected_ids},
        "boundHashesChecked": bound_checked,
        "finalChecksumEntriesChecked": checksum_entries,
        "r8ImmutableFilesChecked": len(provenance["files"]),
        "r8ImmutableAggregateSha256": provenance["aggregateSha256"],
        "apiCalls": 0, "errors": errors,
    }
    output = R9 / "validation/r9_namespace_policy_and_integrity_report.json"
    # Before finalization this report becomes a bound lock artifact. After the
    # lock exists, verification is strictly read-only so its own evidence cannot
    # invalidate the checksum it is checking.
    if not final_lock_path.exists():
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
