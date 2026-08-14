from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, OWL, RDF, RDFS, URIRef

import build_dev_r9_foundation as r9


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R10_GRAPH_COMPLETION"
OUT = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R11_FAILURE_CLOSURE"
BATCH = MVP / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190"
RUNS = MVP / "SHACL_GENERATION_PIPELINE/outputs/development_r10/runs"
BASE = r9.BASE
UNIT = r9.UNIT
QV = r9.QUDT_QUANTITY_VALUE
XSD = "http://www.w3.org/2001/XMLSchema#"
DEV_ID = "VOCAB-DEV-2026-08-14-R11-FAILURE-CLOSURE"
VERSION = "2.11.0-dev-failure-closure"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cls(parent="benchmarkEntity", module="regulation", requirements=()):
    return {"kind": "Class", "range": parent, "module": module, "requirements": list(requirements)}


def obj(domain, range_, module="regulation", requirements=()):
    return {"kind": "ObjectProperty", "domain": domain, "range": range_, "module": module, "requirements": list(requirements)}


def lit(domain, datatype="boolean", module="regulation", requirements=(), aliases=()):
    return {"kind": "DatatypeProperty", "domain": domain, "range": XSD + datatype, "datatype": "xsd:" + datatype, "module": module, "requirements": list(requirements), "aliases": list(aliases)}


def qty(domain, unit, symbol, quantity_kind, module="hull", requirements=(), aliases=()):
    return {"kind": "QuantityProperty", "domain": domain, "range": QV, "unit": UNIT + unit if unit else "", "unitSymbol": symbol, "quantityKind": quantity_kind, "module": module, "requirements": list(requirements), "aliases": list(aliases)}


def ind(parent, module="regulation", requirements=()):
    return {"kind": "NamedIndividual", "range": parent, "module": module, "requirements": list(requirements)}


