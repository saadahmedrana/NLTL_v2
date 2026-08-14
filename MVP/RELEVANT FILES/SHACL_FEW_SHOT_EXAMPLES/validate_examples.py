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


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
CATALOG_PATH = ROOT / "catalog.json"
ONTOLOGY_PATH = PROJECT / "BENCHMARK_VOCABULARY/STAGE2/ontology/nltl_benchmark_vocabulary.ttl"
NLTL = "https://w3id.org/nltl/vocab#"

ALLOWED_EXTERNAL_NAMESPACES = (
    "urn:nltl:few-shot:",
    NLTL,
    "http://purl.org/dc/terms/",
    "http://qudt.org/schema/qudt/",
    "http://qudt.org/vocab/unit/",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/2001/XMLSchema#",
    "http://www.w3.org/ns/shacl#",
    "http://www.w3.org/ns/sosa/",
)


def sha256(path):
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_turtle(path):
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def check_style(path):
    errors = []
    text = path.read_text(encoding="utf-8")
    if any(line.lstrip().startswith("#") for line in text.splitlines()):
        errors.append(f"{path}: comment line found")

    declarations = re.findall(r"^@prefix\s+([A-Za-z][A-Za-z0-9_-]*):", text, flags=re.MULTILINE)
    content = re.sub(r"^@prefix\s+[^\n]+\n?", "", text, flags=re.MULTILINE)
    for prefix in declarations:
        if not re.search(rf"(?<![A-Za-z0-9_-]){re.escape(prefix)}:", content):
            errors.append(f"{path}: unused prefix {prefix}:")
    return errors


def graph_iris(graph):
    iris = set()
    for triple in graph:
        for value in triple:
            if isinstance(value, URIRef):
                iris.add(str(value))
    return iris


def check_namespaces(path, graph):
    errors = []
    for iri in graph_iris(graph):
        if not iri.startswith(ALLOWED_EXTERNAL_NAMESPACES):
            errors.append(f"{path}: unapproved external IRI {iri}")
    return errors


def nltl_iris(path, graph):
    found = {iri for iri in graph_iris(graph) if iri.startswith(NLTL)}
    text = path.read_text(encoding="utf-8")
    found.update(re.findall(r"https://w3id\.org/nltl/vocab#[A-Za-z][A-Za-z0-9]*", text))
    return found


def run_validation(data_graph, shape_graph):
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
    return bool(conforms), report_graph, str(report_text)


