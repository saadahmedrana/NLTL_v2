from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

from rdflib import Graph, Literal, OWL, RDF, RDFS, URIRef

import build_dev_r9_foundation as r9


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R12_FINAL_GAP_CLOSURE"
OUT = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R13_APPLICABILITY_MATRIX_CLOSURE"
BATCH = MVP / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190"
RUNS = MVP / "SHACL_GENERATION_PIPELINE/outputs/development_r12/runs"
BASE = r9.BASE
XSD = "http://www.w3.org/2001/XMLSchema#"
DEV_ID = "VOCAB-DEV-2026-08-14-R13-APPLICABILITY-MATRIX-CLOSURE"
VERSION = "2.13.0-dev-applicability-matrix-closure"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cls(parent="benchmarkEntity", module="operations", requirements=()):
    return {"kind": "Class", "range": parent, "module": module, "requirements": list(requirements)}


def obj(domain, range_, module="operations", requirements=()):
    return {"kind": "ObjectProperty", "domain": domain, "range": range_, "module": module, "requirements": list(requirements)}


def lit(domain, datatype="boolean", module="regulation", requirements=(), aliases=()):
    return {"kind": "DatatypeProperty", "domain": domain, "range": XSD + datatype, "datatype": "xsd:" + datatype, "module": module, "requirements": list(requirements), "aliases": list(aliases)}


def ind(parent, module="operations", requirements=(), aliases=()):
    return {"kind": "NamedIndividual", "range": parent, "module": module, "requirements": list(requirements), "aliases": list(aliases)}


SPECS = {
    "polarClassRequirementsApplicable": lit("ship", requirements=("I2-046",), aliases=("Polar Class applicability status",)),
    "iceFreeIceCondition": ind("iceConditionValue", requirements=("IMO-102",), aliases=("Ice free",)),
    "otherWatersIceCondition": ind("iceConditionValue", requirements=("IMO-102",), aliases=("Other waters",)),
    "polarTrainingShipTypeValue": cls("benchmarkEntity", requirements=("IMO-102",)),
    "polarTrainingShipTypeClassification": obj("ship", "polarTrainingShipTypeValue", requirements=("IMO-102",)),
    "tankerPolarTrainingShipType": ind("polarTrainingShipTypeValue", requirements=("IMO-102",), aliases=("Tankers",)),
    "passengerShipPolarTrainingShipType": ind("polarTrainingShipTypeValue", requirements=("IMO-102",), aliases=("Passenger ships",)),
    "otherShipPolarTrainingType": ind("polarTrainingShipTypeValue", requirements=("IMO-102",), aliases=("Other",)),
    "polarTrainingCrewRoleValue": cls("benchmarkEntity", requirements=("IMO-102",)),
    "polarTrainingCrewRoleClassification": obj("crewMember", "polarTrainingCrewRoleValue", requirements=("IMO-102",)),
    "masterPolarTrainingRole": ind("polarTrainingCrewRoleValue", requirements=("IMO-102",), aliases=("master",)),
    "chiefMatePolarTrainingRole": ind("polarTrainingCrewRoleValue", requirements=("IMO-102",), aliases=("chief mate",)),
    "officerInChargeOfNavigationalWatchPolarTrainingRole": ind("polarTrainingCrewRoleValue", requirements=("IMO-102",), aliases=("officer in charge of a navigational watch", "OICNW")),
}


TERM_LINKS = {
    "I2-046": ["polarClassRequirementsApplicable"],
    "IMO-102": [
        "iceFreeIceCondition", "openWaterIceCondition", "otherWatersIceCondition",
        "polarTrainingShipTypeValue", "polarTrainingShipTypeClassification",
        "tankerPolarTrainingShipType", "passengerShipPolarTrainingShipType", "otherShipPolarTrainingType",
        "polarTrainingCrewRoleValue", "polarTrainingCrewRoleClassification",
        "masterPolarTrainingRole", "chiefMatePolarTrainingRole", "officerInChargeOfNavigationalWatchPolarTrainingRole",
    ],
}


CONFIRMATION = ["I2-046", "IMO-102"]
GENERATOR_ONLY = ["I2-015", "I2-022", "I2-030", "I2-034", "TRF-114"]