SPECS = {
    # IACS formula operands and case pairing exposed by R10.
    "displacementFactorThreshold": qty("ship", "M", "m", "Length", "hull", ("I2-017",), ("CF_DIS",)),
    "flatBarStructuralSection": ind("structuralSectionTypeValue", "hull", ("I2-040",)),
    "bowSubregionCalculatedForce": qty("bowSubregionCalculationCase", "MegaN", "MN", "Force", "hull", ("I2-014",)),
    "bowSubregionCalculatedLineLoad": qty("bowSubregionCalculationCase", "MegaN-M-PER-M2", "MN/m", "Force per length", "hull", ("I2-014",)),
    "bowSubregionCalculatedPressure": qty("bowSubregionCalculationCase", "MegaPA", "MPa", "Pressure", "hull", ("I2-014",)),
    "hasFailureClassFactorLookupCase": obj("bowSubregionCalculationCase", "tableLookupCase", "hull", ("I2-015",)),
    "hasPlating": obj("ship", "plating", "hull", ("I2-022", "I2-023")),
    "platingSupportedByStructuralMember": obj("plating", "structuralMember", "hull", ("I2-022", "I2-023")),
    "hasStructuralMemberLoadCase": obj("structuralMember", "loadCase", "hull", ("I2-031", "I2-034")),
    "transverseFrameOrientation": lit("structuralMember", requirements=("I2-031",)),
    "longitudinalFrameOrientation": lit("structuralMember", requirements=("I2-034",)),
    "interpolationPointCoordinate": qty("interpolationPoint", "UNITLESS", "1", "Dimensionless", "hull", ("I2-030", "I2-052", "I2-054")),
    "interpolationPointResult": qty("interpolationPoint", "", "", "Context-dependent quantity", "hull", ("I2-030", "I2-052", "I2-054")),
    "hullGirderBendingMomentCalculationCase": cls("calculationCase", "hull", ("I2-054",)),
    "hasHullGirderBendingMomentCalculationCase": obj("ship", "hullGirderBendingMomentCalculationCase", "hull", ("I2-054",)),
    "caseHullGirderLongitudinalPositionFromAft": qty("hullGirderBendingMomentCalculationCase", "M", "m", "Length", "hull", ("I2-054",)),
    "caseBendingMomentDistributionFactor": qty("hullGirderBendingMomentCalculationCase", "UNITLESS", "1", "Dimensionless", "hull", ("I2-054",), ("C_m",)),
    "caseDesignVerticalIceBendingMoment": qty("hullGirderBendingMomentCalculationCase", "MegaN-M", "MN m", "Torque", "hull", ("I2-054",), ("M_I",)),
    "minorPermanentDeformationAssessmentSatisfied": lit("calculationCase", requirements=("I2-065",)),
    # Document and per-person evidence paths.
    "certificateScheduleDate": lit("certificateScheduleDateRecord", "date", "documents", ("IMO-017",)),
    "certificateScheduleDateType": lit("certificateScheduleDateRecord", "string", "documents", ("IMO-017",)),
    "polarCertificateSupplement": cls("documentRecord", "documents", ("IMO-017",)),
    "hasPolarCertificateSupplement": obj("ship", "polarCertificateSupplement", "documents", ("IMO-017",)),
    "hasRequiredEquipmentRecords": obj("polarCertificateSupplement", "requiredEquipmentRecords", "documents", ("IMO-017",)),
    "personalSurvivalEquipmentInstructionCompleted": lit("passenger", requirements=("IMO-078",)),
    "personalAndGroupSurvivalEquipmentTrainingCompleted": lit("crewMember", requirements=("IMO-078",)),
    # TRAFICOM scope and assessment models.
    "fixedPitchPropellerReversalLoadIncluded": lit("designCondition", requirements=("TRF-069",), aliases=("FP reversal loads included",)),
    "factoredExtremeLoadOperabilityAssessment": cls("calculationCase", "machinery", ("TRF-118",)),
    "hasFactoredExtremeLoadOperabilityAssessment": obj("ship", "factoredExtremeLoadOperabilityAssessment", "machinery", ("TRF-118",)),
    "assessedThrusterComponent": obj("factoredExtremeLoadOperabilityAssessment", "shipComponent", "machinery", ("TRF-118",)),
    "assessedFactoredExtremeLoad": qty("factoredExtremeLoadOperabilityAssessment", "KiloN", "kN", "Force", "machinery", ("TRF-118",)),
    "assessmentOperabilityMaintained": lit("factoredExtremeLoadOperabilityAssessment", requirements=("TRF-118",)),
    "assessmentRepairRequired": lit("factoredExtremeLoadOperabilityAssessment", requirements=("TRF-118",)),
    "lookupInputQuantity": qty("tableLookupCase", "", "", "Context-dependent quantity", "regulation", ("TRF-085",)),
    "thrusterImpactCaseAppliesToBody": obj("thrusterIceImpactLoadCase", "thrusterBody", "machinery", ("TRF-114",)),
    "designConditionExpectedLoad": qty("designCondition", "KiloN", "kN", "Force", "machinery", ("TRF-070",)),
    "designConditionLocalStrengthCapacity": qty("designCondition", "KiloN", "kN", "Force", "machinery", ("TRF-070",)),
    "occasionalForceComponentStress": qty("shipComponent", "MegaPA", "MPa", "Pressure", "machinery", ("TRF-123",)),
    "occasionalForceCaseAssessedComponent": obj("occasionalForceLoadCase", "shipComponent", "machinery", ("TRF-123",)),
}


