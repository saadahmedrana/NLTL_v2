#!/usr/bin/env python3
"""Deterministically enrich the MethodV2 NLTL manual-audit workbook.

This program never invokes a generation pipeline or reruns an RDF behavioural
case.  It imports recorded evidence, computes narrowly scoped static evidence,
and patches only the MethodV2 automatic columns in a new XLSX file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import posixpath
import shutil
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from xml.etree import ElementTree as ET

from rdflib import BNode, Graph, Literal, RDF, RDFS, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, SH


ARCHITECTURES = ("V2_FALLBACK25", "NO_SEMANTIC", "SINGLESHOT")
SHEET_BY_ARCHITECTURE = {
    "V2_FALLBACK25": "V2",
    "NO_SEMANTIC": "NoSemantic",
    "SINGLESHOT": "SingleShot",
}
EXPECTED_AVAILABILITY = {
    "V2_FALLBACK25": 262,
    "NO_SEMANTIC": 263,
    "SINGLESHOT": 254,
}
INPUT_WORKBOOK_NAME = "NLTL_Manual_Audit_ready_v2.xlsx"
OUTPUT_WORKBOOK_NAME = "NLTL_Manual_Audit_ready_v2_enriched.xlsx"
SELECTION_NAME = "audit_selection.json"
EVIDENCE_NAME = "automatic_evidence.jsonl"
SUMMARY_NAME = "automatic_summary.json"
DISCREPANCIES_NAME = "automatic_evidence_discrepancies.csv"

AUTOMATIC_HEADERS = (
    "SHACL specification validity",
    "SHACL vocabulary validity",
    "Selected-case target activation",
    "Node-shape count",
    "Property-shape count",
    "SHACL Core component count",
    "SHACL Core components used",
    "SHACL-SPARQL constraint count",
    "Maximum property-path depth",
    "Maximum logical nesting depth",
)
IDENTITY_HEADERS = (
    "Requirement ID",
    "Selected generation run",
    "Selected SHACL path",
    "Selected SHACL SHA-256",
    "Recorded Turtle parse status",
    "Recorded deterministic status",
    "Selected case 1",
    "Original expected 1",
    "Recorded actual 1",
    "Recorded outcome 1",
    "Selected case 2",
    "Original expected 2",
    "Recorded actual 2",
    "Recorded outcome 2",
)
REQUIRED_HEADERS = IDENTITY_HEADERS + AUTOMATIC_HEADERS

# SHACL Core constraint parameters.  Metadata, targets, severity, messages,
# prefix declarations, and SHACL-SPARQL's sh:sparql predicate are excluded.
CORE_CONSTRAINT_PARAMETERS = frozenset(
    SH[name]
    for name in (
        "and", "class", "closed", "datatype", "disjoint", "equals",
        "flags", "hasValue", "ignoredProperties", "in", "languageIn",
        "lessThan", "lessThanOrEquals", "maxCount", "maxExclusive",
        "maxInclusive", "maxLength", "minCount", "minExclusive",
        "minInclusive", "minLength", "node", "nodeKind", "not", "or",
        "pattern", "property", "qualifiedMaxCount", "qualifiedMinCount",
        "qualifiedValueShape", "qualifiedValueShapesDisjoint", "uniqueLang",
        "xone",
    )
)
LOGICAL_PREDICATES = frozenset({SH["and"], SH["or"], SH["xone"], SH["not"]})
PATH_OPERATORS = frozenset(
    {SH.alternativePath, SH.inversePath, SH.zeroOrMorePath, SH.oneOrMorePath, SH.zeroOrOnePath}
)

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"x": NS_MAIN, "r": NS_DOC_REL, "pr": NS_PKG_REL}
ET.register_namespace("", NS_MAIN)
ET.register_namespace("r", NS_DOC_REL)


class EnrichmentError(RuntimeError):
    """A fail-closed input, identity, or preservation error."""


@dataclass(frozen=True)
class Discrepancy:
    severity: str
    category: str
    architecture: str = ""
    requirement_id: str = ""
    case_id: str = ""
    workbook_sheet: str = ""
    workbook_cell: str = ""
    field: str = ""
    workbook_value: str = ""
    source_value: str = ""
    source_path: str = ""
    message: str = ""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_lines(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _local_name(term: URIRef) -> str:
    value = str(term)
    return value[len(str(SH)) :] if value.startswith(str(SH)) else value


def _display_core_term(term: URIRef) -> str:
    return f"sh:{_local_name(term)}"


def actual_verdict(row: Mapping[str, Any]) -> str:
    value = row.get("actual_conforms")
    if row.get("execution_status") != "EXECUTED" or value is None:
        return "NO_VERDICT"
    return "PASS" if value is True else "FAIL"


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "MVP/SHACL_GENERATION_PIPELINE").is_dir():
            return candidate
    raise EnrichmentError(f"Could not locate repository root above {start}")


def column_number(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    value = 0
    for letter in letters:
        value = value * 26 + ord(letter) - 64
    return value


def column_letters(number: int) -> str:
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _normalise_xlsx_target(source: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


class WorkbookXML:
    """Minimal XLSX reader/patcher that leaves unrelated ZIP parts untouched."""

    def __init__(self, path: Path):
        self.path = path
        with zipfile.ZipFile(path) as archive:
            self.members = {name: archive.read(name) for name in archive.namelist()}
        workbook_part = "xl/workbook.xml"
        workbook = ET.fromstring(self.members[workbook_part])
        relationships = ET.fromstring(self.members["xl/_rels/workbook.xml.rels"])
        targets = {
            rel.attrib["Id"]: _normalise_xlsx_target(workbook_part, rel.attrib["Target"])
            for rel in relationships.findall(f"{{{NS_PKG_REL}}}Relationship")
        }
        self.sheet_parts: dict[str, str] = {}
        for sheet in workbook.findall("x:sheets/x:sheet", NS):
            self.sheet_parts[sheet.attrib["name"]] = targets[sheet.attrib[f"{{{NS_DOC_REL}}}id"]]
        self.shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in self.members:
            root = ET.fromstring(self.members["xl/sharedStrings.xml"])
            for item in root.findall("x:si", NS):
                self.shared_strings.append("".join(node.text or "" for node in item.findall(".//x:t", NS)))
        self.sheet_roots = {
            name: ET.fromstring(self.members[part]) for name, part in self.sheet_parts.items()
        }

    def sheet_names(self) -> list[str]:
        return list(self.sheet_parts)

    def _cell_value(self, cell: ET.Element | None) -> Any:
        if cell is None:
            return None
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            return "".join(node.text or "" for node in cell.findall(".//x:t", NS))
        value = cell.find("x:v", NS)
        if value is None:
            return None
        raw = value.text or ""
        if cell_type == "s":
            return self.shared_strings[int(raw)]
        if cell_type in {"str", "e"}:
            return raw
        if cell_type == "b":
            return raw == "1"
        try:
            number = float(raw)
            return int(number) if number.is_integer() else number
        except ValueError:
            return raw

    def _rows(self, sheet_name: str) -> list[ET.Element]:
        try:
            root = self.sheet_roots[sheet_name]
        except KeyError as exc:
            raise EnrichmentError(f"Required worksheet is missing: {sheet_name}") from exc
        sheet_data = root.find("x:sheetData", NS)
        return [] if sheet_data is None else list(sheet_data.findall("x:row", NS))

    @staticmethod
    def _cells_by_column(row: ET.Element) -> dict[int, ET.Element]:
        return {column_number(cell.attrib["r"]): cell for cell in row.findall("x:c", NS)}

    def discover_headers(self, sheet_name: str, required: Sequence[str]) -> tuple[int, dict[str, int]]:
        required_set = set(required)
        for row in self._rows(sheet_name):
            pairs = [
                (self._cell_value(cell), column)
                for column, cell in self._cells_by_column(row).items()
                if isinstance(self._cell_value(cell), str)
            ]
            values = dict(pairs)
            if required_set.issubset(values):
                duplicates = [header for header in required if sum(value == header for value, _ in pairs) > 1]
                if duplicates:
                    raise EnrichmentError(f"Duplicate required headers in {sheet_name}: {duplicates}")
                return int(row.attrib["r"]), {header: values[header] for header in required}
        missing = ", ".join(required)
        raise EnrichmentError(f"Required MethodV2 headers were not found in {sheet_name}: {missing}")

    def row_records(self, sheet_name: str, header_row: int, headers: Mapping[str, int]) -> list[tuple[int, dict[str, Any]]]:
        records = []
        for row in self._rows(sheet_name):
            row_number = int(row.attrib["r"])
            if row_number <= header_row:
                continue
            cells = self._cells_by_column(row)
            record = {header: self._cell_value(cells.get(column)) for header, column in headers.items()}
            if record.get("Requirement ID") not in (None, ""):
                records.append((row_number, record))
        return records

    def get_cell(self, sheet_name: str, row_number: int, column: int) -> ET.Element | None:
        for row in self._rows(sheet_name):
            if int(row.attrib["r"]) == row_number:
                return self._cells_by_column(row).get(column)
        return None

    def set_if_blank(
        self,
        sheet_name: str,
        row_number: int,
        column: int,
        value: Any,
    ) -> tuple[bool, Any]:
        rows = self._rows(sheet_name)
        row = next((item for item in rows if int(item.attrib["r"]) == row_number), None)
        if row is None:
            raise EnrichmentError(f"Missing row {row_number} in {sheet_name}")
        cell = self._cells_by_column(row).get(column)
        current = self._cell_value(cell)
        if cell is not None and cell.find("x:f", NS) is not None:
            return False, current
        if current not in (None, ""):
            return False, current
        if cell is None:
            reference = f"{column_letters(column)}{row_number}"
            cell = ET.Element(f"{{{NS_MAIN}}}c", {"r": reference})
            inserted = False
            for index, existing in enumerate(row.findall("x:c", NS)):
                if column_number(existing.attrib["r"]) > column:
                    row.insert(index, cell)
                    inserted = True
                    break
            if not inserted:
                row.append(cell)
        for child in list(cell):
            if child.tag in {f"{{{NS_MAIN}}}v", f"{{{NS_MAIN}}}is"}:
                cell.remove(child)
        if isinstance(value, bool):
            cell.attrib["t"] = "b"
            ET.SubElement(cell, f"{{{NS_MAIN}}}v").text = "1" if value else "0"
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            cell.attrib.pop("t", None)
            ET.SubElement(cell, f"{{{NS_MAIN}}}v").text = str(value)
        else:
            cell.attrib["t"] = "inlineStr"
            inline = ET.SubElement(cell, f"{{{NS_MAIN}}}is")
            text = ET.SubElement(inline, f"{{{NS_MAIN}}}t")
            text.text = "" if value is None else str(value)
        return True, current

    def save(self, path: Path, changed_sheets: Iterable[str]) -> None:
        replacements = {
            self.sheet_parts[name]: ET.tostring(
                self.sheet_roots[name], encoding="UTF-8", xml_declaration=True, short_empty_elements=True
            )
            for name in changed_sheets
        }
        with zipfile.ZipFile(path, "w") as output:
            for name, payload in self.members.items():
                output.writestr(name, replacements.get(name, payload))


def load_supported_shacl_vocabulary() -> set[URIRef]:
    import pyshacl

    assets = Path(pyshacl.__file__).resolve().parent / "assets"
    allowed: set[URIRef] = set()
    for name in ("shacl.ttl", "shacl-shacl.ttl"):
        graph = Graph().parse(assets / name, format="turtle")
        for triple in graph:
            for term in triple:
                if isinstance(term, URIRef) and str(term).startswith(str(SH)):
                    allowed.add(term)
    return allowed


def check_shacl_vocabulary(graph: Graph, allowed: set[URIRef]) -> tuple[str, list[str]]:
    used = {
        term
        for triple in graph
        for term in triple
        if isinstance(term, URIRef) and str(term).startswith(str(SH))
    }
    unknown = sorted(str(term) for term in used - allowed)
    return ("INVALID" if unknown else "VALID"), unknown


def structural_profile(graph: Graph) -> dict[str, Any]:
    node_shapes = set(graph.subjects(RDF.type, SH.NodeShape))
    property_shapes = set(graph.subjects(RDF.type, SH.PropertyShape))
    property_shapes.update(graph.objects(None, SH.property))
    property_shapes.update(graph.subjects(SH.path, None))
    occurrences = [(subject, predicate, obj) for subject, predicate, obj in graph if predicate in CORE_CONSTRAINT_PARAMETERS]
    components = sorted({_display_core_term(predicate) for _, predicate, _ in occurrences})
    sparql_constraints = list(graph.triples((None, SH.sparql, None)))
    path_depths = []
    for path_node in graph.objects(None, SH.path):
        path_depths.append(shacl_path_depth(graph, path_node))
    logical_depths = [logical_nesting_depth(graph, subject) for subject in set(graph.subjects())]
    return {
        "node_shape_count": len(node_shapes),
        "property_shape_count": len(property_shapes),
        "shacl_core_component_occurrence_count": len(occurrences),
        "shacl_core_components_used": components,
        "sparql_constraint_count": len(sparql_constraints),
        "maximum_property_path_depth": max(path_depths, default=0),
        "maximum_logical_constraint_nesting_depth": max(logical_depths, default=0),
    }


def _rdf_list(graph: Graph, head: Any) -> list[Any] | None:
    if head == RDF.nil:
        return []
    if (head, RDF.first, None) not in graph:
        return None
    try:
        return list(Collection(graph, head))
    except Exception:
        return None


def shacl_path_depth(graph: Graph, node: Any, visiting: frozenset[Any] = frozenset()) -> int:
    if isinstance(node, URIRef):
        return 1
    if node in visiting:
        return 0
    visiting = visiting | {node}
    sequence = _rdf_list(graph, node)
    if sequence is not None:
        return 1 + max((shacl_path_depth(graph, item, visiting) for item in sequence), default=0)
    for predicate in PATH_OPERATORS:
        values = list(graph.objects(node, predicate))
        if values:
            depths = []
            for value in values:
                alternatives = _rdf_list(graph, value) if predicate == SH.alternativePath else None
                if alternatives is not None:
                    depths.extend(shacl_path_depth(graph, item, visiting) for item in alternatives)
                else:
                    depths.append(shacl_path_depth(graph, value, visiting))
            return 1 + max(depths, default=0)
    return 0


def logical_nesting_depth(graph: Graph, node: Any, visiting: frozenset[Any] = frozenset()) -> int:
    if node in visiting:
        return 0
    visiting = visiting | {node}
    best = 0
    for predicate in LOGICAL_PREDICATES:
        for value in graph.objects(node, predicate):
            children = [value]
            if predicate in {SH["and"], SH["or"], SH["xone"]}:
                parsed = _rdf_list(graph, value)
                if parsed is None:
                    continue
                children = parsed
            best = max(best, 1 + max((logical_nesting_depth(graph, child, visiting) for child in children), default=0))
    return best


def target_activation(shape_graph: Graph, data_graph: Graph) -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    if any(True for _ in shape_graph.triples((None, OWL.imports, None))) or any(
        True for _ in data_graph.triples((None, OWL.imports, None))
    ):
        return "NOT_EVALUATED", [], ["owl:imports makes target activation ambiguous without import processing"]
    if any(True for _ in shape_graph.triples((None, SH.target, None))):
        return "NOT_EVALUATED", [], ["custom or SPARQL sh:target declaration is not evaluated"]

    declared = False
    focus_nodes: set[Any] = set()
    graph_nodes = {term for subject, predicate, obj in data_graph for term in (subject, predicate, obj)}
    for target in shape_graph.objects(None, SH.targetNode):
        declared = True
        if target in graph_nodes:
            focus_nodes.add(target)
    for target_class in shape_graph.objects(None, SH.targetClass):
        declared = True
        classes = {target_class}
        changed = True
        while changed:
            changed = False
            for subclass, _, superclass in data_graph.triples((None, RDFS.subClassOf, None)):
                if superclass in classes and subclass not in classes:
                    classes.add(subclass)
                    changed = True
        for class_iri in classes:
            focus_nodes.update(data_graph.subjects(RDF.type, class_iri))
    for predicate in shape_graph.objects(None, SH.targetSubjectsOf):
        declared = True
        focus_nodes.update(data_graph.subjects(predicate, None))
    for predicate in shape_graph.objects(None, SH.targetObjectsOf):
        declared = True
        focus_nodes.update(data_graph.objects(None, predicate))
    if focus_nodes:
        return "ACTIVATED", sorted(str(node) for node in focus_nodes), warnings
    if not declared:
        warnings.append("no supported standard target declaration was found")
    return "NOT_ACTIVATED", [], warnings


def derive_meta_shacl_from_rows(rows: Sequence[Mapping[str, Any]], artifact_sha256: str) -> tuple[str, str] | None:
    for row in rows:
        if (
            row.get("generated_shape_sha256") == artifact_sha256
            and row.get("shape_parse_status") == "PARSED"
            and row.get("execution_status") == "EXECUTED"
            and row.get("pyshacl_options", {}).get("meta_shacl") is True
        ):
            return "VALID", "DERIVED_FROM_SUCCESSFUL_META_SHACL_EXECUTION"
    return None


def standalone_meta_shacl(graph: Graph) -> tuple[str, str]:
    try:
        from pyshacl.entrypoints import meta_validate

        conforms, _, report_text = meta_validate(graph, inference="rdfs", advanced=True)
        return ("VALID" if conforms else "INVALID"), str(report_text)
    except Exception as exc:
        return "ERROR", f"{type(exc).__name__}: {exc}"


def _resolve_repo_path(repo_root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = (repo_root / value).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise EnrichmentError(f"Selected path escapes repository root: {value}") from exc
    return path


def _relative_to_run_root(metadata_path: Path, artifact_path: Path) -> str:
    run_root = metadata_path.parent.parent
    return artifact_path.relative_to(run_root).as_posix()


def recorded_meta_shacl(
    repo_root: Path,
    record: Mapping[str, Any],
    artifact_sha256: str,
) -> tuple[str, dict[str, Any]] | None:
    evidence_path = _resolve_repo_path(repo_root, record.get("deterministic_validation_path"))
    metadata_path = _resolve_repo_path(repo_root, record.get("artifact_metadata_path"))
    if not evidence_path or not metadata_path or not evidence_path.is_file() or not metadata_path.is_file():
        return None
    expected_evidence_sha = record.get("deterministic_validation_sha256")
    if not expected_evidence_sha or sha256_file(evidence_path) != expected_evidence_sha:
        return None
    rows = list(csv.DictReader(metadata_path.open(encoding="utf-8", newline="")))
    evidence_rel = _relative_to_run_root(metadata_path, evidence_path)
    attempt = str(record.get("candidate_attempt") or "")
    evidence_rows = [
        row for row in rows
        if row.get("ARTIFACT_PATH") == evidence_rel
        and row.get("SHA256") == expected_evidence_sha
        and (not attempt or row.get("ITERATION") == attempt)
    ]
    candidate_rows = [
        row for row in rows
        if row.get("SHA256") == artifact_sha256 and (not attempt or row.get("ITERATION") == attempt)
    ]
    if not evidence_rows or not candidate_rows:
        return None
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    validation = payload.get("deterministicValidation", payload)
    value = validation.get("meta_shacl_valid")
    if not isinstance(value, bool):
        return None
    detail = {
        "method": "RECORDED_PIPELINE_META_SHACL",
        "source_path": str(evidence_path.relative_to(repo_root)),
        "source_sha256": expected_evidence_sha,
        "artifact_metadata_path": str(metadata_path.relative_to(repo_root)),
        "candidate_attempt": record.get("candidate_attempt"),
        "recorded_value": value,
    }
    return ("VALID" if value else "INVALID"), detail


class LedgerCache:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def load(self, relative_path: str, expected_sha256: str) -> list[dict[str, Any]]:
        key = (relative_path, expected_sha256)
        if key in self._cache:
            return self._cache[key]
        path = _resolve_repo_path(self.repo_root, relative_path)
        if path is None or not path.is_file():
            raise EnrichmentError(f"Recorded source ledger is missing: {relative_path}")
        actual_sha = sha256_file(path)
        if actual_sha != expected_sha256:
            raise EnrichmentError(f"Source ledger hash mismatch: {relative_path}: {actual_sha} != {expected_sha256}")
        rows = json_lines(path)
        self._cache[key] = rows
        return rows


def _architecture_configuration_matches(architecture: str, configuration: str) -> bool:
    if architecture == "NO_SEMANTIC":
        return configuration == "NO_SEMANTIC"
    if architecture == "SINGLESHOT":
        return configuration == "SINGLESHOT"
    return configuration in {"FULL_REPAIR_V2", "FULL_REPAIR_V2_REJECTED_ATTEMPT4_DIAGNOSTIC"}


def reconcile_ledger_rows(
    record: Mapping[str, Any],
    ledger_rows: Sequence[Mapping[str, Any]],
    artifact_available: bool,
) -> tuple[list[dict[str, Any]], list[Discrepancy]]:
    discrepancies: list[Discrepancy] = []
    matched: list[dict[str, Any]] = []
    artifact_sha = record.get("shape_sha256")
    for case_id in record.get("selected_case_ids", []):
        candidates = [
            row for row in ledger_rows
            if row.get("requirement_id") == record["requirement_id"]
            and row.get("case_id") == case_id
            and _architecture_configuration_matches(record["architecture"], row.get("configuration", ""))
            and row.get("generation_run", "RUN_01") == "RUN_01"
        ]
        if artifact_available:
            candidates = [row for row in candidates if row.get("generated_shape_sha256") == artifact_sha]
        if len(candidates) != 1:
            discrepancies.append(Discrepancy(
                "ERROR", "LEDGER_RECONCILIATION", record["architecture"], record["requirement_id"], case_id,
                field="selected behavioural row", source_path=record.get("source_ledger_path", ""),
                message=f"Expected one exact ledger row; found {len(candidates)}",
            ))
            continue
        matched.append(dict(candidates[0]))
    return matched, discrepancies


def _compare_workbook(
    discrepancies: list[Discrepancy],
    architecture: str,
    requirement_id: str,
    sheet: str,
    row_number: int,
    header_columns: Mapping[str, int],
    workbook_record: Mapping[str, Any],
    field: str,
    source_value: Any,
    source_path: str,
    case_id: str = "",
) -> None:
    workbook_value = workbook_record.get(field)
    if workbook_value != source_value:
        discrepancies.append(Discrepancy(
            "WARNING", "WORKBOOK_SOURCE_DISAGREEMENT", architecture, requirement_id, case_id,
            sheet, f"{column_letters(header_columns[field])}{row_number}", field,
            "" if workbook_value is None else str(workbook_value), "" if source_value is None else str(source_value),
            source_path, "Existing workbook value was preserved",
        ))


def _rdf_path(repo_root: Path, row: Mapping[str, Any]) -> Path:
    path = repo_root / "MVP/SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13" / row["rdf_path"]
    path = path.resolve()
    if not path.is_file():
        raise EnrichmentError(f"Selected RDF case is missing: {path}")
    if sha256_file(path) != row.get("rdf_sha256"):
        raise EnrichmentError(f"Selected RDF hash mismatch: {path}")
    return path


def _spec_cell_value(result: str) -> str:
    return {
        "VALID": "PASS",
        "INVALID": "FAIL",
        "NOT_TESTED": "NOT_EVALUATED",
        "MISSING_ARTIFACT": "UNAVAILABLE",
        "ERROR": "ERROR",
    }[result]


def _activation_cell_value(activation: Mapping[str, Mapping[str, Any]]) -> str:
    ordered = []
    for label in ("PASS", "FAIL"):
        item = activation.get(label)
        if item:
            ordered.append(f"{item['case_id']}={item['result']}")
    return " | ".join(ordered) if ordered else "NOT_EVALUATED"


def _automatic_cell_values(evidence: Mapping[str, Any]) -> dict[str, Any]:
    profile = evidence.get("structural_profile") or {}
    return {
        "SHACL specification validity": _spec_cell_value(evidence["shacl_specification_validity"]),
        "SHACL vocabulary validity": evidence["shacl_vocabulary_validity"],
        "Selected-case target activation": _activation_cell_value(evidence["selected_case_target_activation"]),
        "Node-shape count": profile.get("node_shape_count", ""),
        "Property-shape count": profile.get("property_shape_count", ""),
        "SHACL Core component count": profile.get("shacl_core_component_occurrence_count", ""),
        "SHACL Core components used": ", ".join(profile.get("shacl_core_components_used", [])),
        "SHACL-SPARQL constraint count": profile.get("sparql_constraint_count", ""),
        "Maximum property-path depth": profile.get("maximum_property_path_depth", ""),
        "Maximum logical nesting depth": profile.get("maximum_logical_constraint_nesting_depth", ""),
    }


def build_evidence_record(
    repo_root: Path,
    record: Mapping[str, Any],
    ledger_cache: LedgerCache,
    supported_vocabulary: set[URIRef],
    recheck_unresolved: bool,
) -> tuple[dict[str, Any], list[Discrepancy]]:
    if record.get("generation_run") != "RUN_01" or record.get("selected_generation_run", "RUN_01") != "RUN_01":
        raise EnrichmentError(f"Only RUN_01 is permitted: {record['architecture']} {record['requirement_id']}")
    selected_path = _resolve_repo_path(repo_root, record.get("shape_path"))
    expected_sha = record.get("shape_sha256")
    exists = bool(selected_path and selected_path.is_file())
    actual_sha = sha256_file(selected_path) if exists and selected_path else None
    hash_matches = bool(exists and expected_sha and actual_sha == expected_sha)
    availability = "AVAILABLE" if hash_matches else "MISSING_ARTIFACT" if not exists else "HASH_MISMATCH"
    warnings: list[str] = []
    discrepancies: list[Discrepancy] = []
    if exists and not hash_matches:
        discrepancies.append(Discrepancy(
            "ERROR", "ARTIFACT_HASH_MISMATCH", record["architecture"], record["requirement_id"],
            field="Selected SHACL SHA-256", source_value=str(expected_sha or ""), source_path=record.get("shape_path", ""),
            message=f"Observed SHA-256 {actual_sha}; no replacement selected",
        ))
    if not exists:
        warnings.append("selected artifact is absent; no replacement was selected")

    ledger_rows = ledger_cache.load(record["source_ledger_path"], record["source_ledger_sha256"])
    selected_rows, ledger_discrepancies = reconcile_ledger_rows(record, ledger_rows, hash_matches)
    discrepancies.extend(ledger_discrepancies)
    behavioural = []
    for row in selected_rows:
        behavioural.append({key: row.get(key) for key in (
            "configuration", "requirement_id", "case_id", "generated_shape_sha256", "rdf_path", "rdf_sha256",
            "expected_outcome", "actual_conforms", "execution_status", "behavioral_match", "outcome_class",
            "shape_parse_status", "generation_pipeline_status", "pyshacl_options", "pyshacl_version", "rdflib_version",
        )})

    base = {
        "architecture": record["architecture"],
        "requirement_id": record["requirement_id"],
        "generation_run": "RUN_01",
        "artifact_path": record.get("shape_path"),
        "artifact_sha256": expected_sha,
        "artifact_observed_sha256": actual_sha,
        "artifact_selection_category": record.get("output_origin"),
        "availability": availability,
        "existing_parsing_evidence": {
            "status": record.get("parse_status"),
            "source": SELECTION_NAME,
            "ledger_statuses": sorted({row.get("shape_parse_status") for row in selected_rows if row.get("shape_parse_status")}),
        },
        "existing_pipeline_validation_evidence": {
            "status": record.get("deterministic_status"),
            "generation_status": record.get("original_generation_status"),
            "source_path": record.get("deterministic_validation_path"),
            "source_sha256": record.get("deterministic_validation_sha256"),
            "findings": record.get("deterministic_findings"),
        },
        "existing_behavioural_ledger_evidence": {
            "source_path": record.get("source_ledger_path"),
            "source_sha256": record.get("source_ledger_sha256"),
            "selected_case_rows": behavioural,
        },
        "warnings_or_unresolved_limitations": warnings,
    }
    if not hash_matches:
        base.update({
            "shacl_specification_validity": "MISSING_ARTIFACT" if not exists else "ERROR",
            "specification_validity_provenance": "MISSING_ARTIFACT" if not exists else "ERROR",
            "specification_validity_provenance_detail": "Selected artifact is absent" if not exists else "Selected artifact hash mismatch",
            "shacl_vocabulary_validity": "MISSING_ARTIFACT" if not exists else "ERROR",
            "unknown_shacl_terms": [],
            "selected_case_target_activation": {
                label: {"case_id": case_id, "result": "MISSING_ARTIFACT" if not exists else "ERROR", "focus_nodes": [], "warnings": []}
                for label, case_id in zip(("PASS", "FAIL"), record.get("selected_case_ids", []))
            },
            "structural_profile": None,
        })
        return base, discrepancies

    shape_graph = Graph()
    try:
        shape_graph.parse(selected_path, format="turtle")
    except Exception as exc:
        base["warnings_or_unresolved_limitations"].append(f"Turtle parsing error during static enrichment: {type(exc).__name__}: {exc}")
        base.update({
            "shacl_specification_validity": "ERROR",
            "specification_validity_provenance": "ERROR",
            "specification_validity_provenance_detail": f"Turtle parsing error: {type(exc).__name__}: {exc}",
            "shacl_vocabulary_validity": "ERROR",
            "unknown_shacl_terms": [],
            "selected_case_target_activation": {
                label: {"case_id": case_id, "result": "ERROR", "focus_nodes": [], "warnings": ["selected SHACL did not parse"]}
                for label, case_id in zip(("PASS", "FAIL"), record.get("selected_case_ids", []))
            },
            "structural_profile": None,
        })
        return base, discrepancies

    recorded = recorded_meta_shacl(repo_root, record, expected_sha)
    if recorded:
        spec_result, detail = recorded
        provenance = "RECORDED"
    else:
        derived = derive_meta_shacl_from_rows(selected_rows, expected_sha)
        if derived:
            spec_result, detail = derived[0], {
                "method": derived[1], "source_path": record.get("source_ledger_path"),
                "qualifying_case_ids": [
                    row["case_id"] for row in selected_rows
                    if row.get("generated_shape_sha256") == expected_sha
                    and row.get("shape_parse_status") == "PARSED"
                    and row.get("execution_status") == "EXECUTED"
                    and row.get("pyshacl_options", {}).get("meta_shacl") is True
                ],
            }
            provenance = "DERIVED"
        elif recheck_unresolved:
            spec_result, report = standalone_meta_shacl(shape_graph)
            provenance = "RECHECKED" if spec_result in {"VALID", "INVALID"} else "ERROR"
            detail = {"method": "STANDALONE_LOCAL_META_SHACL", "report": report}
        else:
            spec_result, provenance = "NOT_TESTED", "NOT_TESTED"
            detail = {"method": "UNRESOLVED_EXISTING_EVIDENCE; standalone recheck disabled"}

    vocabulary_result, unknown_terms = check_shacl_vocabulary(shape_graph, supported_vocabulary)
    activation: dict[str, dict[str, Any]] = {}
    expected_by_case = {row["case_id"]: row["expected_outcome"] for row in selected_rows}
    for case_id in record.get("selected_case_ids", []):
        row = next((item for item in selected_rows if item["case_id"] == case_id), None)
        expected = expected_by_case.get(case_id)
        label = expected if expected in {"PASS", "FAIL"} else case_id
        if row is None:
            activation[label] = {"case_id": case_id, "result": "NOT_EVALUATED", "focus_nodes": [], "warnings": ["exact ledger row unavailable"]}
            continue
        try:
            data_graph = Graph().parse(_rdf_path(repo_root, row), format="turtle")
            result, focus_nodes, target_warnings = target_activation(shape_graph, data_graph)
            activation[label] = {"case_id": case_id, "result": result, "focus_nodes": focus_nodes, "warnings": target_warnings}
        except Exception as exc:
            activation[label] = {"case_id": case_id, "result": "ERROR", "focus_nodes": [], "warnings": [f"{type(exc).__name__}: {exc}"]}

    base.update({
        "shacl_specification_validity": spec_result,
        "specification_validity_provenance": provenance,
        "specification_validity_provenance_detail": detail,
        "shacl_vocabulary_validity": vocabulary_result,
        "unknown_shacl_terms": unknown_terms,
        "selected_case_target_activation": activation,
        "structural_profile": structural_profile(shape_graph),
    })
    return base, discrepancies


def _find_workbook_records(workbook: WorkbookXML) -> dict[tuple[str, str], tuple[str, int, dict[str, int], dict[str, Any]]]:
    found: dict[tuple[str, str], tuple[str, int, dict[str, int], dict[str, Any]]] = {}
    for architecture, sheet_name in SHEET_BY_ARCHITECTURE.items():
        header_row, headers = workbook.discover_headers(sheet_name, REQUIRED_HEADERS)
        for row_number, record in workbook.row_records(sheet_name, header_row, headers):
            requirement_id = str(record["Requirement ID"])
            key = (architecture, requirement_id)
            if key in found:
                raise EnrichmentError(f"Duplicate workbook requirement row: {architecture} {requirement_id}")
            found[key] = (sheet_name, row_number, headers, record)
    return found


def _validate_selection(
    selection: Mapping[str, Any],
    expected_requirements: int,
) -> dict[tuple[str, str], dict[str, Any]]:
    requirements = selection.get("requirements", [])
    if len(requirements) != expected_requirements or len(set(requirements)) != expected_requirements:
        raise EnrichmentError(f"Expected {expected_requirements} unique requirements; found {len(requirements)}/{len(set(requirements))}")
    records: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in selection.get("records", []):
        record = dict(raw)
        key = (record.get("architecture"), record.get("requirement_id"))
        if key[0] not in ARCHITECTURES or key[1] not in requirements:
            raise EnrichmentError(f"Unexpected selection identity: {key}")
        if key in records:
            raise EnrichmentError(f"Duplicate selection identity: {key}")
        if len(record.get("selected_case_ids", [])) != 2:
            raise EnrichmentError(f"Expected exactly two selected cases: {key}")
        records[key] = record
    expected_keys = {(architecture, requirement_id) for architecture in ARCHITECTURES for requirement_id in requirements}
    if set(records) != expected_keys:
        raise EnrichmentError(f"Selection architecture–requirement population mismatch: missing={sorted(expected_keys-set(records))[:5]}")
    return records


def _discrepancy_rows(discrepancies: Sequence[Discrepancy]) -> list[list[str]]:
    fields = list(Discrepancy.__dataclass_fields__)
    return [fields] + [[str(getattr(item, field)) for field in fields] for item in discrepancies]


def write_csv(path: Path, rows: Sequence[Sequence[Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerows(rows)


def _status_count(records: Sequence[Mapping[str, Any]], field: str, values: set[str]) -> tuple[int, int]:
    denominator = sum(record.get(field) in values for record in records)
    numerator = sum(record.get(field) == "VALID" for record in records)
    return numerator, denominator


def build_summary(
    evidence: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    input_workbook: Path,
    output_workbook: Path,
    discrepancies: Sequence[Discrepancy],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": "COMPLETE",
        "input_workbook": str(input_workbook),
        "input_workbook_sha256": sha256_file(input_workbook),
        "output_workbook": str(output_workbook),
        "output_workbook_sha256": sha256_file(output_workbook),
        "architectures": {},
        "discrepancy_count": len(discrepancies),
        "discrepancy_severity_counts": dict(Counter(item.severity for item in discrepancies)),
        "metric_definitions": {
            "artifact_availability": "available selected artifacts / 268 requirements",
            "conditional_turtle_parse_rate": "parse-valid selected artifacts / available selected artifacts",
            "conditional_shacl_specification_validity_rate": "specification-valid artifacts / artifacts for which specification validity was evaluated",
            "conditional_shacl_vocabulary_validity_rate": "vocabulary-valid artifacts / artifacts for which vocabulary validity was evaluated",
            "selected_case_target_activation_rate": "activated selected cases / selected cases for which activation was evaluated",
            "rdf_behavioural_accuracy": "recorded correct PASS/FAIL verdicts / recorded executed PASS/FAIL cases",
            "end_to_end_behavioural_accuracy": "recorded correct cases / all 2,186 frozen cases; unavailable and infrastructure-failure cases receive no credit",
        },
    }
    baseline = selection.get("baseline_metrics", {})
    for architecture in ARCHITECTURES:
        rows = [record for record in evidence if record["architecture"] == architecture]
        available = sum(record["availability"] == "AVAILABLE" for record in rows)
        parse_valid = sum(
            record["availability"] == "AVAILABLE"
            and record["existing_parsing_evidence"].get("status") == "PARSED"
            for record in rows
        )
        spec_evaluated = sum(record["shacl_specification_validity"] in {"VALID", "INVALID"} for record in rows)
        spec_valid = sum(record["shacl_specification_validity"] == "VALID" for record in rows)
        vocab_evaluated = sum(record["shacl_vocabulary_validity"] in {"VALID", "INVALID"} for record in rows)
        vocab_valid = sum(record["shacl_vocabulary_validity"] == "VALID" for record in rows)
        activations = [
            value["result"]
            for record in rows
            for value in record["selected_case_target_activation"].values()
        ]
        activation_evaluated = sum(value in {"ACTIVATED", "NOT_ACTIVATED"} for value in activations)
        activation_yes = sum(value == "ACTIVATED" for value in activations)
        recorded = baseline.get(architecture, {})
        executed = recorded.get("executed", 0)
        cases = recorded.get("cases", 0)
        correct = recorded.get("correct", 0)
        summary["architectures"][architecture] = {
            "artifact_selection_category_counts": dict(Counter(record.get("artifact_selection_category") for record in rows)),
            "pipeline_generation_status_counts": dict(Counter(
                record["existing_pipeline_validation_evidence"].get("generation_status") for record in rows
            )),
            "specification_validity_provenance_counts": dict(Counter(
                record.get("specification_validity_provenance") for record in rows
            )),
            "artifact_availability": {"numerator": available, "denominator": len(rows), "rate": available / len(rows) if rows else None},
            "conditional_turtle_parse_rate": {"numerator": parse_valid, "denominator": available, "rate": parse_valid / available if available else None},
            "conditional_shacl_specification_validity_rate": {"numerator": spec_valid, "denominator": spec_evaluated, "rate": spec_valid / spec_evaluated if spec_evaluated else None},
            "conditional_shacl_vocabulary_validity_rate": {"numerator": vocab_valid, "denominator": vocab_evaluated, "rate": vocab_valid / vocab_evaluated if vocab_evaluated else None},
            "selected_case_target_activation_rate": {"numerator": activation_yes, "denominator": activation_evaluated, "rate": activation_yes / activation_evaluated if activation_evaluated else None},
            "rdf_behavioural_accuracy_recorded_not_recomputed": {"numerator": correct, "denominator": executed, "rate": correct / executed if executed else None},
            "end_to_end_behavioural_accuracy_recorded_not_recomputed": {"numerator": correct, "denominator": cases, "rate": correct / cases if cases else None},
            "recorded_equal_weight_requirement_accuracy": recorded.get("macro"),
            "recorded_requirements_all_cases_correct": {"numerator": recorded.get("exact"), "denominator": recorded.get("requirements")},
            "recorded_false_accepts": recorded.get("fa"),
            "recorded_false_rejects": recorded.get("fr"),
            "recorded_cases_without_verdict": cases - executed if cases and executed is not None else None,
        }
    return summary


def verify_workbook_preservation(input_path: Path, output_path: Path) -> None:
    before = WorkbookXML(input_path)
    after = WorkbookXML(output_path)
    if before.sheet_names() != after.sheet_names():
        raise EnrichmentError("Workbook sheet names or order changed")
    changed_parts = {before.sheet_parts[name] for name in SHEET_BY_ARCHITECTURE.values()}
    if set(before.members) != set(after.members):
        raise EnrichmentError("Workbook ZIP member inventory changed")
    for name in before.members:
        if name not in changed_parts and before.members[name] != after.members[name]:
            raise EnrichmentError(f"Unrelated workbook part changed: {name}")
    for sheet_name in SHEET_BY_ARCHITECTURE.values():
        before_header_row, before_headers = before.discover_headers(sheet_name, REQUIRED_HEADERS)
        after_header_row, after_headers = after.discover_headers(sheet_name, REQUIRED_HEADERS)
        if (before_header_row, before_headers) != (after_header_row, after_headers):
            raise EnrichmentError(f"Workbook headers changed: {sheet_name}")
        allowed_columns = {before_headers[header] for header in AUTOMATIC_HEADERS}
        before_rows = {int(row.attrib["r"]): row for row in before._rows(sheet_name)}
        after_rows = {int(row.attrib["r"]): row for row in after._rows(sheet_name)}
        if set(before_rows) != set(after_rows):
            raise EnrichmentError(f"Workbook row inventory changed: {sheet_name}")
        for row_number in before_rows:
            before_cells = before._cells_by_column(before_rows[row_number])
            after_cells = after._cells_by_column(after_rows[row_number])
            all_columns = set(before_cells) | set(after_cells)
            for column in all_columns:
                if column in allowed_columns and row_number > before_header_row:
                    before_formula = before_cells.get(column).find("x:f", NS) if before_cells.get(column) is not None else None
                    after_formula = after_cells.get(column).find("x:f", NS) if after_cells.get(column) is not None else None
                    if (before_formula is None) != (after_formula is None) or (
                        before_formula is not None and before_formula.text != after_formula.text
                    ):
                        raise EnrichmentError(f"Formula changed in automatic field: {sheet_name}!{column_letters(column)}{row_number}")
                    continue
                left = ET.tostring(before_cells[column]) if column in before_cells else None
                right = ET.tostring(after_cells[column]) if column in after_cells else None
                if left != right:
                    raise EnrichmentError(f"Protected workbook cell changed: {sheet_name}!{column_letters(column)}{row_number}")
        for child_name in ("mergeCells", "conditionalFormatting", "dataValidations", "hyperlinks", "sheetProtection"):
            left = [ET.tostring(node) for node in before.sheet_roots[sheet_name].findall(f"x:{child_name}", NS)]
            right = [ET.tostring(node) for node in after.sheet_roots[sheet_name].findall(f"x:{child_name}", NS)]
            if left != right:
                raise EnrichmentError(f"Workbook feature changed in {sheet_name}: {child_name}")


def run_enrichment(
    repo_root: Path,
    audit_dir: Path,
    *,
    expected_requirements: int = 268,
    expected_availability: Mapping[str, int] = EXPECTED_AVAILABILITY,
    recheck_unresolved: bool = True,
) -> dict[str, Any]:
    input_workbook = audit_dir / INPUT_WORKBOOK_NAME
    output_workbook = audit_dir / OUTPUT_WORKBOOK_NAME
    selection_path = audit_dir / SELECTION_NAME
    targets = [output_workbook, audit_dir / EVIDENCE_NAME, audit_dir / SUMMARY_NAME, audit_dir / DISCREPANCIES_NAME]
    if not input_workbook.is_file():
        available = sorted(path.name for path in audit_dir.glob("*.xlsx"))
        raise EnrichmentError(f"MethodV2 workbook is missing: {input_workbook}. Available: {available}")
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise EnrichmentError(f"Refusing to overwrite existing enrichment outputs: {existing}")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selected_records = _validate_selection(selection, expected_requirements)
    workbook = WorkbookXML(input_workbook)
    workbook_records = _find_workbook_records(workbook)
    if set(workbook_records) != set(selected_records):
        raise EnrichmentError("Workbook and authoritative selection architecture–requirement identities differ")

    supported_vocabulary = load_supported_shacl_vocabulary()
    ledger_cache = LedgerCache(repo_root)
    evidence_records: list[dict[str, Any]] = []
    discrepancies: list[Discrepancy] = []
    for architecture in ARCHITECTURES:
        for requirement_id in selection["requirements"]:
            key = (architecture, requirement_id)
            record = selected_records[key]
            evidence, evidence_discrepancies = build_evidence_record(
                repo_root, record, ledger_cache, supported_vocabulary, recheck_unresolved
            )
            evidence_records.append(evidence)
            discrepancies.extend(evidence_discrepancies)
            sheet_name, row_number, headers, workbook_record = workbook_records[key]
            source_path = record.get("source_ledger_path", "")
            _compare_workbook(discrepancies, architecture, requirement_id, sheet_name, row_number, headers, workbook_record, "Selected generation run", "RUN_01", SELECTION_NAME)
            _compare_workbook(discrepancies, architecture, requirement_id, sheet_name, row_number, headers, workbook_record, "Selected SHACL path", record.get("shape_path") or "MISSING", SELECTION_NAME)
            _compare_workbook(discrepancies, architecture, requirement_id, sheet_name, row_number, headers, workbook_record, "Selected SHACL SHA-256", record.get("shape_sha256") or "UNAVAILABLE", SELECTION_NAME)
            _compare_workbook(discrepancies, architecture, requirement_id, sheet_name, row_number, headers, workbook_record, "Recorded Turtle parse status", record.get("parse_status"), SELECTION_NAME)
            _compare_workbook(discrepancies, architecture, requirement_id, sheet_name, row_number, headers, workbook_record, "Recorded deterministic status", record.get("deterministic_status"), SELECTION_NAME)
            selected_rows = evidence["existing_behavioural_ledger_evidence"]["selected_case_rows"]
            for index, case_id in enumerate(record["selected_case_ids"], start=1):
                row = next((item for item in selected_rows if item["case_id"] == case_id), None)
                if row is None:
                    continue
                _compare_workbook(discrepancies, architecture, requirement_id, sheet_name, row_number, headers, workbook_record, f"Selected case {index}", case_id, source_path, case_id)
                _compare_workbook(discrepancies, architecture, requirement_id, sheet_name, row_number, headers, workbook_record, f"Original expected {index}", row.get("expected_outcome"), source_path, case_id)
                _compare_workbook(discrepancies, architecture, requirement_id, sheet_name, row_number, headers, workbook_record, f"Recorded actual {index}", actual_verdict(row), source_path, case_id)
                _compare_workbook(discrepancies, architecture, requirement_id, sheet_name, row_number, headers, workbook_record, f"Recorded outcome {index}", row.get("outcome_class"), source_path, case_id)
            for header, value in _automatic_cell_values(evidence).items():
                changed, current = workbook.set_if_blank(sheet_name, row_number, headers[header], value)
                if not changed and current != value:
                    discrepancies.append(Discrepancy(
                        "WARNING", "EXISTING_AUTOMATIC_VALUE_DISAGREEMENT", architecture, requirement_id,
                        workbook_sheet=sheet_name, workbook_cell=f"{column_letters(headers[header])}{row_number}",
                        field=header, workbook_value=str(current), source_value=str(value),
                        source_path=record.get("shape_path", ""), message="Existing automatic value or formula was preserved",
                    ))

    observed_availability = Counter(
        record["architecture"] for record in evidence_records if record["availability"] == "AVAILABLE"
    )
    if dict(observed_availability) != dict(expected_availability):
        raise EnrichmentError(
            f"Artifact availability differs from the frozen expectation: observed={dict(observed_availability)} expected={dict(expected_availability)}"
        )

    with tempfile.TemporaryDirectory(prefix="nltl-auto-evidence-", dir=audit_dir) as temporary:
        stage = Path(temporary)
        staged_workbook = stage / OUTPUT_WORKBOOK_NAME
        workbook.save(staged_workbook, SHEET_BY_ARCHITECTURE.values())
        verify_workbook_preservation(input_workbook, staged_workbook)
        staged_evidence = stage / EVIDENCE_NAME
        staged_evidence.write_text(
            "".join(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in evidence_records),
            encoding="utf-8",
        )
        staged_discrepancies = stage / DISCREPANCIES_NAME
        write_csv(staged_discrepancies, _discrepancy_rows(discrepancies))
        summary = build_summary(evidence_records, selection, input_workbook, staged_workbook, discrepancies)
        summary["output_workbook"] = str(output_workbook.relative_to(repo_root))
        staged_summary = stage / SUMMARY_NAME
        staged_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        for staged, target in (
            (staged_workbook, output_workbook),
            (staged_evidence, audit_dir / EVIDENCE_NAME),
            (staged_summary, audit_dir / SUMMARY_NAME),
            (staged_discrepancies, audit_dir / DISCREPANCIES_NAME),
        ):
            if target.exists():
                raise EnrichmentError(f"Refusing to overwrite output created concurrently: {target}")
            shutil.move(staged, target)
    return {
        "output_workbook": str(output_workbook),
        "records": len(evidence_records),
        "availability": dict(observed_availability),
        "discrepancies": len(discrepancies),
    }


def verify_outputs(repo_root: Path, audit_dir: Path, expected_requirements: int = 268) -> dict[str, Any]:
    input_workbook = audit_dir / INPUT_WORKBOOK_NAME
    output_workbook = audit_dir / OUTPUT_WORKBOOK_NAME
    selection = json.loads((audit_dir / SELECTION_NAME).read_text(encoding="utf-8"))
    selected = _validate_selection(selection, expected_requirements)
    evidence = json_lines(audit_dir / EVIDENCE_NAME)
    keys = [(row["architecture"], row["requirement_id"]) for row in evidence]
    if len(evidence) != expected_requirements * len(ARCHITECTURES) or len(set(keys)) != len(evidence):
        raise EnrichmentError("Automatic evidence JSONL does not have one unique row per architecture–requirement")
    if set(keys) != set(selected):
        raise EnrichmentError("Automatic evidence identities differ from audit_selection.json")
    for row in evidence:
        selection_row = selected[(row["architecture"], row["requirement_id"])]
        if row.get("artifact_path") != selection_row.get("shape_path") or row.get("artifact_sha256") != selection_row.get("shape_sha256"):
            raise EnrichmentError(f"Artifact substitution detected in evidence: {row['architecture']} {row['requirement_id']}")
    summary = json.loads((audit_dir / SUMMARY_NAME).read_text(encoding="utf-8"))
    if summary.get("output_workbook_sha256") != sha256_file(output_workbook):
        raise EnrichmentError("Enriched workbook hash differs from automatic_summary.json")
    verify_workbook_preservation(input_workbook, output_workbook)
    with (audit_dir / DISCREPANCIES_NAME).open(encoding="utf-8", newline="") as stream:
        discrepancy_count = max(sum(1 for _ in csv.reader(stream)) - 1, 0)
    if discrepancy_count != summary.get("discrepancy_count"):
        raise EnrichmentError("Discrepancy CSV row count differs from automatic_summary.json")
    return {
        "status": "PASS",
        "evidence_records": len(evidence),
        "output_workbook_sha256": sha256_file(output_workbook),
        "discrepancies": discrepancy_count,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, help="Repository root; normally discovered automatically")
    parser.add_argument("--audit-dir", type=Path, help="Audit directory; defaults to AUDIT_20260915")
    parser.add_argument("--verify-only", action="store_true", help="Verify already-created enrichment outputs without modifying files")
    parser.add_argument(
        "--no-recheck-unresolved-meta-shacl", action="store_true",
        help="Leave unresolved specification validity NOT_TESTED instead of running targeted standalone meta-SHACL",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = (args.repo_root or find_repo_root(Path(__file__).resolve())).resolve()
    audit_dir = (
        args.audit_dir
        or repo_root / "MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915"
    ).resolve()
    try:
        result = (
            verify_outputs(repo_root, audit_dir)
            if args.verify_only
            else run_enrichment(
                repo_root, audit_dir,
                recheck_unresolved=not args.no_recheck_unresolved_meta_shacl,
            )
        )
    except EnrichmentError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
