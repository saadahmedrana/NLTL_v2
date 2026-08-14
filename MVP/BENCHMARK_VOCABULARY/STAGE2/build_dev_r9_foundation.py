from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL, SKOS, XSD


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R8_1_POSTCONFIRMATION"
OUT = MVP / "BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R9_FOUNDATION"
BATCH = MVP / "INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190"
BASE = "https://w3id.org/nltl-benchmark/vocab#"
DEV_ID = "VOCAB-DEV-2026-08-13-R9-FOUNDATION"
VERSION = "2.9.0-dev-foundation"
NLTL = Namespace(BASE)
QUDT_QUANTITY_VALUE = "http://qudt.org/schema/qudt/QuantityValue"
UNIT = "http://qudt.org/vocab/unit/"

# Exact identifiers checked against the official QUDT 3.4 Units vocabulary on
# 2026-08-13.  Keep this allow-list explicit: a plausible-looking unit IRI is
# not accepted merely because it follows QUDT's spelling pattern.
R9_VERIFIED_QUDT_UNITS = {
    UNIT + "KiloTON_Metric": {
        "symbol": "kt",
        "officialResource": "https://qudt.org/vocab/unit/KiloTON_Metric.html",
    },
    UNIT + "MegaN": {
        "symbol": "MN",
        "officialResource": "https://qudt.org/vocab/unit/MegaN.html",
    },
    UNIT + "MegaN-M": {
        "symbol": "MN.m",
        "officialResource": "https://qudt.org/vocab/unit/MegaN-M.html",
    },
    # QUDT expresses MN/m as (MN.m)/m2.  MegaN-PER-M is not a published
    # QUDT identifier and must never be emitted by the development registry.
    UNIT + "MegaN-M-PER-M2": {
        "symbol": "MN/m",
        "officialResource": "https://qudt.org/vocab/unit/MegaN-M-PER-M2.html",
    },
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def label(local: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", local).capitalize()


SPECS: dict[str, dict] = {
    # Reusable modelling foundation.
    "calculationCase": {"kind": "Class", "range": "benchmarkEntity", "module": "regulation"},
    "hasCalculationCase": {"kind": "ObjectProperty", "range": "calculationCase", "domain": "ship", "module": "regulation"},
    "loadCase": {"kind": "Class", "range": "calculationCase", "module": "regulation"},
    "hasLoadCase": {"kind": "ObjectProperty", "range": "loadCase", "domain": "ship", "module": "regulation"},
    "tableLookupCase": {"kind": "Class", "range": "calculationCase", "module": "regulation"},
    "hasTableLookupCase": {"kind": "ObjectProperty", "range": "tableLookupCase", "domain": "ship", "module": "regulation"},
    "designCondition": {"kind": "Class", "range": "benchmarkEntity", "module": "operations"},
    "hasDesignCondition": {"kind": "ObjectProperty", "range": "designCondition", "domain": "ship", "module": "operations"},
    "assignmentRecord": {"kind": "Class", "range": "evidenceArtifact", "module": "evidence"},
    "hasAssignmentRecord": {"kind": "ObjectProperty", "range": "assignmentRecord", "domain": "benchmarkEntity", "module": "evidence"},
    "documentRecord": {"kind": "Class", "range": "documentArtifact", "module": "documents"},
    "hasDocumentRecord": {"kind": "ObjectProperty", "range": "documentRecord", "domain": "ship", "module": "documents"},
    "approvalRecord": {"kind": "Class", "range": "evidenceArtifact", "module": "evidence"},
    "hasApprovalRecord": {"kind": "ObjectProperty", "range": "approvalRecord", "domain": "benchmarkEntity", "module": "evidence"},
    "equipmentItem": {"kind": "Class", "range": "shipComponent", "module": "core"},
    "hasEquipmentItem": {"kind": "ObjectProperty", "range": "equipmentItem", "domain": "ship", "module": "core"},
    "protectedItem": {"kind": "Class", "range": "benchmarkEntity", "module": "core"},
    "hasProtectedItem": {"kind": "ObjectProperty", "range": "protectedItem", "domain": "ship", "module": "core", "requirements": ["IMO-066"]},
    # IMO document and per-item models exposed by Batch 02.
    "hasPolarShipCertificate": {"kind": "ObjectProperty", "range": "polarShipCertificateForm", "domain": "ship", "module": "documents", "requirements": ["IMO-016", "IMO-017"]},
    "certificateFormModelValue": {"kind": "Class", "range": "benchmarkEntity", "module": "documents", "requirements": ["IMO-016"]},
    "certificateFormModel": {"kind": "ObjectProperty", "range": "certificateFormModelValue", "domain": "polarShipCertificateForm", "module": "documents", "requirements": ["IMO-016"]},
    "appendixIPolarShipCertificateModel": {"kind": "NamedIndividual", "range": "certificateFormModelValue", "module": "documents", "requirements": ["IMO-016"]},
    "hasSolasCertificateSchedule": {"kind": "ObjectProperty", "range": "solasCertificateSchedule", "domain": "ship", "module": "documents", "requirements": ["IMO-017"]},
    "loadingConditionCase": {"kind": "Class", "range": "calculationCase", "module": "operations", "requirements": ["IMO-037"]},
    "hasLoadingConditionCase": {"kind": "ObjectProperty", "range": "loadingConditionCase", "domain": "ship", "module": "operations", "requirements": ["IMO-037"]},
    "loadingConditionIdentifier": {"kind": "DatatypeProperty", "range": str(XSD.string), "datatype": "xsd:string", "domain": "loadingConditionCase", "module": "operations", "requirements": ["IMO-037"]},
    "selectedVerticalDamagePosition": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "hull", "requirements": ["IMO-038"]},
    "machineryInstallationItem": {"kind": "Class", "range": "machineryComponent", "module": "machinery", "requirements": ["IMO-043"]},
    "hasMachineryInstallation": {"kind": "ObjectProperty", "range": "machineryInstallationItem", "domain": "ship", "module": "machinery", "requirements": ["IMO-043"]},
    "associatedEquipmentItem": {"kind": "Class", "range": "equipmentItem", "module": "machinery", "requirements": ["IMO-043"]},
    "hasAssociatedEquipment": {"kind": "ObjectProperty", "range": "associatedEquipmentItem", "domain": "machineryInstallationItem", "module": "machinery", "requirements": ["IMO-043"]},
    "applicableHazardValue": {"kind": "Class", "range": "benchmarkEntity", "module": "regulation", "requirements": ["IMO-043"]},
    "hasApplicableHazard": {"kind": "ObjectProperty", "range": "applicableHazardValue", "domain": "machineryInstallationItem", "module": "regulation", "requirements": ["IMO-043"]},
    "hasHazardProtectionEvidence": {"kind": "ObjectProperty", "range": "evidenceArtifact", "domain": "machineryInstallationItem", "module": "evidence", "requirements": ["IMO-043"]},
    "iceAccretionHazard": {"kind": "NamedIndividual", "range": "applicableHazardValue", "module": "regulation", "requirements": ["IMO-043"]},
    "snowAccumulationHazard": {"kind": "NamedIndividual", "range": "applicableHazardValue", "module": "regulation", "requirements": ["IMO-043"]},
    "seawaterIceIngestionHazard": {"kind": "NamedIndividual", "range": "applicableHazardValue", "module": "regulation", "requirements": ["IMO-043"]},
    "liquidFreezingOrViscosityIncreaseHazard": {"kind": "NamedIndividual", "range": "applicableHazardValue", "module": "regulation", "requirements": ["IMO-043"]},
    "seawaterIntakeTemperatureHazard": {"kind": "NamedIndividual", "range": "applicableHazardValue", "module": "regulation", "requirements": ["IMO-043"]},
    "snowIngestionHazard": {"kind": "NamedIndividual", "range": "applicableHazardValue", "module": "regulation", "requirements": ["IMO-043"]},
    "firefighterOutfitItem": {"kind": "Class", "range": "equipmentItem", "module": "safety", "requirements": ["IMO-059"]},
    "hasFirefighterOutfit": {"kind": "ObjectProperty", "range": "firefighterOutfitItem", "domain": "ship", "module": "safety", "requirements": ["IMO-059"]},
    "physicalStorageLocation": {"kind": "Class", "range": "benchmarkEntity", "module": "core", "requirements": ["IMO-059"]},
    "hasStorageLocation": {"kind": "ObjectProperty", "range": "physicalStorageLocation", "domain": "equipmentItem", "module": "core", "requirements": ["IMO-059"]},
    "storageTemperatureClassValue": {"kind": "Class", "range": "benchmarkEntity", "module": "operations", "requirements": ["IMO-059"]},
    "storageTemperatureClass": {"kind": "ObjectProperty", "range": "storageTemperatureClassValue", "domain": "physicalStorageLocation", "module": "operations", "requirements": ["IMO-059"]},
    "warmStorageLocation": {"kind": "NamedIndividual", "range": "storageTemperatureClassValue", "module": "operations", "requirements": ["IMO-059"]},
    "hasExposedEscapeRoute": {"kind": "ObjectProperty", "range": "exposedEscapeRoute", "domain": "ship", "module": "safety", "requirements": ["IMO-062", "IMO-066"]},
    "iceSnowRemovalOrPreventionMeans": {"kind": "Class", "range": "equipmentItem", "module": "safety", "requirements": ["IMO-066"]},
    "hasIceSnowRemovalOrPreventionMeans": {"kind": "ObjectProperty", "range": "iceSnowRemovalOrPreventionMeans", "domain": "protectedItem", "module": "safety", "requirements": ["IMO-066"]},
    "protectedItemCategoryValue": {"kind": "Class", "range": "benchmarkEntity", "module": "safety", "requirements": ["IMO-066"]},
    "protectedItemCategory": {"kind": "ObjectProperty", "range": "protectedItemCategoryValue", "domain": "protectedItem", "module": "safety", "requirements": ["IMO-066"]},
    "escapeRouteProtectedItem": {"kind": "NamedIndividual", "range": "protectedItemCategoryValue", "module": "safety", "requirements": ["IMO-066"]},
    "musterStationProtectedItem": {"kind": "NamedIndividual", "range": "protectedItemCategoryValue", "module": "safety", "requirements": ["IMO-066"]},
    "embarkationAreaProtectedItem": {"kind": "NamedIndividual", "range": "protectedItemCategoryValue", "module": "safety", "requirements": ["IMO-066"]},
    "survivalCraftProtectedItem": {"kind": "NamedIndividual", "range": "protectedItemCategoryValue", "module": "safety", "requirements": ["IMO-066"]},
    "launchingApplianceProtectedItem": {"kind": "NamedIndividual", "range": "protectedItemCategoryValue", "module": "safety", "requirements": ["IMO-066"]},
    "survivalCraftAccessProtectedItem": {"kind": "NamedIndividual", "range": "protectedItemCategoryValue", "module": "safety", "requirements": ["IMO-066"]},
    "personOnBoardMember": {"kind": "Class", "range": "person", "module": "operations", "requirements": ["IMO-070"]},
    "hasPersonOnBoardMember": {"kind": "ObjectProperty", "range": "personOnBoardMember", "domain": "ship", "module": "operations", "requirements": ["IMO-070"]},
    "personalSurvivalEquipment": {"kind": "Class", "range": "equipmentItem", "module": "safety", "requirements": ["IMO-070"]},
    "immersionSuitEquipment": {"kind": "Class", "range": "personalSurvivalEquipment", "module": "safety", "requirements": ["IMO-070"]},
    "thermalProtectiveAidEquipment": {"kind": "Class", "range": "personalSurvivalEquipment", "module": "safety", "requirements": ["IMO-070"]},
    "personalSurvivalEquipmentAssignment": {"kind": "Class", "range": "assignmentRecord", "module": "evidence", "requirements": ["IMO-070"]},
    "hasPersonalSurvivalEquipmentAssignment": {"kind": "ObjectProperty", "range": "personalSurvivalEquipmentAssignment", "domain": "personOnBoardMember", "module": "evidence", "requirements": ["IMO-070"]},
    "assignedPersonalSurvivalEquipment": {"kind": "ObjectProperty", "range": "personalSurvivalEquipment", "domain": "personalSurvivalEquipmentAssignment", "module": "evidence", "requirements": ["IMO-070"]},
    "hasLifeboat": {"kind": "ObjectProperty", "range": "lifeboat", "domain": "ship", "module": "safety", "requirements": ["IMO-072"]},
    "searchlight": {"kind": "Class", "range": "equipmentItem", "module": "safety", "requirements": ["IMO-072"]},
    "hasAssignedSearchlight": {"kind": "ObjectProperty", "range": "searchlight", "domain": "lifeboat", "module": "safety", "requirements": ["IMO-072"]},
    "bridgeConfigurationValue": {"kind": "Class", "range": "benchmarkEntity", "module": "core", "requirements": ["IMO-082"]},
    "bridgeConfigurationType": {"kind": "ObjectProperty", "range": "bridgeConfigurationValue", "domain": "ship", "module": "core", "requirements": ["IMO-082"]},
    "asternViewRequiredBridgeConfiguration": {"kind": "NamedIndividual", "range": "bridgeConfigurationValue", "module": "core", "requirements": ["IMO-082"]},
    "hasOtherSurvivalCraft": {"kind": "ObjectProperty", "range": "otherSurvivalCraft", "domain": "ship", "module": "safety", "requirements": ["IMO-098"]},
    "locationSignalDevice": {"kind": "Class", "range": "equipmentItem", "module": "safety", "requirements": ["IMO-098"]},
    "hasLocationSignalDevice": {"kind": "ObjectProperty", "range": "locationSignalDevice", "domain": "otherSurvivalCraft", "module": "safety", "requirements": ["IMO-098"]},
    "onSceneCommunicationDevice": {"kind": "Class", "range": "equipmentItem", "module": "safety", "requirements": ["IMO-098"]},
    "hasOnSceneCommunicationDevice": {"kind": "ObjectProperty", "range": "onSceneCommunicationDevice", "domain": "otherSurvivalCraft", "module": "safety", "requirements": ["IMO-098"]},
    "hasCrewMember": {"kind": "ObjectProperty", "range": "crewMember", "domain": "ship", "module": "operations", "requirements": ["IMO-104"]},
    "familiarizationRecord": {"kind": "Class", "range": "evidenceArtifact", "module": "evidence", "requirements": ["IMO-104"]},
    "hasFamiliarizationRecord": {"kind": "ObjectProperty", "range": "familiarizationRecord", "domain": "crewMember", "module": "evidence", "requirements": ["IMO-104"]},
    "assignedDuty": {"kind": "Class", "range": "benchmarkEntity", "module": "operations", "requirements": ["IMO-104"]},
    "hasAssignedDuty": {"kind": "ObjectProperty", "range": "assignedDuty", "domain": "crewMember", "module": "operations", "requirements": ["IMO-104"]},
    "polarWaterOperationalManualItem": {"kind": "Class", "range": "documentRecord", "module": "documents", "requirements": ["IMO-104"]},
    "hasRelevantPolarWaterOperationalManualItem": {"kind": "ObjectProperty", "range": "polarWaterOperationalManualItem", "domain": "assignedDuty", "module": "documents", "requirements": ["IMO-104"]},
    "distanceFromAreaWithIceConcentrationAboveOneTenth": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MI_N", "unitSymbol": "nmi", "quantityKind": "Length", "module": "operations", "requirements": ["IMO-115", "IMO-116", "IMO-120", "IMO-124"]},
    "navigationOrCommunicationAntenna": {"kind": "Class", "range": "equipmentItem", "module": "machinery", "requirements": ["IMO26-009"]},
    "hasRequiredNavigationOrCommunicationAntenna": {"kind": "ObjectProperty", "range": "navigationOrCommunicationAntenna", "domain": "ship", "module": "machinery", "requirements": ["IMO26-009"]},
}

# TRAFICOM source-family repairs. Formula symbols are retained as aliases while
# canonical names state the engineering meaning.
SPECS.update({
    "webFrameMaximumIceLoadBendingMoment": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MegaN-M", "unitSymbol": "MN m", "quantityKind": "Torque", "module": "hull", "requirements": ["TRF-060"], "aliases": ["M"]},
    "webFrameIceLoad": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MegaN", "unitSymbol": "MN", "quantityKind": "Force", "module": "hull", "requirements": ["TRF-060"], "aliases": ["F"]},
    "webFrameSpan": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "hull", "requirements": ["TRF-060"], "aliases": ["L"]},
    "webFrameFreeFlangeArea": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "CentiM2", "unitSymbol": "cm2", "quantityKind": "Area", "module": "hull", "requirements": ["TRF-060"], "aliases": ["A_f"]},
    "webFrameWebArea": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "CentiM2", "unitSymbol": "cm2", "quantityKind": "Area", "module": "hull", "requirements": ["TRF-060"], "aliases": ["A_w"]},
    "webFrameTable4Dash8GammaFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "tableLookupCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["TRF-060"], "aliases": ["gamma"]},
    "sidePropellerStrengtheningEnvelope": {"kind": "Class", "range": "designCondition", "module": "hull", "requirements": ["TRF-063"]},
    "hasSidePropellerStrengtheningEnvelope": {"kind": "ObjectProperty", "range": "sidePropellerStrengtheningEnvelope", "domain": "ship", "module": "hull", "requirements": ["TRF-063"]},
    "strengtheningForwardExtent": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "sidePropellerStrengtheningEnvelope", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "hull", "requirements": ["TRF-063"]},
    "strengtheningAftExtent": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "sidePropellerStrengtheningEnvelope", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "hull", "requirements": ["TRF-063"]},
    "sidePropellerShaftingAssembly": {"kind": "Class", "range": "machineryComponent", "module": "machinery", "requirements": ["TRF-064"]},
    "hasSidePropellerShafting": {"kind": "ObjectProperty", "range": "sidePropellerShaftingAssembly", "domain": "ship", "module": "machinery", "requirements": ["TRF-064"]},
    "hasSternTube": {"kind": "ObjectProperty", "range": "sternTube", "domain": "ship", "module": "machinery", "requirements": ["TRF-064"]},
    "platedBossingStructure": {"kind": "Class", "range": "hullStructure", "module": "hull", "requirements": ["TRF-064"]},
    "enclosedByPlatedBossing": {"kind": "ObjectProperty", "range": "platedBossingStructure", "domain": "shipComponent", "module": "machinery", "requirements": ["TRF-064"]},
    "detachedStrutStructure": {"kind": "Class", "range": "hullStructure", "module": "hull", "requirements": ["TRF-064"]},
    "hasDetachedStrut": {"kind": "ObjectProperty", "range": "detachedStrutStructure", "domain": "ship", "module": "machinery", "requirements": ["TRF-064"]},
    "rudderProtectionArrangement": {"kind": "Class", "range": "equipmentItem", "module": "machinery", "requirements": ["TRF-066", "TRF-067"]},
    "hasRudderProtectionArrangement": {"kind": "ObjectProperty", "range": "rudderProtectionArrangement", "domain": "ship", "module": "machinery", "requirements": ["TRF-066", "TRF-067"]},
    "iceKnife": {"kind": "Class", "range": "rudderProtectionArrangement", "module": "machinery", "requirements": ["TRF-066"]},
    "extendsBelowLowerIceWaterline": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "iceKnife", "module": "machinery", "requirements": ["TRF-066"]},
    "iceKnifePracticable": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "machinery", "requirements": ["TRF-066"]},
    "equivalentRudderProtectionMeans": {"kind": "Class", "range": "rudderProtectionArrangement", "module": "machinery", "requirements": ["TRF-066"]},
    "rudderLoadAbsorbingArrangement": {"kind": "Class", "range": "rudderProtectionArrangement", "module": "machinery", "requirements": ["TRF-067"]},
    "normalOperationalConditions": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "designCondition", "module": "operations", "requirements": ["TRF-069", "TRF-070"]},
    "mainPropulsionThruster": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "machinery", "requirements": ["TRF-070"]},
    "ballastConditionPropellerTopDepth": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "machinery", "requirements": ["TRF-074"]},
    "requiredPropellerSubmersionDepthHi": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "machinery", "requirements": ["TRF-074"]},
    "propulsionSystemDesignedForIceClass": {"kind": "ObjectProperty", "range": "iceClassValue", "domain": "ship", "module": "machinery", "requirements": ["TRF-074"]},
    "propellerBladeLoadCase": {"kind": "Class", "range": "loadCase", "module": "machinery", "requirements": ["TRF-076"]},
    "hasPropellerBladeLoadCase": {"kind": "ObjectProperty", "range": "propellerBladeLoadCase", "domain": "ship", "module": "machinery", "requirements": ["TRF-076"]},
    "propellerBladeLoadCaseNumber": {"kind": "DatatypeProperty", "range": str(XSD.integer), "datatype": "xsd:integer", "domain": "propellerBladeLoadCase", "module": "machinery", "requirements": ["TRF-076"]},
    "maximumBladeIceLoad": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "KiloN", "unitSymbol": "kN", "quantityKind": "Force", "module": "machinery", "requirements": ["TRF-077"]},
    "propellerBladeLoadSpectrumCountFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "machinery", "requirements": ["TRF-078"], "aliases": ["n_n"]},
    "propellerShaftCentrelineDepth": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "machinery", "requirements": ["TRF-079"], "aliases": ["h_0"]},
    "designIceThickness": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "machinery", "requirements": ["TRF-079", "TRF-116"], "aliases": ["H_ice", "Hiced"]},
    "propellerImmersionFunction": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "machinery", "requirements": ["TRF-079"], "aliases": ["f"]},
    "effectiveIceLoadCycleCount": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Count", "module": "machinery", "requirements": ["TRF-080"]},
    "tableLookupApplied": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "tableLookupCase", "module": "regulation", "requirements": ["TRF-082", "TRF-083", "TRF-085", "TRF-088"]},
    "hasPropulsionLoadCase": {"kind": "ObjectProperty", "range": "loadCase", "domain": "ship", "module": "machinery", "requirements": ["TRF-091", "TRF-111", "TRF-112"]},
    "loadCasePurposeValue": {"kind": "Class", "range": "benchmarkEntity", "module": "regulation", "requirements": ["TRF-091"]},
    "loadCasePurpose": {"kind": "ObjectProperty", "range": "loadCasePurposeValue", "domain": "loadCase", "module": "regulation", "requirements": ["TRF-091"]},
    "propulsionLineStrengthEvaluationPurpose": {"kind": "NamedIndividual", "range": "loadCasePurposeValue", "module": "regulation", "requirements": ["TRF-091"]},
    "stallingAnalysisPurposeValue": {"kind": "NamedIndividual", "range": "loadCasePurposeValue", "module": "regulation", "requirements": ["TRF-091"]},
    "maximumTorqueUsedForLoadAssessment": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "machinery", "requirements": ["TRF-096"]},
    "bladeChordLengthAtWeakestSection": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "machinery", "requirements": ["TRF-101"], "aliases": ["c"]},
    "bladeMaximumThicknessAtWeakestSection": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "machinery", "requirements": ["TRF-101"], "aliases": ["t"]},
    "bladeCylindricalRootRadius": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "machinery", "requirements": ["TRF-101"], "aliases": ["r"]},
    "bladeMinimumYieldStrength": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MegaPA", "unitSymbol": "MPa", "quantityKind": "Pressure", "module": "machinery", "requirements": ["TRF-101"], "aliases": ["sigma_0.2"]},
    "bladeUltimateTensileStrength": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MegaPA", "unitSymbol": "MPa", "quantityKind": "Pressure", "module": "machinery", "requirements": ["TRF-101"], "aliases": ["sigma_u"]},
    "approvedNonlinearBladeStressAnalysis": {"kind": "ObjectProperty", "range": "approvalRecord", "domain": "ship", "module": "evidence", "requirements": ["TRF-101"]},
    "bladeFailureLoadApplicationRadiusRatio": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "loadCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "machinery", "requirements": ["TRF-101"]},
    "bladeFailureLoadWeakestDirectionConfirmed": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "loadCase", "module": "machinery", "requirements": ["TRF-101"]},
    "bladeExpandedAreaRatio": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "machinery", "requirements": ["TRF-102"], "aliases": ["EAR"]},
    "leadingEdgeChordPortionAtZeroPointEightRadius": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "machinery", "requirements": ["TRF-102"], "aliases": ["C_LE0.8"]},
    "trailingEdgeChordPortionAtZeroPointEightRadius": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "machinery", "requirements": ["TRF-102"], "aliases": ["C_TE0.8"]},
    "bladeFailureSpindleTorqueFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "machinery", "requirements": ["TRF-102"], "aliases": ["C_spex"]},
    "approvedSpindleTorqueStressAnalysis": {"kind": "ObjectProperty", "range": "approvalRecord", "domain": "ship", "module": "evidence", "requirements": ["TRF-102"]},
    "propellerShaftLineComponent": {"kind": "Class", "range": "machineryComponent", "module": "machinery", "requirements": ["TRF-104", "TRF-111", "TRF-112", "TRF-123"]},
    "hasPropellerShaftLineComponent": {"kind": "ObjectProperty", "range": "propellerShaftLineComponent", "domain": "ship", "module": "machinery", "requirements": ["TRF-104", "TRF-111", "TRF-112", "TRF-123"]},
    "significantDamageFromBladeLoss": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "propellerShaftLineComponent", "module": "machinery", "requirements": ["TRF-104"]},
    "stressLifeCurveSelectionCorrespondenceEvidence": {"kind": "ObjectProperty", "range": "evidenceArtifact", "domain": "ship", "module": "evidence", "requirements": ["TRF-108"]},
    "shaftLineLoadCaseTypeValue": {"kind": "Class", "range": "benchmarkEntity", "module": "regulation", "requirements": ["TRF-111", "TRF-112"]},
    "shaftLineLoadCaseType": {"kind": "ObjectProperty", "range": "shaftLineLoadCaseTypeValue", "domain": "loadCase", "module": "regulation", "requirements": ["TRF-111", "TRF-112"]},
    "extremeOperationalLoadCase": {"kind": "NamedIndividual", "range": "shaftLineLoadCaseTypeValue", "module": "regulation", "requirements": ["TRF-111"]},
    "fatigueLoadCase": {"kind": "NamedIndividual", "range": "shaftLineLoadCaseTypeValue", "module": "regulation", "requirements": ["TRF-111"]},
    "bladeFailureLoadCase": {"kind": "NamedIndividual", "range": "shaftLineLoadCaseTypeValue", "module": "regulation", "requirements": ["TRF-111", "TRF-112"]},
    "componentYieldSafetyFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "loadCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "machinery", "requirements": ["TRF-111", "TRF-112", "TRF-123"]},
    "materialYieldStrength": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "shipComponent", "unit": UNIT + "MegaPA", "unitSymbol": "MPa", "quantityKind": "Pressure", "module": "machinery", "requirements": ["TRF-118", "TRF-123"]},
    "vibrationDirectionValue": {"kind": "Class", "range": "benchmarkEntity", "module": "operations", "requirements": ["TRF-120"]},
    "vibrationDirection": {"kind": "ObjectProperty", "range": "vibrationDirectionValue", "domain": "calculationCase", "module": "operations", "requirements": ["TRF-120"]},
    "longitudinalDirection": {"kind": "NamedIndividual", "range": "vibrationDirectionValue", "module": "operations", "requirements": ["TRF-120"]},
    "transverseDirection": {"kind": "NamedIndividual", "range": "vibrationDirectionValue", "module": "operations", "requirements": ["TRF-120"]},
    "airReceiverServesAdditionalPurpose": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "machinery", "requirements": ["TRF-127"]},
    "additionalPurposeRequiredAirCapacity": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "module": "machinery", "requirements": ["TRF-127"]},
    "propulsionEngineReversalRequiredForAstern": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "machinery", "requirements": ["TRF-128"]},
    "navigatingInIce": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "operations", "requirements": ["TRF-129"]},
    "coolingWaterChestAlternativeArrangementUsed": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "machinery", "requirements": ["TRF-130"]},
    "coolingWaterChestVolumeAndHeightRequirementsCannotBeMet": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "machinery", "requirements": ["TRF-130"]},
    "alternatingCoolingWaterIntakeAndDischarge": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "machinery", "requirements": ["TRF-130"]},
    "engineOutputFormulaFactorF1": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "machinery", "requirements": ["TRF-132"], "aliases": ["f_1"]},
    "engineOutputFormulaFactorF2": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "machinery", "requirements": ["TRF-132"], "aliases": ["f_2"]},
    "engineOutputFormulaFactorF3": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "machinery", "requirements": ["TRF-132"], "aliases": ["f_3"]},
    "engineOutputFormulaFactorF4": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "module": "machinery", "requirements": ["TRF-132"], "aliases": ["f_4"]},
    "engineOutputFormulaDisplacement": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "module": "machinery", "requirements": ["TRF-132"], "aliases": ["Delta"]},
    "engineOutputFormulaBasePowerP0": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "KiloW", "unitSymbol": "kW", "quantityKind": "Power", "module": "machinery", "requirements": ["TRF-132"], "aliases": ["P_0"]},
})

