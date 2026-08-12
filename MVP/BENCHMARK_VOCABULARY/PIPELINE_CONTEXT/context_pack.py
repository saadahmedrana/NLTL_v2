#!/usr/bin/env python3
"""Build deterministic, requirement-scoped vocabulary context packs for LLM runs.

This module does not generate SHACL. It supplies the future pipeline with the
locked canonical terms, URIs, datatypes, units, aliases, and node patterns that
are relevant to a selected requirement or integrated case.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
BENCHMARK_ROOT = HERE.parent
PROJECT_ROOT = BENCHMARK_ROOT.parent
STAGE2 = BENCHMARK_ROOT / "STAGE2"
MASTER_DIR = HERE / "master"
EXAMPLES_DIR = HERE / "examples"
LOCK_PATH = PROJECT_ROOT / "benchmark_vocabulary_stage2_LOCK-2026-08-12-R1.lock.json"

REGISTRY_PATH = STAGE2 / "registry" / "term_registry.json"
EVIDENCE_PATH = STAGE2 / "evidence" / "stage1_approved.json"
MANIFEST_PATH = STAGE2 / "stage2_manifest.json"
RETIRED_PATH = STAGE2 / "registry" / "retired_stage1_candidates.json"
PROFILE_DIR = STAGE2 / "profiles"

PROFILE_NAMES = (
    "master",
    "traficom",
    "iacs_ur_i2",
    "imo_polar_code",
    "imo_amend_2026",
    "direct_deterministic",
    "evidence_and_deferred",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_sources() -> dict[str, Any]:
    return {
        "lock": read_json(LOCK_PATH),
        "manifest": read_json(MANIFEST_PATH),
        "terms": read_json(REGISTRY_PATH),
        "evidence": read_json(EVIDENCE_PATH),
        "retired": read_json(RETIRED_PATH),
        "profiles": {name: read_json(PROFILE_DIR / f"{name}.json") for name in PROFILE_NAMES},
    }


def verify_locked_sources(sources: dict[str, Any]) -> None:
    lock = sources["lock"]
    bound = lock["boundMachineReadableArtifacts"]
    expected = {
        REGISTRY_PATH: bound["registry/term_registry.json"],
        STAGE2 / "context" / "nltl_benchmark_context.jsonld": bound["context/nltl_benchmark_context.jsonld"],
        MANIFEST_PATH: bound["stage2_manifest.json"],
        PROJECT_ROOT / lock["workbook"]: lock["workbookSha256"],
    }
    expected.update(
        (PROFILE_DIR / filename, checksum)
        for filename, checksum in lock["profileSha256"].items()
    )
    mismatches = [
        {"path": str(path), "expected": checksum, "actual": sha256(path)}
        for path, checksum in expected.items()
        if not path.exists() or sha256(path) != checksum
    ]
    if mismatches:
        raise RuntimeError(f"Locked Stage 2 source mismatch: {json.dumps(mismatches)}")


def jsonld_base_context() -> dict[str, Any]:
    return {
        "@version": 1.1,
        "@protected": True,
        "nltl": {"@id": "https://w3id.org/nltl-benchmark/vocab#", "@prefix": True},
        "owl": {"@id": "http://www.w3.org/2002/07/owl#", "@prefix": True},
        "rdf": {"@id": "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "@prefix": True},
        "rdfs": {"@id": "http://www.w3.org/2000/01/rdf-schema#", "@prefix": True},
        "skos": {"@id": "http://www.w3.org/2004/02/skos/core#", "@prefix": True},
        "xsd": {"@id": "http://www.w3.org/2001/XMLSchema#", "@prefix": True},
        "qudt": {"@id": "http://qudt.org/schema/qudt/", "@prefix": True},
        "unitVocab": {"@id": "http://qudt.org/vocab/unit/", "@prefix": True},
        "sosa": {"@id": "http://www.w3.org/ns/sosa/", "@prefix": True},
        "dct": {"@id": "http://purl.org/dc/terms/", "@prefix": True},
    }


def master_context() -> dict[str, Any]:
    context = jsonld_base_context()
    context.update(
        {
            "version": "owl:versionInfo",
            "termCount": {"@id": "nltl:termCount", "@type": "xsd:integer"},
            "sourceLockId": "nltl:sourceLockId",
            "sourceLockSha256": "nltl:sourceLockSha256",
            "containsRegulatoryAnswerLogic": {"@id": "nltl:containsRegulatoryAnswerLogic", "@type": "xsd:boolean"},
            "term": {"@id": "nltl:term", "@type": "@id", "@container": "@set"},
            "localName": "nltl:localName",
            "termKind": "nltl:termKind",
            "moduleName": "nltl:moduleName",
            "prefLabel": {"@id": "skos:prefLabel", "@language": "en"},
            "definition": {"@id": "skos:definition", "@language": "en"},
            "alias": {"@id": "skos:altLabel", "@container": "@set"},
            "sourceConceptId": {"@id": "nltl:draftConceptId", "@container": "@set"},
            "stage1LocalName": {"@id": "nltl:stage1LocalName", "@container": "@set"},
            "sourceRequirementId": {"@id": "nltl:sourceRequirementId", "@container": "@set"},
            "sourceReference": "nltl:sourceReference",
            "evidenceExcerpt": "nltl:evidenceExcerpt",
            "range": {"@id": "rdfs:range", "@type": "@id"},
            "subClassOf": {"@id": "rdfs:subClassOf", "@type": "@id"},
            "datatypeName": "nltl:datatypeName",
            "unitSymbol": "nltl:unitSymbol",
            "recommendedUnit": {"@id": "nltl:recommendedUnit", "@type": "@id"},
            "quantityKindLabel": "nltl:quantityKindLabel",
            "unitDecisionStatus": "nltl:unitDecisionStatus",
            "roleDecision": "nltl:roleDecisionBasis",
            "namingBasis": "nltl:namingBasis",
            "namingRule": "nltl:namingRule",
            "nameQaStatus": "nltl:nameQaStatus",
            "confidence": "nltl:confidence",
            "mappingStatus": "nltl:mappingStatus",
            "exactMatch": {"@id": "skos:exactMatch", "@type": "@id"},
        }
    )
    return context


def term_jsonld(term: dict[str, Any]) -> dict[str, Any]:
    rdf_type = {
        "Class": "owl:Class",
        "DatatypeProperty": "owl:DatatypeProperty",
        "ObjectProperty": "owl:ObjectProperty",
        "QuantityProperty": "owl:ObjectProperty",
    }[term["kind"]]
    payload: dict[str, Any] = {
        "@id": term["iri"],
        "@type": rdf_type,
        "localName": term["localName"],
        "termKind": term["kind"],
        "moduleName": term["module"],
        "prefLabel": term["label"],
        "definition": term["normalizedDefinition"],
        "alias": term["aliases"],
        "sourceConceptId": term["sourceConceptIds"],
        "stage1LocalName": term["stage1LocalNames"],
        "sourceRequirementId": term["requirements"],
        "sourceReference": term["sourceRefs"],
        "evidenceExcerpt": term["evidenceExcerpt"],
        "roleDecision": term["roleDecision"],
        "namingBasis": term["namingBasis"],
        "namingRule": term["namingRule"],
        "nameQaStatus": term["nameQaStatus"],
        "confidence": term["confidence"],
        "mappingStatus": term["mappingStatus"],
        "unitDecisionStatus": term["unitDecisionStatus"],
    }
    if term["kind"] == "Class":
        payload["subClassOf"] = term["parentOrRange"]
    else:
        payload["range"] = term["parentOrRange"]
    if term["datatype"]:
        payload["datatypeName"] = term["datatype"]
    if term["unitSymbol"]:
        payload["unitSymbol"] = term["unitSymbol"]
    if term["unitIri"]:
        payload["recommendedUnit"] = term["unitIri"]
    if term["quantityKindLabel"]:
        payload["quantityKindLabel"] = term["quantityKindLabel"]
    if term["haithamUri"]:
        payload["exactMatch"] = term["haithamUri"]
    return payload


def build_master_vocabulary(sources: dict[str, Any]) -> dict[str, Any]:
    terms = sorted(sources["terms"], key=lambda item: item["localName"])
    lock = sources["lock"]
    manifest = sources["manifest"]
    return {
        "@context": master_context(),
        "@id": f"https://w3id.org/nltl-benchmark/vocabulary-registry/{manifest['version']}",
        "@type": "nltl:VocabularyRegistry",
        "version": manifest["version"],
        "termCount": len(terms),
        "sourceLockId": lock["lockId"],
        "sourceLockSha256": lock["workbookSha256"],
        "containsRegulatoryAnswerLogic": False,
        "term": [term_jsonld(term) for term in terms],
    }


def requirement_term_index(sources: dict[str, Any]) -> dict[str, list[str]]:
    result: defaultdict[str, set[str]] = defaultdict(set)
    for term in sources["terms"]:
        for requirement_id in term["requirements"]:
            result[requirement_id].add(term["localName"])
    for retired in sources["retired"].values():
        for requirement_id, redirect in retired["requirementRedirects"].items():
            result[requirement_id].add(redirect)
    requirement_ids = {item["id"] for item in sources["evidence"]["requirements"]}
    missing = sorted(requirement_ids - set(result))
    if missing:
        raise RuntimeError(f"Requirements without vocabulary terms: {missing}")
    return {key: sorted(result[key]) for key in sorted(requirement_ids)}


def scoped_jsonld_context(terms: Iterable[dict[str, Any]]) -> dict[str, Any]:
    context: dict[str, Any] = jsonld_base_context()
    context.update(
        {
            "id": "@id",
            "type": "@type",
            "numericValue": {"@id": "qudt:numericValue", "@type": "xsd:decimal"},
            "unit": {"@id": "qudt:unit", "@type": "@id"},
            "hasObservation": {"@id": "nltl:hasObservation", "@type": "@id"},
            "hasEvidence": {"@id": "nltl:hasEvidence", "@type": "@id"},
        }
    )
    for term in sorted(terms, key=lambda item: item["localName"]):
        if term["kind"] == "Class":
            context[term["localName"]] = f"nltl:{term['localName']}"
        elif term["kind"] in {"ObjectProperty", "QuantityProperty"}:
            context[term["localName"]] = {"@id": f"nltl:{term['localName']}", "@type": "@id"}
        else:
            context[term["localName"]] = {"@id": f"nltl:{term['localName']}", "@type": term["datatype"]}
    return {"@context": context}


def compact_term(term: dict[str, Any], include_evidence: bool) -> dict[str, Any]:
    payload = {
        "localName": term["localName"],
        "iri": term["iri"],
        "label": term["label"],
        "kind": term["kind"],
        "module": term["module"],
        "range": term["parentOrRange"],
        "datatype": term["datatype"] or None,
        "recommendedUnit": term["unitIri"] or None,
        "unitSymbol": term["unitSymbol"] or None,
        "quantityKind": term["quantityKindLabel"] or None,
        "aliases": term["aliases"],
        "definition": term["normalizedDefinition"],
        "sourceConceptIds": term["sourceConceptIds"],
        "sourceReferences": term["sourceRefs"],
        "namingBasis": term["namingBasis"],
        "namingRule": term["namingRule"],
        "roleDecision": term["roleDecision"],
        "unitDecision": term["unitDecisionStatus"],
        "mapping": {
            "status": term["mappingStatus"],
            "verifiedExactUri": term["haithamUri"] or None,
        },
    }
    if include_evidence:
        payload["evidenceExcerpt"] = term["evidenceExcerpt"]
    return payload


def selected_node_patterns(terms: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    kinds = {term["kind"] for term in terms}
    patterns: list[dict[str, Any]] = []
    if "Class" in kinds:
        patterns.append({
            "id": "rdfType",
            "appliesToKind": "Class",
            "graphPattern": "node rdf:type canonicalClassIri",
        })
    if "DatatypeProperty" in kinds:
        patterns.append({
            "id": "typedLiteral",
            "appliesToKind": "DatatypeProperty",
            "graphPattern": "subject canonicalProperty typedLiteral",
            "datatypeComesFrom": "term.datatype",
        })
    if "ObjectProperty" in kinds:
        patterns.append({
            "id": "objectIri",
            "appliesToKind": "ObjectProperty",
            "graphPattern": "subject canonicalProperty objectIri",
            "rangeComesFrom": "term.range",
        })
    if "QuantityProperty" in kinds:
        patterns.append({
            "id": "qudtQuantityValue",
            "appliesToKind": "QuantityProperty",
            "graphPattern": "subject canonicalProperty quantityNode; quantityNode qudt:numericValue xsd:decimal; qudt:unit unitIri",
            "recommendedUnitComesFrom": "term.recommendedUnit",
            "viscosityException": "For the three viscosity terms, the case must declare dynamic or kinematic kind and use the same unit across minimum, observation, and maximum.",
        })
    return patterns


def requirement_payload(requirement: dict[str, Any], include_text: bool) -> dict[str, Any]:
    payload = {
        "id": requirement["id"],
        "source": requirement["source"],
        "sourceSheet": requirement["sourceSheet"],
        "edition": requirement["edition"],
        "page": requirement["page"],
        "clause": requirement["clause"],
        "verificationCategory": requirement["category"],
        "activationStatus": requirement["activeStatus"],
        "codability": requirement["codability"],
        "encodingPatternHint": requirement["encodingPattern"],
        "figureDependent": requirement["figureDependent"],
    }
    if include_text:
        payload["verifiedSourceText"] = requirement["sourceText"]
        payload["normalizedRequirement"] = requirement["normalizedRequirement"]
    return payload


def build_context_pack(
    sources: dict[str, Any],
    requirement_ids: Iterable[str],
    *,
    include_evidence: bool = False,
    vocabulary_only: bool = False,
) -> dict[str, Any]:
    requested = sorted(set(requirement_ids))
    if not requested:
        raise ValueError("At least one requirement ID is required")
    requirements_by_id = {item["id"]: item for item in sources["evidence"]["requirements"]}
    unknown = sorted(set(requested) - set(requirements_by_id))
    if unknown:
        raise KeyError(f"Unknown requirement ID(s): {', '.join(unknown)}")
    index = requirement_term_index(sources)
    local_names = sorted({name for requirement_id in requested for name in index[requirement_id]})
    terms_by_local = {term["localName"]: term for term in sources["terms"]}
    missing_terms = sorted(set(local_names) - set(terms_by_local))
    if missing_terms:
        raise RuntimeError(f"Indexed canonical terms missing from registry: {missing_terms}")
    selected_terms = [terms_by_local[name] for name in local_names]
    applicable_profiles = [
        name for name, profile in sources["profiles"].items()
        if set(requested) <= set(profile["requirementIds"])
    ]
    key = json.dumps(
        {"requirements": requested, "evidence": include_evidence, "vocabularyOnly": vocabulary_only},
        sort_keys=True,
        separators=(",", ":"),
    )
    pack_id = "context-pack-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    payload = {
        "packVersion": "1.0.0",
        "packId": pack_id,
        "sourceLock": {
            "lockId": sources["lock"]["lockId"],
            "workbookSha256": sources["lock"]["workbookSha256"],
            "vocabularyVersion": sources["manifest"]["version"],
            "registrySha256": sha256(REGISTRY_PATH),
        },
        "selection": {
            "mode": "integrated-case" if len(requested) > 1 else "requirement",
            "requirementIds": requested,
            "applicableProfiles": applicable_profiles,
            "termCount": len(selected_terms),
            "all821TermsIncluded": len(selected_terms) == len(sources["terms"]),
        },
        "usagePolicy": {
            "useOnlyAllowedCanonicalTerms": True,
            "useExactCanonicalIris": True,
            "doNotCoinSynonyms": True,
            "doNotChangeDatatypesOrUnits": True,
            "doNotInferExternalMappings": True,
            "reportVocabularyGapInsteadOfInventingATerm": True,
            "containsRegulatoryAnswerLogic": False,
            "pipelineResponsibility": "Derive requirement-specific SHACL from the verified requirement text while using only this pack's canonical vocabulary contract.",
        },
        "requirements": [requirement_payload(requirements_by_id[item], not vocabulary_only) for item in requested],
        "terms": [compact_term(term, include_evidence) for term in selected_terms],
        "nodePatterns": selected_node_patterns(selected_terms),
        "scopedJsonLdContext": scoped_jsonld_context(selected_terms),
    }
    payload["sizeEstimate"] = {
        "characters": len(json.dumps(payload, ensure_ascii=True, separators=(",", ":"))),
        "roughTokensAtFourCharactersPerToken": len(json.dumps(payload, ensure_ascii=True, separators=(",", ":"))) // 4,
    }
    validate_context_pack(payload, sources)
    return payload


def validate_context_pack(payload: dict[str, Any], sources: dict[str, Any]) -> None:
    required = {
        "packVersion", "packId", "sourceLock", "selection", "usagePolicy", "requirements",
        "terms", "nodePatterns", "scopedJsonLdContext", "sizeEstimate",
    }
    if set(payload) != required:
        raise RuntimeError(f"Context-pack fields differ from the 1.0.0 contract: {sorted(set(payload) ^ required)}")
    if payload["packVersion"] != "1.0.0" or not payload["packId"].startswith("context-pack-"):
        raise RuntimeError("Invalid context-pack version or ID")
    selected_ids = payload["selection"]["requirementIds"]
    index = requirement_term_index(sources)
    expected_names = {name for requirement_id in selected_ids for name in index[requirement_id]}
    actual_names = [term["localName"] for term in payload["terms"]]
    if len(actual_names) != len(set(actual_names)) or set(actual_names) != expected_names:
        raise RuntimeError("Context-pack term allow-list is not the exact requirement-index union")
    registry_by_local = {term["localName"]: term for term in sources["terms"]}
    for term in payload["terms"]:
        source = registry_by_local[term["localName"]]
        if term["iri"] != source["iri"] or term["kind"] != source["kind"]:
            raise RuntimeError(f"Context-pack canonical identity mismatch for {term['localName']}")
        if term["datatype"] != (source["datatype"] or None):
            raise RuntimeError(f"Context-pack datatype mismatch for {term['localName']}")
        if term["recommendedUnit"] != (source["unitIri"] or None):
            raise RuntimeError(f"Context-pack unit mismatch for {term['localName']}")
    context = payload["scopedJsonLdContext"].get("@context", {})
    if not set(actual_names) <= set(context):
        raise RuntimeError("Scoped JSON-LD context does not cover every allowed term")
    if payload["selection"]["termCount"] != len(actual_names):
        raise RuntimeError("Context-pack termCount is inconsistent")
    if payload["usagePolicy"]["containsRegulatoryAnswerLogic"] is not False:
        raise RuntimeError("Context pack must not declare embedded answer logic")


def build_assets(sources: dict[str, Any]) -> None:
    master_path = MASTER_DIR / "vocabulary_master.jsonld"
    index_path = MASTER_DIR / "requirement_term_index.json"
    write_json(master_path, build_master_vocabulary(sources))
    index = requirement_term_index(sources)
    write_json(
        index_path,
        {
            "version": "1.0.0",
            "sourceLockId": sources["lock"]["lockId"],
            "requirementCount": len(index),
            "termCount": len(sources["terms"]),
            "requirements": index,
        },
    )
    write_json(
        HERE / "context_assets_manifest.json",
        {
            "version": "1.0.0",
            "generatedDate": sources["manifest"]["generatedDate"],
            "sourceLockId": sources["lock"]["lockId"],
            "sourceWorkbookSha256": sources["lock"]["workbookSha256"],
            "sourceRegistrySha256": sha256(REGISTRY_PATH),
            "masterJsonLd": {
                "path": "master/vocabulary_master.jsonld",
                "sha256": sha256(master_path),
                "terms": len(sources["terms"]),
                "containsRegulatoryAnswerLogic": False,
            },
            "requirementTermIndex": {
                "path": "master/requirement_term_index.json",
                "sha256": sha256(index_path),
                "requirements": len(index),
            },
            "contextPackSchema": {
                "path": "schemas/context_pack.schema.json",
                "sha256": sha256(HERE / "schemas" / "context_pack.schema.json"),
            },
            "recommendedPromptPolicy": "Use one requirement-scoped pack, or the exact union for an integrated case; do not inject all 821 master terms by default.",
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build", help="Build the full JSON-LD master vocabulary and requirement index")
    pack = subparsers.add_parser("pack", help="Build a compact context pack for one requirement or an integrated case")
    pack.add_argument("--requirement", action="append", required=True, help="Requirement ID; repeat for an integrated case")
    pack.add_argument("--include-evidence", action="store_true", help="Include term-level evidence excerpts (larger prompt)")
    pack.add_argument("--vocabulary-only", action="store_true", help="Omit requirement text for non-SHACL vocabulary tasks")
    pack.add_argument("--output", type=Path, required=True, help="Output JSON file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sources = load_sources()
    verify_locked_sources(sources)
    if args.command == "build":
        build_assets(sources)
        print(json.dumps({"status": "PASS", "master": str(MASTER_DIR / "vocabulary_master.jsonld"), "requirements": 313, "terms": 821}, indent=2))
        return
    payload = build_context_pack(
        sources,
        args.requirement,
        include_evidence=args.include_evidence,
        vocabulary_only=args.vocabulary_only,
    )
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    write_json(output, payload)
    print(json.dumps({"status": "PASS", "output": str(output), "requirements": payload["selection"]["requirementIds"], "terms": payload["selection"]["termCount"], "characters": payload["sizeEstimate"]["characters"]}, indent=2))


if __name__ == "__main__":
    main()