TERM_LINKS = {
    "I2-014": ["bowSubregionCalculatedForce", "bowSubregionCalculatedLineLoad", "bowSubregionCalculatedPressure"],
    "I2-015": ["hasFailureClassFactorLookupCase"],
    "I2-017": ["displacementFactorThreshold", "upperIceWaterlineDraughtDUI"],
    "I2-022": ["hasPlating", "platingSupportedByStructuralMember"],
    "I2-023": ["hasPlating", "platingSupportedByStructuralMember"],
    "I2-030": ["interpolationPointCoordinate", "interpolationPointResult"],
    "I2-031": ["hasStructuralMemberLoadCase", "transverseFrameOrientation"],
    "I2-034": ["hasStructuralMemberLoadCase", "longitudinalFrameOrientation"],
    "I2-040": ["flatBarStructuralSection"],
    "I2-052": ["interpolationPointCoordinate", "interpolationPointResult"],
    "I2-054": ["hullGirderBendingMomentCalculationCase", "hasHullGirderBendingMomentCalculationCase", "caseHullGirderLongitudinalPositionFromAft", "caseBendingMomentDistributionFactor", "caseDesignVerticalIceBendingMoment", "interpolationPointCoordinate", "interpolationPointResult"],
    "I2-065": ["minorPermanentDeformationAssessmentSatisfied"],
    "IMO-017": ["certificateScheduleDate", "certificateScheduleDateType", "polarCertificateSupplement", "hasPolarCertificateSupplement", "hasRequiredEquipmentRecords"],
    "IMO-078": ["personalSurvivalEquipmentInstructionCompleted", "personalAndGroupSurvivalEquipmentTrainingCompleted"],
    "TRF-069": ["fixedPitchPropellerReversalLoadIncluded"],
    "TRF-070": ["designConditionExpectedLoad", "designConditionLocalStrengthCapacity"],
    "TRF-085": ["lookupInputQuantity", "lookupResultQuantity"],
    "TRF-114": ["thrusterImpactCaseAppliesToBody"],
    "TRF-118": ["factoredExtremeLoadOperabilityAssessment", "hasFactoredExtremeLoadOperabilityAssessment", "assessedThrusterComponent", "assessedFactoredExtremeLoad", "assessmentOperabilityMaintained", "assessmentRepairRequired"],
    "TRF-123": ["occasionalForceComponentStress", "occasionalForceCaseAssessedComponent"],
}


TIER1 = [
    "I2-014", "I2-015", "I2-017", "I2-019", "I2-022", "I2-030", "I2-031", "I2-032",
    "I2-034", "I2-040", "I2-046", "I2-052", "I2-054", "I2-065", "IMO-017", "IMO-078",
    "IMO-102", "IMO26-009", "TRF-069", "TRF-070", "TRF-082", "TRF-085", "TRF-114", "TRF-118", "TRF-123",
]


def r10_failures():
    records = []
    for directory in sorted(RUNS.glob("RUN-*")):
        path = directory / "events.jsonl"
        if not path.exists():
            continue
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        start = next((event for event in events if event.get("event_type") == "run_started"), {})
        finish = next((event for event in reversed(events) if event.get("event_type") == "run_finished"), {})
        if finish.get("accepted"):
            continue
        records.append({
            "requirement_id": finish.get("requirement_id"),
            "status": finish.get("status"),
            "attempts": finish.get("attempts"),
            "final_feedback": finish.get("final_feedback"),
            "run_directory": str(directory.relative_to(MVP)),
            "started_utc": start.get("timestamp_utc", ""),
        })
    return records


def ontology_domains(graph: Graph, name: str) -> list[str]:
    subject = URIRef(BASE + name)
    return [str(value)[len(BASE):] for value in graph.objects(subject, RDFS.domain) if str(value).startswith(BASE)]


