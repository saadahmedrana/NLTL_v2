from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from rdflib import Graph, Namespace, RDF, RDFS
from rdflib.compare import isomorphic
from rdflib.namespace import OWL


MVP = Path(__file__).resolve().parents[2]
PIPELINE = MVP / "SHACL_GENERATION_PIPELINE"
LOCK = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R7"
CANONICAL = "https://w3id.org/nltl/vocab#"
NLTL = Namespace(CANONICAL)
TEXT_SUFFIXES = {".ttl", ".rdf", ".json", ".jsonl", ".jsonld", ".csv", ".md", ".txt", ".py", ".mjs"}
ACTIVE_ROOTS = [
    LOCK,
    PIPELINE / "src",
    PIPELINE / "tests",
    PIPELINE / "prompts",
    PIPELINE / "config/pipeline.r7-prelock-offline.json",
    MVP / "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES",
]
EXPECTED_NEW = {
    "calculationCaseAssessedHullStructure", "frameAttachmentRecord", "hasWeld",
    "iceConditionLessSevereThanCategoryAAndB", "linearCalculationMethodValue",
    "mediumFirstYearIceWithPossibleOldIceInclusions", "ownerRequested2008EngineOutputRequirements",
    "timberLoadLineMarkApplicable", "warningTriangleUpperEdgeVerticallyAboveIceMark", "weld",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files():
    seen = set()
    for root in ACTIVE_ROOTS:
        candidates = [root] if root.is_file() else root.rglob("*") if root.exists() else []
        for path in candidates:
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and path not in seen:
                seen.add(path)
                yield path


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors = []
    counts = {"json": 0, "jsonlRecords": 0, "turtle": 0, "rdfXml": 0}
    active_files = list(files())
    for path in active_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "nltl-benchmark" in text:
            errors.append(f"retired project namespace token: {path.relative_to(MVP)}")
        try:
            if path.suffix == ".json":
                json.loads(text); counts["json"] += 1
            elif path.suffix == ".jsonl":
                for line in text.splitlines():
                    if line.strip(): json.loads(line); counts["jsonlRecords"] += 1
            elif path.suffix == ".ttl":
                Graph().parse(path, format="turtle"); counts["turtle"] += 1
            elif path.suffix == ".rdf":
                Graph().parse(path, format="xml"); counts["rdfXml"] += 1
        except Exception as exc:
            errors.append(f"parse error {path.relative_to(MVP)}: {exc}")

    registry = read(LOCK / "registry/term_registry.json")
    names = [row["localName"] for row in registry]
    if len(names) != len(set(names)):
        errors.append("registry local names are not unique")
    bad = [row["localName"] for row in registry if row["iri"] != CANONICAL + row["localName"]]
    if bad:
        errors.append(f"registry IRI mismatch: {bad[:10]}")
    source_terms = {row["localName"] for row in read(MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R6/registry/term_registry.json")}
    actual_new = set(names) - source_terms
    if actual_new != EXPECTED_NEW:
        errors.append(f"unexpected R7 term delta: expected {sorted(EXPECTED_NEW)}, actual {sorted(actual_new)}")
    if any("startingair" in name.lower() and "capacity" in name.lower() for name in names):
        errors.append("prohibited starting-air-capacity term introduced")

    context = read(LOCK / "context/nltl_benchmark_context.jsonld")["@context"]
    nltl = context["nltl"]
    if (nltl.get("@id") if isinstance(nltl, dict) else nltl) != CANONICAL:
        errors.append("JSON-LD project prefix is not canonical")
    for local in EXPECTED_NEW:
        if local not in context:
            errors.append(f"new R7 term absent from JSON-LD context: {local}")

    ttl = Graph().parse(LOCK / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(LOCK / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf):
        errors.append("Turtle and RDF/XML ontologies are not isomorphic")
    if (NLTL.residualStabilityFactorSI, RDFS.domain, NLTL.loadingConditionCase) not in ttl:
        errors.append("residualStabilityFactorSI is not loadingConditionCase-owned")
    if (NLTL.hasStructuralMemberLoadCase, RDF.type, OWL.ObjectProperty) not in ttl:
        errors.append("existing hasStructuralMemberLoadCase relationship is missing")
    if (NLTL.inletChest, RDF.type, OWL.Class) not in ttl:
        errors.append("existing inletChest class is missing")

    binding = read(LOCK / "r7_prelock_binding.json")
    checked = 0
    for relative, expected in binding["boundMachineReadableArtifacts"].items():
        target = LOCK / relative
        checked += 1
        if not target.exists() or digest(target) != expected:
            errors.append(f"prelock hash mismatch: {relative}")

    provenance = read(LOCK / "provenance/r6_immutable_source_hashes.json")
    r6_changed = []
    for relative, expected in provenance["files"].items():
        target = MVP / relative
        if not target.exists() or digest(target) != expected:
            r6_changed.append(relative)
    if r6_changed:
        errors.append(f"R6 immutability failure: {r6_changed[:10]}")

    index = read(LOCK / "requirement_term_index.json")
    if len(index["dependencyContracts"]) != 313:
        errors.append("dependency contract count is not 313")
    complete = [c for c in index["dependencyContracts"].values() if c.get("status") == "COMPLETE"]
    if len(complete) != 238:
        errors.append("COMPLETE dependency contract count is not 238")
    r6_index = read(MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R6/requirement_term_index.json")
    if index["dependencyContracts"]["I2-009"] != r6_index["dependencyContracts"]["I2-009"]:
        errors.append("I2-009 contract changed")
    if index["requirements"]["I2-009"] != r6_index["requirements"]["I2-009"]:
        errors.append("I2-009 requirement index changed")
    if "starting-air" in json.dumps(index["dependencyContracts"]["TRF-127"]).lower():
        # The explanatory prohibition is allowed; an additive formula is not.
        formula = index["dependencyContracts"]["TRF-127"].get("formulaExpression", "")
        if formula:
            errors.append("TRF-127 still contains a starting-air formula")
    if "hasStructuralMemberLoadCase" not in index["dependencyContracts"]["I2-037"]["relationshipTerms"]:
        errors.append("I2-037 does not reuse hasStructuralMemberLoadCase")
    if "inletChest" not in index["requirements"]["TRF-130"]:
        errors.append("TRF-130 does not reuse inletChest")

    sys.path.insert(0, str(PIPELINE / "src"))
    from nltl_pipeline.config import PipelineConfig
    from nltl_pipeline.retrieval.context import VocabularyRepository
    vocabulary = VocabularyRepository(PipelineConfig.load(PIPELINE / "config/pipeline.r7-prelock-offline.json"))
    resolved = 0
    try:
        for requirement_id in sorted(vocabulary.requirements):
            vocabulary.build_context_pack(requirement_id)
            resolved += 1
    except Exception as exc:
        errors.append(f"context resolution failed after {resolved}: {exc}")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "lockCandidate": "VOCAB-LOCK-2026-08-20-R7",
        "canonicalVocabularyNamespace": CANONICAL,
        "registryTerms": len(registry), "newCanonicalTerms": sorted(actual_new),
        "localNamesUnique": len(names) == len(set(names)),
        "activeTextFilesChecked": len(active_files), "boundHashesChecked": checked,
        "contextsResolved": resolved, "completeContracts": len(complete),
        "r6ImmutableFilesChecked": len(provenance["files"]),
        "i2_009Unchanged": not any("I2-009" in item for item in errors),
        "trf_127NoStartingAirCapacityTerm": not any("starting-air" in item for item in errors),
        **counts, "errors": errors, "apiCalls": 0,
    }
    output = LOCK / "validation/r7_namespace_and_integrity_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
