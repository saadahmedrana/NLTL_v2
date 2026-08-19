from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from rdflib import Graph
from rdflib.compare import isomorphic


MVP = Path(__file__).resolve().parents[2]
LOCK = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R6"
CANONICAL = "https://w3id.org/nltl/vocab#"
TEXT_SUFFIXES = {".ttl", ".rdf", ".json", ".jsonl", ".jsonld", ".csv", ".md", ".txt", ".py", ".mjs"}
ACTIVE_ROOTS = [
    LOCK,
    MVP / "SHACL_GENERATION_PIPELINE/src",
    MVP / "SHACL_GENERATION_PIPELINE/tests",
    MVP / "SHACL_GENERATION_PIPELINE/prompts",
    MVP / "SHACL_GENERATION_PIPELINE/config/pipeline.r6-prelock-offline.json",
    MVP / "SHACL_GENERATION_PIPELINE/config/pipeline.development-r6-terra-failed10-rerun-01.json",
    MVP / "SHACL_GENERATION_PIPELINE/inputs/development_r6_terra_failed10_rerun_01.json",
    MVP / "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES",
]


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


def main() -> int:
    errors = []
    counts = {"json": 0, "jsonlRecords": 0, "turtle": 0, "rdfXml": 0}
    for path in files():
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

    registry = json.loads((LOCK / "registry/term_registry.json").read_text(encoding="utf-8"))
    names = [row["localName"] for row in registry]
    if len(names) != len(set(names)):
        errors.append("registry local names are not unique")
    bad = [row["localName"] for row in registry if row["iri"] != CANONICAL + row["localName"]]
    if bad:
        errors.append(f"registry IRI mismatch: {bad[:10]}")
    context = json.loads((LOCK / "context/nltl_benchmark_context.jsonld").read_text(encoding="utf-8"))["@context"]
    nltl = context["nltl"]
    if (nltl.get("@id") if isinstance(nltl, dict) else nltl) != CANONICAL:
        errors.append("JSON-LD project prefix is not canonical")
    for prompt in ("generator.txt", "validator.txt", "vocabulary_matcher.txt", "syntax_repair.txt"):
        if CANONICAL not in (MVP / "SHACL_GENERATION_PIPELINE/prompts" / prompt).read_text(encoding="utf-8"):
            errors.append(f"canonical namespace absent from {prompt}")
    ttl = Graph().parse(LOCK / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(LOCK / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf):
        errors.append("Turtle and RDF/XML ontologies are not isomorphic")
    binding = json.loads((LOCK / "r6_prelock_binding.json").read_text(encoding="utf-8"))
    checked = 0
    for relative, expected in binding["boundMachineReadableArtifacts"].items():
        target = LOCK / relative
        checked += 1
        if not target.exists() or digest(target) != expected:
            errors.append(f"prelock hash mismatch: {relative}")
    report = {
        "status": "PASS" if not errors else "FAIL",
        "lockCandidate": "VOCAB-LOCK-2026-08-19-R6",
        "canonicalVocabularyNamespace": CANONICAL,
        "registryTerms": len(registry),
        "localNamesUnique": len(names) == len(set(names)),
        "activeTextFilesChecked": sum(1 for _ in files()),
        "boundHashesChecked": checked,
        **counts,
        "errors": errors,
    }
    output = LOCK / "validation/r6_namespace_and_integrity_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