def finalize_binding() -> None:
    tracker = BATCH / "r11_engineering_change_tracker.xlsx"
    if not tracker.exists():
        raise FileNotFoundError(tracker)
    binding = read_json(OUT / "development_binding.json")
    binding["workbookSha256"] = sha256(tracker)
    binding["boundMachineReadableArtifacts"] = {
        "registry/term_registry.json": sha256(OUT / "registry/term_registry.json"),
        "ontology/nltl_benchmark_vocabulary.ttl": sha256(OUT / "ontology/nltl_benchmark_vocabulary.ttl"),
        "evidence/stage1_approved.json": sha256(OUT / "evidence/stage1_approved.json"),
    }
    binding["boundRequirementIndex"] = {"requirement_term_index.json": sha256(OUT / "requirement_term_index.json")}
    write_json(OUT / "development_binding.json", binding)
    print(json.dumps({"status": "PASS", "binding": str(OUT / "development_binding.json")}, indent=2))


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)
    evidence_payload = read_json(OUT / "evidence/stage1_approved.json")
    evidence = {item["id"]: item for item in evidence_payload["requirements"]}
    registry = read_json(OUT / "registry/term_registry.json")
    existing = {item["localName"] for item in registry}
    additions = [
        r9.registry_record(name, spec, f"VOC-DEV-R11-{number:04d}", evidence)
        for number, (name, spec) in enumerate(sorted(SPECS.items()), 1)
        if name not in existing
    ]
    registry = sorted(registry + additions, key=lambda item: item["localName"])
    write_json(OUT / "registry/term_registry.json", registry)
    fields = list(csv.DictReader((SOURCE / "registry/term_registry.csv").open(encoding="utf-8")).fieldnames or [])
    with (OUT / "registry/term_registry.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
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
    index["version"] = "2.11.0-dev-contract-schema-v3-owner-domain"
    for rid, names in TERM_LINKS.items():
        index["requirements"][rid] = sorted(set(index["requirements"].get(rid, [])) | set(names))

    # Populate authoritative owners for every indexed property with one
    # specific ontology domain. Existing explicit assignments remain primary.
    term_owners = index.setdefault("termOwners", {})
    by_name = {item["localName"]: item for item in registry}
    inferred_count = 0
    for rid, names in index["requirements"].items():
        owners = term_owners.setdefault(rid, {})
        for name in names:
            item = by_name.get(name, {})
            if item.get("kind") not in {"ObjectProperty", "DatatypeProperty", "QuantityProperty"}:
                continue
            domains = [value for value in ontology_domains(graph, name) if value != "benchmarkEntity"]
            if name not in owners and len(set(domains)) == 1:
                owners[name] = domains[0]
                inferred_count += 1

    # Remove contradictory R10 role heuristics and declare the exact new model.
    for rid, names in TERM_LINKS.items():
        contract = index["dependencyContracts"][rid]
        contract["schemaVersion"] = 3
        contract["status"] = "COMPLETE"
        contract["engineeringDecision"] = "R11_OWNER_DOMAIN_AND_MISSING_MODEL_CLOSURE"
        linked = index["requirements"][rid]
        contract["relationshipTerms"] = sorted(name for name in linked if by_name.get(name, {}).get("kind") == "ObjectProperty")
        contract["controlledValueTerms"] = sorted(name for name in linked if by_name.get(name, {}).get("kind") == "NamedIndividual")
        contract["modelPaths"] = [
            {"fromOwner": term_owners[rid][name], "via": name, "toOwner": str(by_name[name]["parentOrRange"])[len(BASE):]}
            for name in contract["relationshipTerms"]
            if name in term_owners[rid] and str(by_name[name].get("parentOrRange", "")).startswith(BASE)
        ]
    index["dependencyContracts"]["I2-017"].update({
        "applicabilityTerms": [],
        "operandTerms": ["crushingFailureClassFactor", "loadPatchDimensionClassFactor", "upperIceWaterlineDraughtDUI", "displacementFactorThreshold"],
        "resultTerms": ["shipDisplacementFactor", "nonBowIceForce", "nonBowIceLineLoad"],
        "formulaExpression": "DF=D_UI^0.64 when D_UI<=CF_DIS, otherwise DF=CF_DIS^0.64+0.10*(D_UI-CF_DIS); F_NonBow=0.36*C_FC*DF; Q_NonBow=0.639*F_NonBow^0.61*C_FD",
        "requiredModelFields": ["comparisonModel", "formulaExpression"],
    })
    index["dependencyContracts"]["I2-040"]["controlledValueTerms"] = ["flatBarStructuralSection", "bulbSection", "teeSection", "angleSection"]
    index["dependencyContracts"]["I2-054"].update({
        "operandTerms": ["caseHullGirderLongitudinalPositionFromAft", "caseBendingMomentDistributionFactor", "upperIceWaterlineLengthLUI", "stemAngle", "designVerticalIceForceAtBow"],
        "resultTerms": ["caseDesignVerticalIceBendingMoment"],
        "formulaExpression": "For each linked case M_I=0.1*C_m*L_UI*sin(gamma_stem)^(-0.2)*F_IB; C_m follows the stated points and linear interpolation.",
        "requiredModelFields": ["comparisonModel", "formulaExpression"],
    })
    index["dependencyContracts"]["I2-065"].update({
        "resultTerms": ["minorPermanentDeformationAssessmentSatisfied"],
        "evidenceTerms": ["nonlinearAnalysisAcceptanceEvidence"],
        "comparisonModel": evidence["I2-065"]["normalizedRequirement"] + " No numerical minor-deformation ratio is supplied; require the explicit assessment result and evidence, not an invented threshold.",
    })
    index["dependencyContracts"]["IMO-078"].update({
        "resultTerms": ["personalSurvivalEquipmentInstructionCompleted", "personalAndGroupSurvivalEquipmentTrainingCompleted"],
        "comparisonModel": "Every linked passenger must have personalSurvivalEquipmentInstructionCompleted=true and every linked crewMember must have personalAndGroupSurvivalEquipmentTrainingCompleted=true.",
    })
    index["dependencyContracts"]["TRF-069"]["evidenceTerms"] = ["normalServiceLifePropellerIceLoadCondition", "fixedPitchPropellerReversalLoadIncluded", "stoppedPropellerDraggingOutsideLoadModel", "radialIceEntryOutsideLoadModel"]
    index["dependencyContracts"]["TRF-118"].update({
        "operandTerms": ["thrusterExtremeLoad", "yieldSafetyFactor", "nominalVonMisesStress", "localStressConcentration", "componentMaterialYieldStrength"],
        "resultTerms": ["assessedFactoredExtremeLoad", "assessmentOperabilityMaintained", "assessmentRepairRequired"],
        "comparisonModel": evidence["TRF-118"]["normalizedRequirement"] + " The assessment node pairs each component, the explicit factored load result, operability=true, and repairRequired=false.",
    })
    index["dependencyContracts"]["IMO26-009"]["operandTerms"] = ["antennaIceAccumulationPreventionPresent"]
    index["dependencyContracts"]["TRF-082"]["evidenceTerms"] = ["tableLookupApplied", "lookupSelectionEvidence"]
    index["termCount"] = len(registry)
    write_json(OUT / "requirement_term_index.json", index)

    failures = r10_failures()
    failure_by_id = {item["requirement_id"]: item for item in failures}
    classifications = []
    for item in failures:
        rid = item["requirement_id"]
        changes = []
        if rid in TERM_LINKS: changes.append("NEW_CANONICAL_TERM_OR_PATH")
        if rid in TIER1: changes.append("OWNER_OR_CONTRACT_CONTEXT_REPAIR")
        if not changes: changes.append("GENERATOR_OR_FORMULA_REPAIR_ONLY")
        classifications.append({**item, "classification": changes, "r11_terms": TERM_LINKS.get(rid, []), "confirmation_tier": 1 if rid in TIER1 else 2})
    analysis = {
        "analysis_id": "R11-R10-FAILURE-CLOSURE-V1",
        "r10_runs": 62,
        "r10_failures": len(failures),
        "status_counts": dict(Counter(item["status"] for item in failures)),
        "owner_assignments_inferred": inferred_count,
        "tier1_count": len(TIER1),
        "tier2_count": len(failures) - len(TIER1),
        "records": classifications,
    }
    write_json(BATCH / "r11_failure_analysis.json", analysis)
    write_json(BATCH / "generation_queue_r11_tier1.json", {
        "queue_id": "DEV-R11-TIER1-SCHEMA-CLOSURE-ONE-RUN",
        "description": "One confirmation run only for R10 failures whose owner metadata, dependency contract, or canonical graph model changed in R11.",
        "development_vocabulary_id": DEV_ID,
        "repetitions": 1,
        "requirements": TIER1,
    })
    tier2 = [item["requirement_id"] for item in failures if item["requirement_id"] not in TIER1]
    write_json(BATCH / "generation_queue_r11_tier2.json", {
        "queue_id": "DEV-R11-TIER2-GENERATOR-CONFIRMATION-ONE-RUN",
        "description": "Run only after Tier 1 review; these cases had sufficient vocabulary and mainly require generator/formula repair confirmation.",
        "development_vocabulary_id": DEV_ID,
        "repetitions": 1,
        "requirements": tier2,
    })

    decisions = [{
        "canonicalLocalName": item["localName"], "action": "ADD_R11_FAILURE_CLOSURE_TERM",
        "kind": item["kind"], "domain": SPECS[item["localName"]].get("domain", ""),
        "range": item["parentOrRange"], "linkedRequirements": item["requirements"],
        "rationale": "Source-grounded hidden input, owner-local result, relationship, controlled value, or evidence role required to encode the verified R10 obligation without inventing logic.",
    } for item in additions]
    write_json(OUT / "registry/r11_change_decisions.json", decisions)

    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    errors = []
    if len({item["localName"] for item in registry}) != len(registry): errors.append("duplicate localName")
    if len({item["iri"] for item in registry}) != len(registry): errors.append("duplicate IRI")
    bad = [item["localName"] for item in registry if not re.fullmatch(r"[a-z][A-Za-z0-9]*", item["localName"])]
    if bad: errors.append("invalid local names: " + ", ".join(bad))
    indexed = {name for names in index["requirements"].values() for name in names}
    known = {item["localName"] for item in registry} | {str(s)[len(BASE):] for s in graph.subjects() if str(s).startswith(BASE)}
    missing = sorted(indexed - known)
    if missing: errors.append("indexed terms absent: " + ", ".join(missing))
    report = {"status": "PASS" if not errors else "FAIL", "developmentId": DEV_ID, "registryTerms": len(registry), "addedTerms": len(additions), "requirements": 313, "tier1Queue": len(TIER1), "tier2Queue": len(tier2), "ownerAssignmentsInferred": inferred_count, "errors": errors}
    write_json(OUT / "validation/validation_report.json", report)
    if errors: raise RuntimeError("; ".join(errors))

    tracker = BATCH / "r11_engineering_change_tracker.xlsx"
    write_json(OUT / "development_binding.json", {
        "lockId": DEV_ID, "status": "DEVELOPMENT_BINDING_NOT_EVALUATION_LOCK",
        "workbook": tracker.name, "workbookSha256": "PENDING_TRACKER_BUILD",
        "boundMachineReadableArtifacts": {}, "boundRequirementIndex": {},
        "warning": "R11 is an engineering-development binding. Do not use confirmation outputs as final experiment data.",
    })
    (OUT / "README.md").write_text(
        f"# R11 failure-closure development vocabulary\n\nIdentifier: `{DEV_ID}`. R11 preserves R10, repairs unsafe ship-default ownership, and closes source-grounded graph/model gaps exposed by the 62-case R10 run. It is not a final evaluation lock.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "development_id": DEV_ID, "registry_terms": len(registry), "added_terms": len(additions), "tier1": len(TIER1), "tier2": len(tier2), "owners_inferred": inferred_count, "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize-binding", action="store_true")
    args = parser.parse_args()
    finalize_binding() if args.finalize_binding else main()
