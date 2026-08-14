from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from rdflib import Graph


MVP = Path(__file__).resolve().parents[2]
CANONICAL = "https://w3id.org/nltl/vocab#"
RETIRED_TOKEN = "nltl" + "-benchmark"
TEXT_SUFFIXES = {".ttl", ".rdf", ".json", ".jsonl", ".jsonld", ".ndjson", ".csv", ".md", ".txt", ".py", ".mjs", ".yaml", ".yml", ".toml", ".sh"}
ACTIVE_ROOTS = [
    MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R4",
    MVP / "BENCHMARK_VOCABULARY/STAGE2",
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
    seen = set()
    for root in ACTIVE_ROOTS:
        candidates = [root] if root.is_file() else root.rglob("*") if root.exists() else []
        for path in candidates:
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and "node_modules" not in path.parts and "ARCHIVE" not in path.parts:
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
            for file_key, hash_key in (("shape_file", "shape_sha256"), ("data_file", "data_sha256"), ("shapeFile", "shapeSha256"), ("dataFile", "dataSha256")):
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
    retired_occurrences = []
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
                json.loads(text); json_files += 1
                manifest_hashes += verify_manifest(path, errors)
            elif path.suffix == ".jsonl":
                for line_number, line in enumerate(text.splitlines(), 1):
                    if line.strip():
                        json.loads(line); jsonl_records += 1
            elif path.suffix == ".ttl":
                Graph().parse(path, format="turtle"); turtle_files += 1
            elif path.suffix == ".rdf":
                Graph().parse(path, format="xml"); rdfxml_files += 1
        except Exception as exc:
            errors.append(f"parse error: {path.relative_to(MVP)}: {exc}")
    if retired_occurrences:
        errors.extend(f"retired namespace token: {path}" for path in retired_occurrences)

    registry_path = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R4/registry/term_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    local_names = [row["localName"] for row in registry]
    if len(local_names) != 1625 or len(set(local_names)) != 1625:
        errors.append("registry local-name count or uniqueness changed")
    bad_registry = [row["localName"] for row in registry if row.get("iri") != CANONICAL + row["localName"]]
    if bad_registry:
        errors.append(f"registry canonical IRI mismatch: {bad_registry[:10]}")

    context = json.loads((MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R4/context/nltl_benchmark_context.jsonld").read_text(encoding="utf-8"))
    nltl_context = context.get("@context", {}).get("nltl")
    nltl_context_iri = nltl_context.get("@id") if isinstance(nltl_context, dict) else nltl_context
    if nltl_context_iri != CANONICAL:
        errors.append("JSON-LD nltl prefix is not canonical")
    for prompt in ("generator.txt", "validator.txt", "vocabulary_matcher.txt"):
        text = (MVP / "SHACL_GENERATION_PIPELINE/prompts" / prompt).read_text(encoding="utf-8")
        if CANONICAL not in text:
            errors.append(f"canonical namespace absent from prompt: {prompt}")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "canonicalVocabularyNamespace": CANONICAL,
        "activeTextFilesChecked": len(text_files),
        "retiredNamespaceOccurrences": len(retired_occurrences),
        "registryTerms": len(registry),
        "localNamesUnique": len(set(local_names)) == len(local_names),
        "jsonFilesParsed": json_files,
        "jsonlRecordsParsed": jsonl_records,
        "turtleFilesParsed": turtle_files,
        "rdfXmlFilesParsed": rdfxml_files,
        "manifestHashesChecked": manifest_hashes,
        "errors": errors,
    }
    output = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R4/validation/namespace_acceptance_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
