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
import build_dev_r11_failure_closure as r11


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R11_FAILURE_CLOSURE"
OUT = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R12_FINAL_GAP_CLOSURE"
BATCH = MVP / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190"
RUNS = MVP / "SHACL_GENERATION_PIPELINE/outputs/development_r11/runs"
BASE = r9.BASE
UNIT = r9.UNIT
QV = r9.QUDT_QUANTITY_VALUE
XSD = "http://www.w3.org/2001/XMLSchema#"
DEV_ID = "VOCAB-DEV-2026-08-14-R12-FINAL-GAP-CLOSURE"
VERSION = "2.12.0-dev-final-gap-closure"


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


def qty(domain, unit, symbol, quantity_kind, module="hull", requirements=(), aliases=()):
    return {"kind": "QuantityProperty", "domain": domain, "range": QV, "unit": UNIT + unit if unit else "", "unitSymbol": symbol, "quantityKind": quantity_kind, "module": module, "requirements": list(requirements), "aliases": list(aliases)}


def ind(parent, module="regulation", requirements=(), aliases=()):
    return {"kind": "NamedIndividual", "range": parent, "module": module, "requirements": list(requirements), "aliases": list(aliases)}


# Every coined name below is tied to exact wording in the cited requirement. No
# external equivalence is claimed. Controlled values replace unsafe free text.
SPECS = {
    "bowFormApplicabilityValue": cls("benchmarkEntity", "hull", ("I2-015",)),
    "bowFormApplicabilityClassification": obj("bowSubregionCalculationCase", "bowFormApplicabilityValue", "hull", ("I2-015",)),
    "i231vBowFormApplicability": ind("bowFormApplicabilityValue", "hull", ("I2-015",), ("bow forms defined in I2.3.1(v)",)),
    "platingHullAreaClassification": obj("plating", "hullAreaValue", "hull", ("I2-022",)),
    "bowIntermediateBottomHullArea": ind("hullAreaValue", "hull", ("I2-022", "I2-031"), ("BI_b", "BIb")),
    "midbodyBottomHullArea": ind("hullAreaValue", "hull", ("I2-022", "I2-031"), ("M_b", "Mb")),
    "sternBottomHullArea": ind("hullAreaValue", "hull", ("I2-022", "I2-031"), ("S_b", "Sb")),
    "localFrameSectionCalculationCase": cls("calculationCase", "hull", ("I2-030",)),
    "hasLocalFrameSectionCalculationCase": obj("structuralMember", "localFrameSectionCalculationCase", "hull", ("I2-030",)),
    "sectionCalculationCasePlating": obj("localFrameSectionCalculationCase", "plating", "hull", ("I2-030",)),
    "sectionCalculationCaseStructuralMember": obj("localFrameSectionCalculationCase", "structuralMember", "hull", ("I2-030",)),
    "bowSubregionCalculationEvidence": obj("bowSubregionCalculationCase", "evidenceArtifact", "hull", ("I2-014",)),
    "internalStructureCorrosionAbrasionAddition": qty("internalIceStrengthenedStructure", "MilliM", "mm", "Length", "hull", ("I2-046",), ("ts",)),
    "basicPolarTrainingLevel": ind("trainingLevelValue", "operations", ("IMO-102",), ("Basic training",)),
    "advancedPolarTrainingLevel": ind("trainingLevelValue", "operations", ("IMO-102",), ("Advanced training",)),
    "polarTrainingNotApplicable": ind("trainingLevelValue", "operations", ("IMO-102",), ("Not applicable",)),
    "designIceBlockTableReference": obj("thrusterIceImpactLoadCase", "tableReferenceValue", "regulation", ("TRF-114",)),
    "impactLoadCaseTableReference": obj("thrusterIceImpactLoadCase", "tableReferenceValue", "regulation", ("TRF-114",)),
    "traficomTable6Dash3Reference": ind("tableReferenceValue", "regulation", ("TRF-114",), ("Table 6-3",)),
    "traficomTable6Dash16Reference": ind("tableReferenceValue", "regulation", ("TRF-114",), ("Table 6-16",)),
    "contactGeometryValue": cls("benchmarkEntity", "machinery", ("TRF-114",)),
    "contactGeometryClassification": obj("thrusterIceImpactLoadCase", "contactGeometryValue", "machinery", ("TRF-114",)),
    "hemisphericalContactGeometry": ind("contactGeometryValue", "machinery", ("TRF-114",), ("hemispherical",)),
    "nonHemisphericalContactGeometry": ind("contactGeometryValue", "machinery", ("TRF-114",), ("differs from the shape of the hemisphere",)),
}