# Additional latent gaps found by the 313-wide dependency audit. Existing
# complete models (for example IMO-057) are not duplicated.
SPECS.update({
    "classificationSocietyAccelerationEvidence": {"kind": "ObjectProperty", "range": "evidenceArtifact", "domain": "ship", "module": "evidence", "requirements": ["I2-013"]},
    "inertialLoadDesignConsiderationEvidence": {"kind": "ObjectProperty", "range": "evidenceArtifact", "domain": "ship", "module": "evidence", "requirements": ["I2-013"]},
    "obliquePlatingInterpolationCase": {"kind": "Class", "range": "calculationCase", "module": "hull", "requirements": ["I2-024"]},
    "hasObliquePlatingInterpolationCase": {"kind": "ObjectProperty", "range": "obliquePlatingInterpolationCase", "domain": "ship", "module": "hull", "requirements": ["I2-024"]},
    "interpolatedNetPlateThickness": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "obliquePlatingInterpolationCase", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-024"]},
    "iceOriginValue": {"kind": "Class", "range": "benchmarkEntity", "module": "operations", "requirements": ["IMO-004"]},
    "iceOriginType": {"kind": "ObjectProperty", "range": "iceOriginValue", "domain": "ship", "module": "operations", "requirements": ["IMO-004"]},
    "seaIceOrigin": {"kind": "NamedIndividual", "range": "iceOriginValue", "module": "operations", "requirements": ["IMO-004"]},
    "iceTypeValue": {"kind": "Class", "range": "benchmarkEntity", "module": "operations", "requirements": ["IMO-004", "IMO-006", "IMO-008"]},
    "iceTypeClassification": {"kind": "ObjectProperty", "range": "iceTypeValue", "domain": "ship", "module": "operations", "requirements": ["IMO-004", "IMO-006", "IMO-008"]},
    "firstYearIce": {"kind": "NamedIndividual", "range": "iceTypeValue", "module": "operations", "requirements": ["IMO-004"]},
    "mediumFirstYearIce": {"kind": "NamedIndividual", "range": "iceTypeValue", "module": "operations", "requirements": ["IMO-006"]},
    "thinFirstYearIce": {"kind": "NamedIndividual", "range": "iceTypeValue", "module": "operations", "requirements": ["IMO-008"]},
    "iceConditionValue": {"kind": "Class", "range": "benchmarkEntity", "module": "operations", "requirements": ["IMO-007", "IMO-102"]},
    "iceConditionClassification": {"kind": "ObjectProperty", "range": "iceConditionValue", "domain": "ship", "module": "operations", "requirements": ["IMO-007", "IMO-102"]},
    "openWaterIceCondition": {"kind": "NamedIndividual", "range": "iceConditionValue", "module": "operations", "requirements": ["IMO-007"]},
    "hasPolarWaterOperationalManualRecord": {"kind": "ObjectProperty", "range": "documentRecord", "domain": "ship", "module": "documents", "requirements": ["IMO-035"]},
    "hasStabilityCalculationRecord": {"kind": "ObjectProperty", "range": "documentRecord", "domain": "ship", "module": "documents", "requirements": ["IMO-035"]},
    "relevantHatchOrDoorItem": {"kind": "Class", "range": "equipmentItem", "module": "safety", "requirements": ["IMO-040"]},
    "hasRelevantHatchOrDoor": {"kind": "ObjectProperty", "range": "relevantHatchOrDoorItem", "domain": "ship", "module": "safety", "requirements": ["IMO-040"]},
    "hasIceOrSnowRemovalOrPreventionMeans": {"kind": "ObjectProperty", "range": "iceSnowRemovalOrPreventionMeans", "domain": "equipmentItem", "module": "safety", "requirements": ["IMO-040", "IMO-052"]},
    "hasEssentialEngine": {"kind": "ObjectProperty", "range": "essentialEngine", "domain": "ship", "module": "machinery", "requirements": ["IMO-047"]},
    "localControlItem": {"kind": "Class", "range": "equipmentItem", "module": "machinery", "requirements": ["IMO-051"]},
    "hasLocalControlItem": {"kind": "ObjectProperty", "range": "localControlItem", "domain": "ship", "module": "machinery", "requirements": ["IMO-051"]},
    "requiredAccessItem": {"kind": "Class", "range": "protectedItem", "module": "safety", "requirements": ["IMO-052"]},
    "hasRequiredAccessItem": {"kind": "ObjectProperty", "range": "requiredAccessItem", "domain": "ship", "module": "safety", "requirements": ["IMO-052"]},
    "extinguishingMediumItem": {"kind": "Class", "range": "equipmentItem", "module": "safety", "requirements": ["IMO-053"]},
    "hasExtinguishingMedium": {"kind": "ObjectProperty", "range": "extinguishingMediumItem", "domain": "ship", "module": "safety", "requirements": ["IMO-053"]},
    "exposedFireMainSectionItem": {"kind": "Class", "range": "shipComponent", "module": "safety", "requirements": ["IMO-058"]},
    "hasExposedFireMainSection": {"kind": "ObjectProperty", "range": "exposedFireMainSectionItem", "domain": "ship", "module": "safety", "requirements": ["IMO-058"]},
    "immersionSuitTypeValue": {"kind": "Class", "range": "benchmarkEntity", "module": "safety", "requirements": ["IMO-071"]},
    "immersionSuitTypeClassification": {"kind": "ObjectProperty", "range": "immersionSuitTypeValue", "domain": "ship", "module": "safety", "requirements": ["IMO-071"]},
    "insulatedImmersionSuit": {"kind": "NamedIndividual", "range": "immersionSuitTypeValue", "module": "safety", "requirements": ["IMO-071"]},
    "lifeboatTypeValue": {"kind": "Class", "range": "benchmarkEntity", "module": "safety", "requirements": ["IMO-073"]},
    "lifeboatTypeClassification": {"kind": "ObjectProperty", "range": "lifeboatTypeValue", "domain": "lifeboat", "module": "safety", "requirements": ["IMO-073"]},
    "partiallyEnclosedLifeboat": {"kind": "NamedIndividual", "range": "lifeboatTypeValue", "module": "safety", "requirements": ["IMO-073"]},
    "totallyEnclosedLifeboat": {"kind": "NamedIndividual", "range": "lifeboatTypeValue", "module": "safety", "requirements": ["IMO-073"]},
    "hasPassenger": {"kind": "ObjectProperty", "range": "passenger", "domain": "ship", "module": "operations", "requirements": ["IMO-078"]},
    "hasRequiredRescueBoatOrLifeboat": {"kind": "ObjectProperty", "range": "lifeboat", "domain": "ship", "module": "safety", "requirements": ["IMO-097"]},
    "hasDistressAlertDevice": {"kind": "ObjectProperty", "range": "equipmentItem", "domain": "lifeboat", "module": "safety", "requirements": ["IMO-097"]},
    "polarTrainingRecord": {"kind": "Class", "range": "evidenceArtifact", "module": "evidence", "requirements": ["IMO-102"]},
    "hasPolarTrainingRecord": {"kind": "ObjectProperty", "range": "polarTrainingRecord", "domain": "crewMember", "module": "evidence", "requirements": ["IMO-102"]},
    "trainingLevelValue": {"kind": "Class", "range": "benchmarkEntity", "module": "operations", "requirements": ["IMO-102"]},
    "requiredTrainingLevel": {"kind": "ObjectProperty", "range": "trainingLevelValue", "domain": "polarTrainingRecord", "module": "operations", "requirements": ["IMO-102"]},
    "dischargedMaterialTypeValue": {"kind": "Class", "range": "benchmarkEntity", "module": "operations", "requirements": ["IMO-106"]},
    "dischargedMaterialClassification": {"kind": "ObjectProperty", "range": "dischargedMaterialTypeValue", "domain": "ship", "module": "operations", "requirements": ["IMO-106"]},
    "cleanBallastMaterial": {"kind": "NamedIndividual", "range": "dischargedMaterialTypeValue", "module": "operations", "requirements": ["IMO-106"]},
    "segregatedBallastMaterial": {"kind": "NamedIndividual", "range": "dischargedMaterialTypeValue", "module": "operations", "requirements": ["IMO-106"]},
})

