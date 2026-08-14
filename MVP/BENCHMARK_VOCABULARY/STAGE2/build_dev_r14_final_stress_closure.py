from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

from rdflib import Graph, Literal, OWL, RDF

import build_dev_r9_foundation as r9


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R3"
OUT = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R14_FINAL_STRESS_GAP_CLOSURE"
BASE = r9.BASE
DEV_ID = "VOCAB-DEV-2026-08-14-R14-FINAL-STRESS-GAP-CLOSURE"
VERSION = "2.14.0-dev-final-stress-gap-closure"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cls(parent, module, requirements, aliases=()):
    return {"kind": "Class", "range": parent, "module": module, "requirements": list(requirements), "aliases": list(aliases)}


def obj(domain, range_, module, requirements, aliases=()):
    return {"kind": "ObjectProperty", "domain": domain, "range": range_, "module": module, "requirements": list(requirements), "aliases": list(aliases)}


SPECS = {
    "hullBoundaryPoint": cls("benchmarkEntity", "hull", ("I2-005",), ("boundary point",)),
    "hasBottomRegionLowerRegionBoundaryPoint": obj("ship", "hullBoundaryPoint", "hull", ("I2-005",), ("boundary between bottom and lower regions",)),
    "nonMagneticHeadingMeans": cls("navigationEquipmentItem", "machinery", ("IMO-086", "IMO26-012"), ("non-magnetic means to determine and display heading",)),
    "hasNonMagneticHeadingMeans": obj("ship", "nonMagneticHeadingMeans", "machinery", ("IMO-086", "IMO26-012"), ("provided with two non-magnetic means",)),
    "independentFromHeadingMeans": obj("nonMagneticHeadingMeans", "nonMagneticHeadingMeans", "machinery", ("IMO-086", "IMO26-012"), ("both means shall be independent",)),
}