TERM_LINKS = {
    "I2-014": ["bowSubregionCalculationEvidence"],
    "I2-015": ["bowFormApplicabilityValue", "bowFormApplicabilityClassification", "i231vBowFormApplicability"],
    "I2-022": ["platingHullAreaClassification", "bowIntermediateBottomHullArea", "midbodyBottomHullArea", "sternBottomHullArea"],
    "I2-030": ["localFrameSectionCalculationCase", "hasLocalFrameSectionCalculationCase", "sectionCalculationCasePlating", "sectionCalculationCaseStructuralMember"],
    "I2-034": ["structuralLocation", "sideStructureLocation"],
    "I2-046": ["internalStructureCorrosionAbrasionAddition"],
    "IMO-102": ["basicPolarTrainingLevel", "advancedPolarTrainingLevel", "polarTrainingNotApplicable"],
    "TRF-114": ["designIceBlockTableReference", "impactLoadCaseTableReference", "traficomTable6Dash3Reference", "traficomTable6Dash16Reference", "contactGeometryValue", "contactGeometryClassification", "hemisphericalContactGeometry", "nonHemisphericalContactGeometry"],
}


SCHEMA_CONFIRMATION = ["I2-014", "I2-015", "I2-022", "I2-030", "I2-034", "I2-046", "IMO-102", "TRF-114"]
GENERATOR_CONTROL = ["I2-019", "I2-031", "I2-054", "TRF-070", "TRF-085"]


def r11_results():
    records = []
    for directory in sorted(RUNS.glob("RUN-*")):
        path = directory / "events.jsonl"
        if not path.exists():
            continue
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        finish = next((event for event in reversed(events) if event.get("event_type") == "run_finished"), {})
        if not finish:
            continue
        records.append({
            "requirement_id": finish.get("requirement_id"),
            "status": finish.get("status"),
            "accepted": bool(finish.get("accepted")),
            "attempts": finish.get("attempts"),
            "final_feedback": finish.get("final_feedback", ""),
            "run_directory": str(directory.relative_to(MVP)),
        })
    return records


def ontology_domains(graph: Graph, name: str) -> list[str]:
    subject = URIRef(BASE + name)
    return [str(value)[len(BASE):] for value in graph.objects(subject, RDFS.domain) if str(value).startswith(BASE)]