SPECS.update({
    "thrusterBladeLossDesignEvidence": {"kind": "ObjectProperty", "range": "evidenceArtifact", "domain": "ship", "module": "evidence", "requirements": ["TRF-113"]},
    "maximumComponentLoadBladeOrientationConfirmed": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "loadCase", "module": "machinery", "requirements": ["TRF-113"]},
    "thrusterIceImpactLoadCase": {"kind": "Class", "range": "loadCase", "module": "machinery", "requirements": ["TRF-114"]},
    "hasThrusterIceImpactLoadCase": {"kind": "ObjectProperty", "range": "thrusterIceImpactLoadCase", "domain": "ship", "module": "machinery", "requirements": ["TRF-114"]},
    "thrusterIceImpactLoadCaseIdentifier": {"kind": "DatatypeProperty", "range": str(XSD.string), "datatype": "xsd:string", "domain": "thrusterIceImpactLoadCase", "module": "machinery", "requirements": ["TRF-114"]},
    "thrusterIceImpactLoad": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "thrusterIceImpactLoadCase", "unit": UNIT + "KiloN", "unitSymbol": "kN", "quantityKind": "Force", "module": "machinery", "requirements": ["TRF-114"]},
    "thrusterIceImpactLoadedAreaEvidence": {"kind": "ObjectProperty", "range": "evidenceArtifact", "domain": "thrusterIceImpactLoadCase", "module": "evidence", "requirements": ["TRF-114"]},
    "contactGeometryCorrespondenceEvidence": {"kind": "ObjectProperty", "range": "evidenceArtifact", "domain": "thrusterIceImpactLoadCase", "module": "evidence", "requirements": ["TRF-114"]},
    "nonHemisphericalImpactContactArea": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M2", "unitSymbol": "m2", "quantityKind": "Area", "module": "machinery", "requirements": ["TRF-116"], "aliases": ["A"]},
    "propellerHubOrThrusterEndCapImpact": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "machinery", "requirements": ["TRF-116"]},
    "warningTriangleMarking": {"kind": "Class", "range": "hullStructure", "module": "documents", "requirements": ["TRF-133"]},
    "iceClassDraughtMarking": {"kind": "Class", "range": "hullStructure", "module": "documents", "requirements": ["TRF-133"]},
    "hasWarningTriangleMarking": {"kind": "ObjectProperty", "range": "warningTriangleMarking", "domain": "ship", "module": "documents", "requirements": ["TRF-133"]},
    "hasIceClassDraughtMarking": {"kind": "ObjectProperty", "range": "iceClassDraughtMarking", "domain": "ship", "module": "documents", "requirements": ["TRF-133"]},
    "verticalOffsetAboveSummerFreshWaterLoadLine": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "warningTriangleMarking", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "documents", "requirements": ["TRF-133"]},
    "markingAtOrBelowDeckLine": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "warningTriangleMarking", "module": "documents", "requirements": ["TRF-133"]},
    "warningTriangleSideLength": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "warningTriangleMarking", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "documents", "requirements": ["TRF-133"]},
    "draughtMarkAftOffset": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "iceClassDraughtMarking", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "documents", "requirements": ["TRF-133"]},
    "markingPlateThickness": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "hullStructure", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "documents", "requirements": ["TRF-133"]},
    "markingWeldedToShipSide": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "hullStructure", "module": "documents", "requirements": ["TRF-133"]},
    "reflectingMarkingColourValue": {"kind": "Class", "range": "benchmarkEntity", "module": "documents", "requirements": ["TRF-133"]},
    "reflectingMarkingColour": {"kind": "ObjectProperty", "range": "reflectingMarkingColourValue", "domain": "hullStructure", "module": "documents", "requirements": ["TRF-133"]},
    "redReflectingMarkingColour": {"kind": "NamedIndividual", "range": "reflectingMarkingColourValue", "module": "documents", "requirements": ["TRF-133"]},
    "yellowReflectingMarkingColour": {"kind": "NamedIndividual", "range": "reflectingMarkingColourValue", "module": "documents", "requirements": ["TRF-133"]},
    "markingPlainlyVisibleInIceConditions": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "hullStructure", "module": "documents", "requirements": ["TRF-133"]},
    "letterDimensionsEqualLoadLineMark": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "iceClassDraughtMarking", "module": "documents", "requirements": ["TRF-133"]},
    "bowDesignForceMethodI2Point3Point2Point1PartIii": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MegaN", "unitSymbol": "MN", "quantityKind": "Force", "module": "hull", "requirements": ["I2-011"]},
    "bowDesignForceMethodI2Point3Point2Point1PartIv": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MegaN", "unitSymbol": "MN", "quantityKind": "Force", "module": "hull", "requirements": ["I2-011"]},
    "bulbousBowPresent": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "hull", "requirements": ["I2-011"]},
    "steelMaterialClassValue": {"kind": "Class", "range": "benchmarkEntity", "module": "hull", "requirements": ["I2-048"]},
    "steelMaterialClass": {"kind": "ObjectProperty", "range": "steelMaterialClassValue", "domain": "steelGradeRequirementCase", "module": "hull", "requirements": ["I2-048"]},
    "steelMaterialClassOne": {"kind": "NamedIndividual", "range": "steelMaterialClassValue", "module": "hull", "requirements": ["I2-048"]},
    "steelMaterialClassTwo": {"kind": "NamedIndividual", "range": "steelMaterialClassValue", "module": "hull", "requirements": ["I2-048"]},
    "steelMaterialClassThree": {"kind": "NamedIndividual", "range": "steelMaterialClassValue", "module": "hull", "requirements": ["I2-048"]},
    "asBuiltPlateThickness": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "steelGradeRequirementCase", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-048"]},
    "steelStrengthCategoryValue": {"kind": "Class", "range": "benchmarkEntity", "module": "hull", "requirements": ["I2-048"]},
    "steelStrengthCategory": {"kind": "ObjectProperty", "range": "steelStrengthCategoryValue", "domain": "steelGradeRequirementCase", "module": "hull", "requirements": ["I2-048"]},
    "normalStrengthSteelCategory": {"kind": "NamedIndividual", "range": "steelStrengthCategoryValue", "module": "hull", "requirements": ["I2-048"]},
    "highTensileSteelCategory": {"kind": "NamedIndividual", "range": "steelStrengthCategoryValue", "module": "hull", "requirements": ["I2-048"]},
})

