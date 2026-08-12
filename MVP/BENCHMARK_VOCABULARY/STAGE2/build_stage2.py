from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, OWL, PROV, SH, SKOS, XSD


ROOT = Path(__file__).resolve().parents[2]
STAGE2 = Path(__file__).resolve().parent
TMP_DATA = Path("/tmp/nltl_stage1/stage1_data.json")
SNAPSHOT = STAGE2 / "evidence" / "stage1_approved.json"
GENERATED_DATE = "2026-08-12"
VERSION = "2.1.0-stage2"

VOCAB_BASE = "https://w3id.org/nltl-benchmark/vocab#"
SHAPES_BASE = "https://w3id.org/nltl-benchmark/shapes#"
PROFILE_BASE = "https://w3id.org/nltl-benchmark/profile/"

NLTL = Namespace(VOCAB_BASE)
NSH = Namespace(SHAPES_BASE)
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
SSP = Namespace("https://w3id.org/mtl-requirements/ssp#")

VERIFIED_QUDT_UNIT_URIS = {
    "http://qudt.org/vocab/unit/CentiM2", "http://qudt.org/vocab/unit/CentiM3",
    "http://qudt.org/vocab/unit/DAY", "http://qudt.org/vocab/unit/DEG", "http://qudt.org/vocab/unit/DEG_C",
    "http://qudt.org/vocab/unit/HR", "http://qudt.org/vocab/unit/HZ", "http://qudt.org/vocab/unit/J",
    "http://qudt.org/vocab/unit/KN", "http://qudt.org/vocab/unit/KiloGM",
    "http://qudt.org/vocab/unit/KiloGM-PER-M2", "http://qudt.org/vocab/unit/KiloN",
    "http://qudt.org/vocab/unit/KiloN-M", "http://qudt.org/vocab/unit/KiloN-PER-M",
    "http://qudt.org/vocab/unit/KiloW", "http://qudt.org/vocab/unit/M", "http://qudt.org/vocab/unit/M2",
    "http://qudt.org/vocab/unit/M3", "http://qudt.org/vocab/unit/MI_N", "http://qudt.org/vocab/unit/MegaHZ",
    "http://qudt.org/vocab/unit/MegaPA", "http://qudt.org/vocab/unit/MilliM", "http://qudt.org/vocab/unit/N",
    "http://qudt.org/vocab/unit/PERCENT", "http://qudt.org/vocab/unit/REV-PER-MIN",
    "http://qudt.org/vocab/unit/TON_Metric", "http://qudt.org/vocab/unit/UNITLESS",
    "http://qudt.org/vocab/unit/YR",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")


def ensure_dirs() -> None:
    for name in ("evidence", "ontology", "context", "shacl", "profiles", "mappings", "registry", "examples", "validation"):
        (STAGE2 / name).mkdir(parents=True, exist_ok=True)


def load_data() -> dict:
    source = TMP_DATA if TMP_DATA.exists() else SNAPSHOT
    if not source.exists():
        raise FileNotFoundError("Stage 1 data is unavailable; run prepare_stage1_data.py first")
    data = json.loads(source.read_text(encoding="utf-8"))
    SNAPSHOT.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return data


MODULES = {
    "core": ("Core ship and benchmark infrastructure", NLTL.ship),
    "hull": ("Hull and structural engineering", NLTL.hullStructure),
    "machinery": ("Machinery and propulsion", NLTL.machineryComponent),
    "operations": ("Operations, time, and observations", NLTL.operationalContext),
    "documents": ("Documents, certificates, approvals, and evidence", NLTL.evidenceArtifact),
    "tests": ("Physical-test evidence", NLTL.physicalTestEvidence),
    "regulation": ("Regulation and provenance", NLTL.regulatoryRequirement),
}


SHIP_CLASSES = {"cargoShip", "fishingVessel", "oilTanker", "passengerShip", "pleasureYacht"}
PERSON_CLASSES = {"crewMember", "passenger"}
HULL_CLASSES = {
    "connectionBracket", "cutout", "frame", "framingMember", "grillageSystem", "hullGirder",
    "iceLoadPatch", "internalStructure", "loadCarryingStringer", "localFrame", "longitudinalLocalFrame",
    "plating", "sternFrame", "structuralMember", "supportingStructure", "tankTop", "transverseFrame", "webFrame",
}
MACHINERY_CLASSES = {
    "coolingWaterSystem", "dieselEnginePlant", "essentialEngine", "firePump", "fireSafetyComponent",
    "inletChest", "oilResidueTank", "oilyBilgeWaterHoldingTank", "propellerBlade",
    "propellerIceInteractionComponent", "shaftComponent", "shaftLineComponent", "sidePropeller",
    "steeringMechanism", "sternTube", "thrusterBody", "thrusterFitting",
}
DOCUMENT_CLASSES = {
    "dischargeDistanceRecords", "polarRoutePlan", "polarShipCertificateForm", "requiredEquipmentRecords",
    "solasCertificateSchedule",
}
CONTROLLED_OBJECT_RANGES = {
    "iceClass": NLTL.iceClassValue,
    "polarClass": NLTL.polarClassValue,
    "shipCategory": NLTL.polarShipCategoryValue,
}

BOOLEAN_SUFFIXES = (
    "Present", "Applicable", "Applies", "Used", "Required", "Available", "Occurs", "Protected",
    "Certified", "Implemented", "Known", "Reached", "Enclosed", "Independent", "Connected", "Permitted",
    "Prohibited", "Allowed", "Retained", "Enabled", "Sufficient", "Likely", "Exposed", "Achieved",
    "Comminuted", "Disinfected", "Strengthened", "Operational", "Accessible", "Provided", "Secured",
)
BOOLEAN_WORDS = (
    "compliance", "coverage", "capability", "applicability", "adequacy", "acceptability", "availability",
    "operability", "continuity", "compatibility", "functionality", "protection", "prohibition", "permission",
)
STRING_SUFFIXES = (
    "Type", "Class", "Category", "Mode", "Method", "Standard", "Language", "Role", "Purpose", "Condition",
    "Region", "Area", "Material", "Grade", "Kind", "Configuration", "Arrangement", "Basis", "Scope",
    "Location", "Position", "Measure", "Geometry", "Curve", "Form", "Environment", "Authority", "Topic",
    "Case", "Distribution", "Sequence", "Criterion", "Principle", "Set", "Boundary", "Response",
    "Evaluation", "Values", "Origin", "Medium", "Liquid", "Orientation",
)
NUMERIC_WORDS = (
    "stress", "strength", "force", "load", "power", "pressure", "temperature", "angle", "length", "breadth",
    "height", "thickness", "spacing", "span", "area", "volume", "capacity", "speed", "torque", "moment",
    "distance", "draught", "draft", "mass", "energy", "frequency", "stiffness", "deflection", "clearance",
    "coefficient", "factor", "ratio", "fraction", "margin", "viscosity", "concentration", "tonnage",
    "displacement", "modulus", "diameter", "radius", "pitch", "chord", "time", "duration", "period",
)

# Stage 2 is allowed to refine a Stage 1 candidate when the refinement is a
# deterministic semantic cleanup, not a new regulatory interpretation.  These
# cases remove unit tokens/opaque symbols or make a Boolean predicate readable.
# The two propeller-speed candidates are also folded into one property because
# the linked clauses define the same physical quantity.
STAGE2_NAME_REFINEMENTS = {
    "actualShearArea": "actualWebFrameCrossSectionalArea",
    "aRequiredCm2": "requiredShearArea",
    "aircraftVoiceFrequencySupportMHz": "supportedAircraftVoiceFrequency",
    "averageImpactEnergyJ": "averageImpactEnergy",
    "deadweightTonnes": "deadweight",
    "displacementDeltaT": "displacementAtMaximumIceClassDraught",
    "displacementUiwlT": "displacementAtUpperIceWaterline",
    "elongationTestPercent": "elongationAtTest",
    "propellerRotationalSpeedAtMcrBollard": "propellerRotationalSpeedAtMaximumContinuousRatingBollard",
    "propellerSpeedMcrBollardRpm": "propellerRotationalSpeedAtMaximumContinuousRatingBollard",
    "sNcurveType": "stressLifeCurveType",
    "solely24HourDaylightOperation": "operatesOnlyInContinuousDaylight",
}

STAGE2_LABEL_REFINEMENTS = {
    "actualWebFrameCrossSectionalArea": "Actual web-frame cross-sectional area",
    "requiredShearArea": "Required shear area",
    "supportedAircraftVoiceFrequency": "Supported aircraft voice frequency",
    "averageImpactEnergy": "Average impact energy",
    "deadweight": "Deadweight",
    "displacementAtMaximumIceClassDraught": "Displacement at maximum ice-class draught",
    "displacementAtUpperIceWaterline": "Displacement at upper ice waterline",
    "elongationAtTest": "Elongation measured by test",
    "propellerRotationalSpeedAtMaximumContinuousRatingBollard": "Propeller rotational speed at maximum continuous rating in bollard condition",
    "stressLifeCurveType": "Stress-life curve type",
    "operatesOnlyInContinuousDaylight": "Operates only in continuous daylight",
}

# Each override is supported by the linked locked requirement's explicit unit
# wording.  QUDT URIs were rechecked against the official QUDT unit vocabulary
# on 2026-08-11.  Unit identifiers remain separate from canonical local names.
STAGE2_UNIT_REFINEMENTS = {
    "actualFrameShearArea": ("cm^2", "http://qudt.org/vocab/unit/CentiM2", "Area", "TRF-048 explicitly gives [cm^2]"),
    "actualWebFrameCrossSectionalArea": ("cm^2", "http://qudt.org/vocab/unit/CentiM2", "Area", "TRF-060 explicitly gives [cm^2]"),
    "requiredShearArea": ("cm^2", "http://qudt.org/vocab/unit/CentiM2", "Area", "TRF-060 defines A as required shear area in the [cm^2] equation"),
    "supportedAircraftVoiceFrequency": ("MHz", "http://qudt.org/vocab/unit/MegaHZ", "Frequency", "IMO-095 explicitly states 121.5 and 123.1 MHz"),
    "averageImpactEnergy": ("J", "http://qudt.org/vocab/unit/J", "Energy", "TRF-072/TRF-073 explicitly state impact energy in J"),
    "corrosionAbrasionAddition": ("mm", "http://qudt.org/vocab/unit/MilliM", "Length", "I2-046 explicitly defines the corrosion/abrasion addition as 1.0 mm"),
    "deadweight": ("t", "http://qudt.org/vocab/unit/TON_Metric", "Mass", "IMO-110 explicitly states the applicability threshold as 5,000 tonnes deadweight"),
    "displacementAtMaximumIceClassDraught": ("t", "http://qudt.org/vocab/unit/TON_Metric", "Mass", "TRF-039 explicitly defines displacement at maximum ice-class draught in [t]"),
    "displacementAtUpperIceWaterline": ("t", "http://qudt.org/vocab/unit/TON_Metric", "Mass", "TRF-016 formula uses displacement at UIWL in tonnes"),
    "elongationAtTest": ("%", "http://qudt.org/vocab/unit/PERCENT", "DimensionlessRatio", "TRF-072 explicitly states elongation percentage"),
    "propellerRotationalSpeedAtMaximumContinuousRatingBollard": ("rev/min", "http://qudt.org/vocab/unit/REV-PER-MIN", "RotationalVelocity", "TRF-083/TRF-085 define rotational propeller speed at MCR in bollard condition"),
    "brashIceChannelResistanceRch": ("N", "http://qudt.org/vocab/unit/N", "Force", "TRF-020/TRAFICOM definition states RCH in newtons"),
}

DIMENSIONLESS_WORDS = ("coefficient", "concentration", "factor", "ratio", "fraction", "tonnage", "margin")

RETIRED_STAGE1_CANDIDATES = {
    "VOC-0747": {
        "stage1LocalName": "tableFallbackValue",
        "reason": "The same generic helper represented thrust, rotational speed, and torque in different requirements, so it has no coherent range or unit.",
        "requirementRedirects": {
            "TRF-082": "hydrodynamicBollardThrust",
            "TRF-083": "propellerRotationalSpeedAtMaximumContinuousRatingBollard",
            "TRF-088": "maximumEngineTorque",
        },
    },
}

BOOLEAN_LOCAL_NAMES = {
    "abandonmentOntoIceOrLandPotential", "accessRequiredAtSea", "addedLifeSavingDeviceRequiresPower",
    "assessedAbandonment", "assessedAdditionalHazards", "assessedCodeHazards", "assessedHighLatitude",
    "assessedIceOperation", "asternIceOperationIntent", "bladeOrderResonance", "bladeOrderTorsionalResonance",
    "bowRegionEquivalent", "bucklingStiffening",
    "additionalEquipmentCarriedInSurvivalCraft", "animalCarcassDischarge", "cargoTankCarriesOil",
    "carriedNoxiousLiquidSubstanceRequiresType3Tank", "certificateIssued", "cleanBallast", "contaminatedByOtherGarbage", "damageCenterForwardOfMaxBreadth",
    "closingDeviceOutsideHabitableEnvironment", "departureAndDestinationWithinArctic", "detachedStrut",
    "devicePowerSourceIndependentOfMainPower", "engagedInTrade", "extendedDarknessOperation", "extendedPeriodOperation",
    "equivalentSupportStatusByDirectCalculation", "fixedWaterSystemSeparateFromMainFirePumps",
    "flashingRed", "foodWasteComminutedOrGround", "foodWasteDischargeOntoIce", "foodWasteDischargeToSea",
    "frameAsymmetrical", "groupSurvivalEquipmentCarried", "interpolatedShellPlateRequirement",
    "globalBladeOrderResonance", "harmfulTorsionalResonance", "iceAccumulationSpaceAboveInlet",
    "icebreakerEscortOperation", "immersionPotential", "lightVisibleFromAstern", "localControl",
    "machinerySeawaterSupply", "manualInitiation", "memberInstability", "midbodyEquivalent",
    "nearCentrelineAndWellAftIfPossible", "noxiousLiquidSubstanceOrNoxiousLiquidSubstanceMixtureDischargeToSea",
    "oilOrOilyMixtureDischargeToSea", "propellerHighestPointSubmerged", "propulsionEngineReversedForAstern",
    "operatesOnlyInContinuousDaylight", "polarWaterOperationalManualPresentOnBoard", "propellerBladeLoss",
    "releasedRescueBoatOrLifeboat", "requiredSensorProjectsBelowHull", "requiredSystemsFunctionalAtPst",
    "rescueCoordinationCentreVoiceOrData", "routeRemainsWithinArctic", "segregatedBallast",
    "residueNotRecoverableByCommonMethods", "shaftLineComponentDamage", "shellPlateButtCrossing", "sidescuttleInIceBelt",
    "sewageDischargeToSea", "sewageDischargeUsesTreatmentPlant", "shipEnRoute", "shipExposedToIceAccretion",
    "shipOperatesInIceCoveredWaters", "shipOperatesInLowAirTemperature", "shipOperatesInPolarWaters",
    "shipProvidesIcebreakingEscort", "storageLocationSubjectToFreezing", "visibleFromAstern",
    "weatherDeckBelowIceBeltUpperLimit", "thrusterBodyLocalStrength",
}

INTEGER_LOCAL_NAMES = {
    "additionalEquipmentCapacityRequirement", "airReceiverConsecutiveStartCapacity",
    "availableSurvivalEquipmentCapacity", "equivalentStressCycles", "personOnBoard", "personsOnBoard",
    "personsCapacityRequirement", "survivalCraftAvailableCapacity",
}

STRING_LOCAL_NAMES = {
    "arcticWaters", "assignedDuties", "assignedImmersionSuit", "assignedSearchlight", "bladePlasticBending",
    "containingCompartment", "exposedFireMainSection", "framingIceStrengtheningExtent",
    "framingIceStrengtheningUpperExtent", "headingOrPositionSystem", "hullAreaRequirementSet",
    "iceOrSnowRemovalOrPreventionMeans", "protectedLocationOrEquipment", "relevantHatchOrDoor",
    "requiredNavigationOrCommunicationAntenna", "shellIceStrengtheningExtent",
    "stabilityCalculationIcingAllowanceValues",
}

NUMERIC_LOCAL_NAMES = {
    "betaIPrime", "clampedHullGeometryTerm", "continuousSurfaceProjectedArea", "corrosionAbrasionAddition",
    "deadweight", "discontinuousSurfaceProjectedArea", "iceClassDraught", "loadedSurvivalCraftRequirement",
    "longitudinalDamageExtent", "observedIceAccretion", "serviceLife", "shearArea", "tableFallbackValue",
    "thrusterGlobalModeFrequency", "verticalDamageExtent", "yieldPoint",
}

GENERAL_ENTITY_CLASSES = {
    "extinguisher", "exposedEquipment", "exposedEscapeRoute", "frameStrengthenedPart", "groupSurvivalEquipmentContainer", "iceBlock",
    "lifeSavingAppliance", "lifeboat", "navigationEquipmentItem", "otherSurvivalCraft", "portableTwoWayRadio",
    "routePoint", "storageLocationSubjectToFreezing", "survivalCraftCommunicationDevice",
    "watertightOrWeathertightClosingDevice",
}


def evidence_class(local: str) -> bool:
    if local.endswith("Evidence"):
        return True
    if local.endswith("Analysis") and not local.endswith(("AnalysisUsed", "AnalysisStatus")):
        return True
    return local in DOCUMENT_CLASSES


def class_parent(local: str) -> URIRef | None:
    if local in GENERAL_ENTITY_CLASSES:
        return NLTL.benchmarkEntity
    if local in SHIP_CLASSES:
        return NLTL.ship
    if local in PERSON_CLASSES:
        return NLTL.person
    if local in HULL_CLASSES:
        return NLTL.hullStructure
    if local in MACHINERY_CLASSES:
        return NLTL.machineryComponent
    if evidence_class(local):
        if "Test" in local or "test" in local:
            return NLTL.physicalTestEvidence
        if local.endswith("Analysis"):
            return NLTL.engineeringAnalysis
        return NLTL.documentEvidence
    return None


def module_for(c: dict, kind: str) -> str:
    local = c["localName"]
    low = local.lower()
    if evidence_class(local) or any(x in low for x in ("document", "certificate", "approval", "record", "manual", "evidence", "survey", "endorsement", "translation")):
        return "documents"
    if c.get("testEvidence") or "Test" in local:
        return "tests"
    if any(x in low for x in ("regulation", "requirement", "applicability", "applies", "paragraph", "chapter", "marpol", "solas", "stcw", "classification", "prescribedprocedure")):
        return "regulation"
    if any(x in low for x in ("propeller", "engine", "thruster", "shaft", "machinery", "cooling", "rudder", "torque", "bollard")):
        return "machinery"
    if any(x in low for x in ("hull", "frame", "plating", "plate", "stringer", "scantling", "structur", "waterline", "bow", "stern", "shell")):
        return "hull"
    if c.get("timeHistory") or any(x in low for x in ("voyage", "route", "observation", "operation", "timestamp")):
        return "operations"
    source_domain = c.get("domain", "")
    if source_domain.startswith("hull"):
        return "hull"
    if source_domain.startswith("machinery"):
        return "machinery"
    if source_domain.startswith("operations"):
        return "operations"
    if source_domain.startswith("documents"):
        return "documents"
    return "core"


def refine_candidate(c: dict) -> dict:
    """Apply only documented Stage 2 naming/unit refinements."""
    out = dict(c)
    stage1_local = c["localName"]
    local = STAGE2_NAME_REFINEMENTS.get(stage1_local, stage1_local)
    out["stage1LocalName"] = stage1_local
    out["localName"] = local
    if local in STAGE2_LABEL_REFINEMENTS:
        out["label"] = STAGE2_LABEL_REFINEMENTS[local]
    if local in STAGE2_UNIT_REFINEMENTS:
        symbol, uri, qk, evidence = STAGE2_UNIT_REFINEMENTS[local]
        out["unit"] = symbol
        out["unitUri"] = uri
        out["quantityKind"] = qk
        out["stage2UnitEvidence"] = evidence
    else:
        out["stage2UnitEvidence"] = ""
    return out


def name_tokens(local: str) -> set[str]:
    """Return whole lowerCamelCase tokens, separating digits from letters.

    Whole-token matching prevents accidental numeric classification from
    substrings such as ``ratio`` inside ``operation`` or ``administration``.
    """
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", local)
    spaced = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", spaced)
    spaced = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", spaced)
    return {x.lower() for x in re.split(r"[^A-Za-z0-9]+", spaced) if x}


def is_numeric_semantic(c: dict) -> bool:
    local = c["localName"]
    return local in NUMERIC_LOCAL_NAMES or bool(name_tokens(local) & set(NUMERIC_WORDS))


def is_dimensionless_semantic(local: str) -> bool:
    return local in {"betaIPrime", "clampedHullGeometryTerm", "loadSpectrumShapeParameter"} or bool(name_tokens(local) & set(DIMENSIONLESS_WORDS))


def canonical_unit_for(local: str) -> tuple[str, str, str, str] | None:
    """Return a benchmark canonical unit chosen by an explicit engineering rule.

    This is a vocabulary normalization decision, not a claim that every source
    prints this unit.  Source-specific conversion remains a data-ingestion task.
    Ambiguous quantities (for example viscosity or generic structural capacity)
    intentionally return None.
    """
    low = local.lower()
    exact = {
        "airReceiverCapacity": ("m^3", str(UNIT.M3), "Volume", "Canonical SI-derived volume unit"),
        "launchingApplianceCapacity": ("kg", str(UNIT.KiloGM), "Mass", "Canonical mass unit for loaded launching-appliance capacity"),
        "loadedSurvivalCraftRequirement": ("kg", str(UNIT.KiloGM), "Mass", "Canonical mass unit for loaded survival-craft requirement"),
        "longitudinalDamageExtent": ("m", str(UNIT.M), "Length", "Canonical length unit for the calculated longitudinal damage extent"),
        "memberCapacity": ("kN", str(UNIT.KiloN), "Force", "IACS source defines member capacity by the load resisted"),
        "serviceLife": ("year", str(UNIT.YR), "Time", "Canonical service-life unit"),
        "plasticStrength": ("kN", str(UNIT.KiloN), "Force", "IACS source defines plastic strength by the magnitude of midspan load at collapse"),
        "propellerPitchAtMcrBollard": ("m", str(UNIT.M), "Length", "Canonical length unit for propeller pitch"),
        "propellerPitchAtMcrFreeRunning": ("m", str(UNIT.M), "Length", "Canonical length unit for propeller pitch"),
        "shipAttachmentStiffness": ("kN/m", str(UNIT["KiloN-PER-M"]), "ForcePerLength", "Canonical translational attachment-stiffness unit"),
        "waterAddedMass": ("kg", str(UNIT.KiloGM), "Mass", "Canonical mass unit"),
        "observedIceAccretion": ("m", str(UNIT.M), "Length", "Canonical ice-accretion thickness/extent unit"),
        "sectionModulus": ("cm^3", str(UNIT.CentiM3), "SectionModulus", "Benchmark unit aligned with the linked scantling equations"),
        "verticalDamageExtent": ("m", str(UNIT.M), "Length", "Canonical length unit for the calculated vertical damage extent"),
    }
    if local in exact:
        return exact[local]
    if is_dimensionless_semantic(local):
        return "1", str(UNIT.UNITLESS), "DimensionlessRatio", "Canonical dimensionless unit"
    if "temperature" in low:
        return "deg C", str(UNIT.DEG_C), "Temperature", "Canonical benchmark temperature unit"
    if "frequency" in low:
        return "Hz", str(UNIT.HZ), "Frequency", "Canonical benchmark frequency unit"
    if "speed" in low:
        if any(x in low for x in ("shaft", "engine", "mcr", "bladeorder", "resonant", "rotational")):
            return "rev/min", str(UNIT["REV-PER-MIN"]), "RotationalVelocity", "Canonical rotational-speed unit"
        return "kn", str(UNIT.KN), "Velocity", "Canonical maritime linear-speed unit"
    if any(x in low for x in ("stress", "pressure", "yieldpoint", "fatiguestrength", "referencestrength")):
        return "MPa", str(UNIT.MegaPA), "PressureOrStress", "Canonical benchmark stress/pressure unit"
    if "lineload" in low:
        return "kN/m", str(UNIT["KiloN-PER-M"]), "ForcePerLength", "Canonical line-load unit"
    if any(x in low for x in ("torque", "moment")):
        return "kN*m", str(UNIT["KiloN-M"]), "TorqueOrMoment", "Canonical benchmark torque/moment unit"
    if "power" in low:
        return "kW", str(UNIT.KiloW), "Power", "Canonical benchmark power unit"
    if "energy" in low:
        return "J", str(UNIT.J), "Energy", "Canonical benchmark energy unit"
    if any(x in low for x in ("angle", "inclination", "rake", "flare")):
        return "deg", str(UNIT.DEG), "Angle", "Canonical benchmark plane-angle unit"
    if "area" in low:
        return "m^2", str(UNIT.M2), "Area", "Canonical benchmark area unit"
    if any(x in low for x in ("thickness", "length", "breadth", "height", "spacing", "span", "distance", "draught", "draft", "diameter", "radius", "clearance", "deflection")):
        return "m", str(UNIT.M), "Length", "Canonical benchmark length unit"
    if any(x in low for x in ("force", "load")) and not any(x in low for x in ("case", "distribution", "sequence", "spectrum")):
        return "kN", str(UNIT.KiloN), "Force", "Canonical benchmark force/load unit"
    return None


def datatype_decision(c: dict) -> tuple[URIRef, str]:
    local = c["localName"]
    declared = c.get("datatype", "")
    # Explicit Stage 2 semantic overrides take precedence over a Stage 1
    # "controlled enumeration" placeholder when the linked clause is binary.
    if local in BOOLEAN_LOCAL_NAMES:
        return XSD.boolean, "Explicit binary applicability/state semantics from the linked requirement"
    if local in INTEGER_LOCAL_NAMES or local.endswith("Cycles"):
        return XSD.integer, "Explicit count/cycle semantics"
    if local in STRING_LOCAL_NAMES:
        return XSD.string, "Explicit categorical/target/reference semantics"
    if declared == "xsd:boolean":
        return XSD.boolean, "Stage 1 explicit boolean"
    if declared == "xsd:integer":
        return XSD.integer, "Stage 1 explicit integer"
    if declared == "xsd:date":
        return XSD.date, "Stage 1 explicit date"
    if declared == "xsd:decimal":
        return XSD.decimal, "Stage 1 explicit decimal"
    if declared == "xsd:string / controlled enumeration":
        return XSD.string, "Stage 1 controlled-enumeration string"
    if local == "observationTime":
        return XSD.dateTime, "Observation timestamp"
    if local.endswith("Date") or "Date" in local:
        return XSD.date, "Date lexical rule"
    if local.endswith("Count") or "NumberOf" in local or local.endswith("Number"):
        return XSD.integer, "Count lexical rule"
    if local.endswith("Status"):
        return XSD.boolean, "Binary benchmark status; evidence lifecycle is modelled separately"
    if local.endswith(BOOLEAN_SUFFIXES) or any(w in local.lower() for w in BOOLEAN_WORDS):
        return XSD.boolean, "Boolean semantic suffix/word rule"
    if local.endswith(STRING_SUFFIXES):
        return XSD.string, "Controlled/textual category rule"
    if is_numeric_semantic(c):
        return XSD.decimal, "Formula/comparison or engineering-quantity rule"
    return XSD.string, "Conservative textual scalar fallback"


def decide_term(c: dict) -> dict:
    c = refine_candidate(c)
    local = c["localName"]
    parent = class_parent(local)
    if parent is not None:
        kind = "Class"
        range_iri = str(parent)
        decision = "Explicit engineering entity/artifact class set"
        datatype = ""
    elif c.get("unit") or c.get("quantityKind"):
        kind = "QuantityProperty"
        range_iri = str(QUDT.QuantityValue)
        decision = "Quantity metadata requires the canonical QUDT QuantityValue node pattern"
        datatype = ""
    elif local in NUMERIC_LOCAL_NAMES:
        kind = "QuantityProperty"
        range_iri = str(QUDT.QuantityValue)
        decision = "Clause-linked engineering quantity override; represented by the canonical QUDT QuantityValue node pattern"
        datatype = ""
    elif local in CONTROLLED_OBJECT_RANGES:
        kind = "ObjectProperty"
        range_iri = str(CONTROLLED_OBJECT_RANGES[local])
        decision = "Verified regulation-defined controlled value set"
        datatype = ""
    elif local.endswith(("ApprovalStatus", "CertificationStatus", "RevocationStatus")):
        kind = "ObjectProperty"
        range_iri = str(NLTL.evidenceState)
        decision = "Evidence lifecycle state decision"
        datatype = ""
    elif c.get("role") == "Object property candidate" or local in {"frameAttachment", "frameShellAttachment", "structuralConnection"}:
        kind = "ObjectProperty"
        range_iri = str(NLTL.benchmarkEntity)
        decision = "Stage 1 relationship usage"
        datatype = ""
    elif c.get("datatype") in {"xsd:boolean", "xsd:integer", "xsd:date", "xsd:string / controlled enumeration"} or local == "observationTime" or local in BOOLEAN_LOCAL_NAMES | INTEGER_LOCAL_NAMES | STRING_LOCAL_NAMES or local.endswith(BOOLEAN_SUFFIXES + STRING_SUFFIXES) or local.endswith("Status") or local.endswith("Cycles") or any(w in local.lower() for w in BOOLEAN_WORDS):
        dt, decision = datatype_decision(c)
        kind = "DatatypeProperty"
        range_iri = str(dt)
        datatype = dt.n3(Graph().namespace_manager)
    elif is_numeric_semantic(c):
        kind = "QuantityProperty"
        range_iri = str(QUDT.QuantityValue)
        decision = "Formula/comparison or engineering-numeric semantics require a unit-bearing QUDT QuantityValue node"
        datatype = ""
    else:
        dt, decision = datatype_decision(c)
        kind = "DatatypeProperty"
        range_iri = str(dt)
        datatype = dt.n3(Graph().namespace_manager)
    module = module_for(c, kind)
    unit_symbol = c.get("unit", "")
    unit_iri = c.get("unitUri", "")
    quantity_kind = c.get("quantityKind", "")
    canonical = canonical_unit_for(local) if kind == "QuantityProperty" and not unit_iri else None
    if canonical:
        unit_symbol, unit_iri, canonical_qk, canonical_basis = canonical
        quantity_kind = quantity_kind or canonical_qk
        unit_decision = f"Recommended canonical QUDT unit selected by Stage 2 engineering normalization: {canonical_basis}"
    elif kind == "QuantityProperty" and unit_iri:
        unit_decision = "Verified recommended QUDT unit from Stage 1 or a documented Stage 2 source-unit refinement"
    elif kind == "QuantityProperty" and unit_symbol:
        unit_decision = "Source unit is explicit, but no exact QUDT unit mapping is asserted"
    elif kind == "QuantityProperty" and "viscosity" in local.lower():
        quantity_kind = "Manufacturer-declared dynamic or kinematic viscosity"
        unit_decision = "Requirement-specific viscosity policy: manufacturer minimum, observation, and manufacturer maximum must use the same declared viscosity quantity kind and unit; no unsupported dynamic-versus-kinematic assumption is made"
    elif kind == "QuantityProperty":
        unit_decision = "A unit IRI is mandatory in data, but no single global recommended unit is asserted; the requirement profile must choose an allowed unit"
    else:
        unit_decision = "Not a quantity property"
    return {
        "conceptId": c["conceptId"],
        "sourceConceptIds": [c["conceptId"]],
        "stage1LocalNames": [c["stage1LocalName"]],
        "localName": local,
        "iri": VOCAB_BASE + local,
        "label": c["label"],
        "kind": kind,
        "parentOrRange": range_iri,
        "datatype": datatype,
        "module": module,
        "roleDecision": decision,
        "unitSymbol": unit_symbol,
        "unitIri": unit_iri,
        "quantityKindLabel": quantity_kind,
        "unitDecisionStatus": unit_decision,
        "stage2UnitEvidence": c.get("stage2UnitEvidence", ""),
        "aliases": [x.strip() for x in c.get("aliases", "").split(";") if x.strip()],
        "requirements": [x.strip() for x in c.get("requirementIds", "").split(";") if x.strip()],
        "sourceRefs": c.get("sourceRefs", ""),
        "evidenceExcerpt": c.get("exactEvidence", ""),
        "normalizedDefinition": c.get("normalizedDefinition", ""),
        "namingBasis": c.get("namingBasis", ""),
        "namingRule": c.get("namingRule", ""),
        "nameQaStatus": c.get("nameQaStatus", ""),
        "confidence": c.get("confidence", ""),
        "haithamUri": c.get("haithamUri", ""),
        "mappingStatus": c.get("mappingStatus", ""),
    }


def merge_terms(terms: list[dict]) -> list[dict]:
    """Fold only exact Stage 2 semantic duplicates onto one canonical URI."""
    by_local: dict[str, dict] = {}
    for term in terms:
        local = term["localName"]
        if local not in by_local:
            by_local[local] = term
            continue
        current = by_local[local]
        for field in ("kind", "parentOrRange", "datatype", "module"):
            if current[field] != term[field]:
                raise RuntimeError(f"Cannot merge {local}: conflicting {field}: {current[field]} vs {term[field]}")
        for field in ("unitSymbol", "unitIri", "quantityKindLabel"):
            if current[field] and term[field] and current[field] != term[field]:
                raise RuntimeError(f"Cannot merge {local}: conflicting {field}: {current[field]} vs {term[field]}")
            current[field] = current[field] or term[field]
        for field in ("sourceConceptIds", "stage1LocalNames", "aliases", "requirements"):
            current[field] = sorted(set(current[field]) | set(term[field]))
        for field in ("sourceRefs", "evidenceExcerpt", "normalizedDefinition", "namingBasis", "namingRule", "stage2UnitEvidence"):
            values = [x.strip() for x in (current.get(field, ""), term.get(field, "")) if x and x.strip()]
            current[field] = " | ".join(dict.fromkeys(values))
        current["conceptId"] = current["sourceConceptIds"][0]
        current["roleDecision"] = "Merged exact semantic duplicate from linked clauses; " + current["roleDecision"]
        current["unitDecisionStatus"] = term["unitDecisionStatus"] if term["unitIri"] else current["unitDecisionStatus"]
    return sorted(by_local.values(), key=lambda t: t["localName"])


def bind(g: Graph) -> None:
    for prefix, ns in (
        ("nltl", NLTL), ("nsh", NSH), ("owl", OWL), ("rdf", RDF), ("rdfs", RDFS),
        ("xsd", XSD), ("skos", SKOS), ("dct", DCTERMS), ("prov", PROV),
        ("qudt", QUDT), ("unit", UNIT), ("sosa", SOSA), ("sh", SH), ("ssp", SSP),
    ):
        g.bind(prefix, ns)


def add_core(g: Graph) -> None:
    ontology = URIRef(VOCAB_BASE.removesuffix("#"))
    g.add((ontology, RDF.type, OWL.Ontology))
    g.add((ontology, RDFS.label, Literal("NLTL benchmark controlled vocabulary")))
    g.add((ontology, DCTERMS.created, Literal(GENERATED_DATE, datatype=XSD.date)))
    g.add((ontology, OWL.versionInfo, Literal(VERSION)))
    g.add((ontology, OWL.versionIRI, URIRef(f"https://w3id.org/nltl-benchmark/vocab/{VERSION}")))
    g.add((ontology, DCTERMS.description, Literal("One controlled vocabulary for NL-to-SHACL benchmark inputs. It defines names and value structures but contains no regulatory threshold, formula, applicability outcome, or pass/fail answer logic.")))
    g.add((ontology, NLTL.publicationStatus, Literal("Stage 2 draft; provisional w3id redirect not yet registered")))

    classes = {
        NLTL.benchmarkEntity: ("Benchmark entity", None),
        NLTL.ship: ("Ship", NLTL.benchmarkEntity),
        NLTL.shipComponent: ("Ship component", NLTL.benchmarkEntity),
        NLTL.hullStructure: ("Hull structure", NLTL.shipComponent),
        NLTL.machineryComponent: ("Machinery component", NLTL.shipComponent),
        NLTL.operationalContext: ("Operational context", NLTL.benchmarkEntity),
        NLTL.person: ("Person", NLTL.benchmarkEntity),
        NLTL.evidenceArtifact: ("Evidence artifact", PROV.Entity),
        NLTL.documentEvidence: ("Document evidence", NLTL.evidenceArtifact),
        NLTL.certificateEvidence: ("Certificate evidence", NLTL.documentEvidence),
        NLTL.approvalEvidence: ("Approval evidence", NLTL.documentEvidence),
        NLTL.engineeringAnalysis: ("Engineering analysis", NLTL.evidenceArtifact),
        NLTL.physicalTestEvidence: ("Physical-test evidence", NLTL.evidenceArtifact),
        NLTL.regulatoryRequirement: ("Regulatory requirement", PROV.Entity),
        NLTL.evidenceState: ("Evidence lifecycle state", SKOS.Concept),
        NLTL.complianceState: ("Compliance state", SKOS.Concept),
        NLTL.iceClassValue: ("Finnish-Swedish ice-class value", SKOS.Concept),
        NLTL.polarClassValue: ("IACS Polar Class value", SKOS.Concept),
        NLTL.polarShipCategoryValue: ("IMO polar ship category value", SKOS.Concept),
        NLTL.vocabularyModule: ("Vocabulary module", SKOS.ConceptScheme),
    }
    for iri, (label, parent) in classes.items():
        g.add((iri, RDF.type, OWL.Class))
        g.add((iri, RDFS.label, Literal(label, lang="en")))
        if parent:
            g.add((iri, RDFS.subClassOf, parent))

    annotations = {
        NLTL.draftConceptId: "Stage 1 stable draft concept identifier",
        NLTL.stage1LocalName: "Stage 1 candidate local name retained for audit traceability",
        NLTL.module: "Internal vocabulary module",
        NLTL.sourceAlias: "Original source label or formula symbol",
        NLTL.sourceRequirementId: "Locked requirement identifier",
        NLTL.sourceReference: "Source, clause, and page reference",
        NLTL.evidenceExcerpt: "Verified evidence excerpt or verified ASCII transcription",
        NLTL.namingBasis: "Naming authority/basis category",
        NLTL.namingRule: "Applied deterministic naming rule",
        NLTL.roleDecisionBasis: "Basis for the Stage 2 class/property/range decision",
        NLTL.quantityKindLabel: "Human-readable quantity-kind label when no exact quantity-kind IRI is asserted",
        NLTL.unitSymbol: "Source unit symbol",
        NLTL.unitDecisionStatus: "Stage 2 unit decision status",
        NLTL.stage2UnitEvidence: "Verified source evidence supporting a Stage 2 unit refinement",
        NLTL.publicationStatus: "Publication status or limitation",
    }
    for iri, label in annotations.items():
        g.add((iri, RDF.type, OWL.AnnotationProperty))
        g.add((iri, RDFS.label, Literal(label, lang="en")))

    object_props = {
        NLTL.hasComponent: (NLTL.ship, NLTL.shipComponent, "has component"),
        NLTL.hasEvidence: (NLTL.benchmarkEntity, NLTL.evidenceArtifact, "has evidence"),
        NLTL.hasObservation: (NLTL.benchmarkEntity, SOSA.Observation, "has observation"),
        NLTL.hasComplianceState: (NLTL.benchmarkEntity, NLTL.complianceState, "has compliance state"),
        NLTL.hasEvidenceState: (NLTL.evidenceArtifact, NLTL.evidenceState, "has evidence state"),
        NLTL.recommendedUnit: (RDF.Property, QUDT.Unit, "recommended unit"),
    }
    for iri, (domain, range_, label) in object_props.items():
        g.add((iri, RDF.type, OWL.ObjectProperty))
        g.add((iri, RDFS.domain, domain))
        g.add((iri, RDFS.range, range_))
        g.add((iri, RDFS.label, Literal(label, lang="en")))

    for module, (label, _) in MODULES.items():
        iri = NLTL[f"module{module.title()}"]
        g.add((iri, RDF.type, NLTL.vocabularyModule))
        g.add((iri, SKOS.prefLabel, Literal(label, lang="en")))

    evidence_states = ("Draft", "Submitted", "UnderReview", "Approved", "Rejected", "Expired", "Revoked")
    for label in evidence_states:
        iri = NLTL[f"evidenceState{label}"]
        g.add((iri, RDF.type, NLTL.evidenceState))
        g.add((iri, SKOS.prefLabel, Literal(label, lang="en")))
    for label in ("Compliant", "NonCompliant", "NotApplicable", "Unknown"):
        iri = NLTL[f"complianceState{label}"]
        g.add((iri, RDF.type, NLTL.complianceState))
        g.add((iri, SKOS.prefLabel, Literal(label, lang="en")))

    controlled_values = {
        NLTL.iceClassValue: (("iceClassIaSuper", "IA Super"), ("iceClassIa", "IA"), ("iceClassIb", "IB"), ("iceClassIc", "IC"), ("iceClassIi", "II"), ("iceClassIii", "III")),
        NLTL.polarClassValue: tuple((f"polarClassPc{i}", f"PC{i}") for i in range(1, 8)),
        NLTL.polarShipCategoryValue: (("polarShipCategoryA", "Category A"), ("polarShipCategoryB", "Category B"), ("polarShipCategoryC", "Category C")),
    }
    for value_class, values in controlled_values.items():
        for local, label in values:
            iri = NLTL[local]
            g.add((iri, RDF.type, value_class))
            g.add((iri, RDF.type, SKOS.Concept))
            g.add((iri, SKOS.prefLabel, Literal(label, lang="en")))


def add_terms(g: Graph, terms: list[dict]) -> None:
    for t in terms:
        iri = URIRef(t["iri"])
        kind = t["kind"]
        if kind == "Class":
            g.add((iri, RDF.type, OWL.Class))
            g.add((iri, RDFS.subClassOf, URIRef(t["parentOrRange"])))
        elif kind in ("QuantityProperty", "ObjectProperty"):
            g.add((iri, RDF.type, OWL.ObjectProperty))
            g.add((iri, RDFS.domain, NLTL.benchmarkEntity))
            g.add((iri, RDFS.range, URIRef(t["parentOrRange"])))
        else:
            g.add((iri, RDF.type, OWL.DatatypeProperty))
            g.add((iri, RDFS.domain, NLTL.benchmarkEntity))
            g.add((iri, RDFS.range, URIRef(t["parentOrRange"])))
        g.add((iri, RDFS.label, Literal(t["label"], lang="en")))
        g.add((iri, SKOS.prefLabel, Literal(t["label"], lang="en")))
        for concept_id in t["sourceConceptIds"]:
            g.add((iri, NLTL.draftConceptId, Literal(concept_id)))
        for stage1_name in t["stage1LocalNames"]:
            g.add((iri, NLTL.stage1LocalName, Literal(stage1_name)))
        g.add((iri, NLTL.module, NLTL[f"module{t['module'].title()}"]))
        g.add((iri, NLTL.roleDecisionBasis, Literal(t["roleDecision"])))
        g.add((iri, NLTL.namingBasis, Literal(t["namingBasis"])))
        g.add((iri, NLTL.namingRule, Literal(t["namingRule"])))
        g.add((iri, NLTL.unitDecisionStatus, Literal(t["unitDecisionStatus"])))
        if t["stage2UnitEvidence"]:
            g.add((iri, NLTL.stage2UnitEvidence, Literal(t["stage2UnitEvidence"])))
        g.add((iri, SKOS.definition, Literal(t["normalizedDefinition"], lang="en")))
        g.add((iri, NLTL.sourceReference, Literal(t["sourceRefs"])))
        g.add((iri, NLTL.evidenceExcerpt, Literal(t["evidenceExcerpt"])))
        for alias in t["aliases"]:
            g.add((iri, SKOS.altLabel, Literal(alias)))
            g.add((iri, NLTL.sourceAlias, Literal(alias)))
        for req in t["requirements"]:
            g.add((iri, NLTL.sourceRequirementId, Literal(req)))
        if t["unitSymbol"]:
            g.add((iri, NLTL.unitSymbol, Literal(t["unitSymbol"])))
        if t["unitIri"]:
            g.add((iri, NLTL.recommendedUnit, URIRef(t["unitIri"])))
        if t["quantityKindLabel"]:
            g.add((iri, NLTL.quantityKindLabel, Literal(t["quantityKindLabel"])))


def build_ontology(terms: list[dict]) -> Graph:
    g = Graph()
    bind(g)
    add_core(g)
    add_terms(g, terms)
    return g


def build_mappings(terms: list[dict]) -> Graph:
    g = Graph()
    bind(g)
    mapping_doc = URIRef("https://w3id.org/nltl-benchmark/mapping/haitham-stage2")
    g.add((mapping_doc, RDF.type, OWL.Ontology))
    g.add((mapping_doc, RDFS.label, Literal("Verified Haitham compatibility mappings")))
    g.add((mapping_doc, DCTERMS.description, Literal("SKOS mappings only; no OWL equivalence is asserted because the legacy named-variable node model differs from the benchmark property/value model.")))
    for t in terms:
        if t["haithamUri"]:
            g.add((URIRef(t["iri"]), SKOS.exactMatch, URIRef(t["haithamUri"])))
    return g


def add_property_shape(g: Graph, entity_shape: URIRef, t: dict) -> None:
    shape = NSH[f"{t['localName']}PropertyShape"]
    g.add((shape, RDF.type, SH.PropertyShape))
    g.add((shape, SH.path, URIRef(t["iri"])))
    g.add((shape, SH.name, Literal(t["label"], lang="en")))
    g.add((shape, SH.description, Literal("Schema-only value-shape constraint; requirement-specific cardinality and answer logic are intentionally excluded.")))
    g.add((entity_shape, SH.property, shape))
    if t["kind"] == "QuantityProperty":
        g.add((shape, SH.node, NSH.quantityValueShape))
        g.add((shape, SH.nodeKind, SH.BlankNodeOrIRI))
    elif t["kind"] == "ObjectProperty":
        g.add((shape, SH["class"], URIRef(t["parentOrRange"])))
        g.add((shape, SH.nodeKind, SH.IRI))
    else:
        g.add((shape, SH.datatype, URIRef(t["parentOrRange"])))


def build_shapes(terms: list[dict]) -> Graph:
    g = Graph()
    bind(g)
    shapes_doc = URIRef(SHAPES_BASE.removesuffix("#"))
    g.add((shapes_doc, RDF.type, OWL.Ontology))
    g.add((shapes_doc, RDFS.label, Literal("NLTL benchmark schema-only SHACL shapes")))
    g.add((shapes_doc, DCTERMS.description, Literal("Validates canonical node/value structures only. It contains no regulatory applicability, threshold, formula, comparison result, or expected pass/fail logic.")))

    entity_shape = NSH.benchmarkEntityShape
    g.add((entity_shape, RDF.type, SH.NodeShape))
    g.add((entity_shape, SH.targetClass, NLTL.benchmarkEntity))
    g.add((entity_shape, SH.closed, Literal(False)))
    g.add((entity_shape, SH.description, Literal("Open structural shape. Source profiles provide vocabulary whitelists; requirement shapes provide case-specific cardinalities later.")))

    quantity_shape = NSH.quantityValueShape
    g.add((quantity_shape, RDF.type, SH.NodeShape))
    g.add((quantity_shape, SH.targetClass, QUDT.QuantityValue))
    for path_, datatype, node_kind, label in (
        (QUDT.numericValue, XSD.decimal, None, "numeric value"),
        (QUDT.unit, None, SH.IRI, "unit"),
    ):
        p = BNode()
        g.add((quantity_shape, SH.property, p))
        g.add((p, SH.path, path_))
        g.add((p, SH.minCount, Literal(1)))
        g.add((p, SH.maxCount, Literal(1)))
        g.add((p, SH.name, Literal(label)))
        if datatype:
            g.add((p, SH.datatype, datatype))
        if node_kind:
            g.add((p, SH.nodeKind, node_kind))

    evidence_shape = NSH.evidenceArtifactShape
    g.add((evidence_shape, RDF.type, SH.NodeShape))
    g.add((evidence_shape, SH.targetClass, NLTL.evidenceArtifact))
    source_prop = BNode()
    g.add((evidence_shape, SH.property, source_prop))
    g.add((source_prop, SH.path, DCTERMS.source))
    g.add((source_prop, SH.minCount, Literal(1)))
    g.add((source_prop, SH.name, Literal("evidence source")))

    observation_shape = NSH.observationShape
    g.add((observation_shape, RDF.type, SH.NodeShape))
    g.add((observation_shape, SH.targetClass, SOSA.Observation))
    for path_, node_kind, datatype, label in (
        (SOSA.hasFeatureOfInterest, SH.IRI, None, "feature of interest"),
        (SOSA.observedProperty, SH.IRI, None, "observed property"),
        (SOSA.resultTime, None, XSD.dateTime, "result time"),
    ):
        p = BNode()
        g.add((observation_shape, SH.property, p))
        g.add((p, SH.path, path_))
        g.add((p, SH.minCount, Literal(1)))
        g.add((p, SH.maxCount, Literal(1)))
        g.add((p, SH.name, Literal(label)))
        if node_kind:
            g.add((p, SH.nodeKind, node_kind))
        if datatype:
            g.add((p, SH.datatype, datatype))

    result_choice = BNode()
    simple_result = BNode()
    node_result = BNode()
    g.add((observation_shape, SH["or"], result_choice))
    Collection(g, result_choice, [simple_result, node_result])
    g.add((simple_result, SH.path, SOSA.hasSimpleResult))
    g.add((simple_result, SH.minCount, Literal(1)))
    g.add((simple_result, SH.maxCount, Literal(1)))
    g.add((node_result, SH.path, SOSA.hasResult))
    g.add((node_result, SH.minCount, Literal(1)))
    g.add((node_result, SH.maxCount, Literal(1)))
    g.add((node_result, SH.nodeKind, SH.BlankNodeOrIRI))

    for t in terms:
        if t["kind"] != "Class":
            add_property_shape(g, entity_shape, t)
    return g


def context_for(terms: list[dict]) -> dict:
    context: dict = {
        "@version": 1.1,
        "@protected": True,
        "nltl": {"@id": VOCAB_BASE, "@prefix": True},
        "qudt": {"@id": str(QUDT), "@prefix": True},
        "unitVocab": {"@id": str(UNIT), "@prefix": True},
        "xsd": {"@id": str(XSD), "@prefix": True},
        "sosa": {"@id": str(SOSA), "@prefix": True},
        "prov": {"@id": str(PROV), "@prefix": True},
        "dct": {"@id": str(DCTERMS), "@prefix": True},
        "type": "@type",
        "id": "@id",
        "benchmarkEntity": "nltl:benchmarkEntity",
        "ship": "nltl:ship",
        "shipComponent": "nltl:shipComponent",
        "hullStructure": "nltl:hullStructure",
        "machineryComponent": "nltl:machineryComponent",
        "operationalContext": "nltl:operationalContext",
        "evidenceArtifact": "nltl:evidenceArtifact",
        "documentEvidence": "nltl:documentEvidence",
        "physicalTestEvidence": "nltl:physicalTestEvidence",
        "hasComponent": {"@id": "nltl:hasComponent", "@type": "@id"},
        "hasEvidence": {"@id": "nltl:hasEvidence", "@type": "@id"},
        "hasObservation": {"@id": "nltl:hasObservation", "@type": "@id"},
        "featureOfInterest": {"@id": "sosa:hasFeatureOfInterest", "@type": "@id"},
        "observedProperty": {"@id": "sosa:observedProperty", "@type": "@id"},
        "resultTime": {"@id": "sosa:resultTime", "@type": "xsd:dateTime"},
        "hasResult": {"@id": "sosa:hasResult", "@type": "@id"},
        "numericValue": {"@id": "qudt:numericValue", "@type": "xsd:decimal"},
        "unit": {"@id": "qudt:unit", "@type": "@id"},
    }
    for t in terms:
        if t["kind"] == "Class":
            context[t["localName"]] = f"nltl:{t['localName']}"
        elif t["kind"] in ("QuantityProperty", "ObjectProperty"):
            context[t["localName"]] = {"@id": f"nltl:{t['localName']}", "@type": "@id"}
        else:
            dt = URIRef(t["parentOrRange"])
            compact = "xsd:" + str(dt).split("#")[-1] if str(dt).startswith(str(XSD)) else str(dt)
            context[t["localName"]] = {"@id": f"nltl:{t['localName']}", "@type": compact}
    return {"@context": context}


def profile_payload(profile_id: str, title: str, terms: list[dict], requirement_ids: list[str], activation: str) -> dict:
    return {
        "profileId": PROFILE_BASE + profile_id,
        "title": title,
        "masterVocabulary": VOCAB_BASE,
        "vocabularyVersion": VERSION,
        "termRegistry": "../registry/term_registry.json",
        "jsonLdContext": "../context/nltl_benchmark_context.jsonld",
        "schemaOnlyShapes": "../shacl/schema_only_shapes.ttl",
        "unitPolicy": "Use each registry term's recommended unitIri. For the three viscosity terms only, use one manufacturer-declared viscosity quantity kind and identical unit across minimum, observation, and maximum values.",
        "activationBoundary": activation,
        "containsRequirementLogic": False,
        "requirementIds": sorted(requirement_ids),
        "allowedClasses": sorted(t["iri"] for t in terms if t["kind"] == "Class"),
        "allowedProperties": sorted(t["iri"] for t in terms if t["kind"] != "Class"),
        "termCount": len(terms),
    }


def build_profiles(data: dict, terms: list[dict]) -> dict[str, dict]:
    req_by_id = {r["id"]: r for r in data["requirements"]}
    term_by_req: defaultdict[str, set[str]] = defaultdict(set)
    term_by_local = {t["localName"]: t for t in terms}
    term_by_concept = {cid: t for t in terms for cid in t["sourceConceptIds"]}
    for r in data["requirements"]:
        for cid in [x.strip() for x in r["conceptIds"].split(";") if x.strip()]:
            if cid in term_by_concept:
                term_by_req[r["id"]].add(term_by_concept[cid]["localName"])
            elif cid not in RETIRED_STAGE1_CANDIDATES:
                raise RuntimeError(f"Requirement {r['id']} references unmapped concept {cid}")

    profiles = {}
    specs = {
        "traficom": ("TRAFICOM vocabulary whitelist", lambda r: r["sourceSheet"] == "TRAFICOM", "All locked TRAFICOM requirements; activation remains requirement-specific"),
        "iacs_ur_i2": ("IACS UR I2 vocabulary whitelist", lambda r: r["sourceSheet"] == "IACS_UR_I2", "All locked IACS UR I2 requirements; activation remains requirement-specific"),
        "imo_polar_code": ("IMO Polar Code vocabulary whitelist", lambda r: r["sourceSheet"] == "IMO_POLAR_CODE", "All locked main Polar Code requirements; activation remains requirement-specific"),
        "imo_amend_2026": ("IMO January 2026 amendment vocabulary whitelist", lambda r: r["sourceSheet"] == "IMO_AMEND_2026", "All locked amendment requirements; separate from the main Polar Code"),
        "direct_deterministic": ("Direct/deterministic Stage 2 vocabulary whitelist", lambda r: r["activeStatus"] == "Stage 2 candidate - direct/deterministic", "240 approved Static/Static Calculation candidates"),
        "evidence_and_deferred": ("Evidence/deferred vocabulary whitelist", lambda r: r["activeStatus"] != "Stage 2 candidate - direct/deterministic", "Complex, dynamic, and physical-test evidence requirements only"),
    }
    for pid, (title, predicate, activation) in specs.items():
        reqs = [r for r in data["requirements"] if predicate(r)]
        locals_ = sorted({local for r in reqs for local in term_by_req[r["id"]]})
        selected = [term_by_local[x] for x in locals_]
        profiles[pid] = profile_payload(pid, title, selected, [r["id"] for r in reqs], activation)

    profiles["master"] = profile_payload(
        "master", "Master controlled vocabulary", terms,
        [r["id"] for r in data["requirements"]],
        f"All {len(terms)} canonical Stage 2 terms derived from 823 Stage 1 candidates; this profile is a vocabulary allow-list, not a compliance rule set",
    )
    return profiles


def write_registry(terms: list[dict]) -> None:
    json_path = STAGE2 / "registry" / "term_registry.json"
    json_path.write_text(json.dumps(terms, indent=2, sort_keys=True), encoding="utf-8")
    fields = [
        "conceptId", "sourceConceptIds", "stage1LocalNames", "localName", "iri", "label", "kind", "parentOrRange", "datatype", "module",
        "roleDecision", "unitSymbol", "unitIri", "quantityKindLabel", "unitDecisionStatus", "stage2UnitEvidence", "aliases", "requirements",
        "sourceRefs", "namingBasis", "namingRule", "nameQaStatus", "confidence", "haithamUri",
    ]
    with (STAGE2 / "registry" / "term_registry.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for t in terms:
            row = {k: t.get(k, "") for k in fields}
            row["sourceConceptIds"] = "; ".join(t["sourceConceptIds"])
            row["stage1LocalNames"] = "; ".join(t["stage1LocalNames"])
            row["aliases"] = "; ".join(t["aliases"])
            row["requirements"] = "; ".join(t["requirements"])
            writer.writerow(row)


def write_example(terms: list[dict]) -> None:
    by_local = {t["localName"]: t for t in terms}
    power = by_local.get("maximumContinuousRatingPower")
    category = by_local.get("shipCategory")
    if not power or not category:
        raise RuntimeError("Expected example terms are missing")
    text = f'''@prefix ex: <https://example.org/nltl-stage2/> .
@prefix nltl: <{VOCAB_BASE}> .
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:illustrativeShip a nltl:ship ;
    nltl:shipCategory nltl:polarShipCategoryA ;
    nltl:maximumContinuousRatingPower ex:illustrativePower ;
    nltl:hasObservation ex:illustrativeObservation .

ex:illustrativePower a qudt:QuantityValue ;
    qudt:numericValue "1.0"^^xsd:decimal ;
    qudt:unit unit:KiloW .

ex:illustrativeObservation a <http://www.w3.org/ns/sosa/Observation> ;
    <http://www.w3.org/ns/sosa/hasFeatureOfInterest> ex:illustrativeShip ;
    <http://www.w3.org/ns/sosa/observedProperty> nltl:maximumContinuousRatingPower ;
    <http://www.w3.org/ns/sosa/resultTime> "2026-08-12T00:00:00Z"^^xsd:dateTime ;
    <http://www.w3.org/ns/sosa/hasResult> ex:illustrativePower .
'''
    (STAGE2 / "examples" / "illustrative_ship.ttl").write_text(text, encoding="utf-8")
    jsonld = {
        "@context": "../context/nltl_benchmark_context.jsonld",
        "@id": "https://example.org/nltl-stage2/illustrativeShip",
        "@type": "ship",
        "shipCategory": "nltl:polarShipCategoryA",
        "maximumContinuousRatingPower": {
            "@id": "https://example.org/nltl-stage2/illustrativePower",
            "@type": "qudt:QuantityValue",
            "numericValue": 1.0,
            "unit": "unitVocab:KiloW",
        },
        "hasObservation": {
            "@id": "https://example.org/nltl-stage2/illustrativeObservation",
            "@type": "sosa:Observation",
            "featureOfInterest": "https://example.org/nltl-stage2/illustrativeShip",
            "observedProperty": "nltl:maximumContinuousRatingPower",
            "resultTime": "2026-08-12T00:00:00Z",
            "hasResult": "https://example.org/nltl-stage2/illustrativePower",
        },
    }
    (STAGE2 / "examples" / "illustrative_ship.jsonld").write_text(json.dumps(jsonld, indent=2), encoding="utf-8")


def write_stage2_evidence(terms: list[dict]) -> None:
    refinements = []
    by_stage1 = {old: new for old, new in STAGE2_NAME_REFINEMENTS.items()}
    specific_reasons = {
        "deadweightTonnes": "Remove the unit token from the canonical identifier; retain tonnes as QUDT unit metadata and the Stage 1 name as lineage.",
        "sNcurveType": "Expand the standard S-N abbreviation to the readable engineering label stress-life curve; retain S-N variants as aliases.",
        "solely24HourDaylightOperation": "Express the clause condition as a readable Boolean predicate rather than misclassifying the embedded time expression as a quantity.",
    }
    for old, new in sorted(by_stage1.items()):
        refinements.append({
            "stage1LocalName": old,
            "stage2LocalName": new,
            "action": "Merged into one canonical property" if new == "propellerRotationalSpeedAtMaximumContinuousRatingBollard" else "Renamed",
            "reason": specific_reasons.get(old, "Remove unit token or expand opaque engineering abbreviation/symbol while preserving the Stage 1 name and source notation as traceability metadata."),
        })
    (STAGE2 / "registry" / "naming_refinements.json").write_text(json.dumps(refinements, indent=2), encoding="utf-8")
    (STAGE2 / "registry" / "retired_stage1_candidates.json").write_text(
        json.dumps(RETIRED_STAGE1_CANDIDATES, indent=2, sort_keys=True), encoding="utf-8"
    )

    unit_iris = sorted({t["unitIri"] for t in terms if t["unitIri"]})
    unverified = set(unit_iris) - VERIFIED_QUDT_UNIT_URIS
    if unverified:
        raise RuntimeError(f"Unverified QUDT unit URI(s): {sorted(unverified)}")
    verified_units = [{
        "uri": uri,
        "officialVocabulary": "QUDT Units",
        "officialResource": uri + ".html",
        "officialVocabularyIndex": "https://www.qudt.org/doc/DOC_VOCAB-UNITS.html",
        "verifiedDate": GENERATED_DATE,
        "verificationStatus": "Exact QUDT unit local identifier present in the official QUDT units vocabulary",
    } for uri in unit_iris]
    (STAGE2 / "evidence" / "external_uri_verification.json").write_text(json.dumps({
        "policy": "Only exact URIs are asserted. No DNV GMOD exact mapping is claimed because no versioned exact GMOD code/path was verified for a candidate term.",
        "qudtUnits": verified_units,
        "w3cNamespaces": [
            "http://www.w3.org/2001/XMLSchema#",
            "http://www.w3.org/ns/sosa/",
            "http://www.w3.org/ns/prov#",
            "http://www.w3.org/2004/02/skos/core#",
        ],
    }, indent=2), encoding="utf-8")


def write_manifest(data: dict, terms: list[dict], profiles: dict[str, dict]) -> None:
    counts = Counter(t["kind"] for t in terms)
    modules = Counter(t["module"] for t in terms)
    datatypes = Counter(t["parentOrRange"] for t in terms if t["kind"] == "DatatypeProperty")
    manifest = {
        "stage": 2,
        "version": VERSION,
        "generatedDate": GENERATED_DATE,
        "provisionalVocabularyBase": VOCAB_BASE,
        "stage1LockId": data["summary"]["lockId"],
        "lockedWorkbookSha256": data["summary"]["lockedWorkbookActualSha256"],
        "stage1ApprovedSnapshotSha256": sha256(SNAPSHOT),
        "requirements": len(data["requirements"]),
        "terms": len(terms),
        "stage1CandidateTerms": len(data["concepts"]),
        "stage2NamingRefinementRows": len(STAGE2_NAME_REFINEMENTS),
        "stage2SemanticMerges": len(data["concepts"]) - len(RETIRED_STAGE1_CANDIDATES) - len(terms),
        "retiredStage1Candidates": len(RETIRED_STAGE1_CANDIDATES),
        "termKinds": dict(counts),
        "modules": dict(modules),
        "datatypes": dict(datatypes),
        "profiles": {k: {"termCount": v["termCount"], "requirementCount": len(v["requirementIds"])} for k, v in profiles.items()},
        "containsRegulatoryAnswerLogic": False,
        "publicationLimitations": data.get("publicationLimitations", []),
    }
    (STAGE2 / "stage2_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    data = load_data()
    active_candidates = [c for c in data["concepts"] if c["conceptId"] not in RETIRED_STAGE1_CANDIDATES]
    terms = merge_terms([decide_term(c) for c in active_candidates])
    expected_terms = len(data["concepts"]) - len(RETIRED_STAGE1_CANDIDATES) - 1  # one duplicate pair is folded
    if len(terms) != expected_terms or len({t["localName"] for t in terms}) != expected_terms:
        raise RuntimeError(f"Stage 2 expected {expected_terms} unique canonical terms after one documented merge")

    ontology = build_ontology(terms)
    ontology.serialize(STAGE2 / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
    ontology.serialize(STAGE2 / "ontology" / "nltl_benchmark_vocabulary.rdf", format="xml")

    mappings = build_mappings(terms)
    mappings.serialize(STAGE2 / "mappings" / "haitham_exact_mappings.ttl", format="turtle")

    shapes = build_shapes(terms)
    shapes.serialize(STAGE2 / "shacl" / "schema_only_shapes.ttl", format="turtle")

    (STAGE2 / "context" / "nltl_benchmark_context.jsonld").write_text(
        json.dumps(context_for(terms), indent=2, sort_keys=True), encoding="utf-8"
    )

    profiles = build_profiles(data, terms)
    for pid, payload in profiles.items():
        (STAGE2 / "profiles" / f"{pid}.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    write_registry(terms)
    write_stage2_evidence(terms)
    write_example(terms)
    write_manifest(data, terms, profiles)
    print(json.dumps(json.loads((STAGE2 / "stage2_manifest.json").read_text()), indent=2))


if __name__ == "__main__":
    main()