def latest_r12_results():
    records = []
    for directory in sorted(RUNS.glob("RUN-*")):
        path = directory / "events.jsonl"
        if not path.exists():
            continue
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        finish = next((event for event in reversed(events) if event.get("event_type") == "run_finished"), {})
        if finish:
            records.append({
                "requirement_id": finish.get("requirement_id"),
                "status": finish.get("status"),
                "accepted": bool(finish.get("accepted")),
                "attempts": finish.get("attempts"),
                "final_feedback": finish.get("final_feedback", ""),
                "run_directory": str(directory.relative_to(MVP)),
            })
    return records


def domains(graph: Graph, name: str) -> list[str]:
    return [str(value)[len(BASE):] for value in graph.objects(URIRef(BASE + name), RDFS.domain) if str(value).startswith(BASE)]


def finalize_binding() -> None:
    tracker = BATCH / "r13_engineering_change_tracker.xlsx"
    if not tracker.exists():
        raise FileNotFoundError(tracker)
    binding = read_json(OUT / "development_binding.json")
    binding["workbookSha256"] = sha256(tracker)
    binding["boundMachineReadableArtifacts"] = {
        "registry/term_registry.json": sha256(OUT / "registry/term_registry.json"),
        "ontology/nltl_benchmark_vocabulary.ttl": sha256(OUT / "ontology/nltl_benchmark_vocabulary.ttl"),
        "context/nltl_benchmark_context.jsonld": sha256(OUT / "context/nltl_benchmark_context.jsonld"),
        "evidence/stage1_approved.json": sha256(OUT / "evidence/stage1_approved.json"),
    }
    binding["boundRequirementIndex"] = {"requirement_term_index.json": sha256(OUT / "requirement_term_index.json")}
    write_json(OUT / "development_binding.json", binding)
    print(json.dumps({"status": "PASS", "binding": str(OUT / "development_binding.json")}, indent=2))