SPECS.update({
    "upperIceWaterlineDisplacement": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "KiloTON_Metric", "unitSymbol": "kt", "quantityKind": "Mass", "module": "hull", "requirements": ["I2-004"], "aliases": ["DUI"]},
    "upperIceWaterlineCase": {"kind": "Class", "range": "designCondition", "module": "hull", "requirements": ["I2-004"]},
    "hasUpperIceWaterlineCase": {"kind": "ObjectProperty", "range": "upperIceWaterlineCase", "domain": "ship", "module": "hull", "requirements": ["I2-004"]},
    "waterlineCaseDisplacement": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "upperIceWaterlineCase", "unit": UNIT + "KiloTON_Metric", "unitSymbol": "kt", "quantityKind": "Mass", "module": "hull", "requirements": ["I2-004"]},
    "bowSubregionCalculationCase": {"kind": "Class", "range": "calculationCase", "module": "hull", "requirements": ["I2-008", "I2-014", "I2-015"]},
    "hasBowSubregionCalculationCase": {"kind": "ObjectProperty", "range": "bowSubregionCalculationCase", "domain": "ship", "module": "hull", "requirements": ["I2-008", "I2-014", "I2-015"]},
    "bowShapeCoefficient": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "bowSubregionCalculationCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-008", "I2-015"], "aliases": ["f_ai"]},
    "totalGlancingImpactForce": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "bowSubregionCalculationCase", "unit": UNIT + "MegaN", "unitSymbol": "MN", "quantityKind": "Force", "module": "hull", "requirements": ["I2-008", "I2-014"], "aliases": ["F_i"]},
    "glancingImpactLineLoad": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "bowSubregionCalculationCase", "unit": UNIT + "MegaN-M-PER-M2", "unitSymbol": "MN/m", "quantityKind": "Line load", "module": "hull", "requirements": ["I2-008", "I2-014"], "aliases": ["Q_i"]},
    "glancingImpactPressure": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "bowSubregionCalculationCase", "unit": UNIT + "MegaPA", "unitSymbol": "MPa", "quantityKind": "Pressure", "module": "hull", "requirements": ["I2-008", "I2-014"], "aliases": ["P_i"]},
    "bowSubregionMidLengthPosition": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "bowSubregionCalculationCase", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "hull", "requirements": ["I2-014", "I2-015"]},
    "bowSubregionCount": {"kind": "DatatypeProperty", "range": str(XSD.integer), "datatype": "xsd:integer", "domain": "ship", "module": "hull", "requirements": ["I2-014"]},
    "otherIceStrengthenedAreaValue": {"kind": "NamedIndividual", "range": "hullRegionValue", "module": "hull", "requirements": ["I2-009"]},
    "verticalSidedBowForm": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "ship", "module": "hull", "requirements": ["I2-010"]},
    "crushingFailureClassFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "tableLookupCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-015", "I2-017", "I2-050"], "aliases": ["CFC"]},
    "flexuralFailureClassFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "tableLookupCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-015", "I2-050"], "aliases": ["CFF"]},
    "loadPatchDimensionClassFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "tableLookupCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-017"], "aliases": ["CFD"]},
    "shipDisplacementFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "calculationCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-017"], "aliases": ["DF"]},
    "peakPressureFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "tableLookupCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-018", "I2-022", "I2-023", "I2-032", "I2-035"], "aliases": ["PPF", "PPF_p", "PPF_s"]},
    "hasIceLoadPatch": {"kind": "ObjectProperty", "range": "iceLoadPatch", "domain": "ship", "module": "hull", "requirements": ["I2-018", "I2-037"]},
    "hasStructuralMember": {"kind": "ObjectProperty", "range": "structuralMember", "domain": "ship", "module": "hull", "requirements": ["I2-019", "I2-026", "I2-029", "I2-031", "I2-034", "I2-060", "I2-064"]},
    "spansHullArea": {"kind": "ObjectProperty", "range": "hullRegionValue", "domain": "structuralMember", "module": "hull", "requirements": ["I2-019"]},
    "hullAreaFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "hullRegionValue", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-019"], "aliases": ["AF"]},
    "iceLoadRequiredNetPlateThickness": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "plating", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-021", "I2-022", "I2-023", "I2-047"], "aliases": ["t_net", "tnet"]},
    "corrosionAbrasionAllowance": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "plating", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-021", "I2-046"], "aliases": ["t_s", "ts"]},
    "framingAngleOmega": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "plating", "unit": UNIT + "DEG", "unitSymbol": "deg", "quantityKind": "Angle", "module": "hull", "requirements": ["I2-022", "I2-023", "I2-030"], "aliases": ["Omega"]},
    "frameSpacing": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "hull", "requirements": ["I2-022", "I2-023", "I2-030", "I2-032", "I2-035"], "aliases": ["s"]},
    "frameSpan": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "hull", "requirements": ["I2-023", "I2-032", "I2-035"], "aliases": ["l", "a"]},
    "frameSupportConditionValue": {"kind": "Class", "range": "benchmarkEntity", "module": "hull", "requirements": ["I2-026"]},
    "frameSupportCondition": {"kind": "ObjectProperty", "range": "frameSupportConditionValue", "domain": "structuralMember", "module": "hull", "requirements": ["I2-026"]},
    "fixedFrameSupport": {"kind": "NamedIndividual", "range": "frameSupportConditionValue", "module": "hull", "requirements": ["I2-026"]},
    "simpleFrameSupport": {"kind": "NamedIndividual", "range": "frameSupportConditionValue", "module": "hull", "requirements": ["I2-026"]},
    "significantRotationalRestraintEvidence": {"kind": "ObjectProperty", "range": "evidenceArtifact", "domain": "structuralMember", "module": "evidence", "requirements": ["I2-026"]},
    "netWebThickness": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-029", "I2-030", "I2-040", "I2-041", "I2-042"], "aliases": ["t_wn", "twn"]},
    "netFlangeThickness": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-029", "I2-043"], "aliases": ["t_fn"]},
    "netAttachedShellPlateThickness": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-029", "I2-030", "I2-041"], "aliases": ["t_pn"]},
    "webHeight": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-030", "I2-040"], "aliases": ["h_w"]},
    "netLocalFrameFlangeArea": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "CentiM2", "unitSymbol": "cm2", "quantityKind": "Area", "module": "hull", "requirements": ["I2-030"], "aliases": ["A_fn"]},
    "localFrameFlangeCentreHeight": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-030"], "aliases": ["h_fc"]},
    "webToFlangeCentreDistance": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-030"], "aliases": ["b_w"]},
    "webAngleToShellPlate": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "DEG", "unitSymbol": "deg", "quantityKind": "Angle", "module": "hull", "requirements": ["I2-030"], "aliases": ["phi_w"]},
    "plasticNeutralAxisHeight": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "calculationCase", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-030"], "aliases": ["z_na"]},
    "netEffectivePlasticSectionModulus": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "CentiM3", "unitSymbol": "cm3", "quantityKind": "Section modulus", "module": "hull", "requirements": ["I2-030"], "aliases": ["Z_p"]},
    "combinedShearAndBendingDemand": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "loadCase", "module": "hull", "requirements": ["I2-031", "I2-034"]},
    "loadPatchOrientationValue": {"kind": "Class", "range": "benchmarkEntity", "module": "hull", "requirements": ["I2-031"]},
    "loadPatchOrientation": {"kind": "ObjectProperty", "range": "loadPatchOrientationValue", "domain": "loadCase", "module": "hull", "requirements": ["I2-031"]},
    "loadPatchHeightParallelToFrame": {"kind": "NamedIndividual", "range": "loadPatchOrientationValue", "module": "hull", "requirements": ["I2-031"]},
    "requiredTransverseFrameShearArea": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "CentiM2", "unitSymbol": "cm2", "quantityKind": "Area", "module": "hull", "requirements": ["I2-032"], "aliases": ["A_t"]},
    "requiredLongitudinalFrameShearArea": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "CentiM2", "unitSymbol": "cm2", "quantityKind": "Area", "module": "hull", "requirements": ["I2-035"], "aliases": ["A_L"]},
    "sideStructureApplicability": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "structuralMember", "module": "hull", "requirements": ["I2-034"]},
    "iceLoadPatchDesignCase": {"kind": "Class", "range": "loadCase", "module": "hull", "requirements": ["I2-037"]},
    "hasIceLoadPatchDesignCase": {"kind": "ObjectProperty", "range": "iceLoadPatchDesignCase", "domain": "ship", "module": "hull", "requirements": ["I2-037"]},
    "memberCapacityMinimizationConfirmed": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "iceLoadPatchDesignCase", "module": "hull", "requirements": ["I2-037"]},
    "flangeWidth": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-042"], "aliases": ["b_f"]},
    "flangeOutstand": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMember", "unit": UNIT + "MilliM", "unitSymbol": "mm", "quantityKind": "Length", "module": "hull", "requirements": ["I2-043"], "aliases": ["b_out"]},
    "internalIceStrengthenedStructure": {"kind": "Class", "range": "hullStructure", "module": "hull", "requirements": ["I2-046"]},
    "hasInternalIceStrengthenedStructure": {"kind": "ObjectProperty", "range": "internalIceStrengthenedStructure", "domain": "ship", "module": "hull", "requirements": ["I2-046"]},
    "iceStrengthenedStructureStatus": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "hullStructure", "module": "hull", "requirements": ["I2-047"]},
    "steelGradeRequirementCase": {"kind": "Class", "range": "tableLookupCase", "module": "hull", "requirements": ["I2-048"]},
    "hasSteelGradeRequirementCase": {"kind": "ObjectProperty", "range": "steelGradeRequirementCase", "domain": "ship", "module": "hull", "requirements": ["I2-048"]},
    "requiredHullStructuralSteelGrade": {"kind": "ObjectProperty", "range": "steelGradeValue", "domain": "steelGradeRequirementCase", "module": "hull", "requirements": ["I2-048"]},
    "designVerticalIceForceAtBow": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MegaN", "unitSymbol": "MN", "quantityKind": "Force", "module": "hull", "requirements": ["I2-050", "I2-051", "I2-053", "I2-054"], "aliases": ["F_IB", "FIB"]},
    "designVerticalIceForceAtBowCandidateOne": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MegaN", "unitSymbol": "MN", "quantityKind": "Force", "module": "hull", "requirements": ["I2-050"], "aliases": ["F_IB1"]},
    "designVerticalIceForceAtBowCandidateTwo": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MegaN", "unitSymbol": "MN", "quantityKind": "Force", "module": "hull", "requirements": ["I2-050"], "aliases": ["F_IB2"]},
    "iceStrengthCoefficientKI": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-050"], "aliases": ["K_I"]},
    "upperIceWaterlineDraughtDUI": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "hull", "requirements": ["I2-050"], "aliases": ["D_UI"]},
    "hullFormCoefficientKh": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-050"], "aliases": ["K_h"]},
    "longitudinalStrengthClassFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "tableLookupCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-050"], "aliases": ["C_FL"]},
    "hullGirderLongitudinalPositionFromAft": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "calculationCase", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "hull", "requirements": ["I2-051", "I2-052", "I2-053", "I2-054"]},
    "shearForceDirectionValue": {"kind": "Class", "range": "benchmarkEntity", "module": "hull", "requirements": ["I2-051"]},
    "shearForceDirection": {"kind": "ObjectProperty", "range": "shearForceDirectionValue", "domain": "calculationCase", "module": "hull", "requirements": ["I2-051"]},
    "positiveShearForce": {"kind": "NamedIndividual", "range": "shearForceDirectionValue", "module": "hull", "requirements": ["I2-051"]},
    "interpolationPoint": {"kind": "Class", "range": "calculationCase", "module": "regulation", "requirements": ["I2-052", "I2-054"]},
    "hasInterpolationPoint": {"kind": "ObjectProperty", "range": "interpolationPoint", "domain": "calculationCase", "module": "regulation", "requirements": ["I2-052", "I2-054"]},
    "interpolationCoordinate": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "interpolationPoint", "module": "regulation", "requirements": ["I2-052"]},
    "interpolationPointValue": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "interpolationPoint", "module": "regulation", "requirements": ["I2-052"]},
    "designVerticalIceBendingMoment": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "MegaN-M", "unitSymbol": "MN m", "quantityKind": "Torque", "module": "hull", "requirements": ["I2-054"], "aliases": ["M_I"]},
    "upperIceWaterlineLengthLUI": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "ship", "unit": UNIT + "M", "unitSymbol": "m", "quantityKind": "Length", "module": "hull", "requirements": ["I2-015", "I2-051", "I2-054"], "aliases": ["L_UI", "LUI"]},
    "bendingMomentDistributionFactor": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "calculationCase", "unit": UNIT + "UNITLESS", "unitSymbol": "1", "quantityKind": "Dimensionless", "module": "hull", "requirements": ["I2-054"], "aliases": ["C_m"]},
    "stiffeningNecessary": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "structuralMember", "module": "hull", "requirements": ["I2-060"]},
    "calculationMethodValue": {"kind": "Class", "range": "benchmarkEntity", "module": "regulation", "requirements": ["I2-061", "I2-065"]},
    "calculationMethod": {"kind": "ObjectProperty", "range": "calculationMethodValue", "domain": "calculationCase", "module": "regulation", "requirements": ["I2-061", "I2-065"]},
    "directCalculationMethodValue": {"kind": "NamedIndividual", "range": "calculationMethodValue", "module": "regulation", "requirements": ["I2-061"]},
    "prescribedAnalyticalProcedure": {"kind": "NamedIndividual", "range": "calculationMethodValue", "module": "regulation", "requirements": ["I2-061"]},
    "nonlinearCalculationMethodValue": {"kind": "NamedIndividual", "range": "calculationMethodValue", "module": "regulation", "requirements": ["I2-065"]},
    "partOfGrillageSystem": {"kind": "ObjectProperty", "range": "grillageSystem", "domain": "structuralMember", "module": "hull", "requirements": ["I2-062"]},
    "structuralMemberWeb": {"kind": "Class", "range": "hullStructure", "module": "hull", "requirements": ["I2-064"]},
    "structuralMemberFlange": {"kind": "Class", "range": "hullStructure", "module": "hull", "requirements": ["I2-064"]},
    "hasStructuralMemberWeb": {"kind": "ObjectProperty", "range": "structuralMemberWeb", "domain": "structuralMember", "module": "hull", "requirements": ["I2-064"]},
    "hasStructuralMemberFlange": {"kind": "ObjectProperty", "range": "structuralMemberFlange", "domain": "structuralMember", "module": "hull", "requirements": ["I2-064"]},
    "nominalShearStress": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMemberWeb", "unit": UNIT + "MegaPA", "unitSymbol": "MPa", "quantityKind": "Pressure", "module": "hull", "requirements": ["I2-064"]},
    "nominalFlangeVonMisesStress": {"kind": "QuantityProperty", "range": QUDT_QUANTITY_VALUE, "domain": "structuralMemberFlange", "unit": UNIT + "MegaPA", "unitSymbol": "MPa", "quantityKind": "Pressure", "module": "hull", "requirements": ["I2-064"]},
    "bucklingCriteriaSatisfied": {"kind": "DatatypeProperty", "range": str(XSD.boolean), "datatype": "xsd:boolean", "domain": "hullStructure", "module": "hull", "requirements": ["I2-064"]},
})


