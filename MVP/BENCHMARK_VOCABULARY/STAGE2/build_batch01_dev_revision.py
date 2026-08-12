from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import DCTERMS, OWL, SKOS, XSD


MVP = Path(__file__).resolve().parents[2]
R2 = MVP / "BENCHMARK_VOCABULARY" / "STAGE2_R2"
OUT = MVP / "BENCHMARK_VOCABULARY" / "DEVELOPMENT" / "DEV_R5_BATCH01"
BATCH = MVP / "INPUTS" / "DEVELOPMENT_CALIBRATION" / "BATCH_01_FIRST_50"
R2_INDEX = MVP / "BENCHMARK_VOCABULARY" / "PIPELINE_CONTEXT" / "R2" / "requirement_term_index.json"
DEV_INDEX = OUT / "requirement_term_index.json"
BASE = "https://w3id.org/nltl-benchmark/vocab#"
VERSION = "2.5.0-dev-batch01"
DEV_ID = "VOCAB-DEV-2026-08-12-BATCH01-R5"

NLTL = Namespace(BASE)
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def label(local: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", local).replace(" point ", " point ").capitalize()


# These redirects are semantic consolidations, not spelling-only changes.
REDIRECTS = {
    # "All regions" is represented by all three hull-region IRIs, not a pseudo-region value.
    "allRegions": "hasAntitrippingSupportRegion",
    "antitrippingSupportRegion": "hasAntitrippingSupportRegion",
    "attachedToSupportingStructure": "hasAttachedSupportingStructure",
    "coefficientA": "shipSizeEngineOutputCoefficientA",
    "coefficientB": "shipSizeEngineOutputCoefficientB",
    "coefficientK": "shipSizeEngineOutputCoefficientK",
    "classificationSocietySectionPropertyCalculationEvidence": "hasClassificationSocietySectionPropertyCalculationEvidence",
    "combinedBendingShearCapacity": "combinedBendingAndShearEvaluated",
    "fixedPitchPropeller": "fixedPitch",
    "controllablePitchPropeller": "controllablePitch",
    "longitudinalFraming": "longitudinalFramingOrientation",
    # c_a is the same ice-load-area factor in the pressure/load-length clauses.
    "loadLengthCoefficientCa": "iceLoadAreaFactorCa",
    "transverseFraming": "transverseFramingOrientation",
    "netActualFrameShearArea": "actualFrameShearArea",
    "terminatesAboveSupportingStructure": "hasTerminationAboveSupportingStructure",
    "terminatesBelowSupportingStructure": "hasTerminationBelowSupportingStructure",
    # This label describes the result of a length comparison, not a raw input.
    "veryLongHatch": "hatchOpeningLength",
    # Table 4-8 is selected by A_f/A_w, not an informal cross-section type.
    "webFrameCrossSectionType": "freeFlangeToWebAreaRatio",
}

# Supporting terms are necessary to make the candidate properties typeable. They
# contain schema semantics only; no regulatory threshold or pass/fail answer.
SUPPORT_TERMS = {
    "documentArtifact", "frameEnd", "iceClassRegulationEditionValue",
    "engineOutputComplianceMethodValue", "propellerPitchControlTypeValue", "propulsionSystemTypeValue",
    "platingFramingOrientationValue", "frameProfileTypeValue", "weldTypeValue", "iceLoadSourceTypeValue",
    "hasClassCertificate", "hasIceDraughtRestrictionDocument",
    "hasEffectiveMemberCrossSection", "hasIceClassDesignParameterSet", "grossFrameShearArea",
    "propellerPitchControlType", "hasClassificationSocietySectionPropertyCalculationEvidence",
    "hullRegionValue", "hullRegion", "sternRegion", "frameBoundaryConditionTypeValue",
    "frameBoundaryConditionType", "bulkCarrierTopWingTankFrameCondition",
    "singleDeckTankTopToMainDeckFrameCondition", "multiDeckOrStringerContinuousFrameCondition",
    "twoDeckFrameCondition", "freeFlangeArea", "webPlateArea", "freeFlangeToWebAreaRatio",
    "requiredShellPlatingThickness", "frameWebThickness", "netShellPlatingThickness",
    "frameShellWeldType", "steelGradeValue", "hullStructuralSteelGrade",
    "normalStrengthHullStructuralSteel", "highStrengthHullStructuralSteel",
    "hasHatchCoverDesignEvidence", "hasHatchFittingDesignEvidence",
    "framingIceStrengtheningAboveUpperIceWaterline", "framingIceStrengtheningBelowLowerIceWaterline",
    "reachesUpperBowIceBeltTop", "frameShearDistributionFactorF3", "longitudinalFrameShearFactorF5",
    "iceStringerDistributionFactorF6", "iceStringerSafetyFactorF7", "iceStringerShearFactorF8",
    "outsideIceBeltDistributionFactorF9", "outsideIceBeltSafetyFactorF10", "outsideIceBeltShearFactorF11",
    "webFrameShearDistributionFactorF13",
    "transversePlatingFactorF1", "longitudinalPlatingFactorF2",
    "longitudinalFrameLoadDistributionFactorF4",
    "iceClassRegulatoryProvisionValue", "applicableIceClassRegulatoryProvision",
    "iceClassSection1Point8Provision2021", "iceClassDraughtChapter2Provision2021",
    "loadPositionTypeValue", "frameBoundaryConditionEvidence",
    "kilogramPerSquareMetreSquareSecondUnit", "kilogramPerSquareSecondUnit",
    "newtonPerMetreToPowerOnePointFiveUnit",
    "gramPerKilogramSalinityUnit", "requiredSectionModulus", "actualSectionModulus",
    "actualShearArea", "abreastOfHatch",
}

CLASS_TERMS = {
    "ballastTank", "classCertificate", "directAnalysisCase", "documentArtifact", "effectiveMemberCrossSection",
    "frameEnd", "horizontalConnectionMember", "iceClassDesignParameterSet", "iceDraughtRestrictionDocument",
    "iceWaterline", "profileSection", "waterlineProfilePoint", "narrowDeckStrip",
    "iceClassRegulationEditionValue", "engineOutputComplianceMethodValue",
    "propellerPitchControlTypeValue", "propulsionSystemTypeValue", "platingFramingOrientationValue",
    "frameProfileTypeValue", "weldTypeValue", "iceLoadSourceTypeValue", "hullRegionValue",
    "frameBoundaryConditionTypeValue",
    "steelGradeValue",
    "iceClassRegulatoryProvisionValue",
    "iceStringer", "mainFrame", "intermediateIceFrame", "longitudinalFrame",
    "deckStructure", "tankBoundaryPlating", "tankBottom", "bulkhead", "weatherdeckHatch",
    "loadPositionTypeValue", "frameBoundaryConditionEvidence",
}

VALUE_TYPES = {
    "iceClassRegulationEdition2002": "iceClassRegulationEditionValue",
    "iceClassRegulationEdition2008": "iceClassRegulationEditionValue",
    "iceClassRegulationEdition2010": "iceClassRegulationEditionValue",
    "iceClassRegulationEdition2017": "iceClassRegulationEditionValue",
    "iceClassRegulationEdition2021": "iceClassRegulationEditionValue",
    "iceClassRuleEdition1985": "iceClassRegulationEditionValue",
    "traficom2017Section3Point2Point2Method": "engineOutputComplianceMethodValue",
    "traficom2017Section3Point2Point4Method": "engineOutputComplianceMethodValue",
    "fixedPitch": "propellerPitchControlTypeValue",
    "controllablePitch": "propellerPitchControlTypeValue",
    "conventionalPropulsionSystem": "propulsionSystemTypeValue",
    "electricPropulsionMachinery": "propulsionSystemTypeValue",
    "hydraulicPropulsionMachinery": "propulsionSystemTypeValue",
    "longitudinalFramingOrientation": "platingFramingOrientationValue",
    "transverseFramingOrientation": "platingFramingOrientationValue",
    "profileSection": "frameProfileTypeValue",
    "flatBarSection": "frameProfileTypeValue",
    "doubleContinuousWeld": "weldTypeValue",
    "bowRegion": "hullRegionValue",
    "midbodyRegion": "hullRegionValue",
    "sternRegion": "hullRegionValue",
    "iceStringerLoadSource": "iceLoadSourceTypeValue",
    "longitudinalFramingLoadSource": "iceLoadSourceTypeValue",
    "bulkCarrierTopWingTankFrameCondition": "frameBoundaryConditionTypeValue",
    "singleDeckTankTopToMainDeckFrameCondition": "frameBoundaryConditionTypeValue",
    "multiDeckOrStringerContinuousFrameCondition": "frameBoundaryConditionTypeValue",
    "twoDeckFrameCondition": "frameBoundaryConditionTypeValue",
    "normalStrengthHullStructuralSteel": "steelGradeValue",
    "highStrengthHullStructuralSteel": "steelGradeValue",
    "iceClassSection1Point8Provision2021": "iceClassRegulatoryProvisionValue",
    "iceClassDraughtChapter2Provision2021": "iceClassRegulatoryProvisionValue",
    "upperIceWaterlineCenteredPosition": "loadPositionTypeValue",
    "halfLoadHeightBelowLowerIceWaterlinePosition": "loadPositionTypeValue",
    "intermediateVerticalPosition": "loadPositionTypeValue",
    "midSpanOrSpacingCenteredPosition": "loadPositionTypeValue",
    "otherHorizontalPosition": "loadPositionTypeValue",
    "kilogramPerSquareMetreSquareSecondUnit": "http://qudt.org/schema/qudt/Unit",
    "kilogramPerSquareSecondUnit": "http://qudt.org/schema/qudt/Unit",
    "newtonPerMetreToPowerOnePointFiveUnit": "http://qudt.org/schema/qudt/Unit",
    "gramPerKilogramSalinityUnit": "http://qudt.org/schema/qudt/Unit",
}

OBJECT_RANGES = {
    "applicableIceClassRegulationEdition": "iceClassRegulationEditionValue",
    "engineOutputRegulationEdition": "iceClassRegulationEditionValue",
    "engineOutputComplianceMethod": "engineOutputComplianceMethodValue",
    "propulsionSystemType": "propulsionSystemTypeValue",
    "propellerPitchControlType": "propellerPitchControlTypeValue",
    "platingFramingOrientation": "platingFramingOrientationValue",
    "frameProfileType": "frameProfileTypeValue",
    "hasAntitrippingSupportRegion": "hullRegionValue",
    "iceLoadSourceType": "iceLoadSourceTypeValue",
    "hullRegion": "hullRegionValue",
    "frameBoundaryConditionType": "frameBoundaryConditionTypeValue",
    "frameShellWeldType": "weldTypeValue",
    "hullStructuralSteelGrade": "steelGradeValue",
    "applicableIceClassRegulatoryProvision": "iceClassRegulatoryProvisionValue",
    "hasUpperIceWaterline": "iceWaterline",
    "hasLowerIceWaterline": "iceWaterline",
    "hasIntendedIceOperatingWaterline": "iceWaterline",
    "hasWaterlineProfilePoint": "waterlineProfilePoint",
    "hasBallastTank": "ballastTank",
    "hasDirectAnalysisCase": "directAnalysisCase",
    "hasUpperEnd": "frameEnd",
    "hasLowerEnd": "frameEnd",
    "hasAttachedSupportingStructure": "supportingStructure",
    "hasTerminationAboveSupportingStructure": "supportingStructure",
    "hasTerminationBelowSupportingStructure": "supportingStructure",
    "hasSupportingWebFrame": "supportingStructure",
    "hasSupportingBulkhead": "supportingStructure",
    "hasFrameAttachment": "frameAttachment",
    "hasClassCertificate": "classCertificate",
    "hasIceDraughtRestrictionDocument": "iceDraughtRestrictionDocument",
    "hasEffectiveMemberCrossSection": "effectiveMemberCrossSection",
    "hasIceClassDesignParameterSet": "iceClassDesignParameterSet",
    "hasClassificationSocietySectionPropertyCalculationEvidence": "evidenceArtifact",
    "hasHatchCoverDesignEvidence": "hatchCoverDesignEvidence",
    "hasHatchFittingDesignEvidence": "hatchFittingDesignEvidence",
    "hasHorizontalConnectionMember": "horizontalConnectionMember",
    "connectsToAdjacentMainFrame": "mainFrame",
    "hasWeatherdeckHatch": "weatherdeckHatch",
    "verticalLoadPositionType": "loadPositionTypeValue",
    "horizontalLoadPositionType": "loadPositionTypeValue",
    "hasFrameBoundaryConditionEvidence": "frameBoundaryConditionEvidence",
    "hasConnectionBracket": "connectionBracket",
}

DATE_TERMS = {"deliveryDate", "assessmentDate", "firstScheduledDryDockingDate"}
INTEGER_TERMS = {"webPlateConnectionSideCount"}

EXPLICIT_QUANTITY_TERMS = {
    "classificationSocietyRequiredScantling", "regulationRequiredScantling", "selectedDesignScantling",
    "maximumPermittedIceTrim", "framingIceStrengtheningAboveUpperIceWaterline",
    "framingIceStrengtheningBelowLowerIceWaterline",
    "iceClassDraughtMarkDraughtAmidships", "continuousPropulsionPowerAvailableInIce",
    "brashIceChannelResistanceAtUpperIceWaterline", "brashIceChannelResistanceAtLowerIceWaterline",
    "distanceToIceBelt", "distanceToAdjacentIceStringer",
    "requiredSectionModulus", "actualSectionModulus", "actualShearArea",
}

BOOLEAN_WORDS = (
    "Present", "Maintained", "Applies", "Required", "Used", "Stiffened", "Strengthened", "Available",
    "Retained", "Situated", "Permitted", "Determined", "NormalToPlating", "SameScantlings", "ServesAs",
    "VeryLong", "Narrow", "Supported", "UsedToReach",
)
BOOLEAN_TERMS = {
    "bracketEdgeStiffened", "iceClassDraughtMarkPresent", "loadLengthDeterminedFromArrangement",
    "combinedBendingAndShearEvaluated",
    "reachesUpperBowIceBeltTop",
    "mainFrameBelowIceBeltStrengthened", "memberNormalToPlating", "ordinaryFrameScantlingsUsed",
    "propulsionOutputRestrictionApplies", "readilyAvailableToMaster", "retainedOnBoard",
    "sameScantlingsAsMainFrame", "servesAsIceStringer", "situatedAboveLowerIceWaterline",
    "specialSurfaceCoatingMaintained", "supportedStringerOutsideIceBelt",
    "supportingStructureAtOrAboveIceBeltUpperLimit", "supportingStructureAtOrBelowIceBeltLowerLimit",
    "usedToReachLowerIceWaterline", "veryLongHatch", "warningTrianglePresent", "iceClassDraughtMarkPresent",
    "navigatingInIce", "capacityMinimizingLoadPositionConfirmed", "withinIceStrengthenedArea",
    "effectiveAttachmentConfirmed", "passesThroughSupportingStructure", "terminatesAtDeckOrIceStringer",
    "inLieuOfFrame", "locatedWithinIceBelt", "locatedOutsideIceBelt", "supportsIceStrengthenedFrames",
    "significantlyDifferentBoundaryConditions",
    "abreastOfHatch",
}

UNITS: dict[str, tuple[str, str, str]] = {
    "Power": ("kW", str(UNIT.KiloW), "Power"),
    "Output": ("kW", str(UNIT.KiloW), "Power"),
    "Force": ("kN", str(UNIT.KiloN), "Force"),
    "Pressure": ("MPa", str(UNIT.MegaPA), "Pressure"),
    "Area": ("cm^2", str(UNIT.CentiM2), "Area"),
    "SectionModulus": ("cm^3", str(UNIT.CentiM3), "Volume"),
    "Draught": ("m", str(UNIT.M), "Length"),
    "Displacement": ("t", str(UNIT.TON_Metric), "Mass"),
    "Thickness": ("mm", str(UNIT.MilliM), "Length"),
    "Height": ("m", str(UNIT.M), "Length"),
    "Length": ("m", str(UNIT.M), "Length"),
    "Span": ("m", str(UNIT.M), "Length"),
    "Position": ("m", str(UNIT.M), "Length"),
    "Distance": ("m", str(UNIT.M), "Length"),
    "Coordinate": ("m", str(UNIT.M), "Length"),
    "Angle": ("deg", str(UNIT.DEG), "Angle"),
    "Trim": ("m", str(UNIT.M), "Length"),
    "Salinity": ("g/kg", BASE + "gramPerKilogramSalinityUnit", "Mass fraction"),
    "Stress": ("MPa", str(UNIT.MegaPA), "Pressure"),
    "LineLoad": ("kN/m", str(UNIT["KiloN-PER-M"]), "Force per length"),
    "Scantling": ("", "", "Quantity selected per scantling measure and unit"),
}

UNITLESS_HINTS = (
    "Coefficient", "Factor", "Alpha", "Ratio", "SideCount",
)

NO_FIXED_UNIT_TERMS = {
    "brashIceResistanceCoefficientC1", "brashIceResistanceCoefficientC2",
    "classificationSocietyRequiredScantling", "regulationRequiredScantling", "selectedDesignScantling",
}

MILLIMETRE_TERMS = {
    "adjacentFrameHeight", "requiredShellPlatingThickness", "frameWebThickness", "netShellPlatingThickness",
}

METRE_TERMS = {
    "framingIceStrengtheningAboveUpperIceWaterline", "framingIceStrengtheningBelowLowerIceWaterline",
}

PARENT_CLASSES = {
    "ballastTank": "shipComponent", "classCertificate": "documentArtifact",
    "iceDraughtRestrictionDocument": "documentArtifact", "directAnalysisCase": "benchmarkEntity",
    "documentArtifact": "evidenceArtifact", "effectiveMemberCrossSection": "benchmarkEntity",
    "frameEnd": "hullStructure", "horizontalConnectionMember": "hullStructure",
    "iceClassDesignParameterSet": "benchmarkEntity", "iceWaterline": "benchmarkEntity",
    "waterlineProfilePoint": "benchmarkEntity", "narrowDeckStrip": "hullStructure",
    "iceStringer": "hullStructure", "mainFrame": "frame", "intermediateIceFrame": "frame",
    "longitudinalFrame": "frame", "deckStructure": "hullStructure", "tankBoundaryPlating": "plating",
    "tankBottom": "tankBoundaryPlating", "bulkhead": "hullStructure", "weatherdeckHatch": "shipComponent",
    "loadPositionTypeValue": "benchmarkEntity", "frameBoundaryConditionEvidence": "evidenceArtifact",
}

PROPERTY_DOMAINS = {
    "hasUpperIceWaterline": "ship", "hasLowerIceWaterline": "ship",
    "hasIntendedIceOperatingWaterline": "ship", "hasDirectAnalysisCase": "ship",
    "hasWaterlineProfilePoint": "iceWaterline",
    "longitudinalPosition": "waterlineProfilePoint", "verticalCoordinate": "waterlineProfilePoint",
    "waterlineDisplacement": "iceWaterline", "hasUpperEnd": "transverseFrame", "hasLowerEnd": "transverseFrame",
    "hasAttachedSupportingStructure": "frameEnd", "hasTerminationAboveSupportingStructure": "frameEnd",
    "hasTerminationBelowSupportingStructure": "frameEnd", "hasFrameAttachment": "frame",
    "hasHorizontalConnectionMember": "frameEnd", "connectsToAdjacentMainFrame": "horizontalConnectionMember",
    "hasFrameBoundaryConditionEvidence": "longitudinalFrame", "hasConnectionBracket": "frameAttachment",
    "hasWeatherdeckHatch": "ship", "verticalLoadPositionType": "directAnalysisCase",
    "horizontalLoadPositionType": "directAnalysisCase",
    "verticalLoadPosition": "directAnalysisCase", "horizontalLoadPosition": "directAnalysisCase",
    "loadPatchLength": "directAnalysisCase", "iceLoadAreaFactorCa": "directAnalysisCase",
    "capacityMinimizingLoadPositionConfirmed": "directAnalysisCase",
    "combinedBendingAndShearEvaluated": "directAnalysisCase",
    "hasIceClassDesignParameterSet": "ship", "levelIceThickness": "iceClassDesignParameterSet",
    "designIceLoadHeight": "iceClassDesignParameterSet",
    "framingIceStrengtheningAboveUpperIceWaterline": "frame",
    "framingIceStrengtheningBelowLowerIceWaterline": "frame",
    "reachesUpperBowIceBeltTop": "frame",
    "frameBoundaryConditionType": "transverseFrame", "frameBoundaryConditionFactorM0": "transverseFrame",
    "frameMomentFactorMt": "transverseFrame", "frameShearDistributionFactorF3": "transverseFrame",
    "requiredSectionModulus": "narrowDeckStrip", "actualSectionModulus": "narrowDeckStrip",
    "requiredShearArea": "hullStructure", "actualShearArea": "narrowDeckStrip",
    "abreastOfHatch": "narrowDeckStrip", "servesAsIceStringer": "narrowDeckStrip",
    "permittedReducedLineLoad": "narrowDeckStrip", "scantlingApprovalStatus": "narrowDeckStrip",
    "freeFlangeArea": "webFrame", "webPlateArea": "webFrame",
    "freeFlangeToWebAreaRatio": "webFrame", "webFrameShearFactorAlpha": "webFrame",
    "webFrameShearDistributionFactorF13": "webFrame", "maximumCalculatedShearForce": "webFrame",
}


# Terms exposed by actual generation/validation failures.  Every item is still
# grounded in the cited Batch 01 clause; this is development calibration, not a
# final benchmark lock.
CALIBRATION_GAP_TERMS = {
    "TRF-014": {"iceClassDraughtMarkDraughtAmidships"},
    "TRF-015": {"navigatingInIce"},
    "TRF-016": {"navigatingInIce"},
    "TRF-020": {"brashIceChannelResistanceAtUpperIceWaterline", "brashIceChannelResistanceAtLowerIceWaterline", "electricPropulsionMachinery", "hydraulicPropulsionMachinery"},
    "TRF-030": {
        "capacityMinimizingLoadPositionConfirmed", "verticalLoadPositionType", "horizontalLoadPositionType",
        "upperIceWaterlineCenteredPosition", "halfLoadHeightBelowLowerIceWaterlinePosition",
        "intermediateVerticalPosition", "midSpanOrSpacingCenteredPosition", "otherHorizontalPosition",
    },
    "TRF-034": {"iceStringer"},
    "TRF-037": {"continuousPropulsionPowerAvailableInIce"},
    "TRF-046": {
        "mainFrame", "intermediateIceFrame", "deckStructure", "tankBoundaryPlating", "iceStringer",
        "hasHorizontalConnectionMember", "connectsToAdjacentMainFrame",
    },
    "TRF-047": {
        "mainFrame", "intermediateIceFrame", "deckStructure", "tankBoundaryPlating", "tankTop", "iceStringer",
        "hasHorizontalConnectionMember", "connectsToAdjacentMainFrame",
    },
    "TRF-048": {
        "longitudinalFrame", "frameBoundaryConditionEvidence", "hasFrameBoundaryConditionEvidence",
        "significantlyDifferentBoundaryConditions",
    },
    "TRF-049": {
        "longitudinalFrame", "transverseFrame", "withinIceStrengthenedArea", "effectiveAttachmentConfirmed",
        "passesThroughSupportingStructure", "terminatesAtDeckOrIceStringer", "hasConnectionBracket",
    },
    "TRF-043": {"frame"},
    "TRF-051": {"deckStructure", "tankBoundaryPlating", "tankBottom", "tankTop", "bulkhead", "inLieuOfFrame"},
    "TRF-053": {"iceStringer", "locatedWithinIceBelt"},
    "TRF-054": {
        "iceStringer", "locatedOutsideIceBelt", "supportsIceStrengthenedFrames",
        "distanceToIceBelt", "distanceToAdjacentIceStringer",
    },
    "TRF-055": {"abreastOfHatch", "requiredSectionModulus", "actualSectionModulus", "actualShearArea"},
    "TRF-056": {"weatherdeckHatch", "hasWeatherdeckHatch"},
}


def candidate_sources() -> tuple[dict[str, set[str]], dict[str, dict]]:
    preflight = read_json(BATCH / "engineering_preflight.json")["requirements"]
    evidence = read_json(OUT / "evidence" / "stage1_approved.json")
    requirements = {item["id"]: item for item in evidence["requirements"]}
    sources: dict[str, set[str]] = defaultdict(set)
    for row in preflight:
        rid = row["requirement_id"]
        for draft in row["draft_new_terms"]:
            sources[REDIRECTS.get(draft, draft)].add(rid)
    # Keep supporting-schema provenance focused on the clauses that need it.
    focused = {
        "documentArtifact": {"TRF-014", "TRF-034"}, "frameEnd": {"TRF-046", "TRF-047"},
        "hasClassCertificate": {"TRF-014"}, "hasIceDraughtRestrictionDocument": {"TRF-014"},
        "hasEffectiveMemberCrossSection": {"TRF-034"}, "hasIceClassDesignParameterSet": {"TRF-036"},
        "grossFrameShearArea": {"TRF-048"}, "propellerPitchControlType": {"TRF-020"},
        "hasClassificationSocietySectionPropertyCalculationEvidence": {"TRF-034"},
        "hullRegion": {"TRF-035", "TRF-037", "TRF-043", "TRF-052"},
        "bowRegion": {"TRF-035", "TRF-037", "TRF-043", "TRF-052"},
        "midbodyRegion": {"TRF-035", "TRF-037", "TRF-043", "TRF-052"},
        "sternRegion": {"TRF-035", "TRF-037", "TRF-043", "TRF-052"},
        "frameBoundaryConditionType": {"TRF-044"},
        "bulkCarrierTopWingTankFrameCondition": {"TRF-044"},
        "singleDeckTankTopToMainDeckFrameCondition": {"TRF-044"},
        "multiDeckOrStringerContinuousFrameCondition": {"TRF-044"},
        "twoDeckFrameCondition": {"TRF-044"},
        "freeFlangeArea": {"TRF-059"}, "webPlateArea": {"TRF-059"},
        "freeFlangeToWebAreaRatio": {"TRF-059"},
        "requiredShellPlatingThickness": {"TRF-041", "TRF-042"},
        "frameWebThickness": {"TRF-049", "TRF-051"},
        "netShellPlatingThickness": {"TRF-051"},
        "frameShellWeldType": {"TRF-050"},
        "hullStructuralSteelGrade": {"TRF-041", "TRF-042", "TRF-051"},
        "normalStrengthHullStructuralSteel": {"TRF-041", "TRF-042", "TRF-051"},
        "highStrengthHullStructuralSteel": {"TRF-041", "TRF-042", "TRF-051"},
        "hasHatchCoverDesignEvidence": {"TRF-056"},
        "hasHatchFittingDesignEvidence": {"TRF-056"},
        "framingIceStrengtheningAboveUpperIceWaterline": {"TRF-043"},
        "framingIceStrengtheningBelowLowerIceWaterline": {"TRF-043"},
        "reachesUpperBowIceBeltTop": {"TRF-043"},
        "frameShearDistributionFactorF3": {"TRF-044"},
        "longitudinalFrameShearFactorF5": {"TRF-048"},
        "iceStringerDistributionFactorF6": {"TRF-053"},
        "iceStringerSafetyFactorF7": {"TRF-053"},
        "iceStringerShearFactorF8": {"TRF-053"},
        "outsideIceBeltDistributionFactorF9": {"TRF-054"},
        "outsideIceBeltSafetyFactorF10": {"TRF-054"},
        "outsideIceBeltShearFactorF11": {"TRF-054"},
        "webFrameShearDistributionFactorF13": {"TRF-059"},
        "transversePlatingFactorF1": {"TRF-041"},
        "longitudinalPlatingFactorF2": {"TRF-041", "TRF-042"},
        "longitudinalFrameLoadDistributionFactorF4": {"TRF-048"},
        "applicableIceClassRegulatoryProvision": {"TRF-001"},
        "iceClassSection1Point8Provision2021": {"TRF-001"},
        "iceClassDraughtChapter2Provision2021": {"TRF-001"},
        "kilogramPerSquareMetreSquareSecondUnit": {"TRF-022", "TRF-027"},
        "kilogramPerSquareSecondUnit": {"TRF-022", "TRF-027"},
        "newtonPerMetreToPowerOnePointFiveUnit": {"TRF-022", "TRF-027"},
        "gramPerKilogramSalinityUnit": {"TRF-015"},
    }
    for name, ids in focused.items(): sources[name] = set(ids)
    for rid, names in CALIBRATION_GAP_TERMS.items():
        for name in names:
            sources[name].add(rid)
    # Value classes inherit provenance from their property/value users.
    for name in CLASS_TERMS:
        if not sources[name]:
            dependent = [n for n, parent in VALUE_TYPES.items() if parent == name]
            for child in dependent: sources[name].update(sources[child])
            for prop, rng in OBJECT_RANGES.items():
                if rng == name: sources[name].update(sources[prop])
    return sources, requirements


def enrich_verified_evidence() -> None:
    """Append table values checked directly against TRAFICOM pages 9-24."""
    path = OUT / "evidence" / "stage1_approved.json"
    payload = read_json(path)
    additions = {
        "TRF-020": " Table 3-1 values for conventional propulsion systems: 1 propeller: CP propeller or electric or hydraulic propulsion machinery 2.03, FP propeller 2.26; 2 propellers: 1.44 and 1.60; 3 propellers: 1.18 and 1.31.",
        "TRF-022": " Table 3-2 values: f1=23 N/m2, f2=45.8 N/m, f3=14.7 N/m, f4=29 N/m2, g1=1530 N, g2=170 N/m, g3=400 N/m1.5.",
        "TRF-027": " Section 3.2.4 applies to IA Super or IA ships whose keel was laid or which were at a similar stage of construction before 1 September 2003. Table 3-3 values: f1=10.3 N/m2, f2=45.8 N/m, f3=2.94 N/m, f4=5.8 N/m2, g1=1530 N, g2=170 N/m, g3=400 N/m1.5.",
        "TRF-036": " Table 4-1 values (ice class: hi, h in metres): IA Super: 1.0, 0.35; IA: 0.8, 0.30; IB: 0.6, 0.25; IC: 0.4, 0.22.",
        "TRF-043": " Table 4-6 values: IA Super framing above UIWL 1.2 m; below LIWL bow down to tank top or below top of floors, midbody 2.0 m, stern 1.6 m. IA, IB and IC framing above UIWL 1.0 m; below LIWL bow 1.6 m, midbody 1.3 m, stern 1.0 m.",
        "TRF-044": " Table 4-7 m0 values: bulk carrier frames with top wing tanks 7; frames from tank top to main deck of a single-decked vessel 6; continuous frames between several decks or stringers 5.7; frames between two decks only 5.",
        "TRF-059": " Table 4-8 (Af/Aw: alpha, gamma): 0:1.5,0; 0.2:1.23,0.44; 0.4:1.16,0.62; 0.6:1.11,0.71; 0.8:1.09,0.76; 1.0:1.07,0.80; 1.2:1.06,0.83; 1.4:1.05,0.85; 1.6:1.05,0.87; 1.8:1.04,0.88; 2.0:1.04,0.89.",
    }
    for requirement in payload["requirements"]:
        suffix = additions.get(requirement["id"])
        if suffix and suffix.strip() not in requirement["sourceText"]:
            requirement["sourceText"] += suffix
            requirement["normalizedRequirement"] += suffix
    write_json(path, payload)


def infer_spec(name: str, ids: set[str], reqs: dict[str, dict]) -> dict:
    source_refs = []
    evidence = []
    for rid in sorted(ids):
        r = reqs[rid]
        source_refs.append(f"{rid} | TRAFICOM p.{r['page']} | {r['clause']}")
        evidence.append(f"[{rid}] {r['sourceText']}")

    if name in VALUE_TYPES:
        kind, parent, datatype = "NamedIndividual", VALUE_TYPES[name], ""
    elif name in CLASS_TERMS:
        kind, parent, datatype = "Class", PARENT_CLASSES.get(name, "benchmarkEntity"), ""
    elif name in OBJECT_RANGES:
        kind, parent, datatype = "ObjectProperty", OBJECT_RANGES[name], ""
    elif name in EXPLICIT_QUANTITY_TERMS:
        kind, parent, datatype = "QuantityProperty", str(QUDT.QuantityValue), ""
    elif name in DATE_TERMS:
        kind, parent, datatype = "DatatypeProperty", str(XSD.date), "xsd:date"
    elif name in INTEGER_TERMS:
        kind, parent, datatype = "DatatypeProperty", str(XSD.integer), "xsd:integer"
    elif name in BOOLEAN_TERMS or any(word in name for word in BOOLEAN_WORDS):
        kind, parent, datatype = "DatatypeProperty", str(XSD.boolean), "xsd:boolean"
    else:
        unit = next((value for key, value in UNITS.items() if key.lower() in name.lower()), None)
        if unit or any(key.lower() in name.lower() for key in UNITLESS_HINTS):
            kind, parent, datatype = "QuantityProperty", str(QUDT.QuantityValue), ""
        else:
            kind, parent, datatype = "DatatypeProperty", str(XSD.string), "xsd:string"

    unit_symbol = unit_iri = quantity_kind = ""
    if kind == "QuantityProperty":
        unit = next((value for key, value in UNITS.items() if key.lower() in name.lower()), None)
        if name in MILLIMETRE_TERMS:
            unit_symbol, unit_iri, quantity_kind = "mm", str(UNIT.MilliM), "Length"
        elif name in METRE_TERMS:
            unit_symbol, unit_iri, quantity_kind = "m", str(UNIT.M), "Length"
        elif name in NO_FIXED_UNIT_TERMS:
            if "Salinity" in name:
                unit_symbol, quantity_kind = "g/kg", "Mass fraction"
            elif "Scantling" in name:
                quantity_kind = "Quantity selected per scantling measure and unit"
        elif any(key.lower() in name.lower() for key in UNITLESS_HINTS):
            unit_symbol, unit_iri, quantity_kind = "1", str(UNIT.UNITLESS), "Dimensionless"
        elif unit:
            unit_symbol, unit_iri, quantity_kind = unit

    if kind == "NamedIndividual":
        role = "Controlled benchmark value used instead of an unconstrained text literal."
        naming_rule = "N6 - concise ASCII lowerCamelCase controlled-value name grounded in the linked regulation."
    elif kind == "Class":
        role = "Explicit entity/node type needed for targeting, traversal, repeatable cases, or evidence attachment."
        naming_rule = "N4 - singular ASCII lowerCamelCase entity name derived from the linked regulatory role."
    elif kind == "ObjectProperty":
        role = "Typed relationship needed to traverse between engineering or evidence nodes."
        naming_rule = "N5 - ASCII lowerCamelCase relationship; use has + object role when it improves direction clarity."
    elif kind == "QuantityProperty":
        role = "Numeric operand, comparison value, formula input/output, or engineering measurement."
        naming_rule = "N4 - explicit engineering quantity in ASCII lowerCamelCase; formula symbols remain aliases only."
    else:
        role = "Typed literal required for applicability, state, identification, or non-quantity evidence."
        naming_rule = "N4 - explicit regulatory concept in ASCII lowerCamelCase with an XSD datatype."

    return {
        "aliases": sorted({k for k, v in REDIRECTS.items() if v == name}),
        "conceptId": "",
        "confidence": "High" if ids else "Medium",
        "datatype": datatype,
        "evidenceExcerpt": " | ".join(evidence),
        "haithamUri": "",
        "iri": BASE + name,
        "kind": kind,
        "label": label(name),
        "localName": name,
        "mappingStatus": "No exact external mapping claimed; benchmark term is grounded only in the linked verified regulation evidence.",
        "module": "hull" if any(r.startswith("TRF-") for r in ids) else "core",
        "nameQaStatus": "Passed - ASCII-only lowerCamelCase and semantic-collision review",
        "namingBasis": "Applicable TRAFICOM regulation wording plus explicit engineering node/operand role",
        "namingRule": naming_rule,
        "normalizedDefinition": f"NORMALIZED (Batch 01 development): {label(name)} is the benchmark representation of the linked requirement operand, relationship, evidence role, or controlled value. Exact scope is limited to the cited requirements.",
        "parentOrRange": BASE + parent if not parent.startswith("http") else parent,
        "quantityKindLabel": quantity_kind,
        "requirements": sorted(ids),
        "roleDecision": role,
        "sourceConceptIds": [],
        "sourceRefs": "; ".join(source_refs),
        "stage1LocalNames": sorted({name, *[k for k, v in REDIRECTS.items() if v == name]}),
        "stage2UnitEvidence": "Canonical Batch 01 engineering unit; source equations and fixtures must normalize values before comparison." if kind == "QuantityProperty" else "",
        "unitDecisionStatus": ("Development unit selected and fixture conversion required" if unit_iri else "No external unit IRI claimed; preserve the source unit in evidence") if kind == "QuantityProperty" else "Not a quantity property",
        "unitIri": unit_iri,
        "unitSymbol": unit_symbol,
    }


def build_registry() -> tuple[list[dict], list[dict]]:
    base = read_json(R2 / "registry" / "term_registry.json")
    # PDF-verified units replace R2's generic unitless defaults only in this
    # development copy. The R2 lock and files remain unchanged.
    coefficient_units = {
        "coefficientF1": ("N/m^2", "http://qudt.org/vocab/unit/N-PER-M2"),
        "coefficientF2": ("N/m", "http://qudt.org/vocab/unit/N-PER-M"),
        "coefficientF3": ("N/m", "http://qudt.org/vocab/unit/N-PER-M"),
        "coefficientF4": ("N/m^2", "http://qudt.org/vocab/unit/N-PER-M2"),
        "coefficientG1": ("N", "http://qudt.org/vocab/unit/N"),
        "coefficientG2": ("N/m", "http://qudt.org/vocab/unit/N-PER-M"),
        "coefficientG3": ("N/m^1.5", BASE + "newtonPerMetreToPowerOnePointFiveUnit"),
        "coefficientC3": ("kg/(m^2*s^2)", BASE + "kilogramPerSquareMetreSquareSecondUnit"),
        "coefficientC4": ("kg/(m^2*s^2)", BASE + "kilogramPerSquareMetreSquareSecondUnit"),
        "coefficientC5": ("kg/s^2", BASE + "kilogramPerSquareSecondUnit"),
    }
    for item in base:
        if item["localName"] in coefficient_units:
            symbol, iri = coefficient_units[item["localName"]]
            item["unitSymbol"] = symbol
            item["unitIri"] = iri
            item["quantityKindLabel"] = "PDF-defined formula coefficient"
            item["unitDecisionStatus"] = "Corrected in Batch 01 development from PDF Tables 3-2/3-3; R2 remains unchanged"
            item["stage2UnitEvidence"] = "TRAFICOM.pdf pp.10-11, Tables 3-2 and 3-3"
    by_name = {item["localName"]: item for item in base}
    sources, reqs = candidate_sources()
    decisions = []
    additions = []
    for index, name in enumerate(sorted(sources), start=1):
        if name in by_name:
            action = "REUSE_EXISTING"
            canonical = name
        else:
            spec = infer_spec(name, sources[name], reqs)
            spec["conceptId"] = f"VOC-DEV-B01-{index:03d}"
            spec["sourceConceptIds"] = [spec["conceptId"]]
            additions.append(spec)
            action = "ADD_DEVELOPMENT_TERM"
            canonical = name
        decisions.append({
            "candidate": name, "canonicalLocalName": canonical, "action": action,
            "linkedRequirements": sorted(sources[name]),
            "rationale": "Reused exact active R2 term." if action == "REUSE_EXISTING" else "Added only after role, range/datatype, naming, unit, and source-link review.",
        })
    registry = sorted(base + additions, key=lambda item: item["localName"])
    write_json(OUT / "registry" / "term_registry.json", registry)
    write_json(OUT / "registry" / "batch01_candidate_decisions.json", decisions)
    fields = [
        "conceptId", "sourceConceptIds", "stage1LocalNames", "localName", "iri", "label", "kind", "parentOrRange", "datatype", "module",
        "roleDecision", "unitSymbol", "unitIri", "quantityKindLabel", "unitDecisionStatus", "stage2UnitEvidence", "aliases", "requirements",
        "sourceRefs", "namingBasis", "namingRule", "nameQaStatus", "confidence", "haithamUri", "mappingStatus",
    ]
    with (OUT / "registry" / "term_registry.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in registry:
            row = {key: item.get(key, "") for key in fields}
            for key in ("sourceConceptIds", "stage1LocalNames", "aliases", "requirements"):
                row[key] = "; ".join(item.get(key, []))
            writer.writerow(row)
    with (OUT / "registry" / "batch01_candidate_decisions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["candidate", "canonicalLocalName", "action", "linkedRequirements", "rationale"])
        writer.writeheader()
        for item in decisions:
            row = dict(item); row["linkedRequirements"] = "; ".join(row["linkedRequirements"]); writer.writerow(row)
    return registry, additions


def add_ontology_term(graph: Graph, item: dict) -> None:
    iri = URIRef(item["iri"])
    kind = item["kind"]
    if kind == "Class":
        graph.add((iri, RDF.type, OWL.Class))
        graph.add((iri, RDFS.subClassOf, URIRef(item["parentOrRange"])))
    elif kind == "NamedIndividual":
        graph.add((iri, RDF.type, URIRef(item["parentOrRange"])))
        graph.add((iri, RDF.type, OWL.NamedIndividual))
    elif kind in {"ObjectProperty", "QuantityProperty"}:
        graph.add((iri, RDF.type, OWL.ObjectProperty))
        graph.add((iri, RDFS.domain, URIRef(BASE + PROPERTY_DOMAINS.get(item["localName"], "benchmarkEntity"))))
        graph.add((iri, RDFS.range, URIRef(item["parentOrRange"])))
    else:
        graph.add((iri, RDF.type, OWL.DatatypeProperty))
        graph.add((iri, RDFS.domain, URIRef(BASE + PROPERTY_DOMAINS.get(item["localName"], "benchmarkEntity"))))
        graph.add((iri, RDFS.range, URIRef(item["parentOrRange"])))
    graph.add((iri, RDFS.label, Literal(item["label"], lang="en")))
    graph.add((iri, SKOS.prefLabel, Literal(item["label"], lang="en")))
    graph.add((iri, SKOS.definition, Literal(item["normalizedDefinition"], lang="en")))
    graph.add((iri, NLTL.draftConceptId, Literal(item["conceptId"])))
    graph.add((iri, NLTL.roleDecisionBasis, Literal(item["roleDecision"])))
    graph.add((iri, NLTL.namingBasis, Literal(item["namingBasis"])))
    graph.add((iri, NLTL.namingRule, Literal(item["namingRule"])))
    graph.add((iri, NLTL.unitDecisionStatus, Literal(item["unitDecisionStatus"])))
    for source in item["requirements"]:
        graph.add((iri, NLTL.sourceRequirementId, Literal(source)))
    for alias in item["aliases"]:
        graph.add((iri, SKOS.altLabel, Literal(alias)))
        graph.add((iri, NLTL.sourceAlias, Literal(alias)))
    if item["unitIri"]:
        graph.add((iri, NLTL.recommendedUnit, URIRef(item["unitIri"])))


def build_ontology(additions: list[dict]) -> None:
    graph = Graph().parse(R2 / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
    coefficient_units = {
        "coefficientF1": "http://qudt.org/vocab/unit/N-PER-M2",
        "coefficientF2": "http://qudt.org/vocab/unit/N-PER-M",
        "coefficientF3": "http://qudt.org/vocab/unit/N-PER-M",
        "coefficientF4": "http://qudt.org/vocab/unit/N-PER-M2",
        "coefficientG1": "http://qudt.org/vocab/unit/N",
        "coefficientG2": "http://qudt.org/vocab/unit/N-PER-M",
        "coefficientG3": BASE + "newtonPerMetreToPowerOnePointFiveUnit",
        "coefficientC3": BASE + "kilogramPerSquareMetreSquareSecondUnit",
        "coefficientC4": BASE + "kilogramPerSquareMetreSquareSecondUnit",
        "coefficientC5": BASE + "kilogramPerSquareSecondUnit",
    }
    for local_name, unit_iri in coefficient_units.items():
        term_iri = URIRef(BASE + local_name)
        graph.remove((term_iri, NLTL.recommendedUnit, None))
        graph.remove((term_iri, NLTL.unitDecisionStatus, None))
        graph.add((term_iri, NLTL.unitDecisionStatus, Literal("PDF-verified Batch 01 development correction from TRAFICOM Tables 3-2/3-3; R2 remains unchanged.")))
        if unit_iri:
            graph.add((term_iri, NLTL.recommendedUnit, URIRef(unit_iri)))
    # Retire representations that are structurally incompatible with Batch 01.
    replacements = {
        "upperIceWaterline": "hasUpperIceWaterline",
        "lowerIceWaterline": "hasLowerIceWaterline",
        "classificationSocietyScantling": "classificationSocietyRequiredScantling",
        "regulationDerivedScantling": "regulationRequiredScantling",
        "propellerType": "propellerPitchControlType",
        "weldType": "frameShellWeldType",
        "steelGrade": "hullStructuralSteelGrade",
    }
    for old_name, new_name in replacements.items():
        old = URIRef(BASE + old_name)
        graph.remove((old, RDF.type, OWL.DatatypeProperty))
        graph.add((old, OWL.deprecated, Literal(True)))
        graph.add((old, DCTERMS.isReplacedBy, URIRef(BASE + new_name)))
        graph.add((old, SKOS.changeNote, Literal(f"Retired in {DEV_ID}: string representation cannot express the required Batch 01 node/value model.")))
    for item in additions:
        add_ontology_term(graph, item)
    for ontology in graph.subjects(RDF.type, OWL.Ontology):
        graph.remove((ontology, OWL.versionInfo, None))
        graph.remove((ontology, OWL.versionIRI, None))
        graph.add((ontology, OWL.versionInfo, Literal(VERSION)))
        graph.add((ontology, OWL.versionIRI, URIRef(f"https://w3id.org/nltl-benchmark/vocab/{VERSION}")))
    (OUT / "ontology").mkdir(parents=True, exist_ok=True)
    graph.serialize(OUT / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.serialize(OUT / "ontology" / "nltl_benchmark_vocabulary.rdf", format="xml")


def build_context(additions: list[dict]) -> None:
    payload = read_json(R2 / "context" / "nltl_benchmark_context.jsonld")
    ctx = payload["@context"]
    for retired in (
        "upperIceWaterline", "lowerIceWaterline", "classificationSocietyScantling",
        "regulationDerivedScantling", "propellerType", "weldType", "steelGrade",
    ):
        ctx.pop(retired, None)
    for item in additions:
        if item["kind"] in {"ObjectProperty", "QuantityProperty"}:
            ctx[item["localName"]] = {"@id": "nltl:" + item["localName"], "@type": "@id"}
        else:
            ctx[item["localName"]] = "nltl:" + item["localName"]
    write_json(OUT / "context" / "nltl_benchmark_context.jsonld", payload)


def build_index(registry: list[dict]) -> dict:
    payload = read_json(R2_INDEX)
    payload["version"] = "1.4.0-dev-batch01"
    payload["sourceLockId"] = DEV_ID
    existing = {item["localName"] for item in registry}
    ontology_graph = Graph().parse(OUT / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
    existing.update(
        str(subject)[len(BASE):]
        for subject in ontology_graph.subjects()
        if str(subject).startswith(BASE)
    )
    preflight = read_json(BATCH / "engineering_preflight.json")["requirements"]
    for row in preflight:
        rid = row["requirement_id"]
        names = set(payload["requirements"].get(rid, []))
        names.update(row["existing_terms_to_link"])
        for draft in row["draft_new_terms"]:
            names.add(REDIRECTS.get(draft, draft))
        # Add structural dependency terms introduced by consolidation.
        extra = {
            "TRF-001": {
                "applicableIceClassRegulatoryProvision", "iceClassSection1Point8Provision2021",
                "iceClassDraughtChapter2Provision2021",
            },
            "TRF-014": {"hasClassCertificate", "hasIceDraughtRestrictionDocument"},
            "TRF-015": {"navigatingInIce"},
            "TRF-016": {"navigatingInIce", "hasLowerIceWaterline"},
            "TRF-020": {"propellerPitchControlType", "electricPropulsionMachinery", "hydraulicPropulsionMachinery"},
            "TRF-022": {
                "constructionStageDate", "kilogramPerSquareMetreSquareSecondUnit",
                "kilogramPerSquareSecondUnit", "newtonPerMetreToPowerOnePointFiveUnit",
            },
            "TRF-027": {
                "iceClass", "iceClassIaSuper", "iceClassIa", "constructionStageDate", "kilogramPerSquareMetreSquareSecondUnit",
                "kilogramPerSquareSecondUnit", "newtonPerMetreToPowerOnePointFiveUnit",
            },
            "TRF-030": {"icePressure"},
            "TRF-034": {"hasEffectiveMemberCrossSection"},
            "TRF-035": {"hullRegion", "bowRegion", "midbodyRegion", "sternRegion"},
            "TRF-036": {"hasIceClassDesignParameterSet"},
            "TRF-037": {
                "hullRegion", "displacementAtMaximumIceClassDraught",
                "continuousPropulsionPowerAvailableInIce",
            },
            "TRF-041": {
                "requiredShellPlatingThickness", "hullStructuralSteelGrade",
                "transversePlatingFactorF1", "longitudinalPlatingFactorF2",
            },
            "TRF-042": {"requiredShellPlatingThickness", "hullStructuralSteelGrade", "longitudinalPlatingFactorF2"},
            "TRF-043": {
                "hullRegion", "frame", "framingIceStrengtheningAboveUpperIceWaterline",
                "framingIceStrengtheningBelowLowerIceWaterline", "reachesUpperBowIceBeltTop",
            },
            "TRF-044": {"requiredShearArea", "frameBoundaryConditionType", "frameShearDistributionFactorF3"},
            "TRF-048": {
                "grossFrameShearArea", "longitudinalFrameShearFactorF5",
                "longitudinalFrameLoadDistributionFactorF4",
            },
            "TRF-046": {"ordinaryFrameScantlingsUsed"},
            "TRF-047": {"ordinaryFrameScantlingsUsed"},
            "TRF-049": {"frameWebThickness", "hasAttachedSupportingStructure"},
            "TRF-050": {"frameShellWeldType"},
            "TRF-051": {"frameWebThickness", "netShellPlatingThickness", "hullStructuralSteelGrade", "tankBottom"},
            "TRF-052": {"hasAntitrippingSupportRegion"},
            "TRF-053": {
                "requiredShearArea", "iceStringerDistributionFactorF6", "iceStringerSafetyFactorF7",
                "iceStringerShearFactorF8",
            },
            "TRF-054": {
                "requiredShearArea", "outsideIceBeltDistributionFactorF9", "outsideIceBeltSafetyFactorF10",
                "outsideIceBeltShearFactorF11",
            },
            "TRF-055": {"requiredShearArea", "abreastOfHatch", "requiredSectionModulus", "actualSectionModulus", "actualShearArea"},
            "TRF-056": {"hasHatchCoverDesignEvidence", "hasHatchFittingDesignEvidence"},
            "TRF-059": {
                "requiredShearArea", "freeFlangeArea", "webPlateArea", "freeFlangeToWebAreaRatio",
                "webFrameShearDistributionFactorF13",
            },
        }
        names.update(CALIBRATION_GAP_TERMS.get(rid, set()))
        names.update(extra.get(rid, set()))
        remove = {
            "TRF-017": {"additionalPropulsionPower"},
            "TRF-037": {"shipLength", "maximumContinuousRatingPower", "propulsionMachineryContinuousOutput", "waterlineDisplacement"},
            "TRF-041": {"thickness", "coefficientF1", "coefficientF2"},
            "TRF-042": {"steelGrade", "coefficientF2"},
            "TRF-043": {"framingIceStrengtheningUpperExtent", "upperBowIceBeltTop"},
            "TRF-044": {"shearArea"},
            "TRF-049": {"frameWebPlateThickness"},
            "TRF-051": {"frameWebPlateThickness", "netThickness", "thickness", "steelGrade"},
            "TRF-053": {"shearArea"}, "TRF-059": {"shearArea"},
            "TRF-031": {"directCalculationMethod"},
            "TRF-046": {"attachmentType", "frameUpperEnd", "connectionMemberScantling", "iceBeltUpperLimit"},
            "TRF-047": {"attachmentType", "frameLowerEnd", "connectionMemberScantling", "iceBeltLowerLimit"},
            "TRF-050": {"weldType"},
            "TRF-052": {"antitrippingSupportScope"},
            "TRF-055": {"shearArea"},
            "TRF-048": {"coefficientF4", "shearArea"},
            "TRF-054": {"shearArea", "stringerOutsideIceBeltHeight"},
        }
        names.difference_update(remove.get(rid, set()))
        names.difference_update({
            "upperIceWaterline", "lowerIceWaterline", "classificationSocietyScantling",
            "regulationDerivedScantling", "propellerType",
        })
        missing = sorted(name for name in names if name not in existing)
        if missing:
            raise RuntimeError(f"{rid} index contains absent terms: {missing}")
        payload["requirements"][rid] = sorted(names)
    payload["termCount"] = len(registry)
    write_json(DEV_INDEX, payload)
    return payload


def validate(registry: list[dict], index: dict) -> dict:
    graph = Graph().parse(OUT / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
    Graph().parse(OUT / "ontology" / "nltl_benchmark_vocabulary.rdf", format="xml")
    locals_ = [item["localName"] for item in registry]
    iris = [item["iri"] for item in registry]
    errors = []
    if len(locals_) != len(set(locals_)): errors.append("duplicate localName")
    if len(iris) != len(set(iris)): errors.append("duplicate IRI")
    bad_names = sorted(name for name in locals_ if not re.fullmatch(r"[a-z][A-Za-z0-9]*", name))
    if bad_names: errors.append(f"non-lowerCamelCase names: {bad_names}")
    graph_locals = {str(s)[len(BASE):] for s in graph.subjects() if str(s).startswith(BASE)}
    missing_graph = sorted(set(locals_) - graph_locals)
    if missing_graph: errors.append(f"registry terms absent from ontology: {missing_graph}")
    batch_ids = [row["requirement_id"] for row in read_json(BATCH / "engineering_preflight.json")["requirements"]]
    uncovered = [rid for rid in batch_ids if not index["requirements"].get(rid)]
    if uncovered: errors.append(f"unindexed requirements: {uncovered}")
    report = {
        "status": "PASS" if not errors else "FAIL", "developmentId": DEV_ID,
        "registryTerms": len(registry), "ontologyTriples": len(graph), "batchRequirements": len(batch_ids),
        "batchIndexTerms": len(set().union(*(set(index["requirements"][rid]) for rid in batch_ids))),
        "errors": errors,
    }
    write_json(OUT / "validation" / "validation_report.json", report)
    if errors: raise RuntimeError("; ".join(errors))
    return report


def write_docs(registry: list[dict], additions: list[dict], report: dict) -> None:
    revision_label = DEV_ID.rsplit("-", 1)[-1]
    (OUT / "README.md").write_text(
        f"# Batch 01 {revision_label} development vocabulary\n\n"
        f"Development identifier: `{DEV_ID}`. This is **not an evaluation lock**. It is a calibration revision for the first 50 eligible TRAFICOM requirements. "
        "R2 remains untouched. The revision adds only schema terms, controlled values, datatypes, ranges, and unit recommendations; it contains no regulatory threshold, formula result, or expected conformance outcome.\n\n"
        "The `registry/batch01_candidate_decisions.*` files explain every reuse/addition. The requirement index is local to this development package. "
        "After all fixtures and generated shapes regress cleanly, a later reviewed revision can be locked and all final simulations rerun from scratch.\n",
        encoding="utf-8",
    )
    (OUT / "VALIDATION_REPORT.md").write_text(
        "# Validation report\n\n"
        f"Status: **{report['status']}**\n\n- Active registry terms: {len(registry)}\n- Batch 01 additions: {len(additions)}\n"
        f"- Parsed ontology triples: {report['ontologyTriples']}\n- Indexed Batch 01 requirements: {report['batchRequirements']}\n"
        f"- Distinct Batch 01 context terms: {report['batchIndexTerms']}\n- Naming collisions/errors: none\n",
        encoding="utf-8",
    )


def build_manifest(registry: list[dict], additions: list[dict], report: dict) -> None:
    files = [
        OUT / "registry" / "term_registry.json", OUT / "ontology" / "nltl_benchmark_vocabulary.ttl",
        OUT / "context" / "nltl_benchmark_context.jsonld", DEV_INDEX,
        OUT / "registry" / "batch01_candidate_decisions.json",
    ]
    manifest = {
        "developmentId": DEV_ID, "version": VERSION, "status": "DEVELOPMENT_NOT_EVALUATION_LOCK",
        "baseRevision": "VOCAB-DEV-2026-08-12-BATCH01-R4", "requirements": 50,
        "registryTerms": len(registry), "addedRegistryTerms": len(additions),
        "addedKinds": dict(Counter(item["kind"] for item in additions)),
        "validation": report, "artifacts": {str(path.relative_to(OUT)): sha256(path) for path in files},
        "leakagePolicy": "Calibration artifacts may be used to close vocabulary gaps. Final benchmark runs must use a later fixed lock and freshly generated outputs against hidden fixtures.",
    }
    write_json(OUT / "development_manifest.json", manifest)


def build_development_binding() -> None:
    binding = {
        "lockId": DEV_ID,
        "status": "DEVELOPMENT_BINDING_NOT_EVALUATION_LOCK",
        "workbook": "batch01_vocabulary_and_fixture_tracker.xlsx",
        "workbookSha256": sha256(BATCH / "batch01_vocabulary_and_fixture_tracker.xlsx"),
        "boundMachineReadableArtifacts": {
            "registry/term_registry.json": sha256(OUT / "registry" / "term_registry.json"),
            "ontology/nltl_benchmark_vocabulary.ttl": sha256(OUT / "ontology" / "nltl_benchmark_vocabulary.ttl"),
            "evidence/stage1_approved.json": sha256(OUT / "evidence" / "stage1_approved.json"),
        },
        "boundRequirementIndex": {
            "requirement_term_index.json": sha256(DEV_INDEX),
        },
        "warning": "This hash binding makes development runs reproducible but does not make them final benchmark runs.",
    }
    write_json(OUT / "development_binding.json", binding)


def main() -> None:
    if OUT.exists():
        # The builder owns this development output only; replace files deterministically.
        shutil.rmtree(OUT)
    for folder in ("context", "evidence", "ontology", "registry", "validation"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    shutil.copy2(R2 / "evidence" / "stage1_approved.json", OUT / "evidence" / "stage1_approved.json")
    shutil.copy2(R2 / "evidence" / "external_uri_verification.json", OUT / "evidence" / "external_uri_verification.json")
    enrich_verified_evidence()
    registry, additions = build_registry()
    build_ontology(additions)
    build_context(additions)
    index = build_index(registry)
    report = validate(registry, index)
    write_docs(registry, additions, report)
    build_manifest(registry, additions, report)
    build_development_binding()
    print(json.dumps({
        "status": "PASS", "development_id": DEV_ID, "registry_terms": len(registry),
        "added_terms": len(additions), "output": str(OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
