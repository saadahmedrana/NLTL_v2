from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, OWL, RDF

import build_dev_r9_foundation as r9


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R9_FOUNDATION"
OUT = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R10_GRAPH_COMPLETION"
BATCH = MVP / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190"
BASE = r9.BASE
UNIT = r9.UNIT
QV = r9.QUDT_QUANTITY_VALUE
XSD = "http://www.w3.org/2001/XMLSchema#"
DEV_ID = "VOCAB-DEV-2026-08-13-R10-GRAPH-COMPLETION"
VERSION = "2.10.0-dev-graph-completion"


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


def lit(domain, datatype="boolean", module="regulation", requirements=()):
    return {"kind": "DatatypeProperty", "domain": domain, "range": XSD + datatype, "datatype": "xsd:" + datatype, "module": module, "requirements": list(requirements)}


def qty(domain, unit, symbol, quantity_kind, module="hull", requirements=(), aliases=()):
    return {"kind": "QuantityProperty", "domain": domain, "range": QV, "unit": UNIT + unit if unit else "", "unitSymbol": symbol, "quantityKind": quantity_kind, "module": module, "requirements": list(requirements), "aliases": list(aliases)}


def ind(parent, module="regulation", requirements=()):
    return {"kind": "NamedIndividual", "range": parent, "module": module, "requirements": list(requirements)}


