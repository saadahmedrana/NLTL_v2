#!/usr/bin/env python3
"""Validate the independent Pilot 01 R13 behavioral RDF fixtures."""

from __future__ import annotations

import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

try:
    from rdflib import Graph, Namespace, RDF, URIRef
except ImportError as exc:  # validation must never be silently skipped
    print(f"ERROR: RDFLib is required: {exc}", file=sys.stderr)
    raise SystemExit(2)


PILOT_ROOT = Path(__file__).resolve().parents[1]
MVP_ROOT = Path(__file__).resolve().parents[4]
LOCK_ROOT = MVP_ROOT / "BENCHMARK_VOCABULARY" / "FINAL_LOCK_R13"
ONTOLOGY_PATH = LOCK_ROOT / "ontology" / "nltl_benchmark_vocabulary.ttl"
REGISTRY_PATH = LOCK_ROOT / "registry" / "term_registry.json"
INDEX_PATH = LOCK_ROOT / "requirement_term_index.json"
MANIFEST_PATH = PILOT_ROOT / "manifests" / "pilot_01_manifest.jsonl"
REPORT_PATH = PILOT_ROOT / "reports" / "pilot_01_validation.json"

NLTL_BASE = "https://w3id.org/nltl/vocab#"
NLTL = Namespace(NLTL_BASE)
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")