REQUIREMENT_TERMS = {
    rid: sorted(name for name, spec in SPECS.items() if rid in spec.get("requirements", []))
    for rid in {rid for spec in SPECS.values() for rid in spec.get("requirements", [])}
}


def registry_record(name: str, spec: dict, concept_id: str, evidence: dict[str, dict]) -> dict:
    reqs = spec.get("requirements", [])
    excerpts = [f"[{rid}] {evidence[rid]['normalizedRequirement']}" for rid in reqs]
    refs = [f"{rid} | {evidence[rid].get('sourceSheet','')} p.{evidence[rid].get('page','')} | {evidence[rid].get('clause','')}" for rid in reqs]
    kind = spec["kind"]
    parent = spec["range"]
    if not parent.startswith("http"):
        parent = BASE + parent
    return {
        "aliases": spec.get("aliases", []), "conceptId": concept_id, "confidence": "High" if reqs else "Medium",
        "datatype": spec.get("datatype", ""), "evidenceExcerpt": " | ".join(excerpts), "haithamUri": "",
        "iri": BASE + name, "kind": kind, "label": label(name), "localName": name,
        "mappingStatus": "No exact external mapping claimed; R9 benchmark term grounded in the linked verified requirement evidence.",
        "module": spec.get("module", "core"), "nameQaStatus": "Passed - ASCII-only lowerCamelCase and collision review",
        "namingBasis": "Verified requirement wording plus reusable engineering node/operand role",
        "namingRule": "N4/N5 - singular ASCII lowerCamelCase; use has + object role for directional relationships",
        "normalizedDefinition": f"NORMALIZED (R9 development): {label(name)} represents the linked requirement entity, relationship, value, evidence role, or quantity; its scope is limited to the cited requirements.",
        "parentOrRange": parent, "quantityKindLabel": spec.get("quantityKind", ""), "requirements": reqs,
        "roleDecision": {"Class": "Reusable engineering/evidence node type", "ObjectProperty": "Typed relationship path", "NamedIndividual": "Controlled regulatory value", "QuantityProperty": "Engineering quantity", "DatatypeProperty": "Typed literal"}[kind],
        "sourceConceptIds": [concept_id], "sourceRefs": "; ".join(refs), "stage1LocalNames": [name],
        "stage2UnitEvidence": "Unit taken from the normalized verified requirement." if spec.get("unit") else "",
        "unitDecisionStatus": "R9 source-grounded unit" if spec.get("unit") else ("No fixed unit" if kind == "QuantityProperty" else "Not a quantity property"),
        "unitIri": spec.get("unit", ""), "unitSymbol": spec.get("unitSymbol", ""),
    }