S: dict[str, dict] = {
    # Reusable graph-completeness foundation.
    "tableReferenceValue": cls("benchmarkEntity"),
    "tableReference": obj("tableLookupCase", "tableReferenceValue"),
    "lookupSelectionEvidence": obj("tableLookupCase", "evidenceArtifact", "evidence"),
    "lookupResultQuantity": qty("tableLookupCase", "", "", "Context-dependent quantity", "regulation"),
    "hasHullAreaAssignment": obj("ship", "hullAreaAssignment", "hull"),
    "hullAreaAssignment": cls("calculationCase", "hull"),
    "assignedHullArea": obj("hullAreaAssignment", "hullAreaValue", "hull"),
    "hullAreaValue": cls("benchmarkEntity", "hull"),
    "otherIceStrengthenedArea": ind("hullAreaValue", "hull", ("I2-009",)),
    "hasSpannedHullArea": obj("structuralMember", "hullAreaValue", "hull", ("I2-019",)),
    "selectedHullAreaFactor": qty("structuralMember", "UNITLESS", "1", "Dimensionless", "hull", ("I2-019", "I2-022", "I2-023", "I2-032", "I2-035"), ("AF",)),
    "hasCalculationInputEvidence": obj("calculationCase", "evidenceArtifact", "evidence"),
    "hasCalculationResultEvidence": obj("calculationCase", "evidenceArtifact", "evidence"),
    # IACS formula, selector, interpolation, and ownership repairs.
    "bowSubregionWaterlineAngle": qty("bowSubregionCalculationCase", "DEG", "deg", "Angle", "hull", ("I2-015",), ("alpha_i",)),
    "bowSubregionAspectRatio": qty("bowSubregionCalculationCase", "UNITLESS", "1", "Dimensionless", "hull", ("I2-014",), ("AR_i",)),
    "selectedMaximumBowForce": qty("ship", "MegaN", "MN", "Force", "hull", ("I2-014",), ("F_Bow",)),
    "selectedMaximumBowLineLoad": qty("ship", "MegaN-M-PER-M2", "MN/m", "Force per length", "hull", ("I2-014",), ("Q_Bow",)),
    "selectedMaximumBowPressure": qty("ship", "MegaPA", "MPa", "Pressure", "hull", ("I2-014",), ("P_Bow",)),
    "nonBowIceLoadCalculationCase": cls("calculationCase", "hull", ("I2-017",)),
    "hasNonBowIceLoadCalculationCase": obj("ship", "nonBowIceLoadCalculationCase", "hull", ("I2-017",)),
    "nonBowIceForce": qty("nonBowIceLoadCalculationCase", "MegaN", "MN", "Force", "hull", ("I2-017",), ("F_NonBow",)),
    "nonBowIceLineLoad": qty("nonBowIceLoadCalculationCase", "MegaN-M-PER-M2", "MN/m", "Force per length", "hull", ("I2-017",), ("Q_NonBow",)),
    "shipDisplacementFactor": qty("nonBowIceLoadCalculationCase", "UNITLESS", "1", "Dimensionless", "hull", ("I2-017",), ("DF",)),
    "peakPressureFactorLookupCase": cls("tableLookupCase", "hull", ("I2-018",)),
    "hasPeakPressureFactorLookupCase": obj("ship", "peakPressureFactorLookupCase", "hull", ("I2-018",)),
    "localizedStructuralMemberCategory": obj("peakPressureFactorLookupCase", "structuralMemberCategoryValue", "hull", ("I2-018",)),
    "structuralMemberCategoryValue": cls("benchmarkEntity", "hull", ("I2-018",)),
    "selectedPeakPressureFactor": qty("peakPressureFactorLookupCase", "UNITLESS", "1", "Dimensionless", "hull", ("I2-018",), ("PPF_i",)),
    "transverseFramingNetPlateThickness": qty("calculationCase", "MilliM", "mm", "Length", "hull", ("I2-024",)),
    "longitudinalFramingNetPlateThickness": qty("calculationCase", "MilliM", "mm", "Length", "hull", ("I2-024",)),
    "hasMemberSupport": obj("structuralMember", "memberSupport", "hull", ("I2-026",)),
    "memberSupport": cls("hullStructure", "hull", ("I2-026",)),
    "continuousThroughSupport": lit("structuralMember", requirements=("I2-026",)),
    "connectionBracketPresent": lit("memberSupport", requirements=("I2-026",)),
    "demonstratedRotationalRestraint": lit("memberSupport", requirements=("I2-026",)),
    "terminatesWithinIceStrengthenedArea": lit("structuralMember", requirements=("I2-026",)),
    "flangeFitted": lit("structuralMember", requirements=("I2-029",)),
    "attachedShellPlatingIncludedInSectionModulus": lit("calculationCase", requirements=("I2-029",)),
    "attachedShellPlatingExcludedFromShearArea": lit("calculationCase", requirements=("I2-029",)),
    "flangeMaterialIncludedInShearArea": lit("calculationCase", requirements=("I2-029",)),
    "interpolationLowerEndpoint": obj("calculationCase", "interpolationPoint", requirements=("I2-024", "I2-030", "I2-052")),
    "interpolationUpperEndpoint": obj("calculationCase", "interpolationPoint", requirements=("I2-024", "I2-030", "I2-052")),
    "structuralLocationValue": cls("benchmarkEntity", "hull", ("I2-031",)),
    "structuralLocation": obj("structuralMember", "structuralLocationValue", "hull", ("I2-031",)),
    "bottomStructureLocation": ind("structuralLocationValue", "hull", ("I2-031",)),
    "sideStructureLocation": ind("structuralLocationValue", "hull", ("I2-031", "I2-034")),
    "midspanPlasticCollapseLoad": qty("structuralMember", "KiloN", "kN", "Force", "hull", ("I2-031", "I2-034")),
    "structuralSectionTypeValue": cls("benchmarkEntity", "hull", ("I2-040",)),
    "structuralSectionType": obj("structuralMember", "structuralSectionTypeValue", "hull", ("I2-040",)),
    "flatBarSection": ind("structuralSectionTypeValue", "hull", ("I2-040",)),
    "bulbSection": ind("structuralSectionTypeValue", "hull", ("I2-040",)),
    "teeSection": ind("structuralSectionTypeValue", "hull", ("I2-040",)),
    "angleSection": ind("structuralSectionTypeValue", "hull", ("I2-040",)),
    "steelGradeOrderRank": lit("steelGradeValue", "integer", "hull", ("I2-048",)),
    "actualHullStructuralSteelGrade": obj("steelGradeRequirementCase", "steelGradeValue", "hull", ("I2-048",)),
    "interpolatedLongitudinalDistributionFactor": qty("calculationCase", "UNITLESS", "1", "Dimensionless", "hull", ("I2-052",), ("C_f",)),
    "hasCutout": obj("structuralMember", "cutout", "hull", ("I2-060",)),
    "memberInWayOfCutout": lit("structuralMember", requirements=("I2-060",)),
    "permanentLateralDeformation": qty("calculationCase", "MilliM", "mm", "Length", "hull", ("I2-065",)),
    "permanentOutOfPlaneDeformation": qty("calculationCase", "MilliM", "mm", "Length", "hull", ("I2-065",)),
    "relevantStructuralDimension": qty("calculationCase", "MilliM", "mm", "Length", "hull", ("I2-065",)),
    "nonlinearAnalysisAcceptanceEvidence": obj("calculationCase", "evidenceArtifact", "evidence", ("I2-065",)),
    # IMO per-item ownership and evidence paths.
    "certificateScheduleDateRecord": cls("documentRecord", "documents", ("IMO-017",)),
    "hasCertificateScheduleDateRecord": obj("solasCertificateSchedule", "certificateScheduleDateRecord", "documents", ("IMO-017",)),
    "hasLoadingConditionResultEvidence": obj("loadingConditionCase", "evidenceArtifact", "evidence", ("IMO-037",)),
    "hasIceOrSnowRemovalOrPreventionMeans": obj("relevantHatchOrDoorItem", "iceOrSnowRemovalOrPreventionMeans", "safety", ("IMO-040",)),
    "localControlProtectionPresent": lit("localControlItem", requirements=("IMO-051",)),
    "localControlContinuouslyAccessible": lit("localControlItem", requirements=("IMO-051",)),
    "extinguishingMediumCompatibilityStatus": lit("extinguishingMediumItem", requirements=("IMO-053",)),
    "fireMainSectionIsolationCapability": lit("exposedFireMainSectionItem", requirements=("IMO-058",)),
    "fireMainSectionDrainageMeansPresent": lit("exposedFireMainSectionItem", requirements=("IMO-058",)),
    "escapeRouteAccessibleStatus": lit("exposedEscapeRoute", requirements=("IMO-062",)),
    "escapeRouteSafeStatus": lit("exposedEscapeRoute", requirements=("IMO-062",)),
    "hasEscapeRouteIceSnowMitigationEvidence": obj("exposedEscapeRoute", "evidenceArtifact", "evidence", ("IMO-062",)),
    "searchlightContinuousUseSuitabilityStatus": lit("searchlight", requirements=("IMO-072",)),
    "hasPassenger": obj("ship", "passenger", "operations", ("IMO-078",)),
    "hasCrewMemberInventory": obj("ship", "crewMember", "operations", ("IMO-078", "IMO-102", "IMO-104")),
    "survivalCraft": cls("equipmentItem", "safety", ("IMO-097",)),
    "hasSurvivalCraft": obj("ship", "survivalCraft", "safety", ("IMO-097",)),
    "shipToShoreDistressAlertDevice": cls("equipmentItem", "safety", ("IMO-097",)),
    "survivalCraftHasLocationSignalDevice": obj("survivalCraft", "locationSignalDevice", "safety", ("IMO-097",)),
    "survivalCraftHasOnSceneCommunicationDevice": obj("survivalCraft", "onSceneCommunicationDevice", "safety", ("IMO-097",)),
    "survivalCraftHasShipToShoreDistressAlertDevice": obj("survivalCraft", "shipToShoreDistressAlertDevice", "safety", ("IMO-097",)),
    "hasCrewTrainingRecord": obj("crewMember", "polarTrainingRecord", "evidence", ("IMO-102",)),
    "trainingRecordLevel": obj("polarTrainingRecord", "trainingLevelValue", "evidence", ("IMO-102",)),
    "stcwQualificationValid": lit("polarTrainingRecord", requirements=("IMO-102",)),
    "familiarizationRecordItem": obj("familiarizationRecord", "polarWaterOperationalManualItem", "evidence", ("IMO-104",)),
    "antennaIceAccumulationPreventionPresent": lit("navigationOrCommunicationAntenna", requirements=("IMO26-009",)),
    # TRAFICOM table/case/branch/component repairs.
    "hasStrutDesignEvidence": obj("detachedStrutStructure", "strutDesignEvidence", "evidence", ("TRF-064",)),
    "hasStrutStrengthEvidence": obj("detachedStrutStructure", "strutStrengthEvidence", "evidence", ("TRF-064",)),
    "hasStrutHullAttachmentEvidence": obj("detachedStrutStructure", "strutHullAttachmentEvidence", "evidence", ("TRF-064",)),
    "stoppedPropellerDraggingOutsideLoadModel": lit("designCondition", requirements=("TRF-069",)),
    "radialIceEntryOutsideLoadModel": lit("designCondition", requirements=("TRF-069",)),
    "normalServiceLifePropellerIceLoadCondition": lit("designCondition", requirements=("TRF-069",)),
    "propellerLocationValue": cls("benchmarkEntity", "machinery", ("TRF-078",)),
    "propellerLocation": obj("ship", "propellerLocationValue", "machinery", ("TRF-078",)),
    "selectedIceClassCycleCount": qty("tableLookupCase", "UNITLESS", "1", "Count", "machinery", ("TRF-078",), ("N_class",)),
    "selectedPropellerLocationFactor": qty("tableLookupCase", "UNITLESS", "1", "Dimensionless", "machinery", ("TRF-078",), ("k_1",)),
    "bollardThrustKnown": lit("ship", requirements=("TRF-082",)),
    "bollardPropellerSpeedKnown": lit("ship", requirements=("TRF-083", "TRF-085")),
    "maximumEngineTorqueKnown": lit("ship", requirements=("TRF-088",)),
    "iceMillingSequenceCase": cls("loadCase", "machinery", ("TRF-091",)),
    "hasIceMillingSequenceCase": obj("ship", "iceMillingSequenceCase", "machinery", ("TRF-091",)),
    "stressLifeCurveTypeValue": cls("benchmarkEntity", "machinery", ("TRF-108",)),
    "stressLifeCurveSelection": obj("ship", "stressLifeCurveTypeValue", "machinery", ("TRF-108",)),
    "twoSlopeStressLifeCurve": ind("stressLifeCurveTypeValue", "machinery", ("TRF-108",)),
    "stressLifeCurveKnown": lit("ship", requirements=("TRF-108",)),
    "fatigueSafetyFactor": qty("shipComponent", "UNITLESS", "1", "Dimensionless", "machinery", ("TRF-111",)),
    "bendingYieldSafetyFactor": qty("shipComponent", "UNITLESS", "1", "Dimensionless", "machinery", ("TRF-112",)),
    "torsionalYieldSafetyFactor": qty("shipComponent", "UNITLESS", "1", "Dimensionless", "machinery", ("TRF-112",)),
    "thrusterResistanceCapacity": qty("thrusterBody", "KiloN", "kN", "Force", "machinery", ("TRF-114",)),
    "thrusterIceImpactDemand": qty("thrusterIceImpactLoadCase", "KiloN", "kN", "Force", "machinery", ("TRF-114",)),
    "hasMaterialProperties": obj("shipComponent", "materialProperties", "machinery", ("TRF-118", "TRF-123")),
    "materialProperties": cls("benchmarkEntity", "machinery", ("TRF-118", "TRF-123")),
    "componentMaterialYieldStrength": qty("materialProperties", "MegaPA", "MPa", "Pressure", "machinery", ("TRF-118", "TRF-123")),
    "shipAttachmentStiffness": qty("thrusterBody", "KiloN-PER-M", "kN/m", "Linear stiffness", "machinery", ("TRF-120",)),
    "hasNaturalFrequencyCalculationCase": obj("thrusterBody", "calculationCase", "machinery", ("TRF-120",)),
    "occasionalForceLoadCase": cls("loadCase", "machinery", ("TRF-123",)),
    "hasOccasionalForceLoadCase": obj("ship", "occasionalForceLoadCase", "machinery", ("TRF-123",)),
    "propellerBladeExcludedFromOccasionalForceScope": lit("occasionalForceLoadCase", requirements=("TRF-123",)),
    "warningTriangle": cls("hullStructure", "hull", ("TRF-133",)),
    "hasWarningTriangle": obj("ship", "warningTriangle", "hull", ("TRF-133",)),
    "markingReferencePointValue": cls("benchmarkEntity", "hull", ("TRF-133",)),
    "draughtMarkAftReferencePoint": obj("iceClassDraughtMarking", "markingReferencePointValue", "hull", ("TRF-133",)),
    "loadLineRingCentreReference": ind("markingReferencePointValue", "hull", ("TRF-133",)),
    "timberLoadLineVerticalReference": ind("markingReferencePointValue", "hull", ("TRF-133",)),
}