def main() -> None:
    if OUT.exists():
        validation = OUT / "validation/validation_report.json"
        binding = OUT / "development_binding.json"
        completed = validation.exists() and binding.exists() and read_json(validation).get("status") == "PASS" and read_json(binding).get("lockId") == DEV_ID
        if completed:
            raise FileExistsError(f"Refusing to overwrite completed R13 directory: {OUT}")
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)

    evidence_payload = read_json(OUT / "evidence/stage1_approved.json")
    evidence = {item["id"]: item for item in evidence_payload["requirements"]}
    registry = read_json(OUT / "registry/term_registry.json")
    existing = {item["localName"] for item in registry}
    additions = [
        r9.registry_record(name, spec, f"VOC-DEV-R13-{number:04d}", evidence)
        for number, (name, spec) in enumerate(sorted(SPECS.items()), 1)
        if name not in existing
    ]
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
        context["@context"][item["localName"]] = ({"@id": "nltl:" + item["localName"], "@type": "@id"} if item["kind"] in {"ObjectProperty", "QuantityProperty"} else "nltl:" + item["localName"])
    write_json(OUT / "context/nltl_benchmark_context.jsonld", context)

    index = read_json(OUT / "requirement_term_index.json")
    index["sourceLockId"] = DEV_ID
    index["version"] = "2.13.0-dev-contract-schema-v5-applicability-matrix"
    for rid, names in TERM_LINKS.items():
        index["requirements"][rid] = sorted(set(index["requirements"].get(rid, [])) | set(names))
    # Controlled selectors supersede unsafe free-text matrix selectors.
    index["requirements"]["IMO-102"] = [name for name in index["requirements"]["IMO-102"] if name not in {"iceCondition", "shipType", "crewRole", "requiredPolarTrainingLevel"}]

    by_name = {item["localName"]: item for item in registry}
    owners = index.setdefault("termOwners", {})
    inferred = 0
    for rid, names in index["requirements"].items():
        requirement_owners = owners.setdefault(rid, {})
        for name in names:
            item = by_name.get(name, {})
            if item.get("kind") not in {"ObjectProperty", "DatatypeProperty", "QuantityProperty"}:
                continue
            term_domains = [value for value in domains(graph, name) if value != "benchmarkEntity"]
            if name not in requirement_owners and len(set(term_domains)) == 1:
                requirement_owners[name] = term_domains[0]
                inferred += 1
    for name in ("iceCondition", "shipType", "crewRole", "requiredPolarTrainingLevel"):
        owners["IMO-102"].pop(name, None)

    i2 = index["dependencyContracts"]["I2-046"]
    i2.update({
        "schemaVersion": 5,
        "status": "COMPLETE",
        "engineeringDecision": "R13_EXPLICIT_APPLICABILITY_SELECTION",
        "applicabilityTerms": ["polarClassRequirementsApplicable", "polarClass"],
        "operandTerms": ["internalStructureCorrosionAbrasionAddition"],
        "resultTerms": ["internalStructureCorrosionAbrasionAddition"],
        "relationshipTerms": ["hasInternalIceStrengthenedStructure", "polarClass"],
        "controlledValueTerms": [],
        "comparisonModel": "Require exactly one polarClassRequirementsApplicable boolean. If true, require valid polarClass evidence and constrain every linked internalIceStrengthenedStructure to have one QuantityValue internalStructureCorrosionAbrasionAddition with decimal numericValue >= 1.0 and exactly one unit:MilliM. If false, the I2.11.3 obligation is non-applicable. The universal rule does not require a structure instance.",
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasInternalIceStrengthenedStructure", "toOwner": "internalIceStrengthenedStructure"},
        ],
    })

    imo = index["dependencyContracts"]["IMO-102"]
    imo.update({
        "schemaVersion": 5,
        "status": "COMPLETE",
        "engineeringDecision": "R13_CONTROLLED_POLAR_TRAINING_MATRIX",
        "applicabilityTerms": ["iceConditionClassification", "polarTrainingShipTypeClassification", "polarTrainingCrewRoleClassification"],
        "operandTerms": ["requiredTrainingLevel", "trainingRecordLevel", "stcwQualificationValid"],
        "resultTerms": [],
        "relationshipTerms": ["hasCrewMemberInventory", "hasCrewTrainingRecord", "hasPolarTrainingRecord", "iceConditionClassification", "polarTrainingShipTypeClassification", "polarTrainingCrewRoleClassification", "requiredTrainingLevel", "trainingRecordLevel"],
        "controlledValueTerms": [
            "iceFreeIceCondition", "openWaterIceCondition", "otherWatersIceCondition",
            "tankerPolarTrainingShipType", "passengerShipPolarTrainingShipType", "otherShipPolarTrainingType",
            "masterPolarTrainingRole", "chiefMatePolarTrainingRole", "officerInChargeOfNavigationalWatchPolarTrainingRole",
            "basicPolarTrainingLevel", "advancedPolarTrainingLevel", "polarTrainingNotApplicable",
        ],
        "comparisonModel": "Use the controlled 12.3.1 matrix selectors. Each represented crew member must have exactly one controlled role and the ship exactly one controlled ice condition and ship type. The linked training record requiredTrainingLevel must equal trainingRecordLevel and stcwQualificationValid must be true whenever the matrix requires Basic or Advanced training. For an Ice-free or other not-applicable matrix cell, requiredTrainingLevel is polarTrainingNotApplicable and no matching STCW training record is required solely by 12.3.1.",
        "tableModel": "MSC.385(94) 12.3.1: Ice free -> Not applicable for Tankers, Passenger ships and Other. Open waters -> Basic for master/chief mate/OICNW on Tankers and Passenger ships; Not applicable for Other. Other waters -> Advanced for master/chief mate and Basic for OICNW for all ship groups.",
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasCrewMemberInventory", "toOwner": "crewMember"},
            {"fromOwner": "crewMember", "via": "hasCrewTrainingRecord", "toOwner": "polarTrainingRecord"},
        ],
    })
    index["termCount"] = len(registry)
    write_json(OUT / "requirement_term_index.json", index)

    results = latest_r12_results()
    records = []
    for item in results:
        rid = item["requirement_id"]
        if item["accepted"]:
            classification, queue = "R12_ACCEPTED", "NONE"
        elif rid in CONFIRMATION:
            classification, queue = "R13_VOCABULARY_GAP_CLOSED", "CONFIRMATION"
        else:
            classification, queue = "GENERATOR_ONLY_NO_R13_TERM", "HELD"
        records.append({**item, "classification": classification, "r13_terms": TERM_LINKS.get(rid, []), "queue": queue})
    analysis = {
        "analysis_id": "R13-R12-APPLICABILITY-MATRIX-CLOSURE-V1",
        "r12_cases": len(results),
        "r12_accepted": sum(1 for item in results if item["accepted"]),
        "r12_failures": sum(1 for item in results if not item["accepted"]),
        "confirmation_count": len(CONFIRMATION),
        "generator_only_held_count": len(GENERATOR_ONLY),
        "records": records,
    }
    write_json(BATCH / "r13_failure_analysis.json", analysis)
    write_json(BATCH / "generation_queue_r13_confirmation.json", {
        "queue_id": "DEV-R13-FINAL-VOCABULARY-CONFIRMATION-ONE-RUN",
        "description": "Confirm only the two R12 failures with genuine vocabulary/applicability matrix gaps.",
        "development_vocabulary_id": DEV_ID,
        "repetitions": 1,
        "requirements": CONFIRMATION,
    })
    write_json(BATCH / "generation_queue_r13_generator_only_held.json", {
        "queue_id": "DEV-R13-GENERATOR-ONLY-HELD",
        "description": "Do not use for vocabulary completeness decisions; these five R12 failures had sufficient terms and reflect generation logic only.",
        "development_vocabulary_id": DEV_ID,
        "repetitions": 1,
        "requirements": GENERATOR_ONLY,
    })

    decisions = [{
        "canonicalLocalName": item["localName"],
        "action": "ADD_R13_APPLICABILITY_OR_MATRIX_TERM",
        "kind": item["kind"],
        "domain": SPECS[item["localName"]].get("domain", ""),
        "range": item["parentOrRange"],
        "linkedRequirements": item["requirements"],
        "rationale": "Explicit applicability or exact MSC.385(94) 12.3.1 matrix selector needed to prevent missing evidence from silently establishing non-applicability.",
    } for item in additions]
    write_json(OUT / "registry/r13_change_decisions.json", decisions)

    errors = []
    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if len({item["localName"] for item in registry}) != len(registry):
        errors.append("duplicate localName")
    if len({item["iri"] for item in registry}) != len(registry):
        errors.append("duplicate IRI")
    bad = [item["localName"] for item in registry if not re.fullmatch(r"[a-z][A-Za-z0-9]*", item["localName"])]
    if bad:
        errors.append("invalid local names: " + ", ".join(bad))
    indexed = {name for names in index["requirements"].values() for name in names}
    known = {item["localName"] for item in registry} | {str(subject)[len(BASE):] for subject in graph.subjects() if str(subject).startswith(BASE)}
    missing = sorted(indexed - known)
    if missing:
        errors.append("indexed terms absent: " + ", ".join(missing))
    report = {
        "status": "PASS" if not errors else "FAIL",
        "developmentId": DEV_ID,
        "registryTerms": len(registry),
        "addedTerms": len(additions),
        "requirements": 313,
        "confirmationQueue": len(CONFIRMATION),
        "generatorOnlyHeld": len(GENERATOR_ONLY),
        "ownerAssignmentsInferred": inferred,
        "errors": errors,
    }
    write_json(OUT / "validation/validation_report.json", report)
    if errors:
        raise RuntimeError("; ".join(errors))

    tracker = BATCH / "r13_engineering_change_tracker.xlsx"
    write_json(OUT / "development_binding.json", {
        "lockId": DEV_ID,
        "status": "DEVELOPMENT_BINDING_NOT_EVALUATION_LOCK",
        "workbook": tracker.name,
        "workbookSha256": "PENDING_TRACKER_BUILD",
        "boundMachineReadableArtifacts": {},
        "boundRequirementIndex": {},
        "warning": "R13 is a development binding pending its two-case confirmation.",
    })
    (OUT / "README.md").write_text(
        f"# R13 applicability and training-matrix closure\n\nIdentifier: `{DEV_ID}`. R13 preserves R12 and closes only the two genuine vocabulary gaps found by its confirmation run. Five generator-only failures are explicitly held outside vocabulary completeness decisions.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "development_id": DEV_ID, "registry_terms": len(registry), "added_terms": len(additions), "confirmation": len(CONFIRMATION), "generator_only_held": len(GENERATOR_ONLY), "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize-binding", action="store_true")
    args = parser.parse_args()
    finalize_binding() if args.finalize_binding else main()