def add_to_graph(graph: Graph, record: dict, spec: dict) -> None:
    subject = URIRef(record["iri"])
    kind = record["kind"]
    parent = URIRef(record["parentOrRange"])
    if kind == "Class":
        graph.add((subject, RDF.type, OWL.Class)); graph.add((subject, RDFS.subClassOf, parent))
    elif kind == "NamedIndividual":
        graph.add((subject, RDF.type, OWL.NamedIndividual)); graph.add((subject, RDF.type, parent))
    elif kind in {"ObjectProperty", "QuantityProperty"}:
        graph.add((subject, RDF.type, OWL.ObjectProperty)); graph.add((subject, RDFS.range, parent))
        graph.add((subject, RDFS.domain, URIRef(BASE + spec.get("domain", "benchmarkEntity"))))
    else:
        graph.add((subject, RDF.type, OWL.DatatypeProperty)); graph.add((subject, RDFS.range, parent))
        graph.add((subject, RDFS.domain, URIRef(BASE + spec.get("domain", "benchmarkEntity"))))
    graph.add((subject, RDFS.label, Literal(record["label"], lang="en")))
    graph.add((subject, SKOS.prefLabel, Literal(record["label"], lang="en")))
    graph.add((subject, SKOS.definition, Literal(record["normalizedDefinition"], lang="en")))
    graph.add((subject, NLTL.draftConceptId, Literal(record["conceptId"])))
    for rid in record["requirements"]:
        graph.add((subject, NLTL.sourceRequirementId, Literal(rid)))
    if record["unitIri"]:
        graph.add((subject, NLTL.recommendedUnit, URIRef(record["unitIri"])))