def main():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    ontology = parse_turtle(ONTOLOGY_PATH)
    results = []
    errors = []

    jsonl_path = ROOT / catalog["promptReadyJsonl"]
    try:
        prompt_pairs = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line]
    except Exception as exc:
        prompt_pairs = []
        errors.append(f"{jsonl_path}: JSONL parse failed: {exc}")
    prompt_by_id = {record.get("exampleId"): record for record in prompt_pairs}
    if len(prompt_pairs) != catalog["exampleCount"]:
        errors.append(
            f"{jsonl_path}: expected {catalog['exampleCount']} prompt pairs, found {len(prompt_pairs)}"
        )

    for item in catalog["examples"]:
        example_dir = ROOT / item["directory"]
        metadata_path = example_dir / "metadata.json"
        shape_path = example_dir / "expected_shape.ttl"
        pass_path = example_dir / "example_data_pass.ttl"
        fail_path = example_dir / "example_data_fail.ttl"
        requirement_path = example_dir / "input_requirement.txt"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        local_errors = []
        prompt_pair = prompt_by_id.get(item["exampleId"])
        if prompt_pair is None:
            local_errors.append(f"{item['exampleId']}: missing prompt-ready JSONL record")
        else:
            if prompt_pair.get("inputRequirement") != requirement_path.read_text(encoding="utf-8").strip():
                local_errors.append(f"{item['exampleId']}: JSONL requirement does not match source file")
            if prompt_pair.get("expectedShapeTurtle") != shape_path.read_text(encoding="utf-8"):
                local_errors.append(f"{item['exampleId']}: JSONL shape does not match source file")
            if prompt_pair.get("generatorVocabulary") != metadata["generatorVocabulary"]:
                local_errors.append(f"{item['exampleId']}: JSONL vocabulary does not match metadata")
            if "passData" in prompt_pair or "failData" in prompt_pair:
                local_errors.append(f"{item['exampleId']}: QA data leaked into prompt-ready JSONL")
        graphs = {}
        for role, path in (("shape", shape_path), ("pass", pass_path), ("fail", fail_path)):
            local_errors.extend(check_style(path))
            try:
                graphs[role] = parse_turtle(path)
                local_errors.extend(check_namespaces(path, graphs[role]))
            except Exception as exc:
                local_errors.append(f"{path}: Turtle parse failed: {exc}")

        metadata_terms = metadata["generatorVocabulary"] + metadata["negativeExampleOnlyVocabulary"]
        declared_iris = {record["iri"] for record in metadata_terms}
        for record in metadata_terms:
            iri = URIRef(record["iri"])
            if not any(ontology.triples((iri, None, None))):
                local_errors.append(f"{metadata_path}: undeclared locked vocabulary term {iri}")

        if len(graphs) == 3:
            used_nltl_iris = set()
            for role, path in (("shape", shape_path), ("pass", pass_path), ("fail", fail_path)):
                used_nltl_iris.update(nltl_iris(path, graphs[role]))
            unexpected = sorted(used_nltl_iris - declared_iris)
            missing = sorted(declared_iris - used_nltl_iris)
            if unexpected:
                local_errors.append(f"{item['exampleId']}: NLTL terms missing from metadata: {unexpected}")
            if missing:
                local_errors.append(f"{item['exampleId']}: metadata terms not used by bundle: {missing}")

            pass_conforms, pass_report, pass_text = run_validation(graphs["pass"], graphs["shape"])
            fail_conforms, fail_report, fail_text = run_validation(graphs["fail"], graphs["shape"])
            if pass_conforms is not True:
                local_errors.append(f"{item['exampleId']}: pass graph did not conform: {pass_text}")
            if fail_conforms is not False:
                local_errors.append(f"{item['exampleId']}: fail graph unexpectedly conformed: {fail_text}")
        else:
            pass_conforms = None
            fail_conforms = None
            pass_report = Graph()
            fail_report = Graph()

        row = {
            "exampleId": item["exampleId"],
            "caseId": item["caseId"],
            "passConforms": pass_conforms,
            "failConforms": fail_conforms,
            "passReportTripleCount": len(pass_report),
            "failReportTripleCount": len(fail_report),
            "fileSha256": {
                "requirement": sha256(requirement_path),
                "shape": sha256(shape_path),
                "passData": sha256(pass_path),
                "failData": sha256(fail_path),
                "metadata": sha256(metadata_path),
            },
            "errors": local_errors,
        }
        results.append(row)
        errors.extend(local_errors)

    report = {
        "libraryId": catalog["libraryId"],
        "validationDate": str(date.today()),
        "pyshaclVersion": pyshacl.__version__,
        "rdflibVersion": rdflib.__version__,
        "exampleCount": len(results),
        "expectedPassGraphCount": len(results),
        "expectedFailGraphCount": len(results),
        "actualPassGraphConformanceCount": sum(row["passConforms"] is True for row in results),
        "actualFailGraphNonConformanceCount": sum(row["failConforms"] is False for row in results),
        "allChecksPassed": not errors,
        "errorCount": len(errors),
        "results": results,
    }
    (ROOT / "validation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# SHACL few-shot validation report",
        "",
        f"- Library: `{report['libraryId']}`",
        f"- Examples: {report['exampleCount']}",
        f"- Expected-pass graphs that conformed: {report['actualPassGraphConformanceCount']}/{report['expectedPassGraphCount']}",
        f"- Expected-fail graphs that did not conform: {report['actualFailGraphNonConformanceCount']}/{report['expectedFailGraphCount']}",
        f"- pySHACL: `{report['pyshaclVersion']}`",
        f"- RDFLib: `{report['rdflibVersion']}`",
        f"- Overall result: {'PASS' if report['allChecksPassed'] else 'FAIL'}",
        "",
        "| Example | Case | Pass graph | Fail graph | QA |",
        "|---|---|---:|---:|---|",
    ]
    for row in results:
        lines.append(
            f"| {row['exampleId']} | {row['caseId']} | "
            f"{'conforms' if row['passConforms'] else 'does not conform'} | "
            f"{'does not conform' if row['failConforms'] is False else 'conforms'} | "
            f"{'PASS' if not row['errors'] else 'FAIL'} |"
        )
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in errors)
    (ROOT / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if errors:
        print(f"FAIL: {len(errors)} validation errors")
        return 1
    print(f"PASS: {len(results)} shapes, {len(results)} conforming pass graphs, {len(results)} non-conforming fail graphs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