EXPECTED_REQUIREMENTS = {"I2-004", "I2-005", "I2-042"}
EXPECTED_CASE_COUNT = 12
REQUIRED_MANIFEST_FIELDS = {
    "case_id", "requirement_id", "rdf_path", "expected", "case_type",
    "provenance", "source_document", "source_clause", "source_page", "rationale",
}
ALLOWED_TERMS = {
    "I2-004": {
        NLTL.ship, NLTL.hasUpperIceWaterlineCase, NLTL.upperIceWaterlineCase,
        NLTL.upperIceWaterlineDisplacement, NLTL.waterlineCaseDisplacement,
    },
    "I2-005": {
        NLTL.ship, NLTL.hullBoundaryPoint,
        NLTL.hasBottomRegionLowerRegionBoundaryPoint, NLTL.shellInclinationAngle,
    },
    "I2-042": {
        NLTL.ship, NLTL.structuralMember, NLTL.hasStructuralMember,
        NLTL.netWebThickness, NLTL.flangeWidth,
    },
}
REQUIRED_PATHS = {
    "I2-004": (NLTL.hasUpperIceWaterlineCase, NLTL.upperIceWaterlineCase),
    "I2-005": (NLTL.hasBottomRegionLowerRegionBoundaryPoint, NLTL.hullBoundaryPoint),
    "I2-042": (NLTL.hasStructuralMember, NLTL.structuralMember),
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_manifest(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def decimal_value(graph: Graph, subject: Any, predicate: URIRef) -> Decimal | None:
    value_nodes = list(graph.objects(subject, predicate))
    if len(value_nodes) != 1:
        return None
    numerics = list(graph.objects(value_nodes[0], QUDT.numericValue))
    if len(numerics) != 1:
        return None
    try:
        return Decimal(str(numerics[0]))
    except InvalidOperation:
        return None


def source_oracle(graph: Graph, requirement_id: str) -> tuple[bool, str]:
    ships = set(graph.subjects(RDF.type, NLTL.ship))

    if requirement_id == "I2-004":
        cases = {case for ship in ships for case in graph.objects(ship, NLTL.hasUpperIceWaterlineCase)}
        case_values = [decimal_value(graph, case, NLTL.waterlineCaseDisplacement) for case in cases]
        selected_values = [decimal_value(graph, ship, NLTL.upperIceWaterlineDisplacement) for ship in ships]
        selected_values = [value for value in selected_values if value is not None]
        passed = (
            bool(cases)
            and len(case_values) == len(cases)
            and all(value is not None for value in case_values)
            and len(selected_values) == 1
            and selected_values[0] == max(value for value in case_values if value is not None)
        )
        return passed, f"selected={selected_values or None}; represented={sorted(value for value in case_values if value is not None)}"

    if requirement_id == "I2-005":
        points = {point for ship in ships for point in graph.objects(ship, NLTL.hasBottomRegionLowerRegionBoundaryPoint)}
        angles = [decimal_value(graph, point, NLTL.shellInclinationAngle) for point in points]
        valid_angles = [angle for angle in angles if angle is not None]
        passed = bool(points) and len(valid_angles) == len(points) == 1 and valid_angles[0] == Decimal("7")
        return passed, f"boundary_points={len(points)}; angles={valid_angles or None}"

    if requirement_id == "I2-042":
        members = {member for ship in ships for member in graph.objects(ship, NLTL.hasStructuralMember)}
        pairs = [
            (decimal_value(graph, member, NLTL.netWebThickness), decimal_value(graph, member, NLTL.flangeWidth))
            for member in members
        ]
        passed = (
            len(pairs) == 1
            and pairs[0][0] is not None
            and pairs[0][1] is not None
            and pairs[0][1] >= Decimal("5") * pairs[0][0]
        )
        return passed, f"member_values={pairs or None}"

    raise ValueError(f"No source oracle for requirement {requirement_id}")


def used_nltl_terms(graph: Graph) -> set[URIRef]:
    terms: set[URIRef] = set()
    for subject, predicate, obj in graph:
        for node in (subject, predicate, obj):
            if isinstance(node, URIRef) and str(node).startswith(NLTL_BASE):
                terms.add(node)
    return terms


def validate() -> tuple[dict[str, Any], int]:
    global_errors: list[str] = []
    per_file: list[dict[str, Any]] = []

    try:
        manifest = load_manifest(MANIFEST_PATH)
    except Exception as exc:
        manifest = []
        global_errors.append(str(exc))

    try:
        registry = load_json(REGISTRY_PATH)
        registry_by_iri = {entry["iri"]: entry for entry in registry if entry.get("iri")}
    except Exception as exc:
        registry_by_iri = {}
        global_errors.append(f"Failed to load R13 term registry {REGISTRY_PATH}: {exc}")

    try:
        requirement_index = load_json(INDEX_PATH)
        indexed_requirements = requirement_index["requirements"]
    except Exception as exc:
        indexed_requirements = {}
        global_errors.append(f"Failed to load R13 requirement index {INDEX_PATH}: {exc}")

    ontology = Graph()
    try:
        ontology.parse(ONTOLOGY_PATH, format="turtle")
        ontology_subjects = {subject for subject in ontology.subjects() if isinstance(subject, URIRef)}
    except Exception as exc:
        ontology_subjects = set()
        global_errors.append(f"Failed to parse R13 ontology {ONTOLOGY_PATH}: {exc}")

    frozen_iris = ontology_subjects | {URIRef(iri) for iri in registry_by_iri}
    quantity_registry = {
        URIRef(iri): entry for iri, entry in registry_by_iri.items()
        if entry.get("kind") == "QuantityProperty"
    }

    if len(manifest) != EXPECTED_CASE_COUNT:
        global_errors.append(f"Manifest has {len(manifest)} rows; expected exactly {EXPECTED_CASE_COUNT}")

    case_ids = [row.get("case_id") for row in manifest]
    duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if duplicates:
        global_errors.append(f"Duplicate case IDs: {duplicates}")

    discovered_ttls = {
        path.relative_to(PILOT_ROOT).as_posix() for path in (PILOT_ROOT / "rdf").rglob("*.ttl")
    }
    manifest_ttls = {row.get("rdf_path") for row in manifest if row.get("rdf_path")}
    if discovered_ttls != manifest_ttls:
        global_errors.append(
            f"Manifest/RDF inventory mismatch: unlisted={sorted(discovered_ttls - manifest_ttls)}, "
            f"missing={sorted(manifest_ttls - discovered_ttls)}"
        )

    specs: dict[str, Any] = {}
    for requirement_id in sorted(EXPECTED_REQUIREMENTS):
        spec_path = PILOT_ROOT / "specifications" / "I2" / f"{requirement_id}.json"
        try:
            spec = load_json(spec_path)
            specs[requirement_id] = spec
            spec_terms = {URIRef(item["iri"]) for item in spec.get("r13_terms", [])}
            if spec_terms != ALLOWED_TERMS[requirement_id]:
                global_errors.append(f"{spec_path}: exact R13 term set does not match the pilot definition")
            if requirement_id not in indexed_requirements:
                global_errors.append(f"{spec_path}: requirement is absent from the frozen requirement index")
        except Exception as exc:
            global_errors.append(f"Failed to load specification {spec_path}: {exc}")

    for row in manifest:
        file_errors: list[str] = []
        checks = {
            "turtle_parse": False,
            "vocabulary": False,
            "qudt_and_unit": False,
            "required_basic_path": False,
            "source_oracle_agreement": False,
        }
        missing_fields = sorted(REQUIRED_MANIFEST_FIELDS - set(row))
        case_id = str(row.get("case_id", "<missing-case-id>"))
        requirement_id = str(row.get("requirement_id", ""))
        rdf_relative = row.get("rdf_path")
        rdf_path = PILOT_ROOT / rdf_relative if isinstance(rdf_relative, str) else PILOT_ROOT / "<missing>"

        if missing_fields:
            file_errors.append(f"manifest row missing fields: {missing_fields}")
        if requirement_id not in EXPECTED_REQUIREMENTS:
            file_errors.append(f"unexpected requirement_id: {requirement_id!r}")
        if row.get("expected") not in {"PASS", "FAIL"}:
            file_errors.append(f"invalid manifest expected verdict: {row.get('expected')!r}")
        if row.get("provenance") != "D_REGULATION_SYNTHETIC":
            file_errors.append(f"invalid provenance: {row.get('provenance')!r}")
        if not rdf_path.is_file():
            file_errors.append(f"manifest RDF path does not exist: {rdf_path}")

        spec = specs.get(requirement_id, {})
        spec_cases = {item.get("case_id"): item for item in spec.get("cases", [])}
        spec_case = spec_cases.get(case_id)
        if spec_case is None:
            file_errors.append("case is absent from its specification")
        elif spec_case.get("expected") != row.get("expected"):
            file_errors.append(
                f"manifest/spec expected mismatch: manifest={row.get('expected')}, spec={spec_case.get('expected')}"
            )

        graph = Graph()
        if rdf_path.is_file():
            try:
                graph.parse(rdf_path, format="turtle")
                checks["turtle_parse"] = True
            except Exception as exc:
                file_errors.append(f"Turtle parse failure: {exc}")

        oracle_result = None
        oracle_detail = None
        if checks["turtle_parse"] and requirement_id in EXPECTED_REQUIREMENTS:
            terms = used_nltl_terms(graph)
            unknown = sorted(str(term) for term in terms - frozen_iris)
            disallowed = sorted(str(term) for term in terms - ALLOWED_TERMS[requirement_id])
            if unknown:
                file_errors.append(f"NLTL terms absent from frozen R13: {unknown}")
            if disallowed:
                file_errors.append(f"NLTL terms outside exact allowed set: {disallowed}")
            checks["vocabulary"] = not unknown and not disallowed

            qudt_errors: list[str] = []
            quantity_nodes_checked = 0
            for predicate in sorted(terms & set(quantity_registry), key=str):
                registry_entry = quantity_registry[predicate]
                fixed_unit = registry_entry.get("unitIri")
                for _, value_node in graph.subject_objects(predicate):
                    quantity_nodes_checked += 1
                    if (value_node, RDF.type, QUDT.QuantityValue) not in graph:
                        qudt_errors.append(f"{predicate} value {value_node} is not typed qudt:QuantityValue")
                    numerics = list(graph.objects(value_node, QUDT.numericValue))
                    units = list(graph.objects(value_node, QUDT.unit))
                    if len(numerics) != 1:
                        qudt_errors.append(f"{predicate} value {value_node} has {len(numerics)} qudt:numericValue values; expected 1")
                    elif decimal_value(graph, next(graph.subjects(predicate, value_node)), predicate) is None:
                        qudt_errors.append(f"{predicate} value {value_node} does not contain a valid decimal numeric value")
                    if len(units) != 1:
                        qudt_errors.append(f"{predicate} value {value_node} has {len(units)} qudt:unit values; expected 1")
                    elif fixed_unit and str(units[0]) != fixed_unit:
                        qudt_errors.append(f"{predicate} uses unit {units[0]}; frozen R13 requires {fixed_unit}")
            file_errors.extend(qudt_errors)
            checks["qudt_and_unit"] = not qudt_errors

            path_predicate, target_class = REQUIRED_PATHS[requirement_id]
            ships = set(graph.subjects(RDF.type, NLTL.ship))
            targets = {target for ship in ships for target in graph.objects(ship, path_predicate)}
            typed_targets = {target for target in targets if (target, RDF.type, target_class) in graph}
            if ships and targets and typed_targets == targets:
                checks["required_basic_path"] = True
            else:
                file_errors.append(
                    f"required path missing or untyped: ship -> {path_predicate} -> {target_class}"
                )

            try:
                oracle_result, oracle_detail = source_oracle(graph, requirement_id)
                oracle_verdict = "PASS" if oracle_result else "FAIL"
                if oracle_verdict == row.get("expected"):
                    checks["source_oracle_agreement"] = True
                else:
                    file_errors.append(
                        f"source oracle disagreement: calculated={oracle_verdict}, manifest={row.get('expected')}; {oracle_detail}"
                    )
            except Exception as exc:
                file_errors.append(f"source oracle error: {exc}")

        per_file.append({
            "case_id": case_id,
            "requirement_id": requirement_id,
            "rdf_path": rdf_relative,
            "manifest_expected": row.get("expected"),
            "calculated_source_oracle": None if oracle_result is None else ("PASS" if oracle_result else "FAIL"),
            "oracle_detail": oracle_detail,
            "checks": checks,
            "status": "PASS" if not file_errors and all(checks.values()) else "FAIL",
            "errors": file_errors,
        })

    counts = {
        "rdf_files": len(discovered_ttls),
        "syntactically_valid": sum(item["checks"]["turtle_parse"] for item in per_file),
        "vocabulary_validation": sum(item["checks"]["vocabulary"] for item in per_file),
        "qudt_unit_validation": sum(item["checks"]["qudt_and_unit"] for item in per_file),
        "source_oracle_agreement": sum(item["checks"]["source_oracle_agreement"] for item in per_file),
    }
    overall_pass = not global_errors and len(per_file) == EXPECTED_CASE_COUNT and all(
        item["status"] == "PASS" for item in per_file
    )
    report = {
        "pilot": "Pilot 01",
        "r13_namespace": NLTL_BASE,
        "authoritative_sources": [
            str(INDEX_PATH.relative_to(MVP_ROOT)),
            str(REGISTRY_PATH.relative_to(MVP_ROOT)),
            str(ONTOLOGY_PATH.relative_to(MVP_ROOT)),
        ],
        "counts": counts,
        "global_errors": global_errors,
        "files": per_file,
        "overall_status": "PASS" if overall_pass else "FAIL",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    return report, 0 if overall_pass else 1


def main() -> int:
    try:
        report, exit_code = validate()
    except Exception as exc:
        print(f"FATAL validation error: {exc}", file=sys.stderr)
        return 1

    counts = report["counts"]
    print(f"RDF files: {counts['rdf_files']}")
    print(f"Syntactically valid: {counts['syntactically_valid']}")
    print(f"Vocabulary validation count: {counts['vocabulary_validation']}")
    print(f"QUDT/unit validation count: {counts['qudt_unit_validation']}")
    print(f"Source-oracle agreement count: {counts['source_oracle_agreement']}")
    print(f"Overall status: {report['overall_status']}")
    if exit_code:
        for error in report["global_errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        for item in report["files"]:
            for error in item["errors"]:
                print(f"ERROR: {item['rdf_path']}: {error}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
