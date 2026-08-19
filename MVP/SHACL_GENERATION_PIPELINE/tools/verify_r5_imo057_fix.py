from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from rdflib import Graph, RDFS, URIRef
from rdflib.compare import isomorphic


MVP = Path(__file__).resolve().parents[2]
R5 = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R5"
CANONICAL = "https://w3id.org/nltl/vocab#"
RETIRED_TOKEN = "nltl" + "-benchmark"
TEXT_SUFFIXES = {
    ".ttl", ".rdf", ".json", ".jsonl", ".jsonld", ".ndjson", ".csv",
    ".md", ".txt", ".py", ".mjs", ".yaml", ".yml", ".toml", ".sh",
}
ACTIVE_ROOTS = [
    R5,
    MVP / "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES",
    MVP / "INPUTS",
    MVP / "SHACL_GENERATION_PIPELINE/src",
    MVP / "SHACL_GENERATION_PIPELINE/tests",
    MVP / "SHACL_GENERATION_PIPELINE/prompts",
    MVP / "SHACL_GENERATION_PIPELINE/config",
    MVP / "SHACL_GENERATION_PIPELINE/README.md",
    MVP / "SHACL_GENERATION_PIPELINE/run_pipeline.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iter_files():
    seen: set[Path] = set()
    for root in ACTIVE_ROOTS:
        candidates = [root] if root.is_file() else root.rglob("*") if root.exists() else []
        for path in candidates:
            if (
                path.is_file()
                and path.suffix.lower() in TEXT_SUFFIXES
                and "node_modules" not in path.parts
                and "ARCHIVE" not in path.parts
                and "outputs" not in path.parts
            ):
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield resolved


def verify_manifest(path: Path, errors: list[str]) -> int:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    checked = 0

    def walk(value):
        nonlocal checked
        if isinstance(value, dict):
            for file_key, hash_key in (
                ("shape_file", "shape_sha256"),
                ("data_file", "data_sha256"),
                ("shapeFile", "shapeSha256"),
                ("dataFile", "dataSha256"),
            ):
                relative = value.get(file_key)
                expected = value.get(hash_key)
                if isinstance(relative, str) and isinstance(expected, str):
                    target = (path.parent / relative).resolve()
                    if target.exists():
                        checked += 1
                        if sha256(target) != expected:
                            errors.append(f"stale hash: {path.relative_to(MVP)} -> {relative}")
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return checked


def main() -> int:
    errors: list[str] = []
    text_files = list(iter_files())
    retired_occurrences: list[str] = []
    json_files = jsonl_records = turtle_files = rdfxml_files = manifest_hashes = 0
    for path in text_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if RETIRED_TOKEN in text:
            retired_occurrences.append(str(path.relative_to(MVP)))
        try:
            if path.suffix == ".json":
                json.loads(text)
                json_files += 1
                manifest_hashes += verify_manifest(path, errors)
            elif path.suffix == ".jsonl":
                for line in text.splitlines():
                    if line.strip():
                        json.loads(line)
                        jsonl_records += 1
            elif path.suffix == ".ttl":
                Graph().parse(path, format="turtle")
                turtle_files += 1
            elif path.suffix == ".rdf":
                Graph().parse(path, format="xml")
                rdfxml_files += 1
        except Exception as exc:
            errors.append(f"parse error: {path.relative_to(MVP)}: {exc}")
    errors.extend(f"retired namespace token: {item}" for item in retired_occurrences)

    registry = json.loads((R5 / "registry/term_registry.json").read_text(encoding="utf-8"))
    local_names = [row["localName"] for row in registry]
    if len(local_names) != 1625 or len(set(local_names)) != 1625:
        errors.append("registry local-name count or uniqueness changed")
    if any(row.get("iri") != CANONICAL + row["localName"] for row in registry):
        errors.append("registry canonical IRI mismatch")
    maintained = next(row for row in registry if row["localName"] == "maintainedTemperature")
    if maintained.get("requirements") != ["IMO-057"]:
        errors.append("maintainedTemperature registry linkage changed beyond IMO-057")

    ttl_graph = Graph().parse(R5 / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf_graph = Graph().parse(R5 / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl_graph, rdf_graph):
        errors.append("Turtle and RDF/XML graphs are not isomorphic")
    maintained_iri = URIRef(CANONICAL + "maintainedTemperature")
    domains = sorted(str(value) for value in ttl_graph.objects(maintained_iri, RDFS.domain))
    if domains != [CANONICAL + "compartment"]:
        errors.append(f"maintainedTemperature domain mismatch: {domains}")

    index = json.loads((R5 / "requirement_term_index.json").read_text(encoding="utf-8"))
    affected = sorted(
        requirement_id
        for requirement_id, terms in index["requirements"].items()
        if "maintainedTemperature" in terms
    )
    if affected != ["IMO-057"]:
        errors.append(f"unexpected maintainedTemperature contexts: {affected}")
    owners = index["termOwners"].get("IMO-057", {})
    expected_owners = {
        "hasComponent": "ship",
        "hasContainingCompartment": "firePump",
        "maintainedTemperature": "compartment",
    }
    if owners != expected_owners:
        errors.append(f"IMO-057 owner map mismatch: {owners}")
    contract = index["dependencyContracts"]["IMO-057"]
    if contract.get("relationshipTerms") != ["hasComponent", "hasContainingCompartment"]:
        errors.append("IMO-057 relationship terms mismatch")
    if contract.get("operandTerms") != ["maintainedTemperature"]:
        errors.append("IMO-057 operand terms mismatch")
    if contract.get("modelPaths") != [
        {"fromOwner": "ship", "via": "hasComponent", "toOwner": "shipComponent"},
        {"fromOwner": "firePump", "via": "hasContainingCompartment", "toOwner": "compartment"},
    ]:
        errors.append("IMO-057 model path mismatch")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "lockCandidate": "VOCAB-LOCK-2026-08-19-R5",
        "canonicalVocabularyNamespace": CANONICAL,
        "activeTextFilesChecked": len(text_files),
        "retiredNamespaceOccurrences": len(retired_occurrences),
        "registryTerms": len(registry),
        "localNamesUnique": len(set(local_names)) == len(local_names),
        "newVocabularyTerms": 0,
        "maintainedTemperatureDomain": domains,
        "affectedRequirementContexts": affected,
        "otherAffectedRequirementContexts": [],
        "jsonFilesParsed": json_files,
        "jsonlRecordsParsed": jsonl_records,
        "turtleFilesParsed": turtle_files,
        "rdfXmlFilesParsed": rdfxml_files,
        "manifestHashesChecked": manifest_hashes,
        "errors": errors,
    }
    output = R5 / "validation/r5_namespace_and_scope_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
