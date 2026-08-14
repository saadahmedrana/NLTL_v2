#!/usr/bin/env python3

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import pyshacl
import rdflib
from pyshacl import validate
from rdflib import Graph, URIRef
from rdflib.namespace import SH


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
MANIFEST_PATH = ROOT / "pilot_manifest.json"
ONTOLOGY_PATH = PROJECT / "BENCHMARK_VOCABULARY/STAGE2/ontology/nltl_benchmark_vocabulary.ttl"
EVIDENCE_PATH = PROJECT / "BENCHMARK_VOCABULARY/STAGE2/evidence/stage1_approved.json"
NLTL = "https://w3id.org/nltl/vocab#"

ALLOWED_NAMESPACES = (
    "urn:nltl:rdf-pilot:",
    NLTL,
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/ns/shacl#",
)


def parse_turtle(path):
    return Graph().parse(path, format="turtle")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def graph_iris(graph):
    return {
        str(value)
        for triple in graph
        for value in triple
        if isinstance(value, URIRef)
    }


def check_turtle(path, graph, ontology):
    errors = []
    text = path.read_text(encoding="utf-8")
    if any(line.lstrip().startswith("#") for line in text.splitlines()):
        errors.append(f"{path}: Turtle comment line found")

    prefixes = re.findall(r"^@prefix\s+([A-Za-z][A-Za-z0-9_-]*):", text, flags=re.MULTILINE)
    body = re.sub(r"^@prefix\s+[^\n]+\n?", "", text, flags=re.MULTILINE)
    for prefix in prefixes:
        if not re.search(rf"(?<![A-Za-z0-9_-]){re.escape(prefix)}:", body):
            errors.append(f"{path}: unused prefix {prefix}:")

    for iri in sorted(graph_iris(graph)):
        if not iri.startswith(ALLOWED_NAMESPACES):
            errors.append(f"{path}: unapproved IRI namespace {iri}")
        if iri.startswith(NLTL) and not any(ontology.triples((URIRef(iri), None, None))):
            errors.append(f"{path}: NLTL term is not declared in the locked ontology: {iri}")
    for iri in re.findall(r"https://w3id\.org/nltl/vocab#[A-Za-z][A-Za-z0-9]*", text):
        if not any(ontology.triples((URIRef(iri), None, None))):
            errors.append(f"{path}: SHACL-SPARQL uses undeclared NLTL term: {iri}")
    return errors


def changed_fact(pass_graph, fail_graph):
    removed = set(pass_graph) - set(fail_graph)
    added = set(fail_graph) - set(pass_graph)
    if len(removed) != 1 or len(added) != 1:
        return None, f"expected one removed and one added triple, found {len(removed)} removed and {len(added)} added"
    old = next(iter(removed))
    new = next(iter(added))
    if old[:2] != new[:2]:
        return None, "paired graphs change more than one subject-predicate fact"
    return {
        "subject": str(old[0]),
        "predicate": str(old[1]),
        "passValue": str(old[2]),
        "failValue": str(new[2]),
    }, None