def main() -> None:
    if OUT.exists():
        validation = OUT / "validation/validation_report.json"
        if validation.exists() and read_json(validation).get("status") == "PASS":
            raise FileExistsError(f"Refusing to overwrite completed R14 directory: {OUT}")
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)
    for stale in ("prelock_manifest.json", "confirmation", "benchmark_vocabulary_stage2_LOCK-2026-08-14-R3.lock.json", "benchmark_vocabulary_stage2_LOCK-2026-08-14-R3.sha256", "benchmark_vocabulary_stage2_LOCK-2026-08-14-R3.xlsx", "benchmark_vocabulary_stage2_LOCK-2026-08-14-R3.xlsx.inspect.ndjson"):
        path = OUT / stale
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    evidence_payload = read_json(OUT / "evidence/stage1_approved.json")
    evidence = {item["id"]: item for item in evidence_payload["requirements"]}
    registry = read_json(OUT / "registry/term_registry.json")
    existing = {item["localName"] for item in registry}
    additions = [r9.registry_record(name, spec, f"VOC-DEV-R14-{number:04d}", evidence)
                 for number, (name, spec) in enumerate(sorted(SPECS.items()), 1) if name not in existing]
    registry = sorted(registry + additions, key=lambda item: item["localName"])
    write_json(OUT / "registry/term_registry.json", registry)
    fields = list(csv.DictReader((SOURCE / "registry/term_registry.csv").open(encoding="utf-8")).fieldnames or [])
    with (OUT / "registry/term_registry.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in registry:
            row = {key: item.get(key, "") for key in fields}
            for key in ("sourceConceptIds", "stage1LocalNames", "aliases", "requirements"):
                row[key] = "; ".join(item.get(key, []))
            writer.writerow(row)

    graph = Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    for item in additions:
        r9.add_to_graph(graph, item, SPECS[item["localName"]])
    for ontology in graph.subjects(RDF.type, OWL.Ontology):
        graph.set((ontology, OWL.versionInfo, Literal(VERSION)))
    graph.serialize(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.serialize(OUT / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")

    context = read_json(OUT / "context/nltl_benchmark_context.jsonld")
    for item in additions:
        context["@context"][item["localName"]] = ({"@id": "nltl:" + item["localName"], "@type": "@id"}
                                                   if item["kind"] == "ObjectProperty" else "nltl:" + item["localName"])
    write_json(OUT / "context/nltl_benchmark_context.jsonld", context)

    index = read_json(OUT / "requirement_term_index.json")
    index["sourceLockId"] = DEV_ID
    index["version"] = "2.14.0-dev-contract-schema-v6-final-stress-closure"
    i2_terms = ["ship", "hullBoundaryPoint", "hasBottomRegionLowerRegionBoundaryPoint", "shellInclinationAngle"]
    index["requirements"]["I2-005"] = i2_terms
    index.setdefault("termOwners", {})["I2-005"] = {
        "hasBottomRegionLowerRegionBoundaryPoint": "ship", "shellInclinationAngle": "hullBoundaryPoint"
    }
    index["dependencyContracts"]["I2-005"].update({
        "schemaVersion": 6, "status": "COMPLETE", "engineeringDecision": "R14_EXPLICIT_BOUNDARY_POINT_MODEL",
        "ownerClasses": ["ship", "hullBoundaryPoint"], "operandTerms": ["shellInclinationAngle"],
        "relationshipTerms": ["hasBottomRegionLowerRegionBoundaryPoint"], "comparisonTerms": ["shellInclinationAngle"],
        "legacyIndexedTerms": ["bottomRegionLowerRegionBoundary"],
        "comparisonModel": "Each ship has a bottom/lower-region boundary point whose shellInclinationAngle QuantityValue is exactly 7 degrees from horizontal.",
        "modelPaths": [{"fromOwner": "ship", "via": "hasBottomRegionLowerRegionBoundaryPoint", "toOwner": "hullBoundaryPoint"}],
    })

    heading_terms = ["ship", "nonMagneticHeadingMeans", "hasNonMagneticHeadingMeans", "independentFromHeadingMeans", "connectedToMainPower", "connectedToEmergencyPower"]
    for rid in ("IMO-086", "IMO26-012"):
        index["requirements"][rid] = heading_terms
        index.setdefault("termOwners", {})[rid] = {
            "hasNonMagneticHeadingMeans": "ship", "independentFromHeadingMeans": "nonMagneticHeadingMeans",
            "connectedToMainPower": "nonMagneticHeadingMeans", "connectedToEmergencyPower": "nonMagneticHeadingMeans",
        }
        index["dependencyContracts"][rid].update({
            "schemaVersion": 6, "status": "COMPLETE", "engineeringDecision": "R14_EXPLICIT_HEADING_MEANS_INVENTORY",
            "ownerClasses": ["ship", "nonMagneticHeadingMeans"], "operandTerms": [],
            "relationshipTerms": ["hasNonMagneticHeadingMeans", "independentFromHeadingMeans", "connectedToMainPower", "connectedToEmergencyPower"],
            "legacyIndexedTerms": ["nonMagneticHeadingMeansCount", "headingMeansIndependent", "mainPower", "emergencyPower"],
            "comparisonModel": "Require at least two distinct nonMagneticHeadingMeans nodes. Each means is connected to main power and emergency power and has an independentFromHeadingMeans relation to another distinct means owned by the same ship.",
            "modelPaths": [{"fromOwner": "ship", "via": "hasNonMagneticHeadingMeans", "toOwner": "nonMagneticHeadingMeans"}],
        })
    index["termCount"] = len(registry)
    write_json(OUT / "requirement_term_index.json", index)

    decisions = [{"canonicalLocalName": item["localName"], "action": "ADD_R14_SOURCE_CONFIRMED_MODEL_TERM",
                  "kind": item["kind"], "linkedRequirements": item["requirements"],
                  "rationale": "Minimal source-confirmed graph structure required by the final R3 stress-test adjudication."}
                 for item in additions]
    write_json(OUT / "registry/r14_change_decisions.json", decisions)

    errors = []
    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if len({item["localName"] for item in registry}) != len(registry): errors.append("duplicate localName")
    if len({item["iri"] for item in registry}) != len(registry): errors.append("duplicate IRI")
    bad = [item["localName"] for item in registry if not re.fullmatch(r"[a-z][A-Za-z0-9]*", item["localName"])]
    if bad: errors.append("invalid local names: " + ", ".join(bad))
    known = {item["localName"] for item in registry} | {
        str(subject)[len(BASE):] for subject in graph.subjects() if str(subject).startswith(BASE)
    }
    missing = sorted({name for names in index["requirements"].values() for name in names} - known)
    if missing: errors.append("indexed terms absent: " + ", ".join(missing))
    report = {"status": "PASS" if not errors else "FAIL", "developmentId": DEV_ID, "registryTerms": len(registry),
              "addedTerms": len(additions), "requirements": 313, "confirmationQueue": 2, "errors": errors}
    write_json(OUT / "validation/validation_report.json", report)
    if errors: raise RuntimeError("; ".join(errors))

    bound = {
        "registry/term_registry.json": sha256(OUT / "registry/term_registry.json"),
        "ontology/nltl_benchmark_vocabulary.ttl": sha256(OUT / "ontology/nltl_benchmark_vocabulary.ttl"),
        "context/nltl_benchmark_context.jsonld": sha256(OUT / "context/nltl_benchmark_context.jsonld"),
        "evidence/stage1_approved.json": sha256(OUT / "evidence/stage1_approved.json"),
    }
    write_json(OUT / "development_binding.json", {
        "lockId": DEV_ID, "status": "DEVELOPMENT_BINDING_NOT_EVALUATION_LOCK", "workbook": "R3 source workbook unchanged",
        "workbookSha256": "", "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {"requirement_term_index.json": sha256(OUT / "requirement_term_index.json")},
        "warning": "R14 is limited to two source-confirmed R3 stress-test gaps and awaits two-case confirmation.",
    })
    (OUT / "README.md").write_text("# R14 final stress-gap closure\n\nMinimal development revision for source-confirmed gaps I2-005 and IMO-086 (also applied to equivalent IMO26-012).\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "development_id": DEV_ID, "registry_terms": len(registry), "added_terms": len(additions), "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
