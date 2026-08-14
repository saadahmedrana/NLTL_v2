from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from rdflib import Graph


MVP = Path(__file__).resolve().parents[3]
OLD_ROOT = "https://w3id.org/nltl-benchmark/"
NEW_ROOT = "https://w3id.org/nltl/"
OLD_VOCAB = OLD_ROOT + "vocab#"
NEW_VOCAB = NEW_ROOT + "vocab#"
ARCHIVE = MVP / "BENCHMARK_VOCABULARY/ARCHIVE/PRE_NAMESPACE_R4_WITHDRAWN_2026-08-14"
FINAL = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R4"
TEXT_SUFFIXES = {".ttl", ".rdf", ".json", ".jsonl", ".jsonld", ".ndjson", ".csv", ".md", ".txt", ".py", ".mjs", ".yaml", ".yml", ".toml", ".sh"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def active_roots() -> list[Path]:
    return [
        FINAL,
        MVP / "BENCHMARK_VOCABULARY/STAGE2",
        MVP / "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES",
        MVP / "INPUTS",
        MVP / "SHACL_GENERATION_PIPELINE/src",
        MVP / "SHACL_GENERATION_PIPELINE/tests",
        MVP / "SHACL_GENERATION_PIPELINE/prompts",
        MVP / "SHACL_GENERATION_PIPELINE/config",
        MVP / "SHACL_GENERATION_PIPELINE/README.md",
        MVP / "SHACL_GENERATION_PIPELINE/run_pipeline.py",
        MVP / "SHACL_GENERATION_PIPELINE/outputs/development_r14",
        MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-14-R4.lock.json",
    ]


def iter_text_files(root: Path):
    if root.is_file():
        if root.suffix.lower() in TEXT_SUFFIXES:
            yield root
        return
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and "node_modules" not in path.parts:
            yield path


def collect_manifest_shape_files() -> set[Path]:
    found: set[Path] = set()
    for manifest in (MVP / "INPUTS").rglob("*.json"):
        try:
            payload = read_json(manifest)
        except Exception:
            continue
        stack = [payload]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"shape_file", "shapeFile"} and isinstance(item, str):
                        path = (manifest.parent / item).resolve()
                        if path.exists() and path.is_file():
                            found.add(path)
                    else:
                        stack.append(item)
            elif isinstance(value, list):
                stack.extend(value)
    return found