def validation_messages(report_graph):
    return sorted({str(value) for value in report_graph.objects(None, SH.resultMessage)})


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    requirement_by_id = {item["id"]: item for item in evidence["requirements"]}
    ontology = parse_turtle(ONTOLOGY_PATH)
    errors = []
    rows = []
    requirement_links = 0

    for case_ref in manifest["cases"]:
        case_dir = ROOT / case_ref["directory"]
        case_path = ROOT / case_ref["metadata"]
        case = json.loads(case_path.read_text(encoding="utf-8"))
        shape_path = case_dir / case["shapeFile"]
        shape_graph = parse_turtle(shape_path)
        case_errors = check_turtle(shape_path, shape_graph, ontology)

        for requirement in case["requirements"]:
            requirement_links += 1
            locked = requirement_by_id.get(requirement["requirementId"])
            if locked is None:
                case_errors.append(f"{case['caseId']}: unknown locked requirement {requirement['requirementId']}")
                continue
            if locked["clause"] != requirement["clause"]:
                case_errors.append(
                    f"{case['caseId']}: clause mismatch for {requirement['requirementId']}"
                )
            source_path = PROJECT / requirement["sourceFile"]
            if not source_path.exists():
                case_errors.append(f"{case['caseId']}: missing regulation source {source_path}")

        variant_graphs = {}
        for variant in case["variants"]:
            data_path = case_dir / variant["dataFile"]
            data_graph = parse_turtle(data_path)
            variant_graphs[variant["variantId"]] = data_graph
            local_errors = check_turtle(data_path, data_graph, ontology)
            conforms, report_graph, report_text = validate(
                data_graph=data_graph,
                shacl_graph=shape_graph,
                inference="none",
                advanced=True,
                meta_shacl=True,
                abort_on_first=False,
                allow_infos=False,
                allow_warnings=False,
            )
            actual = bool(conforms)
            if actual != variant["expectedConforms"]:
                local_errors.append(
                    f"{variant['variantId']}: expected conforms={variant['expectedConforms']} but got {actual}: {report_text}"
                )
            messages = validation_messages(report_graph)
            expected_violations = variant.get("expectedViolatedRequirements", [])
            for requirement_id in expected_violations:
                if not any(message.startswith(requirement_id + ":") for message in messages):
                    local_errors.append(
                        f"{variant['variantId']}: validation report did not identify expected requirement {requirement_id}"
                    )
            rows.append(
                {
                    "caseId": case["caseId"],
                    "caseLevel": case["caseLevel"],
                    "variantId": variant["variantId"],
                    "dataFile": data_path.relative_to(ROOT).as_posix(),
                    "shapeFile": shape_path.relative_to(ROOT).as_posix(),
                    "expectedConforms": variant["expectedConforms"],
                    "actualConforms": actual,
                    "validationMessages": messages,
                    "dataSha256": sha256(data_path),
                    "shapeSha256": sha256(shape_path),
                    "errors": local_errors,
                }
            )
            case_errors.extend(local_errors)

        pass_variant = next(item for item in case["variants"] if item["expectedConforms"] is True)
        fail_variant = next(item for item in case["variants"] if item["expectedConforms"] is False)
        delta, delta_error = changed_fact(
            variant_graphs[pass_variant["variantId"]],
            variant_graphs[fail_variant["variantId"]],
        )
        if delta_error:
            case_errors.append(f"{case['caseId']}: {delta_error}")
        for row in rows:
            if row["caseId"] == case["caseId"]:
                row["pairedGraphDelta"] = delta

        errors.extend(case_errors)

    if manifest["caseCount"] != len(manifest["cases"]):
        errors.append("pilot_manifest.json caseCount does not match case entries")
    if manifest["variantCount"] != len(rows):
        errors.append("pilot_manifest.json variantCount does not match variant entries")

    report = {
        "pilotId": manifest["pilotId"],
        "validationDate": str(date.today()),
        "pyshaclVersion": pyshacl.__version__,
        "rdflibVersion": rdflib.__version__,
        "caseCount": len(manifest["cases"]),
        "variantCount": len(rows),
        "requirementLinkCount": requirement_links,
        "expectedPassCount": sum(row["expectedConforms"] is True for row in rows),
        "actualPassConformanceCount": sum(
            row["expectedConforms"] is True and row["actualConforms"] is True for row in rows
        ),
        "expectedFailCount": sum(row["expectedConforms"] is False for row in rows),
        "actualFailNonConformanceCount": sum(
            row["expectedConforms"] is False and row["actualConforms"] is False for row in rows
        ),
        "allChecksPassed": not errors,
        "errorCount": len(errors),
        "results": rows,
        "errors": errors,
    }
    (ROOT / "validation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# RDF ship graph pilot validation",
        "",
        f"- Pilot: `{report['pilotId']}`",
        f"- Cases: {report['caseCount']}",
        f"- RDF variants: {report['variantCount']}",
        f"- Requirement links: {report['requirementLinkCount']}",
        f"- Expected-pass graphs conforming: {report['actualPassConformanceCount']}/{report['expectedPassCount']}",
        f"- Expected-fail graphs non-conforming: {report['actualFailNonConformanceCount']}/{report['expectedFailCount']}",
        f"- pySHACL: `{report['pyshaclVersion']}`",
        f"- RDFLib: `{report['rdflibVersion']}`",
        f"- Overall result: {'PASS' if report['allChecksPassed'] else 'FAIL'}",
        "",
        "| Variant | Level | Expected | Actual | Deliberate changed property | QA |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        delta = row.get("pairedGraphDelta") or {}
        predicate = delta.get("predicate", "")
        if predicate.startswith(NLTL):
            predicate = predicate[len(NLTL):]
        lines.append(
            f"| {row['variantId']} | {row['caseLevel']} | "
            f"{'conforms' if row['expectedConforms'] else 'does not conform'} | "
            f"{'conforms' if row['actualConforms'] else 'does not conform'} | {predicate} | "
            f"{'PASS' if not row['errors'] else 'FAIL'} |"
        )
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in errors)
    (ROOT / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if errors:
        print(f"FAIL: {len(errors)} errors")
        return 1
    print(
        f"PASS: {report['caseCount']} cases, {report['actualPassConformanceCount']} conforming pass graphs, "
        f"{report['actualFailNonConformanceCount']} non-conforming fail graphs"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