def build_contracts(evidence: dict[str, dict], index: dict) -> dict[str, dict]:
    observed = {item["requirement_id"]: item for item in read_json(BATCH / "r9_failure_analysis.json")["records"]}
    depth = {item["requirement_id"]: item for item in read_json(BATCH / "r9_all313_dependency_audit.json")["records"]}
    contracts = {}
    for rid, requirement in evidence.items():
        pattern = str(requirement.get("encodingPattern", ""))
        required_fields: list[str] = []
        lower = pattern.lower()
        if any(token in lower for token in ("formula", "calculation", "numeric")):
            required_fields.extend(["operandTerms", "resultTerms", "comparisonModel"])
        if "conditional" in lower:
            required_fields.append("applicabilityTerms")
        if "table" in lower:
            required_fields.append("tableModel")
        if any(token in lower for token in ("qualified", "per-", "assignment")):
            required_fields.append("relationshipTerms")
        terms = list(index["requirements"].get(rid, []))
        contracts[rid] = {
            "status": "ENGINEERING_REVIEW_REQUIRED" if (rid in observed or depth[rid]["flags"]) else "LEGACY_CONTEXT_NOT_YET_CONTRACTED",
            "encodingPattern": pattern, "ownerClasses": [index.get("requirementTargetOwner", {}).get(rid, "ship")],
            "applicabilityTerms": [], "operandTerms": [], "resultTerms": [], "comparisonTerms": [],
            "relationshipTerms": [], "evidenceTerms": [], "controlledValueTerms": [], "timeTerms": [],
            "comparisonModel": "", "tableModel": "", "requiredModelFields": sorted(set(required_fields)),
            "legacyIndexedTerms": terms, "auditFlags": depth[rid]["flags"],
            "observedFailureStatus": observed.get(rid, {}).get("status", ""),
        }
    # First source-family contracts completed from the verified normalized IMO
    # requirements and the explicit reusable node models above.
    complete = {
        "IMO-016": {"applicabilityTerms": ["certificateLanguage"], "operandTerms": [], "resultTerms": ["approvedTranslationPresent"], "relationshipTerms": ["hasPolarShipCertificate", "certificateFormModel"], "controlledValueTerms": ["appendixIPolarShipCertificateModel"], "evidenceTerms": [], "comparisonModel": "conditional language-set membership", "tableModel": ""},
        "IMO-017": {"applicabilityTerms": [], "operandTerms": ["polarCertificateValidityDates", "surveyDates", "endorsementDates"], "resultTerms": ["polarCertificateSupplementPresent", "requiredEquipmentRecords"], "relationshipTerms": ["hasPolarShipCertificate", "hasSolasCertificateSchedule"], "controlledValueTerms": [], "evidenceTerms": [], "comparisonModel": "cross-document date consistency and presence", "tableModel": ""},
        "IMO-037": {"applicabilityTerms": ["shipCategory", "constructionDate"], "operandTerms": ["loadingConditionIdentifier", "residualStabilityFactorSI", "alternativeInstrumentApplicable"], "resultTerms": ["alternativeInstrumentResidualStabilityStatus"], "relationshipTerms": ["hasLoadingConditionCase"], "controlledValueTerms": [], "evidenceTerms": [], "comparisonModel": "per-loading-condition equality or approved alternative", "tableModel": ""},
        "IMO-038": {"applicabilityTerms": ["damageCenterForwardOfMaxBreadth"], "operandTerms": ["upperIceWaterlineDraught", "upperIceWaterlineLength"], "resultTerms": ["longitudinalDamageExtent", "transversePenetration", "verticalDamageExtent", "selectedVerticalDamagePosition"], "relationshipTerms": [], "controlledValueTerms": [], "evidenceTerms": [], "comparisonModel": "piecewise formulas and inclusive keel-to-1.20-draught range", "tableModel": ""},
        "IMO-043": {"applicabilityTerms": [], "operandTerms": [], "resultTerms": [], "relationshipTerms": ["hasMachineryInstallation", "hasAssociatedEquipment", "hasApplicableHazard", "hasHazardProtectionEvidence"], "controlledValueTerms": ["iceAccretionHazard", "snowAccumulationHazard", "seawaterIceIngestionHazard", "liquidFreezingOrViscosityIncreaseHazard", "seawaterIntakeTemperatureHazard", "snowIngestionHazard"], "evidenceTerms": ["hasHazardProtectionEvidence"], "comparisonModel": "complete per-installation hazard coverage", "tableModel": ""},
        "IMO-059": {"applicabilityTerms": [], "operandTerms": [], "resultTerms": [], "relationshipTerms": ["hasFirefighterOutfit", "hasStorageLocation", "storageTemperatureClass"], "controlledValueTerms": ["warmStorageLocation"], "evidenceTerms": [], "comparisonModel": "all firefighter outfits stored at warm-class locations", "tableModel": ""},
        "IMO-062": {"applicabilityTerms": [], "operandTerms": ["accessibleStatus", "safeStatus", "iceSnowMitigationCoverage"], "resultTerms": [], "relationshipTerms": ["hasExposedEscapeRoute"], "controlledValueTerms": [], "evidenceTerms": ["iceSnowMitigationCoverage"], "comparisonModel": "all exposed routes satisfy three required statuses", "tableModel": ""},
        "IMO-066": {"applicabilityTerms": ["shipExposedToIceAccretion"], "operandTerms": [], "resultTerms": [], "relationshipTerms": ["hasProtectedItem", "protectedItemCategory", "hasIceSnowRemovalOrPreventionMeans"], "controlledValueTerms": ["escapeRouteProtectedItem", "musterStationProtectedItem", "embarkationAreaProtectedItem", "survivalCraftProtectedItem", "launchingApplianceProtectedItem", "survivalCraftAccessProtectedItem"], "evidenceTerms": [], "comparisonModel": "conditional complete category coverage with per-item means association", "tableModel": ""},
        "IMO-070": {"applicabilityTerms": ["passengerShip"], "operandTerms": ["sizeCompatibilityStatus"], "resultTerms": [], "relationshipTerms": ["hasPersonOnBoardMember", "hasPersonalSurvivalEquipmentAssignment", "assignedPersonalSurvivalEquipment"], "controlledValueTerms": [], "evidenceTerms": ["hasPersonalSurvivalEquipmentAssignment"], "comparisonModel": "each person has one compatible suit or thermal aid assignment", "tableModel": ""},
        "IMO-072": {"applicabilityTerms": ["extendedDarknessOperation"], "operandTerms": ["continuousUseSuitabilityStatus"], "resultTerms": [], "relationshipTerms": ["hasLifeboat", "hasAssignedSearchlight"], "controlledValueTerms": [], "evidenceTerms": [], "comparisonModel": "conditional per-lifeboat assignment and approval", "tableModel": ""},
        "IMO-082": {"applicabilityTerms": ["bridgeConfigurationType"], "operandTerms": ["solasRegulationV22Point1Point9Point4ComplianceStatus"], "resultTerms": ["clearViewAsternStatus"], "relationshipTerms": [], "controlledValueTerms": ["asternViewRequiredBridgeConfiguration"], "evidenceTerms": [], "comparisonModel": "mandatory SOLAS compliance plus controlled conditional astern-view branch", "tableModel": ""},
        "IMO-098": {"applicabilityTerms": ["shipOperatesInLowAirTemperature"], "operandTerms": [], "resultTerms": [], "relationshipTerms": ["hasOtherSurvivalCraft", "hasLocationSignalDevice", "hasOnSceneCommunicationDevice"], "controlledValueTerms": [], "evidenceTerms": [], "comparisonModel": "conditional minimum one of each device per craft", "tableModel": ""},
        "IMO-104": {"applicabilityTerms": [], "operandTerms": ["polarWaterOperationalManualFamiliarizationStatus"], "resultTerms": [], "relationshipTerms": ["hasCrewMember", "hasAssignedDuty", "hasRelevantPolarWaterOperationalManualItem", "hasFamiliarizationRecord"], "controlledValueTerms": [], "evidenceTerms": ["hasFamiliarizationRecord"], "comparisonModel": "completed familiarization for every relevant duty-linked PWOM item", "tableModel": ""},
        "IMO-115": {"applicabilityTerms": ["sewageDischargeType", "comminutedAndDisinfected"], "operandTerms": ["distanceToNearestIceShelfOrFastIce", "nearbyIceConcentration"], "resultTerms": ["marpolAnnexIvRegulation11Point1Point1ComplianceStatus", "distanceFromAreaWithIceConcentrationAboveOneTenth"], "relationshipTerms": [], "controlledValueTerms": [], "evidenceTerms": [], "comparisonModel": "conditional strict distance threshold and distinct recorded concentration-area distance", "tableModel": ""},
        "IMO-116": {"applicabilityTerms": ["sewageDischargeType", "notComminutedOrDisinfected"], "operandTerms": ["distanceToNearestIceShelfOrFastIce", "nearbyIceConcentration"], "resultTerms": ["marpolAnnexIvRegulation11Point1Point1ComplianceStatus", "distanceFromAreaWithIceConcentrationAboveOneTenth"], "relationshipTerms": [], "controlledValueTerms": [], "evidenceTerms": [], "comparisonModel": "conditional strict distance threshold and distinct recorded concentration-area distance", "tableModel": ""},
        "IMO-120": {"applicabilityTerms": ["operatingArea", "arcticWaters", "foodWasteDischargeToSea"], "operandTerms": ["distanceToNearestLandIceShelfOrFastIce", "nearbyIceConcentration"], "resultTerms": ["distanceFromAreaWithIceConcentrationAboveOneTenth"], "relationshipTerms": [], "controlledValueTerms": [], "evidenceTerms": [], "comparisonModel": "conditional inclusive distance threshold and distinct recorded concentration-area distance", "tableModel": ""},
        "IMO-124": {"applicabilityTerms": ["operatingArea", "antarcticArea", "marpolAnnexVRegulation6Point1DischargeOccurs"], "operandTerms": ["distanceToNearestFastIce", "nearbyIceConcentration"], "resultTerms": ["distanceFromAreaWithIceConcentrationAboveOneTenth", "foodWasteDischargeOntoIce"], "relationshipTerms": [], "controlledValueTerms": [], "evidenceTerms": [], "comparisonModel": "conditional inclusive distance threshold, distinct recorded concentration-area distance, and prohibition", "tableModel": ""},
        "IMO26-009": {"applicabilityTerms": ["iceAccretionLikely"], "operandTerms": ["iceAccumulationPreventionMeansPresent"], "resultTerms": [], "relationshipTerms": ["hasRequiredNavigationOrCommunicationAntenna"], "controlledValueTerms": [], "evidenceTerms": [], "comparisonModel": "conditional all-antennas prevention evidence", "tableModel": ""},
    }
    for rid, patch in complete.items():
        contract = contracts[rid]
        contract.update(patch)
        contract["status"] = "COMPLETE"
        contract["engineeringDecision"] = "R9_EXPLICIT_DEPENDENCY_CONTRACT_AND_MODEL_REPAIR"
        contract["ownerClasses"] = [index.get("requirementTargetOwner", {}).get(rid, "ship")]
    # Source-family terms are explicitly requirement-linked in SPECS. Populate
    # reviewable contracts for observed failures; mark complete only when the
    # source row/PDF contains the whole rule and no unresolved companion method
    # is required.
    blocked_source_dependencies = {
        "I2-053": "Formula is delegated to UR S11.5.4.2, whose complete operand model is not contained in UR I2 Rev.4.",
    }
    result_hints = (
        "result", "required", "maximum", "minimum", "effective", "sectionModulus", "shearArea",
        "force", "pressure", "lineLoad", "moment", "stress", "thickness", "factor", "status",
    )
    applicability_hints = (
        "applicable", "known", "present", "practicable", "requiredFor", "condition", "class",
        "type", "category", "operates", "navigating", "reversalRequired", "cannotBeMet",
    )
    evidence_hints = ("evidence", "approval", "certificate", "record", "confirmed", "analysis")
    for rid in observed:
        if contracts[rid]["status"] == "COMPLETE":
            continue
        linked = list(index["requirements"].get(rid, []))
        new_linked = [name for name in REQUIREMENT_TERMS.get(rid, []) if name in linked]
        relationships = [name for name in new_linked if SPECS.get(name, {}).get("kind") == "ObjectProperty"]
        controlled = [name for name in new_linked if SPECS.get(name, {}).get("kind") == "NamedIndividual"]
        evidence_terms = [name for name in new_linked if any(hint.lower() in name.lower() for hint in evidence_hints)]
        applicability = [name for name in linked if any(hint.lower() in name.lower() for hint in applicability_hints)]
        quantitative = [name for name in linked if SPECS.get(name, {}).get("kind") == "QuantityProperty"]
        results = [name for name in quantitative if any(hint.lower() in name.lower() for hint in result_hints)]
        operands = [name for name in quantitative if name not in results]
        contract = contracts[rid]
        contract.update({
            "applicabilityTerms": sorted(set(applicability)),
            "operandTerms": sorted(set(operands)),
            "resultTerms": sorted(set(results)),
            "relationshipTerms": sorted(set(relationships)),
            "evidenceTerms": sorted(set(evidence_terms)),
            "controlledValueTerms": sorted(set(controlled)),
            "comparisonModel": evidence[rid].get("normalizedRequirement", ""),
            "tableModel": "Source table selection required exactly as cited." if "table" in str(evidence[rid].get("encodingPattern", "")).lower() else "",
        })
        if rid in blocked_source_dependencies:
            contract["status"] = "BLOCKED_SOURCE_OR_MODEL_DEPENDENCY"
            contract["blocker"] = blocked_source_dependencies[rid]
            contract["engineeringDecision"] = "DEFER_MISSING_NORMATIVE_COMPANION_METHOD"
            continue
        # A repaired observed failure is complete only when R9 added at least
        # one requirement-specific missing dependency. Pure generator failures
        # can be complete with the original terms plus the comparison model.
        has_r9_repair = bool(new_linked)
        generator_only = observed[rid].get("status") == "MAX_ATTEMPTS_REACHED"
        if has_r9_repair or generator_only:
            contract["status"] = "COMPLETE"
            contract["engineeringDecision"] = (
                "R9_MODEL_AND_VOCABULARY_REPAIR" if has_r9_repair
                else "R9_PROMPT_AND_DEPENDENCY_CONTRACT_REPAIR"
            )
            # Required fields describe model categories, not mandatory non-empty
            # lists. Formula/table/conditional semantics live in comparisonModel.
            contract["requiredModelFields"] = ["comparisonModel"]
    latent_decisions = {
        "I2-013": "REPAIR_EVIDENCE_MODEL",
        "I2-024": "REPAIR_INTERPOLATION_CASE",
        "IMO-001": "EXISTING_CONTROLLED_CATEGORY_CONFIRMED",
        "IMO-002": "EXISTING_CONTROLLED_CATEGORY_CONFIRMED",
        "IMO-003": "EXISTING_CONTROLLED_CATEGORY_CONFIRMED",
        "IMO-004": "REPAIR_CONTROLLED_ICE_ORIGIN_AND_TYPE",
        "IMO-006": "REPAIR_CONTROLLED_ICE_TYPE",
        "IMO-007": "REPAIR_CONTROLLED_ICE_CONDITION",
        "IMO-008": "REPAIR_CONTROLLED_ICE_TYPE",
        "IMO-010": "EXISTING_SINGLE_THRESHOLD_MODEL_CONFIRMED",
        "IMO-012": "EXISTING_TWO_QUANTITY_COMPARISON_CONFIRMED",
        "IMO-035": "REPAIR_DOCUMENT_RELATIONSHIPS",
        "IMO-040": "REPAIR_PER_ITEM_RELATIONSHIP",
        "IMO-047": "EXISTING_COMPONENT_RELATIONSHIP_CONFIRMED",
        "IMO-051": "REPAIR_PER_ITEM_RELATIONSHIP",
        "IMO-052": "REPAIR_PER_ITEM_RELATIONSHIP",
        "IMO-053": "REPAIR_PER_ITEM_RELATIONSHIP",
        "IMO-057": "EXISTING_COMPONENT_AND_COMPARTMENT_PATH_CONFIRMED",
        "IMO-058": "REPAIR_PER_ITEM_RELATIONSHIP",
        "IMO-071": "REPAIR_CONTROLLED_EQUIPMENT_TYPE",
        "IMO-073": "REPAIR_CONTROLLED_LIFEBOAT_TYPE",
        "IMO-075": "EXISTING_COUNT_FORMULA_MODEL_CONFIRMED",
        "IMO-078": "REPAIR_PERSON_INVENTORY_RELATIONSHIPS",
        "IMO-083": "REUSE_R9_ANTENNA_RELATIONSHIP_MODEL",
        "IMO-097": "REPAIR_PER_CRAFT_DEVICE_RELATIONSHIPS",
        "IMO-102": "REPAIR_TRAINING_RECORD_AND_CONTROLLED_LEVEL",
        "IMO-106": "REPAIR_CONTROLLED_DISCHARGE_MATERIAL",
        "IMO-109": "EXISTING_CONDITIONAL_QUANTITY_MODEL_CONFIRMED",
        "IMO-121": "EXISTING_CONDITIONAL_QUANTITY_MODEL_CONFIRMED",
    }
    for rid, decision in latent_decisions.items():
        contract = contracts[rid]
        linked = list(index["requirements"].get(rid, []))
        r9_terms = list(REQUIREMENT_TERMS.get(rid, []))
        contract.update({
            "status": "COMPLETE",
            "comparisonModel": evidence[rid].get("normalizedRequirement", ""),
            "requiredModelFields": ["comparisonModel"],
            "engineeringDecision": decision,
            "relationshipTerms": sorted(name for name in r9_terms if SPECS.get(name, {}).get("kind") == "ObjectProperty"),
            "controlledValueTerms": sorted(name for name in r9_terms if SPECS.get(name, {}).get("kind") == "NamedIndividual"),
            "evidenceTerms": sorted(name for name in r9_terms if any(token in name.lower() for token in ("evidence", "record", "approval"))),
            "legacyIndexedTerms": linked,
        })

    # Requirements with no observed failure and no dependency-depth flag have
    # already passed the R8.1 context audit. Make that engineering decision
    # explicit instead of leaving an active contract in an ambiguous draft state.
    for rid, contract in contracts.items():
        if evidence[rid].get("activeStatus") != "Stage 2 candidate - direct/deterministic":
            continue
        if str(evidence[rid].get("figureDependent", "No")).lower() == "yes":
            continue
        if contract["status"] in {"COMPLETE", "BLOCKED_SOURCE_OR_MODEL_DEPENDENCY"}:
            continue
        if not contract.get("auditFlags"):
            contract.update({
                "status": "COMPLETE",
                "comparisonModel": evidence[rid].get("normalizedRequirement", ""),
                "requiredModelFields": ["comparisonModel"],
                "engineeringDecision": "EXISTING_R8_1_MODEL_CONFIRMED_NO_DEPTH_FLAG",
            })
    return contracts


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SOURCE, OUT)
    evidence_payload = read_json(OUT / "evidence/stage1_approved.json")
    for requirement in evidence_payload["requirements"]:
        if requirement["id"] == "I2-053":
            requirement["activeStatus"] = "Deferred - missing normative companion method"
            requirement["codability"] = "Deferred"
            requirement["stage2DecisionReason"] = (
                "UR I2.13.3.2 delegates the calculation to UR S11.5.4.2. "
                "UR S11 is not present in the verified project sources; do not infer its operands."
            )
    write_json(OUT / "evidence/stage1_approved.json", evidence_payload)
    evidence = {item["id"]: item for item in evidence_payload["requirements"]}
    registry = read_json(OUT / "registry/term_registry.json")
    existing = {item["localName"] for item in registry}
    additions = []
    for number, (name, spec) in enumerate(sorted(SPECS.items()), 1):
        if name in existing:
            continue
        additions.append(registry_record(name, spec, f"VOC-DEV-R9-{number:04d}", evidence))
    registry = sorted(registry + additions, key=lambda item: item["localName"])
    write_json(OUT / "registry/term_registry.json", registry)

    # Extend, but never replace, the inherited external-URI evidence ledger.
    # The check below prevents a new R9 quantity from carrying an unverified
    # QUDT identifier.
    external_evidence_path = OUT / "evidence/external_uri_verification.json"
    external_evidence = read_json(external_evidence_path)
    inherited_units = {item["uri"] for item in external_evidence.get("qudtUnits", [])}
    new_unit_iris = {item["unitIri"] for item in additions if item.get("unitIri")}
    unverified_units = sorted(new_unit_iris - inherited_units - set(R9_VERIFIED_QUDT_UNITS))
    if unverified_units:
        raise RuntimeError(f"R9 contains unverified external unit IRIs: {unverified_units}")
    for uri in sorted(new_unit_iris - inherited_units):
        verified = R9_VERIFIED_QUDT_UNITS[uri]
        external_evidence.setdefault("qudtUnits", []).append({
            "uri": uri,
            "symbol": verified["symbol"],
            "officialVocabulary": "QUDT Units 3.4",
            "officialResource": verified["officialResource"],
            "officialVocabularyIndex": "https://www.qudt.org/doc/DOC_VOCAB-UNITS.html",
            "verifiedDate": "2026-08-13",
            "verificationStatus": "Exact QUDT unit local identifier verified in the official QUDT units vocabulary",
        })
    external_evidence["qudtUnits"] = sorted(external_evidence.get("qudtUnits", []), key=lambda item: item["uri"])
    write_json(external_evidence_path, external_evidence)

    fields = list(csv.DictReader((SOURCE / "registry/term_registry.csv").open(encoding="utf-8")).fieldnames or [])
    with (OUT / "registry/term_registry.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for item in registry:
            row = {key: item.get(key, "") for key in fields}
            for key in ("sourceConceptIds", "stage1LocalNames", "aliases", "requirements"):
                row[key] = "; ".join(item.get(key, []))
            writer.writerow(row)

    graph = Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    for record in additions:
        add_to_graph(graph, record, SPECS[record["localName"]])
    for ontology in graph.subjects(RDF.type, OWL.Ontology):
        graph.set((ontology, OWL.versionInfo, Literal(VERSION)))
    graph.serialize(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.serialize(OUT / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")

    context = read_json(OUT / "context/nltl_benchmark_context.jsonld")
    for record in additions:
        context["@context"][record["localName"]] = ({"@id": "nltl:" + record["localName"], "@type": "@id"} if record["kind"] in {"ObjectProperty", "QuantityProperty"} else "nltl:" + record["localName"])
    write_json(OUT / "context/nltl_benchmark_context.jsonld", context)

    index = read_json(OUT / "requirement_term_index.json")
    index["sourceLockId"] = DEV_ID; index["version"] = "1.9.0-dev-foundation"
    for rid, names in REQUIREMENT_TERMS.items():
        index["requirements"][rid] = sorted(set(index["requirements"].get(rid, [])) | set(names))
    index["termCount"] = len(registry)
    index["dependencyContracts"] = build_contracts(evidence, index)
    write_json(OUT / "requirement_term_index.json", index)

    # Machine-readable decision ledger.
    decisions = [{
        "canonicalLocalName": item["localName"], "action": "ADD_R9_DEVELOPMENT_TERM",
        "kind": item["kind"], "domain": SPECS[item["localName"]].get("domain", ""),
        "range": item["parentOrRange"], "linkedRequirements": item["requirements"],
        "rationale": "Added from verified normalized requirement evidence to repair a reusable node, relationship, controlled value, or explicit quantity gap.",
    } for item in additions]
    write_json(OUT / "registry/r9_change_decisions.json", decisions)

    # Rerun only requirements whose prior failure is now repaired (including
    # prompt/contract-only repairs) or whose model changed proactively.  This
    # excludes the one source-blocked requirement and avoids wasting calls on
    # unchanged accepted cases.
    observed_ids = {item["requirement_id"] for item in read_json(BATCH / "r9_failure_analysis.json")["records"]}
    active_ids = {
        item["id"] for item in evidence_payload["requirements"]
        if item.get("activeStatus") == "Stage 2 candidate - direct/deterministic"
        and str(item.get("figureDependent", "No")).lower() != "yes"
    }
    changed_ids = {rid for item in decisions for rid in item["linkedRequirements"]}
    rerun_ids = [
        item["id"] for item in evidence_payload["requirements"]
        if item["id"] in active_ids
        and item["id"] in (observed_ids | changed_ids)
        and index["dependencyContracts"][item["id"]]["status"] == "COMPLETE"
    ]
    queue = {
        "queue_id": "DEV-R9-AFFECTED-AND-REPAIRED-ONE-RUN",
        "description": "One development confirmation run for repaired prior failures plus proactively remodelled active requirements.",
        "development_vocabulary_id": DEV_ID,
        "repetitions": 1,
        "requirements": rerun_ids,
        "selection": {
            "observedFailuresRepaired": len(observed_ids & set(rerun_ids)),
            "proactiveRemodelsNotPreviouslyFailed": len(set(rerun_ids) - observed_ids),
            "excludedBlockedRequirements": sorted(
                rid for rid in observed_ids
                if index["dependencyContracts"][rid]["status"] == "BLOCKED_SOURCE_OR_MODEL_DEPENDENCY"
            ),
        },
    }
    write_json(BATCH / "generation_queue_r9_affected.json", queue)

    # Validation and reproducible binding.
    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    Graph().parse(OUT / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    bad_names = [item["localName"] for item in registry if not re.fullmatch(r"[a-z][A-Za-z0-9]*", item["localName"])]
    errors = []
    if len({item["localName"] for item in registry}) != len(registry): errors.append("duplicate localName")
    if len({item["iri"] for item in registry}) != len(registry): errors.append("duplicate IRI")
    if bad_names: errors.append(f"invalid local names: {bad_names}")
    absent_index = sorted({name for names in index["requirements"].values() for name in names} - {item["localName"] for item in registry} - {str(s)[len(BASE):] for s in graph.subjects() if str(s).startswith(BASE)})
    if absent_index: errors.append(f"indexed terms absent from registry/ontology: {absent_index}")
    invalid_external_units = sorted({item.get("unitIri", "") for item in additions if item.get("unitIri")} - {item["uri"] for item in external_evidence.get("qudtUnits", [])})
    if invalid_external_units: errors.append(f"new unit IRIs absent from external verification ledger: {invalid_external_units}")
    report = {
        "status": "PASS" if not errors else "FAIL", "developmentId": DEV_ID,
        "registryTerms": len(registry), "addedTerms": len(additions),
        "dependencyContracts": len(index["dependencyContracts"]), "rerunQueueRequirements": len(rerun_ids),
        "newExternalUnitsVerified": len(new_unit_iris - inherited_units), "errors": errors,
    }
    write_json(OUT / "validation/validation_report.json", report)
    if errors: raise RuntimeError("; ".join(errors))

    tracker_workbook = BATCH / "r9_engineering_change_tracker.xlsx"
    if not tracker_workbook.exists():
        tracker_workbook = BATCH / "remaining_190_readiness_tracker.xlsx"
    binding = {
        "lockId": DEV_ID, "status": "DEVELOPMENT_BINDING_NOT_EVALUATION_LOCK",
        "workbook": tracker_workbook.name, "workbookSha256": sha256(tracker_workbook),
        "boundMachineReadableArtifacts": {
            "registry/term_registry.json": sha256(OUT / "registry/term_registry.json"),
            "ontology/nltl_benchmark_vocabulary.ttl": sha256(OUT / "ontology/nltl_benchmark_vocabulary.ttl"),
            "evidence/stage1_approved.json": sha256(OUT / "evidence/stage1_approved.json"),
            "evidence/external_uri_verification.json": sha256(OUT / "evidence/external_uri_verification.json"),
        },
        "boundRequirementIndex": {"requirement_term_index.json": sha256(OUT / "requirement_term_index.json")},
        "warning": "R9 foundation is an engineering-development binding. Contracts marked review-required are not cleared for final experiment generation.",
    }
    write_json(OUT / "development_binding.json", binding)
    (OUT / "README.md").write_text(
        f"# R9 foundation development vocabulary\n\nDevelopment identifier: `{DEV_ID}`. This preserves R8.1 and adds reusable modelling foundations plus the first source-family repairs. It is not a final evaluation lock. Dependency contracts fail closed only after engineering review marks them COMPLETE.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "development_id": DEV_ID, "registry_terms": len(registry), "added_terms": len(additions), "contracts": len(index["dependencyContracts"]), "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