# Exact published table identifiers. They identify provenance/selection only;
# table values remain part of the verified requirement model, not ontology logic.
TABLES = {
    "iacsUrI2Table3": ("I2-018",), "iacsUrI2Table8": ("I2-048",),
    "traficomTable4Dash8": ("TRF-060",), "traficomTable6Dash6": ("TRF-078",),
    "traficomTable6Dash7": ("TRF-078",), "traficomTable6Dash8": ("TRF-082",),
    "traficomTable6Dash9": ("TRF-083", "TRF-085"), "traficomTable6Dash10": ("TRF-088",),
}
for name, reqs in TABLES.items():
    S[name] = ind("tableReferenceValue", "regulation", reqs)


REUSE: dict[str, list[str]] = {
    "I2-009": ["hasHullAreaAssignment", "hullAreaAssignment", "assignedHullArea", "hullAreaValue", "loadPatchAspectRatio", "averageIcePressure", "nonBowLoadPatchHeight", "nonBowLoadPatchLength"],
    "I2-014": ["averageIcePressure", "loadPatchHeight", "loadPatchLength"],
    "I2-018": ["averageIcePressure", "loadPatchHeight", "loadPatchLength", "hasTableLookupCase", "tableReference", "lookupSelectionEvidence"],
    "I2-022": ["hullAreaFactor", "loadPatchHeight"], "I2-023": ["hullAreaFactor", "loadPatchHeight"],
    "I2-024": ["hasCalculationCase"], "I2-029": ["hasCalculationCase"], "I2-030": ["hasCalculationCase"],
    "I2-031": ["frameProfileType"], "I2-032": ["hullAreaFactor", "loadPatchHeight"], "I2-034": ["frameProfileType"],
    "I2-035": ["hullAreaFactor", "loadPatchHeight"], "I2-046": ["polarClass"],
    "I2-048": ["hasTableLookupCase", "tableReference", "lookupSelectionEvidence"],
    "I2-051": ["hasCalculationCase"], "I2-052": ["hasCalculationCase"], "I2-054": ["hasCalculationCase"],
    "I2-061": ["hasCalculationCase", "calculationMethod"], "I2-064": ["hasCalculationCase", "calculationMethod"], "I2-065": ["hasCalculationCase", "calculationMethod"],
    "IMO-017": ["hasPolarShipCertificate", "hasSolasCertificateSchedule"],
    "IMO-037": ["hasLoadingConditionCase"], "IMO-040": ["hasRelevantHatchOrDoor"],
    "IMO-051": ["hasLocalControlItem"], "IMO-053": ["hasExtinguishingMedium"], "IMO-058": ["hasExposedFireMainSection"],
    "IMO-062": ["hasExposedEscapeRoute"], "IMO-072": ["hasLifeboat", "hasAssignedSearchlight"],
    "IMO-073": ["hasLifeboat"], "IMO-097": ["hasLifeboat", "hasOtherSurvivalCraft"],
    "IMO-102": ["requiredTrainingLevel"], "IMO-104": ["hasCrewMember", "hasFamiliarizationRecord"],
    "IMO26-009": ["hasRequiredNavigationOrCommunicationAntenna"],
    "TRF-060": ["hasTableLookupCase", "tableReference", "lookupSelectionEvidence"],
    "TRF-064": ["hasDetachedStrut"], "TRF-069": ["hasDesignCondition"], "TRF-070": ["hasDesignCondition"],
    "TRF-078": ["hasTableLookupCase", "tableReference", "lookupSelectionEvidence"],
    "TRF-079": ["propellerDiameter"], "TRF-082": ["hasTableLookupCase", "tableReference", "lookupSelectionEvidence"],
    "TRF-083": ["hasTableLookupCase", "tableReference", "lookupSelectionEvidence"], "TRF-085": ["hasTableLookupCase", "tableReference", "lookupSelectionEvidence", "propellerDiameter"],
    "TRF-088": ["hasTableLookupCase", "tableReference", "lookupSelectionEvidence"], "TRF-101": ["hasLoadCase"],
    "TRF-114": ["hasThrusterIceImpactLoadCase"], "TRF-116": ["nonHemisphericalImpactContactArea", "equivalentImpactSphereRadius", "designIceThickness", "propellerHubOrThrusterEndCapImpact"],
}