def migrate_file(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return 0
    escaped_old = "https://w3id\\.org/nltl-benchmark/"
    escaped_new = "https://w3id\\.org/nltl/"
    count = text.count(OLD_ROOT) + text.count(escaped_old)
    if count:
        path.write_text(text.replace(OLD_ROOT, NEW_ROOT).replace(escaped_old, escaped_new), encoding="utf-8")
    return count


def refresh_manifest_hashes(path: Path) -> int:
    try:
        payload = read_json(path)
    except Exception:
        return 0
    changed = 0

    def walk(value):
        nonlocal changed
        if isinstance(value, dict):
            pairs = (("shape_file", "shape_sha256"), ("data_file", "data_sha256"), ("shapeFile", "shapeSha256"), ("dataFile", "dataSha256"))
            for path_key, hash_key in pairs:
                relative = value.get(path_key)
                if isinstance(relative, str):
                    target = (path.parent / relative).resolve()
                    if target.exists() and target.is_file():
                        digest = sha256(target)
                        if value.get(hash_key) != digest:
                            value[hash_key] = digest
                            changed += 1
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(payload)
    if changed:
        write_json(path, payload)
    return changed


def main() -> None:
    snapshot = ARCHIVE / "FINAL_LOCK_R4_PRE_NAMESPACE_SNAPSHOT"
    if not snapshot.exists():
        shutil.copytree(FINAL, snapshot)
        for name in (
            "benchmark_vocabulary_stage2_LOCK-2026-08-14-R4.xlsx",
            "benchmark_vocabulary_stage2_LOCK-2026-08-14-R4.lock.json",
            "benchmark_vocabulary_stage2_LOCK-2026-08-14-R4.sha256",
        ):
            source = MVP / name
            if source.exists():
                shutil.copy2(source, ARCHIVE / ("PRE_NAMESPACE_" + name))

    before_registry = read_json(FINAL / "registry/term_registry.json")
    before_names = [row["localName"] for row in before_registry]
    referenced_shapes = collect_manifest_shape_files()
    files = {path for root in active_roots() for path in iter_text_files(root)} | referenced_shapes
    replacements = 0
    changed_files = []
    for path in sorted(files):
        count = migrate_file(path)
        if count:
            replacements += count
            changed_files.append(str(path.relative_to(MVP)))

    hash_updates = 0
    for manifest in (MVP / "INPUTS").rglob("*.json"):
        hash_updates += refresh_manifest_hashes(manifest)

    # Re-serialize the final ontology variants after the controlled URI replacement.
    graph = Graph().parse(FINAL / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.serialize(FINAL / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.serialize(FINAL / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")

    after_registry = read_json(FINAL / "registry/term_registry.json")
    after_names = [row["localName"] for row in after_registry]
    if before_names != after_names:
        raise RuntimeError("Canonical local names changed during namespace migration")
    bad_iris = [row["iri"] for row in after_registry if not row["iri"].startswith(NEW_VOCAB)]
    if bad_iris:
        raise RuntimeError(f"Registry contains non-migrated canonical IRIs: {bad_iris[:5]}")

    prelock = read_json(FINAL / "prelock_manifest.json")
    prelock["status"] = "NAMESPACE_MIGRATED_PENDING_WORKBOOK_AND_RDF_RECONFIRMATION"
    prelock["namespaceMigration"] = {
        "oldProjectRoot": OLD_ROOT,
        "newProjectRoot": NEW_ROOT,
        "oldVocabularyNamespace": OLD_VOCAB,
        "newVocabularyNamespace": NEW_VOCAB,
        "localNamesChanged": 0,
        "textualReplacements": replacements,
        "changedTextFiles": len(changed_files),
        "manifestHashUpdates": hash_updates,
    }
    artifact_paths = [
        "registry/term_registry.json", "registry/term_registry.csv", "registry/r14_change_decisions.json",
        "ontology/nltl_benchmark_vocabulary.ttl", "ontology/nltl_benchmark_vocabulary.rdf",
        "context/nltl_benchmark_context.jsonld", "evidence/stage1_approved.json", "requirement_term_index.json",
        "validation/validation_report.json", "confirmation/r14_confirmation_results.json",
    ]
    prelock["boundArtifacts"] = {relative: sha256(FINAL / relative) for relative in artifact_paths}
    prelock["confirmation"] = "Pre-namespace 2/2 generation and 7/7 RDF evidence retained; namespace-migrated RDF reconfirmation required before sealing active R4."
    write_json(FINAL / "prelock_manifest.json", prelock)

    lock = read_json(FINAL / "benchmark_vocabulary_stage2_LOCK-2026-08-14-R4.lock.json")
    lock["status"] = "WITHDRAWN_PRE_NAMESPACE_BUILD_REPLACEMENT_IN_PROGRESS"
    lock["namespaceMigrationTarget"] = NEW_VOCAB
    write_json(FINAL / "benchmark_vocabulary_stage2_LOCK-2026-08-14-R4.lock.json", lock)
    root_lock = MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-14-R4.lock.json"
    if root_lock.exists():
        write_json(root_lock, lock)

    report = {
        "status": "PASS_PENDING_RDF_RECONFIRMATION_AND_FINAL_LOCK",
        "oldProjectRoot": OLD_ROOT,
        "newProjectRoot": NEW_ROOT,
        "oldVocabularyNamespace": OLD_VOCAB,
        "newVocabularyNamespace": NEW_VOCAB,
        "registryTerms": len(after_registry),
        "localNamesUnchanged": before_names == after_names,
        "textualReplacements": replacements,
        "changedTextFiles": len(changed_files),
        "manifestHashUpdates": hash_updates,
        "changedFiles": changed_files,
        "archiveSnapshot": str(snapshot.relative_to(MVP)),
    }
    write_json(FINAL / "validation/namespace_migration_report.json", report)
    print(json.dumps({key: value for key, value in report.items() if key != "changedFiles"}, indent=2))


if __name__ == "__main__":
    main()