def finalize_binding() -> None:
    tracker = BATCH / "r12_engineering_change_tracker.xlsx"
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
        binding = OUT / "development_binding.json"
        validation = OUT / "validation/validation_report.json"
        completed = binding.exists() and read_json(binding).get("lockId") == DEV_ID and validation.exists() and read_json(validation).get("status") == "PASS"
        if completed:
            raise FileExistsError(f"Refusing to overwrite completed R12 directory: {OUT}")
        # A failed builder attempt may leave only its own incomplete R12 output.
        # It is safe to replace that isolated, unbound directory and no source.
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)
    evidence_payload = read_json(OUT / "evidence/stage1_approved.json")
    evidence = {item["id"]: item for item in evidence_payload["requirements"]}
    registry = read_json(OUT / "registry/term_registry.json")
    existing = {item["localName"] for item in registry}
    additions = [
        r9.registry_record(name, spec, f"VOC-DEV-R12-{number:04d}", evidence)
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
    index["version"] = "2.12.0-dev-contract-schema-v4-final-gap-closure"
    for rid, names in TERM_LINKS.items():
        index["requirements"][rid] = sorted(set(index["requirements"].get(rid, [])) | set(names))
    # Remove unsafe convenience strings once a controlled representation exists.
    index["requirements"]["I2-034"] = [name for name in index["requirements"]["I2-034"] if name != "sideStructureApplicability"]
    index["requirements"]["TRF-114"] = [name for name in index["requirements"]["TRF-114"] if name not in {"contactGeometry", "designIceBlock", "impactLoadCase"}]

    by_name = {item["localName"]: item for item in registry}
    term_owners = index.setdefault("termOwners", {})
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
    term_owners["I2-034"].pop("sideStructureApplicability", None)
    for name in ("contactGeometry", "designIceBlock", "impactLoadCase"):
        term_owners["TRF-114"].pop(name, None)

    def rebuild_contract(rid: str, *, applicability=(), operands=(), results=(), evidence_terms=(), controlled=(), formula="", comparison="", table=""):
        contract = index["dependencyContracts"][rid]
        names = index["requirements"][rid]
        contract.update({
            "schemaVersion": 4,
            "status": "COMPLETE",
            "engineeringDecision": "R12_SOURCE_GROUNDED_FINAL_GAP_CLOSURE",
            "applicabilityTerms": list(applicability),
            "operandTerms": list(operands),
            "resultTerms": list(results),
            "evidenceTerms": list(evidence_terms),
            "controlledValueTerms": list(controlled),
            "formulaExpression": formula,
            "comparisonModel": comparison or evidence[rid]["normalizedRequirement"],
            "tableModel": table,
            "relationshipTerms": sorted(name for name in names if by_name.get(name, {}).get("kind") == "ObjectProperty"),
        })
        contract["modelPaths"] = [
            {"fromOwner": term_owners[rid][name], "via": name, "toOwner": str(by_name[name]["parentOrRange"])[len(BASE):]}
            for name in contract["relationshipTerms"]
            if name in term_owners[rid] and str(by_name[name].get("parentOrRange", "")).startswith(BASE)
        ]

    rebuild_contract("I2-014",
        operands=("bowSubregionMidLengthPosition", "bowSubregionAspectRatio"),
        results=("bowSubregionCalculatedForce", "bowSubregionCalculatedLineLoad", "bowSubregionCalculatedPressure", "selectedMaximumBowForce", "selectedMaximumBowLineLoad", "selectedMaximumBowPressure"),
        evidence_terms=("bowSubregionCalculationEvidence",),
        comparison="Each of four equal-length bow subregions must carry midpoint calculation evidence and reported F, Q, P and AR values. Select the maxima of F, Q and P for downstream Pavg, b and w calculations. I2-014 does not itself supply arithmetic equations equating or deriving these quantities.")
    rebuild_contract("I2-015",
        applicability=("bowFormApplicabilityClassification", "i231vBowFormApplicability"),
        operands=("bowSubregionMidLengthPosition", "upperIceWaterlineLengthLUI", "bowSubregionWaterlineAngle", "betaIPrime", "flexuralFailureClassFactor", "crushingFailureClassFactor"),
        results=("bowShapeCoefficient",),
        controlled=("i231vBowFormApplicability",),
        formula="f_ai=min(f_ai1,f_ai2,f_ai3); f_ai1=(0.097-0.68*(x/L_UI-0.15)^2)*alpha_i/sqrt(beta_i_prime); f_ai2=1.2*C_FF/(sin(beta_i_prime)*C_FC*D_UI^0.64); f_ai3=0.60")
    rebuild_contract("I2-022",
        applicability=("platingHullAreaClassification", "bowIntermediateBottomHullArea", "midbodyBottomHullArea", "sternBottomHullArea", "framingAngleOmega"),
        operands=("frameSpacing", "selectedHullAreaFactor", "peakPressureFactor", "averageIcePressure", "yieldStrength", "loadPatchHeight"),
        results=("iceLoadRequiredNetPlateThickness",),
        controlled=("bowIntermediateBottomHullArea", "midbodyBottomHullArea", "sternBottomHullArea"),
        formula="t_net=500*s*sqrt((AF*PPF_p*P_avg)/sigma_y)/(1+s/(2*b)); applicable when Omega>=70 degrees, including BI_b, M_b and S_b.")
    rebuild_contract("I2-030",
        applicability=("framingAngleOmega",),
        operands=("netLocalFrameFlangeArea", "webHeight", "netWebThickness", "netAttachedShellPlateThickness", "frameSpacing", "localFrameFlangeCentreHeight", "webAngleToShellPlate", "webToFlangeCentreDistance", "interpolationPointCoordinate", "interpolationPointResult"),
        results=("plasticNeutralAxisHeight", "netEffectivePlasticSectionModulus"),
        formula="When A_fn exceeds the attached-plate-flange area, calculate z_na and Z_p using the equations in I2.5.8-I2.5.9. For 20<Omega<70 degrees use linear interpolation between linked endpoint results.")
    rebuild_contract("I2-034",
        applicability=("longitudinalFrameOrientation", "structuralLocation", "sideStructureLocation"),
        operands=("combinedShearAndBendingDemand", "midspanPlasticCollapseLoad", "plasticStrength"),
        controlled=("sideStructureLocation",),
        comparison="For each longitudinal local frame whose structuralLocation is sideStructureLocation, every represented load-case combined shear-and-bending demand must not exceed the member plastic strength/midspan plastic-collapse load. The clause is universal and does not require inventing a member or load case when none is represented.")
    rebuild_contract("I2-046",
        applicability=("polarClass",),
        operands=("internalStructureCorrosionAbrasionAddition",),
        results=("internalStructureCorrosionAbrasionAddition",),
        comparison="Every internalIceStrengthenedStructure linked from an applicable Polar Class ship must have internalStructureCorrosionAbrasionAddition >= 1.0 mm. This includes represented plated members adjacent to shell and stiffener webs/flanges; the universal clause does not require inventing a structure instance.")
    rebuild_contract("IMO-102",
        applicability=("iceConditionClassification", "shipType", "crewRole"),
        operands=("requiredTrainingLevel", "trainingRecordLevel", "stcwQualificationValid"),
        controlled=("basicPolarTrainingLevel", "advancedPolarTrainingLevel", "polarTrainingNotApplicable"),
        evidence_terms=("hasPolarTrainingRecord",),
        comparison="Derive one controlled required level from the exact 12.3.1 matrix. For each applicable crew member, the linked training record level must equal the derived required level and stcwQualificationValid must be true. Not-applicable matrix cells use polarTrainingNotApplicable.",
        table="MSC.385(94), chapter 12, clause 12.3.1 matrix: Ice free is not applicable; Open waters requires basic training for master, chief mate and OICNW on tankers/passenger ships and is not applicable to other ships; Other waters requires advanced for master/chief mate and basic for OICNW for all three ship groups.")
    rebuild_contract("TRF-114",
        applicability=("designIceBlockTableReference", "traficomTable6Dash3Reference", "impactLoadCaseTableReference", "traficomTable6Dash16Reference"),
        operands=("iceOperatingSpeed", "thrusterIceImpactLoad", "thrusterIceImpactDemand", "thrusterResistanceCapacity", "contactGeometryClassification", "equivalentImpactSphereRadius"),
        evidence_terms=("thrusterIceImpactLoadedAreaEvidence", "contactGeometryCorrespondenceEvidence"),
        controlled=("traficomTable6Dash3Reference", "traficomTable6Dash16Reference", "hemisphericalContactGeometry", "nonHemisphericalContactGeometry"),
        comparison="Each linked impact case must reference TRAFICOM Table 6-3 for the design ice block and Table 6-16 for its load case, apply to the thruster body, and classify contact geometry. Non-hemispherical geometry additionally requires an equivalent sphere radius and correspondence evidence.",
        table="TRAFICOM clause 6.6.5.2 explicitly cites Table 6-3 for the design ice block and Table 6-16 for impact load cases.")

    index["termCount"] = len(registry)
    write_json(OUT / "requirement_term_index.json", index)

    results = r11_results()
    records = []
    for item in results:
        rid = item["requirement_id"]
        if item["accepted"]:
            classification = "R11_ACCEPTED_NO_R12_ACTION"
            queue = "NONE"
        elif rid in SCHEMA_CONFIRMATION:
            classification = "VOCABULARY_OR_REQUIREMENT_MODEL_CLOSURE"
            queue = "SCHEMA_CONFIRMATION"
        else:
            classification = "GENERATOR_LOGIC_CONTROL_NO_NEW_VOCABULARY"
            queue = "GENERATOR_CONTROL"
        records.append({**item, "classification": classification, "r12_terms": TERM_LINKS.get(rid, []), "queue": queue})
    analysis = {
        "analysis_id": "R12-R11-FINAL-GAP-CLOSURE-V1",
        "r11_cases": len(results),
        "r11_accepted": sum(1 for item in results if item["accepted"]),
        "r11_failures": sum(1 for item in results if not item["accepted"]),
        "status_counts": dict(Counter(item["status"] for item in results)),
        "schema_confirmation_count": len(SCHEMA_CONFIRMATION),
        "generator_control_count": len(GENERATOR_CONTROL),
        "records": records,
    }
    write_json(BATCH / "r12_failure_analysis.json", analysis)
    write_json(BATCH / "generation_queue_r12_schema_confirmation.json", {
        "queue_id": "DEV-R12-SCHEMA-CONFIRMATION-ONE-RUN",
        "description": "One run for the eight R11 failures whose source-grounded vocabulary or requirement model changed in R12.",
        "development_vocabulary_id": DEV_ID,
        "repetitions": 1,
        "requirements": SCHEMA_CONFIRMATION,
    })
    write_json(BATCH / "generation_queue_r12_generator_control.json", {
        "queue_id": "DEV-R12-GENERATOR-CONTROL-ONE-RUN",
        "description": "Run after schema confirmation. These five R11 failures already had sufficient vocabulary and test generator repair behavior only.",
        "development_vocabulary_id": DEV_ID,
        "repetitions": 1,
        "requirements": GENERATOR_CONTROL,
    })

    decisions = [{
        "canonicalLocalName": item["localName"],
        "action": "ADD_R12_SOURCE_GROUNDED_TERM",
        "kind": item["kind"],
        "domain": SPECS[item["localName"]].get("domain", ""),
        "range": item["parentOrRange"],
        "linkedRequirements": item["requirements"],
        "rationale": "Exact clause wording converted to a typed relationship, controlled value, result/evidence role, or owner-local quantity; no external equivalence claimed.",
    } for item in additions]
    write_json(OUT / "registry/r12_change_decisions.json", decisions)

    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    errors = []
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
        "schemaConfirmationQueue": len(SCHEMA_CONFIRMATION),
        "generatorControlQueue": len(GENERATOR_CONTROL),
        "ownerAssignmentsInferred": inferred_count,
        "errors": errors,
    }
    write_json(OUT / "validation/validation_report.json", report)
    if errors:
        raise RuntimeError("; ".join(errors))

    tracker = BATCH / "r12_engineering_change_tracker.xlsx"
    write_json(OUT / "development_binding.json", {
        "lockId": DEV_ID,
        "status": "DEVELOPMENT_BINDING_NOT_EVALUATION_LOCK",
        "workbook": tracker.name,
        "workbookSha256": "PENDING_TRACKER_BUILD",
        "boundMachineReadableArtifacts": {},
        "boundRequirementIndex": {},
        "warning": "R12 is an engineering-development binding. Do not use confirmation outputs as final experiment data.",
    })
    (OUT / "README.md").write_text(
        f"# R12 final-gap-closure development vocabulary\n\nIdentifier: `{DEV_ID}`. R12 preserves R11, closes the eight source-grounded schema/model gaps exposed by the R11 confirmation run, and separates five generator-control cases. It is not a final evaluation lock.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "development_id": DEV_ID, "registry_terms": len(registry), "added_terms": len(additions), "schema_confirmation": len(SCHEMA_CONFIRMATION), "generator_control": len(GENERATOR_CONTROL), "owners_inferred": inferred_count, "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize-binding", action="store_true")
    args = parser.parse_args()
    finalize_binding() if args.finalize_binding else main()