FAILED = [item["requirement_id"] for item in read_json(BATCH / "r10_failure_analysis.json")["records"]]


def requirement_terms() -> dict[str, list[str]]:
    result = {rid: list(REUSE.get(rid, [])) for rid in FAILED}
    for name, spec in S.items():
        for rid in spec.get("requirements", []):
            result.setdefault(rid, []).append(name)
    return {rid: sorted(set(names)) for rid, names in result.items()}


def exact_formula(rid: str, normalized: str) -> str:
    overrides = {
        "I2-015": "f_ai=min(f_ai1,f_ai2,f_ai3); f_ai1=(0.097-0.68*(x/L_UI-0.15)^2)*alpha_i/sqrt(beta_i_prime); f_ai2=1.2*C_FF/(sin(beta_i_prime)*C_FC*D_UI^0.64); f_ai3=0.60",
        "I2-017": "F_NonBow=0.36*C_FC*DF; Q_NonBow=0.639*F_NonBow^0.61*C_FD; DF=D_UI^0.64 if D_UI<=CF_DIS else CF_DIS^0.64+0.10*(D_UI-CF_DIS)",
        "I2-022": normalized, "I2-023": normalized, "I2-032": normalized, "I2-035": normalized,
        "I2-050": normalized, "I2-051": normalized, "I2-054": normalized,
        "TRF-060": normalized, "TRF-079": normalized,
        "TRF-116": "R_ceq=sqrt(A/pi); if 2*R_ceq>H_iced then R_ceq=H_iced/2, except propeller-hub or thruster-end-cap impacts",
    }
    return overrides.get(rid, "")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)
    evidence_payload = read_json(OUT / "evidence/stage1_approved.json")
    evidence = {item["id"]: item for item in evidence_payload["requirements"]}
    # The I2.3.1 umbrella statement requires equations supplied only by the
    # downstream I2.3.2 clauses. Keep those downstream cases active and defer
    # the duplicate umbrella extraction rather than pretend it is self-contained.
    evidence["I2-008"]["activeStatus"] = "Deferred - non-self-contained umbrella requirement"
    evidence["I2-008"]["codability"] = "Deferred"
    evidence["I2-008"]["stage2DecisionReason"] = "The row states which characteristics must be calculated but does not contain their equations; the complete equations are benchmarked by the downstream I2.3.2 requirements."
    write_json(OUT / "evidence/stage1_approved.json", evidence_payload)

    registry = read_json(OUT / "registry/term_registry.json")
    existing = {item["localName"] for item in registry}
    additions = []
    for number, (name, spec) in enumerate(sorted(S.items()), 1):
        if name not in existing:
            additions.append(r9.registry_record(name, spec, f"VOC-DEV-R10-{number:04d}", evidence))
    registry = sorted(registry + additions, key=lambda item: item["localName"])
    added_names = {item["localName"] for item in additions}
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
        r9.add_to_graph(graph, item, S[item["localName"]])
    for ontology in graph.subjects(RDF.type, OWL.Ontology):
        graph.set((ontology, OWL.versionInfo, Literal(VERSION)))
    graph.serialize(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.serialize(OUT / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    context = read_json(OUT / "context/nltl_benchmark_context.jsonld")
    for item in additions:
        context["@context"][item["localName"]] = ({"@id": "nltl:" + item["localName"], "@type": "@id"} if item["kind"] in {"ObjectProperty", "QuantityProperty"} else "nltl:" + item["localName"])
    write_json(OUT / "context/nltl_benchmark_context.jsonld", context)

    index = read_json(OUT / "requirement_term_index.json")
    index["sourceLockId"] = DEV_ID; index["version"] = "2.0.0-dev-contract-schema-v2"
    terms = requirement_terms()
    for rid, names in terms.items():
        index["requirements"][rid] = sorted(set(index["requirements"].get(rid, [])) | set(names))
    by_name = {item["localName"]: item for item in registry}
    # Authoritative per-requirement ownership.  This is essential for per-item
    # constraints: the generator must not place an item property on the ship.
    for rid, names in terms.items():
        owners = index.setdefault("termOwners", {}).setdefault(rid, {})
        for name in names:
            domain = S.get(name, {}).get("domain")
            if domain:
                owners[name] = domain
    for rid in FAILED:
        contract = index["dependencyContracts"][rid]
        linked = index["requirements"][rid]
        r10 = terms.get(rid, [])
        contract.update({
            "schemaVersion": 2,
            "status": "COMPLETE",
            "engineeringDecision": "R10_GRAPH_PATH_OWNER_AND_CONTRACT_COMPLETION",
            "comparisonModel": evidence[rid].get("normalizedRequirement", ""),
            "formulaExpression": exact_formula(rid, evidence[rid].get("normalizedRequirement", "")),
            "relationshipTerms": sorted(name for name in linked if by_name.get(name, {}).get("kind") == "ObjectProperty"),
            "controlledValueTerms": sorted(name for name in linked if by_name.get(name, {}).get("kind") == "NamedIndividual"),
            "requiredModelFields": ["comparisonModel"],
            "modelPaths": [
                {"fromOwner": S[name].get("domain", "ship"), "via": name, "toOwner": S[name]["range"]}
                for name in r10 if name in added_names and S[name].get("kind") == "ObjectProperty"
            ],
        })
        if contract["formulaExpression"]:
            contract["requiredModelFields"] = ["comparisonModel", "formulaExpression"]
        if "table" in evidence[rid].get("encodingPattern", "").lower() or any(name in TABLES for name in r10):
            contract["tableModel"] = contract.get("tableModel") or "Use the exact cited table reference, explicit selector inputs, attributed result, and selection evidence."
            contract["requiredModelFields"] = sorted(set(contract["requiredModelFields"] + ["tableModel"]))
        # Quantities not classified as outputs are safe operands; specific
        # output roles below override the prior R9 heuristic.
        quantities = [name for name in linked if by_name.get(name, {}).get("kind") == "QuantityProperty"]
        contract["operandTerms"] = sorted(set(contract.get("operandTerms", [])) | set(quantities))
        contract["resultTerms"] = sorted(set(contract.get("resultTerms", [])))
    # Explicit role corrections revealed by R9 confirmation.
    index["dependencyContracts"]["I2-050"]["applicabilityTerms"] = []
    index["dependencyContracts"]["I2-050"]["operandTerms"] = ["crushingFailureClassFactor", "flexuralFailureClassFactor", "hullFormCoefficientKh", "iceStrengthCoefficientKI", "longitudinalStrengthClassFactor", "stemAngle", "upperIceWaterlineDraughtDUI"]
    index["dependencyContracts"]["I2-050"]["resultTerms"] = ["designVerticalIceForceAtBow", "designVerticalIceForceAtBowCandidateOne", "designVerticalIceForceAtBowCandidateTwo"]
    index["dependencyContracts"]["TRF-116"]["operandTerms"] = ["nonHemisphericalImpactContactArea", "designIceThickness", "propellerHubOrThrusterEndCapImpact"]
    index["dependencyContracts"]["TRF-116"]["resultTerms"] = ["equivalentImpactSphereRadius"]
    index["dependencyContracts"]["IMO-040"]["engineeringDecision"] = "R10_GENERATOR_OVERCONSTRAINT_PROMPT_REPAIR_ONLY"
    index["dependencyContracts"]["I2-008"].update({"status": "DEFERRED_NON_SELF_CONTAINED", "schemaVersion": 2, "blocker": evidence["I2-008"]["stage2DecisionReason"], "engineeringDecision": "DEFER_DUPLICATE_UMBRELLA_EXTRACTION"})
    index["termCount"] = len(registry)
    write_json(OUT / "requirement_term_index.json", index)

    decisions = [{"canonicalLocalName": item["localName"], "action": "ADD_R10_GRAPH_COMPLETION_TERM", "kind": item["kind"], "domain": S[item["localName"]].get("domain", ""), "range": item["parentOrRange"], "linkedRequirements": item["requirements"], "rationale": "Adds a source-grounded relationship, owner-local property, formula operand/result, table selector, controlled value, or evidence path exposed by R9 confirmation."} for item in additions]
    write_json(OUT / "registry/r10_change_decisions.json", decisions)

    # Queue all repaired R9 failures except the deferred umbrella requirement.
    queue_ids = [rid for rid in FAILED if index["dependencyContracts"][rid]["status"] == "COMPLETE"]
    write_json(BATCH / "generation_queue_r10_affected.json", {"queue_id": "DEV-R10-FAILED-R9-REPAIRS-ONE-RUN", "description": "One confirmation run for R9 failures repaired by the R10 graph-completion model.", "development_vocabulary_id": DEV_ID, "repetitions": 1, "requirements": queue_ids, "excluded": {"I2-008": "Deferred as a non-self-contained umbrella extraction; downstream formula cases remain active."}})

    # Local integrity validation.
    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    errors = []
    if len({item["localName"] for item in registry}) != len(registry): errors.append("duplicate localName")
    if len({item["iri"] for item in registry}) != len(registry): errors.append("duplicate IRI")
    bad = [item["localName"] for item in registry if not re.fullmatch(r"[a-z][A-Za-z0-9]*", item["localName"])]
    if bad: errors.append("invalid local names: " + ", ".join(bad))
    missing = sorted({name for names in index["requirements"].values() for name in names} - {item["localName"] for item in registry} - {str(s)[len(BASE):] for s in graph.subjects() if str(s).startswith(BASE)})
    if missing: errors.append("indexed terms absent: " + ", ".join(missing))
    report = {"status": "PASS" if not errors else "FAIL", "developmentId": DEV_ID, "registryTerms": len(registry), "addedTerms": len(additions), "requirements": 313, "generationEligible": sum(item.get("activeStatus") == "Stage 2 candidate - direct/deterministic" and str(item.get("figureDependent", "No")).lower() != "yes" for item in evidence_payload["requirements"]), "r10Queue": len(queue_ids), "errors": errors}
    write_json(OUT / "validation/validation_report.json", report)
    if errors: raise RuntimeError("; ".join(errors))

    tracker = BATCH / "r10_engineering_change_tracker.xlsx"
    binding = {"lockId": DEV_ID, "status": "DEVELOPMENT_BINDING_NOT_EVALUATION_LOCK", "workbook": tracker.name, "workbookSha256": sha256(tracker) if tracker.exists() else "PENDING_TRACKER_BUILD", "boundMachineReadableArtifacts": {"registry/term_registry.json": sha256(OUT / "registry/term_registry.json"), "ontology/nltl_benchmark_vocabulary.ttl": sha256(OUT / "ontology/nltl_benchmark_vocabulary.ttl"), "evidence/stage1_approved.json": sha256(OUT / "evidence/stage1_approved.json")}, "boundRequirementIndex": {"requirement_term_index.json": sha256(OUT / "requirement_term_index.json")}, "warning": "R10 is an engineering-development binding. Do not use its confirmation outputs as final experiment data."}
    write_json(OUT / "development_binding.json", binding)
    (OUT / "README.md").write_text(f"# R10 graph-completion development vocabulary\n\nIdentifier: `{DEV_ID}`. R10 preserves R9 and repairs the graph paths, per-node ownership, table attribution, controlled selectors, and contract-role errors exposed by the 112-case R9 confirmation. It is not a final evaluation lock.\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "development_id": DEV_ID, "registry_terms": len(registry), "added_terms": len(additions), "eligible": report["generationEligible"], "queue": len(queue_ids), "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
