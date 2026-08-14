from __future__ import annotations

import hashlib
import json
import math
import shutil
from decimal import Decimal
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import OWL, XSD


MVP = Path(__file__).resolve().parents[4]
BATCH = Path(__file__).resolve().parents[1]
DEV = MVP / "BENCHMARK_VOCABULARY" / "DEVELOPMENT" / "DEV_R8_1_POSTCONFIRMATION"
DEVELOPMENT_ID = "VOCAB-DEV-2026-08-13-BATCH01-R8.1-POSTCONFIRMATION"
OUT = BATCH / "rdf_fixtures"
BASE = "https://w3id.org/nltl/vocab#"
EX_BASE = "urn:nltl:batch01-fixture:"

NLTL = Namespace(BASE)
EX = Namespace(EX_BASE)
QUDT = Namespace("http://qudt.org/schema/qudt/")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def q(value: float | int) -> float:
    return float(value)


# Values are canonicalized to the registry units. For example, 0.15 MN/m is
# represented as 150 kN/m and 0.54 MN as 540 kN.
PASS_VALUES: dict[str, dict[str, object]] = {
    "TRF-001": {"constructionContractDate": "2021-07-05", "applicableIceClassRegulationEdition": "iceClassRegulationEdition2021"},
    "TRF-002": {"constructionContractDate": "2019-01-01", "applicableIceClassRegulationEdition": "iceClassRegulationEdition2017"},
    "TRF-003": {"constructionContractDate": "2012-01-01", "applicableIceClassRegulationEdition": "iceClassRegulationEdition2010"},
    "TRF-004": {"constructionContractDate": "2010-01-01", "applicableIceClassRegulationEdition": "iceClassRegulationEdition2008"},
    "TRF-005": {"constructionContractDate": "2009-12-31", "constructionStageDate": "2003-09-01", "applicableIceClassRegulationEdition": "iceClassRegulationEdition2002"},
    "TRF-006": {"constructionStageDate": "1986-11-01", "applicableIceClassRegulationEdition": "iceClassRuleEdition1985", "engineOutputRegulationEdition": "iceClassRegulationEdition2008"},
    "TRF-007": {"iceClass": "iceClassIa", "constructionStageDate": "2003-08-31", "deliveryDate": "2001-06-01", "assessmentDate": "2021-01-01", "engineOutputComplianceMethod": "traficom2017Section3Point2Point2Method"},
    "TRF-009": {"iceClass": "iceClassIaSuper", "constructionStageDate": "2003-08-31", "deliveryDate": "2001-06-01", "assessmentDate": "2021-01-01", "engineOutputComplianceMethod": "traficom2017Section3Point2Point4Method"},
    "TRF-010": {"iceClass": "iceClassIa"},
    "TRF-013": {"shipIceStrengthened": True, "draughtAtForePerpendicular": 6.0, "draughtAtAftPerpendicular": 6.5, "operatingForeDraught": 6.0, "operatingAftDraught": 6.5},
    "TRF-014": {"constructionDate": "2007-07-01", "retainedOnBoard": True, "readilyAvailableToMaster": True, "warningTrianglePresent": True, "iceClassDraughtMarkPresent": True, "maximumIceClassDraughtFore": 7.0, "minimumIceClassDraughtFore": 5.0, "maximumIceClassDraughtAmidships": 7.2, "minimumIceClassDraughtAmidships": 5.2, "maximumIceClassDraughtAft": 7.0, "minimumIceClassDraughtAft": 5.0, "summerLoadLineFreshWaterDraught": 7.5, "upperIceWaterlineDraught": 7.2, "iceClassDraughtMarkDraughtAmidships": 7.2},
    "TRF-015": {"navigatingInIce": True, "upperIceWaterlineDraught": 7.0, "operatingDraught": 6.9, "maximumPermittedIceTrim": 1.0, "operatingTrim": 1.0, "intendedRouteSeaWaterSalinity": 5.0, "loadingCalculationSeaWaterSalinity": 5.0},
    "TRF-016": {"navigatingInIce": True, "liwlDraughtAmidships": 5.0, "draughtAmidships": 5.0, "levelIceThickness": 0.8, "waterlineDisplacement": 10000.0, "displacementAtUpperIceWaterline": 10000.0, "forwardDraught": 3.6, "propellerHighestPointSubmerged": True, "freezingPreventionPresent": True, "situatedAboveLowerIceWaterline": True, "usedToReachLowerIceWaterline": True},
    "TRF-017": {"maximumContinuousRatingPower": 5500.0, "propulsionMachineryContinuousOutput": 5500.0, "propulsionOutputRestrictionApplies": False, "restrictedPropulsionOutput": 5500.0},
    "TRF-018": {"iceClass": "iceClassIa", "calculatedRequiredPower": 1000.0, "maximumContinuousRatingPower": 1000.0},
    "TRF-020": {"iceClass": "iceClassIa", "constructionStageDate": "2003-09-01", "propulsionSystemType": "conventionalPropulsionSystem", "propellerPitchControlType": "controllablePitch", "propellerCount": 1, "engineOutputCoefficientKe": 2.03, "brashIceChannelResistanceRch": 1_000_000.0, "brashIceChannelResistanceAtUpperIceWaterline": 1_000_000.0, "brashIceChannelResistanceAtLowerIceWaterline": 1_000_000.0, "propellerDiameter": 5.0, "upperIceWaterlineLength": 100.0, "upperIceWaterlineBreadth": 20.0, "minimumRequiredPowerAtUpperIceWaterline": 12838.447, "minimumRequiredPowerAtLowerIceWaterline": 12838.447, "maximumContinuousRatingPower": 13000.0},
    "TRF-022": {"constructionStageDate": "2003-09-01", "shipLength": 100.0, "shipBreadth": 20.0, "iceClassDraught": 5.0, "bowRakeAtQuarterBreadth": 45.0, "waterlineAngleAtQuarterBreadth": 45.0, "flareAngle": 54.735610317245346, "clampedHullGeometryTerm": 5.0, "coefficientC3": 845, "coefficientC4": 42, "coefficientC5": 825, "coefficientF1": 23, "coefficientF2": 45.8, "coefficientF3": 14.7, "coefficientF4": 29, "coefficientG1": 1530, "coefficientG2": 170, "coefficientG3": 400},
    "TRF-023": {"iceClass": "iceClassIb", "applicableIceClassRegulationEdition": "iceClassRuleEdition1985", "requiredPowerUnder1985Rules": 1200.0, "maximumContinuousRatingPower": 1200.0},
    "TRF-024": {"iceClass": "iceClassIa", "constructionStageDate": "2003-08-31", "deliveryDate": "2001-06-01", "assessmentDate": "2021-01-01", "engineOutputComplianceMethod": "traficom2017Section3Point2Point2Method"},
    "TRF-025": {"iceClass": "iceClassIaSuper", "bulbousBowPresent": False, "shipBreadth": 20.0, "shipLength": 100.0, "iceClassDraught": 5.0, "coefficientF1": 10.3, "coefficientF2": 45.8, "coefficientF3": 2.94, "coefficientF4": 5.8, "coefficientG1": 1530.0, "coefficientG2": 170.0, "coefficientG3": 400.0, "brashIceResistanceCoefficientC1": 37303.733333, "brashIceResistanceCoefficientC2": 38153.6},
    "TRF-026": {"iceClass": "iceClassIaSuper", "bulbousBowPresent": True, "shipBreadth": 20.0, "shipLength": 100.0, "iceClassDraught": 5.0, "coefficientF1": 10.3, "coefficientF2": 45.8, "coefficientF3": 2.94, "coefficientF4": 5.8, "coefficientG1": 1530.0, "coefficientG2": 170.0, "coefficientG3": 400.0, "brashIceResistanceCoefficientC1": 50754.233333, "brashIceResistanceCoefficientC2": 53683.1},
    "TRF-027": {"iceClass": "iceClassIa", "constructionStageDate": "2003-08-31", "shipLength": 100.0, "shipBreadth": 20.0, "iceClassDraught": 5.0, "clampedHullGeometryTerm": 5.0, "coefficientF1": 10.3, "coefficientF2": 45.8, "coefficientF3": 2.94, "coefficientF4": 5.8, "coefficientG1": 1530, "coefficientG2": 170, "coefficientG3": 400, "coefficientC3": 460, "coefficientC4": 18.7, "coefficientC5": 825},
    "TRF-030": {"icePressure": 1.0, "appliedIcePressure": 1.8, "combinedBendingAndShearEvaluated": True, "capacityMinimizingLoadPositionConfirmed": True, "loadLengthDeterminedFromArrangement": False, "iceLoadAreaFactorCa": 0.5, "verticalLoadPosition": 0.0, "horizontalLoadPosition": 0.0, "loadPatchHeight": 0.3, "loadPatchLength": 1.0, "spacing": 0.5, "span": 2.0},
    "TRF-031": {"vonMisesYieldCriterion": True, "beamTheoryUsed": True, "yieldPoint": 235.0, "combinedBendingShearStress": 234.0, "yieldShearStress": 135.677, "allowableShearStress": 122.1093},
    "TRF-032": {"iceStrengtheningStatus": False, "classificationSocietyRequiredScantling": 12.0, "regulationRequiredScantling": 10.0, "selectedDesignScantling": 12.0},
    "TRF-034": {"memberNormalToPlating": False, "sectionModulus": 200.0, "shearArea": 0.01},
    "TRF-035": {"ruleLength": 100.0, "classificationSocietyRuleLength": 100.0, "hullRegion": "bowRegion"},
    "TRF-036": {"iceClass": "iceClassIa", "levelIceThickness": 0.8, "designIceLoadHeight": 0.30},
    "TRF-037": {"hullRegion": "bowRegion", "displacementAtMaximumIceClassDraught": 10000.0, "continuousPropulsionPowerAvailableInIce": 5000.0, "shipSizeEngineOutputCoefficientA": 30.0, "shipSizeEngineOutputCoefficientB": 230.0, "shipSizeEngineOutputCoefficientK": 7.071068, "shipSizeEngineOutputFactorCd": 0.442132, "iceClassFactorCp": 1.0, "iceLoadAreaFactorCa": 0.5, "nominalIcePressureP0": 5.6, "icePressure": 1.23797},
    "TRF-041": {"platingFramingOrientation": "transverseFramingOrientation", "spacing": 0.5, "icePressure": 1.0, "platingPressure": 0.75, "transversePlatingFactorF1": 1.0, "longitudinalPlatingFactorF2": 1.0, "yieldStrength": 235.0, "corrosionAbrasionAddition": 2.0, "requiredShellPlatingThickness": 20.8405130698},
    "TRF-042": {"spacing": 0.5, "designIceLoadHeight": 0.5, "longitudinalPlatingFactorF2": 1.0, "yieldStrength": 235.0, "corrosionAbrasionAddition": 2.0, "specialSurfaceCoatingMaintained": False, "hullStructuralSteelGrade": "normalStrengthHullStructuralSteel", "materialApprovalStatus": "evidenceStateApproved", "requiredShellPlatingThickness": 23.754},
    "TRF-043": {"iceClass": "iceClassIaSuper", "hullRegion": "midbodyRegion", "framingIceStrengtheningAboveUpperIceWaterline": 1.2, "framingIceStrengtheningBelowLowerIceWaterline": 2.0, "upperBowIceBeltRequired": False, "reachesUpperBowIceBeltTop": True, "extensionBeyondAdjacentDeckOrTankBoundary": 250.0, "iceStrengtheningTerminationAtAdjacentBoundaryPermitted": True},
    "TRF-044": {"icePressure": 1.0, "spacing": 0.5, "designIceLoadHeight": 0.3, "span": 2.0, "effectiveFrameSpan": 2.0, "frameBoundaryConditionType": "bulkCarrierTopWingTankFrameCondition", "frameBoundaryConditionFactorM0": 7.0, "frameMomentFactorMt": 7.84, "frameShearDistributionFactorF3": 1.2, "yieldStrength": 235.0, "sectionModulus": 162.84, "requiredShearArea": 6.633},
    "TRF-045": {"span": 10.0, "frameSpanWithinIceStrengtheningZone": 1.49, "ordinaryFrameScantlingsUsed": True},
    "TRF-046": {"supportingStructureAtOrAboveIceBeltUpperLimit": True, "sameScantlingsAsMainFrame": True},
    "TRF-047": {"supportingStructureAtOrBelowIceBeltLowerLimit": True, "sameScantlingsAsMainFrame": True, "mainFrameBelowIceBeltStrengthened": True},
    "TRF-048": {"significantlyDifferentBoundaryConditions": False, "icePressure": 1.0, "designIceLoadHeight": 0.3, "spacing": 0.5, "span": 2.0, "longitudinalFrameLoadDistributionFactorF4": 0.88, "longitudinalFrameShearFactorF5": 2.16, "frameMomentFactorM": 13.3, "yieldStrength": 235.0, "sectionModulus": 84.45, "requiredShearArea": 42.0, "grossFrameShearArea": 50.0, "bracketArea": 5.0, "actualFrameShearArea": 45.0},
    "TRF-049": {"withinIceStrengthenedArea": True, "effectiveAttachmentConfirmed": True, "passesThroughSupportingStructure": True, "terminatesAtDeckOrIceStringer": True, "webPlateConnectionSideCount": 2, "bracketThickness": 10.0, "frameWebThickness": 10.0, "bracketEdgeStiffened": True, "bucklingStiffening": True},
    "TRF-050": {"frameShellWeldType": "doubleContinuousWeld", "scallopingPresent": False, "shellPlateButtCrossing": False},
    "TRF-051": {"frameProfileType": "profileSection", "inLieuOfFrame": False, "adjacentFrameHeight": 400.0, "yieldStrength": 235.0, "netShellPlatingThickness": 12.0, "corrosionAbrasionAddition": 2.0, "frameWebThickness": 9.0, "hullStructuralSteelGrade": "normalStrengthHullStructuralSteel"},
    "TRF-052": {"frameAsymmetrical": True, "frameWebAngleToShell": 80.0, "antitrippingSupportSpacing": 1300.0, "frameSpan": 4.0, "iceClass": "iceClassIa", "equivalentSupportStatusByDirectCalculation": False},
    "TRF-053": {"locatedWithinIceBelt": True, "icePressure": 0.3, "designIceLoadHeight": 0.3, "designLineLoad": 150.0, "span": 2.0, "frameMomentFactorM": 13.3, "iceStringerDistributionFactorF6": 0.9, "iceStringerSafetyFactorF7": 1.8, "iceStringerShearFactorF8": 1.2, "yieldStrength": 235.0, "sectionModulus": 310.69, "requiredShearArea": 21.493},
    "TRF-054": {"locatedOutsideIceBelt": True, "supportsIceStrengthenedFrames": True, "icePressure": 0.3, "designIceLoadHeight": 0.3, "designLineLoad": 150.0, "span": 2.0, "stringerSpan": 2.0, "distanceToIceBelt": 0.4, "distanceToAdjacentIceStringer": 2.0, "outsideIceBeltFactor": 0.8, "frameMomentFactorM": 13.3, "outsideIceBeltDistributionFactorF9": 0.8, "outsideIceBeltSafetyFactorF10": 1.8, "outsideIceBeltShearFactorF11": 1.2, "yieldStrength": 235.0, "sectionModulus": 220.93, "requiredShearArea": 15.284},
    "TRF-055": {"hatchOpeningLength": 11.0, "shipBreadth": 20.0, "abreastOfHatch": True, "servesAsIceStringer": True, "scantlingApprovalStatus": "evidenceStateApproved", "designLineLoad": 100.0, "permittedReducedLineLoad": 100.0, "requiredSectionModulus": 200.0, "actualSectionModulus": 200.0, "requiredShearArea": 20.0, "actualShearArea": 20.0},
    "TRF-056": {"hatchOpeningLength": 11.0, "shipBreadth": 20.0, "shipSideDeflection": 0.01},
    "TRF-057": {"iceLoadSourceType": "iceStringerLoadSource", "icePressure": 0.3, "iceLoadHeight": 0.3, "minimumLineLoad": 150.0, "loadLengthParameter": 4.0, "webFrameSpacing": 2.0, "webFrameSafetyFactor": 1.8, "webFrameIceLoad": 540.0},
    "TRF-058": {"iceLoadForce": 540.0, "supportedStringerOutsideIceBelt": True, "stringerOutsideIceBeltHeight": 0.5, "stringerSpan": 2.0, "adjustedIceLoadForce": 405.0},
    "TRF-059": {"freeFlangeArea": 40.0, "webPlateArea": 100.0, "freeFlangeToWebAreaRatio": 0.4, "webFrameShearFactorAlpha": 1.16, "webFrameShearDistributionFactorF13": 1.1, "maximumCalculatedShearForce": 100.0, "yieldStrength": 235.0, "requiredShearArea": 9.407},
}


PASS_VALUES["TRF-013"]["iceClass"] = "iceClassIa"
PASS_VALUES["TRF-043"]["reachesTankTopOrBelowFloorTop"] = True
PASS_VALUES["TRF-049"]["similarAttachmentConstructionPresent"] = False
PASS_VALUES["TRF-055"].update({
    "veryLongHatchOpening": True,
    "reducedLineLoadApprovedByClassificationSociety": True,
})

# Formula-bound fixture values retain full calculation precision so tolerance
# checks measure SHACL logic rather than decimal rounding in the fixture.
_k37 = math.sqrt(10000.0 * 5000.0) / 1000.0
_cd37 = (30.0 * _k37 + 230.0) / 1000.0
PASS_VALUES["TRF-037"].update({
    "shipSizeEngineOutputCoefficientK": _k37,
    "shipSizeEngineOutputFactorCd": _cd37,
    "icePressure": _cd37 * 1.0 * 0.5 * 5.6,
})
# Keep formula outputs at calculation precision. Rounded presentation values
# incorrectly sit outside the generated tolerance even though the intended
# engineering case is conforming.
_pmin20 = 2.03 * (1_000_000.0 / 1000.0) ** 1.5 / 5.0
PASS_VALUES["TRF-020"].update({
    "minimumRequiredPowerAtUpperIceWaterline": _pmin20,
    "minimumRequiredPowerAtLowerIceWaterline": _pmin20,
})
PASS_VALUES["TRF-041"]["requiredShellPlatingThickness"] = 667.0 * 0.5 * math.sqrt(0.75 / 235.0) + 2.0
_mt44 = 7.0 * 7.0 / (7.0 - 5.0 * 0.3 / 2.0)
PASS_VALUES["TRF-044"].update({
    "frameMomentFactorMt": _mt44,
    "sectionModulus": 1.0 * 0.5 * 0.3 * 2.0 / (_mt44 * 235.0) * 1_000_000.0,
    "requiredShearArea": math.sqrt(3.0) * 1.2 * 1.0 * 0.3 * 0.5 / (2.0 * 235.0) * 10_000.0,
})
PASS_VALUES["TRF-048"].update({
    "sectionModulus": 0.88 * 1.0 * 0.3 * 2.0**2 / (4.0 * 13.3 * 235.0) * 1_000_000.0,
    "requiredShearArea": math.sqrt(3.0) * 0.88 * 2.16 * 1.0 * 0.3 * 2.0 / (2.0 * 235.0) * 10_000.0,
})
PASS_VALUES["TRF-053"].update({
    "sectionModulus": 0.9 * 1.8 * 0.15 * 2.0**2 / (13.3 * 235.0) * 1_000_000.0,
    "requiredShearArea": math.sqrt(3.0) * 0.9 * 1.8 * 1.2 * 0.15 * 2.0 / (2.0 * 235.0) * 10_000.0,
})
PASS_VALUES["TRF-054"].update({
    # Preserve the regulation's exact controlled decimal lexical form because
    # SHACL sh:hasValue compares RDF terms, not only numerical equivalence.
    "outsideIceBeltDistributionFactorF9": Decimal("0.80"),
    "sectionModulus": 0.8 * 1.8 * 0.15 * 2.0**2 / (13.3 * 235.0) * 0.8 * 1_000_000.0,
    "requiredShearArea": math.sqrt(3.0) * 0.8 * 1.8 * 1.2 * 0.15 * 2.0 / (2.0 * 235.0) * 0.8 * 10_000.0,
})
PASS_VALUES["TRF-059"]["requiredShearArea"] = math.sqrt(3.0) * 1.16 * 1.1 * 100.0 * 10.0 / 235.0


FAIL_CHANGES: dict[str, tuple[str, object | None]] = {
    "TRF-001": ("applicableIceClassRegulationEdition", "iceClassRegulationEdition2017"),
    "TRF-002": ("applicableIceClassRegulationEdition", "iceClassRegulationEdition2010"),
    "TRF-003": ("applicableIceClassRegulationEdition", "iceClassRegulationEdition2008"),
    "TRF-004": ("applicableIceClassRegulationEdition", "iceClassRegulationEdition2002"),
    "TRF-005": ("applicableIceClassRegulationEdition", "iceClassRegulationEdition2008"),
    "TRF-006": ("applicableIceClassRegulationEdition", "iceClassRegulationEdition2008"),
    "TRF-007": ("engineOutputComplianceMethod", None), "TRF-009": ("engineOutputComplianceMethod", None),
    "TRF-010": ("iceClass", "urn:invalid:ice-class"),
    "TRF-011": ("__waterlineEnvelope", "upper_fail"), "TRF-012": ("__waterlineEnvelope", "lower_fail"),
    "TRF-013": ("operatingForeDraught", 7.5), "TRF-014": ("warningTrianglePresent", False),
    "TRF-015": ("operatingDraught", 7.1), "TRF-016": ("freezingPreventionPresent", False),
    "TRF-017": ("propulsionMachineryContinuousOutput", 5000.0), "TRF-018": ("maximumContinuousRatingPower", 999.0),
    "TRF-020": ("maximumContinuousRatingPower", 12000.0), "TRF-022": ("clampedHullGeometryTerm", 1.953125),
    "TRF-023": ("maximumContinuousRatingPower", 1199.0), "TRF-024": ("engineOutputComplianceMethod", None),
    "TRF-025": ("brashIceResistanceCoefficientC1", 37000.0), "TRF-026": ("brashIceResistanceCoefficientC2", 53000.0),
    "TRF-027": ("clampedHullGeometryTerm", 1.953125), "TRF-030": ("appliedIcePressure", 1.7),
    "TRF-031": ("combinedBendingShearStress", 235.0), "TRF-032": ("selectedDesignScantling", 11.0),
    "TRF-034": ("hasClassificationSocietySectionPropertyCalculationEvidence", None),
    "TRF-035": ("ruleLength", 99.0), "TRF-036": ("designIceLoadHeight", 0.29),
    "TRF-037": ("icePressure", 1.1), "TRF-041": ("requiredShellPlatingThickness", 20.0),
    "TRF-042": ("yieldStrength", 234.0),
    "TRF-043": ("framingIceStrengtheningBelowLowerIceWaterline", 1.9),
    "TRF-044": ("requiredShearArea", 6.0), "TRF-045": ("frameSpanWithinIceStrengtheningZone", 1.5),
    "TRF-046": ("hasAttachedSupportingStructure", None), "TRF-047": ("mainFrameBelowIceBeltStrengthened", False),
    "TRF-048": ("actualFrameShearArea", 50.0), "TRF-049": ("bracketThickness", 9.0),
    "TRF-050": ("scallopingPresent", True), "TRF-051": ("frameWebThickness", 8.9),
    "TRF-052": ("antitrippingSupportSpacing", 1301.0), "TRF-053": ("sectionModulus", 300.0),
    "TRF-054": ("requiredShearArea", 15.0), "TRF-055": ("permittedReducedLineLoad", 99.0),
    "TRF-056": ("hasHatchCoverDesignEvidence", None), "TRF-057": ("webFrameIceLoad", 500.0),
    "TRF-058": ("adjustedIceLoadForce", 400.0), "TRF-059": ("requiredShearArea", 9.0),
}


BOUNDARY_CHANGES: dict[str, dict[str, object]] = {
    "TRF-001": {"constructionContractDate": "2021-07-04"},
    "TRF-002": {"constructionContractDate": "2021-07-05"},
    "TRF-003": {"constructionContractDate": "2019-01-01"},
    "TRF-004": {"constructionContractDate": "2012-01-01"},
    "TRF-005": {"constructionStageDate": "2003-08-31"},
    "TRF-006": {"constructionStageDate": "2003-09-01"},
    "TRF-018": {"iceClass": "iceClassIaSuper", "calculatedRequiredPower": 2800.0, "maximumContinuousRatingPower": 2800.0},
    "TRF-022": {"shipLength": 200.0, "shipBreadth": 10.0, "iceClassDraught": 10.0, "clampedHullGeometryTerm": 20.0},
    "TRF-031": {"allowableShearStress": 122.1093},
    "TRF-036": {"iceClass": "iceClassIc", "levelIceThickness": 0.4, "designIceLoadHeight": 0.22},
    "TRF-043": {"extensionBeyondAdjacentDeckOrTankBoundary": 250.0},
    "TRF-045": {"frameSpanWithinIceStrengtheningZone": 1.5, "ordinaryFrameScantlingsUsed": False},
    "TRF-050": {"scallopingPresent": True, "shellPlateButtCrossing": True},
    "TRF-052": {"antitrippingSupportSpacing": 1300.0},
    "TRF-055": {"permittedReducedLineLoad": 100.0},
    "TRF-056": {"hatchOpeningLength": 10.0},
    "TRF-058": {"supportedStringerOutsideIceBelt": False, "adjustedIceLoadForce": 540.0},
}


SCENARIOS: dict[str, tuple[str, str, str]] = {}


def value_literal(item: dict, value: object) -> Literal:
    datatype = item.get("datatype")
    if datatype == "xsd:boolean": return Literal(bool(value), datatype=XSD.boolean)
    if datatype == "xsd:integer": return Literal(int(value), datatype=XSD.integer)
    if datatype == "xsd:date": return Literal(str(value), datatype=XSD.date)
    return Literal(str(value), datatype=XSD.string)


def build_graph(rid: str, case_kind: str, terms: list[str], registry: dict[str, dict], ownership: dict[str, str]) -> Graph:
    values = dict(PASS_VALUES.get(rid, {}))
    missing: set[str] = set()
    special = ""
    if case_kind == "FAIL":
        term, change = FAIL_CHANGES[rid]
        if term.startswith("__"):
            special = str(change)
        elif change is None:
            missing.add(term)
        else:
            values[term] = change
        if rid == "TRF-046":
            missing.update({"hasAttachedSupportingStructure", "hasTerminationAboveSupportingStructure"})
        if rid == "TRF-047":
            missing.update({"hasAttachedSupportingStructure", "hasTerminationBelowSupportingStructure"})
    elif case_kind == "BOUNDARY":
        values.update(BOUNDARY_CHANGES.get(rid, {}))

    graph = Graph()
    graph.bind("nltl", NLTL)
    graph.bind("ex", EX)
    graph.bind("qudt", QUDT)
    graph.bind("xsd", XSD)
    graph.bind("unit", Namespace("http://qudt.org/vocab/unit/"))
    ship = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:ship")
    component = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:component")
    graph.add((ship, RDF.type, NLTL.ship))
    graph.add((component, RDF.type, NLTL.shipComponent))
    graph.add((ship, NLTL.hasComponent, component))

    controlled_by_type: dict[str, list[str]] = {}
    for item in registry.values():
        if item["kind"] == "NamedIndividual":
            controlled_by_type.setdefault(item["parentOrRange"], []).append(item["localName"])

    structured_skip = {
        "TRF-011": {"hasUpperIceWaterline", "hasLowerIceWaterline", "hasIntendedIceOperatingWaterline", "hasWaterlineProfilePoint"},
        "TRF-012": {"hasUpperIceWaterline", "hasLowerIceWaterline", "hasIntendedIceOperatingWaterline", "hasWaterlineProfilePoint"},
        "TRF-013": {"hasUpperIceWaterline", "hasLowerIceWaterline", "hasIntendedIceOperatingWaterline", "hasWaterlineProfilePoint"},
        "TRF-016": {"hasUpperIceWaterline", "hasLowerIceWaterline", "hasIntendedIceOperatingWaterline", "hasWaterlineProfilePoint", "waterlineDisplacement", "hasBallastTank"},
        "TRF-020": {"hasUpperIceWaterline", "hasLowerIceWaterline", "iceWaterline", "upperIceWaterlineLength", "upperIceWaterlineBreadth"},
        "TRF-030": {"directAnalysisCase", "hasDirectAnalysisCase", "capacityMinimizingLoadPositionConfirmed", "combinedBendingAndShearEvaluated", "verticalLoadPosition", "verticalLoadPositionType", "horizontalLoadPosition", "horizontalLoadPositionType", "loadPatchLength", "iceLoadAreaFactorCa", "upperIceWaterlineReferencePosition", "lowerIceWaterlineReferencePosition"},
        "TRF-037": {"directAnalysisCase", "hasDirectAnalysisCase", "iceLoadAreaFactorCa"},
        "TRF-034": {"hasClassificationSocietySectionPropertyCalculationEvidence", "hasEffectiveMemberCrossSection", "effectiveMemberCrossSection"},
        "TRF-036": {"hasIceClassDesignParameterSet", "levelIceThickness", "designIceLoadHeight", "iceClassDesignParameterSet"},
        "TRF-044": {"mainTransverseFrame", "intermediateTransverseFrame"},
        "TRF-046": {"mainFrame", "intermediateIceFrame", "transverseFrame", "frameStrengthenedPart", "supportingStructure", "horizontalConnectionMember", "deckStructure", "tankBoundaryPlating", "iceStringer", "hasUpperEnd", "hasStrengthenedPart", "hasAttachedSupportingStructure", "hasTerminationAboveSupportingStructure", "hasHorizontalConnectionMember", "connectsToAdjacentMainFrame", "ordinaryFrameScantlingsUsed", "sameScantlingsAsMainFrame", "supportingStructureAtOrAboveIceBeltUpperLimit"},
        "TRF-047": {"mainFrame", "intermediateIceFrame", "transverseFrame", "frameStrengthenedPart", "supportingStructure", "horizontalConnectionMember", "deckStructure", "tankBoundaryPlating", "tankTop", "iceStringer", "hasLowerEnd", "hasAttachedSupportingStructure", "hasTerminationBelowSupportingStructure", "hasHorizontalConnectionMember", "connectsToAdjacentMainFrame", "ordinaryFrameScantlingsUsed", "sameScantlingsAsMainFrame", "supportingStructureAtOrBelowIceBeltLowerLimit", "mainFrameBelowIceBeltStrengthened"},
        "TRF-049": {"longitudinalFrame", "transverseFrame", "frame", "supportingStructure", "frameAttachment", "connectionBracket", "hasFrameAttachment", "hasAttachedSupportingStructure", "hasConnectionBracket", "hasSupportingWebFrame", "hasSupportingBulkhead", "withinIceStrengthenedArea", "effectiveAttachmentConfirmed", "passesThroughSupportingStructure", "terminatesAtDeckOrIceStringer", "webPlateConnectionSideCount", "bracketThickness", "frameWebThickness", "bracketEdgeStiffened", "bucklingStiffening"},
        "TRF-050": {"frameShellAttachment", "frameShellWeldType", "scallopingPresent", "shellPlateButtCrossing"},
        "TRF-056": {"hasWeatherdeckHatch", "hasHatchCoverDesignEvidence", "hasHatchFittingDesignEvidence"},
    }.get(rid, set())

    owner_nodes: dict[str, URIRef] = {"ship": ship}

    def owner_node(owner: str) -> URIRef:
        if owner == "ship": return ship
        if owner in owner_nodes: return owner_nodes[owner]
        if owner == "effectiveMemberCrossSection":
            node = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:effective-cross-section")
            graph.add((node, RDF.type, NLTL.effectiveMemberCrossSection))
            graph.add((component, NLTL.hasEffectiveMemberCrossSection, node))
        elif owner == "iceClassDesignParameterSet":
            node = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:design-parameter-set")
            graph.add((node, RDF.type, NLTL.iceClassDesignParameterSet))
            graph.add((ship, NLTL.hasIceClassDesignParameterSet, node))
        else:
            node = component
            graph.add((component, RDF.type, URIRef(BASE + owner)))
        owner_nodes[owner] = node
        return node

    def property_subjects(local: str) -> tuple[URIRef, ...]:
        return (owner_node(ownership.get(local, "ship")),)

    for local in terms:
        if local in structured_skip:
            continue
        if local in missing or local not in registry:
            continue
        item = registry[local]
        iri = URIRef(item["iri"])
        kind = item["kind"]
        if kind == "Class":
            graph.add((component, RDF.type, iri))
            continue
        if kind == "NamedIndividual":
            continue
        if kind == "QuantityProperty":
            number = values.get(local, 1.0)
            node = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:q:{local}")
            graph.add((node, RDF.type, QUDT.QuantityValue))
            # Preserve an integer-looking decimal lexical form for controlled
            # constants. SHACL sh:hasValue compares RDF terms, so "845.0"
            # and "845" are not interchangeable even with xsd:decimal.
            if isinstance(number, int) and not isinstance(number, bool):
                numeric_literal = Literal(str(number), datatype=XSD.decimal, normalize=False)
            else:
                numeric_literal = Literal(Decimal(str(number)), datatype=XSD.decimal)
            graph.add((node, QUDT.numericValue, numeric_literal))
            if item.get("unitIri"):
                graph.add((node, QUDT.unit, URIRef(item["unitIri"])))
            for subject in property_subjects(local): graph.add((subject, iri, node))
            continue
        if kind == "DatatypeProperty":
            value = values.get(local, True if item.get("datatype") == "xsd:boolean" else (1 if item.get("datatype") == "xsd:integer" else ("2020-01-01" if item.get("datatype") == "xsd:date" else "verified")))
            lit = value_literal(item, value)
            for subject in property_subjects(local): graph.add((subject, iri, lit))
            continue
        if kind == "ObjectProperty":
            chosen = values.get(local)
            if isinstance(chosen, str):
                target = URIRef(chosen if ":" in chosen else BASE + chosen)
            else:
                choices = sorted(controlled_by_type.get(item["parentOrRange"], []))
                target = URIRef(BASE + choices[0]) if choices else URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:node:{local}")
                if not choices and item["parentOrRange"].startswith(BASE):
                    graph.add((target, RDF.type, URIRef(item["parentOrRange"])))
            for subject in property_subjects(local): graph.add((subject, iri, target))

    # Attach evidence objects explicitly for the evidence-trigger cases.
    if rid in {"TRF-034", "TRF-056"} and case_kind != "FAIL":
        for prop, cls in (
            ("hasClassificationSocietySectionPropertyCalculationEvidence", "evidenceArtifact"),
            ("hasHatchCoverDesignEvidence", "hatchCoverDesignEvidence"),
            ("hasHatchFittingDesignEvidence", "hatchFittingDesignEvidence"),
        ):
            if prop in terms:
                node = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:evidence:{prop}")
                graph.add((node, RDF.type, URIRef(BASE + cls)))
                graph.add((owner_node(ownership.get(prop, "ship")), URIRef(BASE + prop), node))

    # Explicit waterline point geometry is needed for envelope semantics.
    if rid in {"TRF-011", "TRF-012", "TRF-013", "TRF-016"}:
        uiwl, liwl, intended = (URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:{name}") for name in ("uiwl", "liwl", "intended"))
        for node in (uiwl, liwl, intended): graph.add((node, RDF.type, NLTL.iceWaterline))
        graph.add((ship, NLTL.hasUpperIceWaterline, uiwl)); graph.add((ship, NLTL.hasLowerIceWaterline, liwl)); graph.add((ship, NLTL.hasIntendedIceOperatingWaterline, intended))
        coordinates = [(uiwl, 10.0), (liwl, 5.0), (intended, 10.0), (intended, 5.0)]
        if special == "upper_fail": coordinates[2] = (intended, 11.0)
        if special == "lower_fail": coordinates[3] = (intended, 4.0)
        for index, (waterline, z) in enumerate(coordinates, start=1):
            point = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:point:{index}")
            qx = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:point:{index}:x")
            qz = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:point:{index}:z")
            graph.add((point, RDF.type, NLTL.waterlineProfilePoint)); graph.add((waterline, NLTL.hasWaterlineProfilePoint, point))
            for qnode, number in ((qx, 0.0), (qz, z)):
                graph.add((qnode, RDF.type, QUDT.QuantityValue)); graph.add((qnode, QUDT.numericValue, Literal(Decimal(str(number)), datatype=XSD.decimal))); graph.add((qnode, QUDT.unit, URIRef("http://qudt.org/vocab/unit/M")))
            graph.add((point, NLTL.longitudinalPosition, qx)); graph.add((point, NLTL.verticalCoordinate, qz))
        if rid == "TRF-016":
            displacement = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:q:waterlineDisplacement")
            graph.add((displacement, RDF.type, QUDT.QuantityValue))
            graph.add((displacement, QUDT.numericValue, Literal(Decimal(str(values["waterlineDisplacement"])), datatype=XSD.decimal)))
            graph.add((displacement, QUDT.unit, URIRef("http://qudt.org/vocab/unit/TON_Metric")))
            graph.add((uiwl, NLTL.waterlineDisplacement, displacement))
            graph.add((ship, NLTL.hasBallastTank, component))
        if rid == "TRF-013":
            for waterline, suffix, fore, aft in (
                (uiwl, "upper", 7.0, 7.0),
                (liwl, "lower", 5.0, 5.0),
            ):
                for prop, number in (("draughtAtForePerpendicular", fore), ("draughtAtAftPerpendicular", aft)):
                    qnode = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:q:{suffix}:{prop}")
                    graph.add((qnode, RDF.type, QUDT.QuantityValue))
                    graph.add((qnode, QUDT.numericValue, Literal(Decimal(str(number)), datatype=XSD.decimal)))
                    graph.add((qnode, QUDT.unit, URIRef("http://qudt.org/vocab/unit/M")))
                    graph.add((waterline, URIRef(BASE + prop), qnode))

    # Clause 3.2.2 defines L and B at UIWL as operands for both UIWL and LIWL
    # power calculations; attach those quantities to the UIWL node explicitly.
    if rid == "TRF-020":
        uiwl = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:uiwl")
        liwl = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:liwl")
        graph.add((uiwl, RDF.type, NLTL.iceWaterline))
        graph.add((liwl, RDF.type, NLTL.iceWaterline))
        graph.add((ship, NLTL.hasUpperIceWaterline, uiwl))
        graph.add((ship, NLTL.hasLowerIceWaterline, liwl))
        for prop in ("upperIceWaterlineLength", "upperIceWaterlineBreadth"):
            qnode = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:q:{prop}:uiwl")
            graph.add((qnode, RDF.type, QUDT.QuantityValue))
            graph.add((qnode, QUDT.numericValue, Literal(Decimal(str(values[prop])), datatype=XSD.decimal)))
            graph.add((qnode, QUDT.unit, URIRef("http://qudt.org/vocab/unit/M")))
            graph.add((uiwl, URIRef(BASE + prop), qnode))
        # R_CH is expressed in newtons. Earlier fixtures left the two
        # draught-specific values unitless, which correctly failed generated
        # unit constraints even though the intended PASS values were sound.
        for prop in (
            "brashIceChannelResistanceAtUpperIceWaterline",
            "brashIceChannelResistanceAtLowerIceWaterline",
        ):
            for qnode in graph.objects(ship, URIRef(BASE + prop)):
                graph.add((qnode, QUDT.unit, URIRef("http://qudt.org/vocab/unit/N")))

    if rid == "TRF-032":
        for prop in ("classificationSocietyRequiredScantling", "regulationRequiredScantling", "selectedDesignScantling"):
            for qnode in graph.objects(None, URIRef(BASE + prop)):
                graph.add((qnode, QUDT.unit, URIRef("http://qudt.org/vocab/unit/MilliM")))

    if rid == "TRF-036":
        design_set = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:design-parameter-set")
        graph.add((design_set, RDF.type, NLTL.iceClassDesignParameterSet))
        graph.add((ship, NLTL.hasIceClassDesignParameterSet, design_set))
        for prop in ("levelIceThickness", "designIceLoadHeight"):
            qnode = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:q:{prop}:design-set")
            graph.add((qnode, RDF.type, QUDT.QuantityValue))
            graph.add((qnode, QUDT.numericValue, Literal(Decimal(str(values[prop])), datatype=XSD.decimal)))
            graph.add((qnode, QUDT.unit, URIRef("http://qudt.org/vocab/unit/M")))
            graph.add((design_set, URIRef(BASE + prop), qnode))

    if rid == "TRF-044":
        graph.add((component, RDF.type, NLTL.mainTransverseFrame))

    # All-region antitripping support is represented by three explicit values.
    if rid == "TRF-052" and case_kind != "FAIL":
        for region in (NLTL.bowRegion, NLTL.midbodyRegion, NLTL.sternRegion):
            graph.add((component, NLTL.hasAntitrippingSupportRegion, region))
    # TRF-001 contains two provision-scoped rules that apply irrespective of
    # build year, independently of the date-scoped whole-edition rule.
    if rid == "TRF-001":
        for provision in (NLTL.iceClassSection1Point8Provision2021, NLTL.iceClassDraughtChapter2Provision2021):
            graph.add((ship, NLTL.applicableIceClassRegulatoryProvision, provision))
            graph.add((component, NLTL.applicableIceClassRegulatoryProvision, provision))

    # Direct analysis requires repeatable cases, not one string-valued location.
    if rid == "TRF-030":
        position_types = (
            NLTL.upperIceWaterlineCenteredPosition,
            NLTL.halfLoadHeightBelowLowerIceWaterlinePosition,
            NLTL.intermediateVerticalPosition,
            NLTL.intermediateVerticalPosition,
            NLTL.midSpanOrSpacingCenteredPosition,
            NLTL.otherHorizontalPosition,
            NLTL.otherHorizontalPosition,
        )
        for index, position_type in enumerate(position_types, start=1):
            case = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:analysis-case:{index}")
            graph.add((case, RDF.type, NLTL.directAnalysisCase))
            graph.add((ship, NLTL.hasDirectAnalysisCase, case))
            graph.add((case, NLTL.capacityMinimizingLoadPositionConfirmed, Literal(case_kind != "FAIL", datatype=XSD.boolean)))
            graph.add((case, NLTL.combinedBendingAndShearEvaluated, Literal(True, datatype=XSD.boolean)))
            predicate = NLTL.verticalLoadPositionType if index <= 4 else NLTL.horizontalLoadPositionType
            graph.add((case, predicate, position_type))
            numeric_prop = NLTL.verticalLoadPosition if index <= 4 else NLTL.horizontalLoadPosition
            numeric = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:analysis-position:{index}")
            graph.add((numeric, RDF.type, QUDT.QuantityValue))
            graph.add((numeric, QUDT.numericValue, Literal(Decimal(str(index)), datatype=XSD.decimal)))
            graph.add((numeric, QUDT.unit, URIRef("http://qudt.org/vocab/unit/M")))
            graph.add((case, numeric_prop, numeric))
            length = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:analysis-length:{index}")
            factor = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:analysis-factor:{index}")
            for qnode, number, unit in ((length, 0.5 + index / 10, "http://qudt.org/vocab/unit/M"), (factor, max(0.35, min(1.0, 0.6 / (0.5 + index / 10))), None)):
                graph.add((qnode, RDF.type, QUDT.QuantityValue))
                graph.add((qnode, QUDT.numericValue, Literal(Decimal(str(number)), datatype=XSD.decimal)))
                if unit: graph.add((qnode, QUDT.unit, URIRef(unit)))
            graph.add((case, NLTL.loadPatchLength, length))
            graph.add((case, NLTL.iceLoadAreaFactorCa, factor))

    # Clause 4.2.2 uses c_a in the pressure formula. R8 assigns that operand to
    # a direct-analysis case and supplies the canonical ship-to-case relation.
    if rid == "TRF-037":
        case = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:analysis-case")
        factor = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:q:iceLoadAreaFactorCa")
        graph.add((case, RDF.type, NLTL.directAnalysisCase))
        graph.add((ship, NLTL.hasDirectAnalysisCase, case))
        graph.add((factor, RDF.type, QUDT.QuantityValue))
        graph.add((factor, QUDT.numericValue, Literal(Decimal(str(values["iceLoadAreaFactorCa"])), datatype=XSD.decimal)))
        graph.add((factor, QUDT.unit, URIRef("http://qudt.org/vocab/unit/UNITLESS")))
        graph.add((case, NLTL.iceLoadAreaFactorCa, factor))

    # Cross-component end/attachment alternatives need explicit nodes and paths.
    if rid in {"TRF-046", "TRF-047"}:
        supporting_types = (NLTL.deckStructure, NLTL.tankBoundaryPlating, NLTL.iceStringer)
        for index, frame_type in enumerate((NLTL.mainFrame, NLTL.intermediateIceFrame), start=1):
            frame_node = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:frame:{index}")
            end_node = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:frame-end:{index}")
            support_node = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:support:{index}")
            graph.add((ship, NLTL.hasComponent, frame_node))
            graph.add((frame_node, RDF.type, frame_type))
            # The target is nltl:frame. State the superclass explicitly so
            # fixture behavior is independent of subclass inference details.
            graph.add((frame_node, RDF.type, NLTL.frame))
            strengthened_part = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:strengthened-part:{index}")
            graph.add((strengthened_part, RDF.type, NLTL.frameStrengthenedPart))
            graph.add((frame_node, NLTL.hasStrengthenedPart, strengthened_part))
            if rid == "TRF-047" and frame_type == NLTL.mainFrame:
                graph.add((frame_node, NLTL.mainFrameBelowIceBeltStrengthened, Literal(case_kind != "FAIL", datatype=XSD.boolean)))
            graph.add((end_node, RDF.type, NLTL.frameEnd))
            graph.add((support_node, RDF.type, supporting_types[index - 1]))
            limit_prop = NLTL.supportingStructureAtOrAboveIceBeltUpperLimit if rid == "TRF-046" else NLTL.supportingStructureAtOrBelowIceBeltLowerLimit
            graph.add((support_node, limit_prop, Literal(True, datatype=XSD.boolean)))
            graph.add((frame_node, NLTL.hasUpperEnd if rid == "TRF-046" else NLTL.hasLowerEnd, end_node))
            if case_kind != "FAIL":
                graph.add((end_node, NLTL.hasAttachedSupportingStructure, support_node))
            if frame_type == NLTL.intermediateIceFrame:
                member = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:horizontal-member")
                graph.add((member, RDF.type, NLTL.horizontalConnectionMember))
                graph.add((end_node, NLTL.hasHorizontalConnectionMember, member))
                graph.add((member, NLTL.sameScantlingsAsMainFrame, Literal(True, datatype=XSD.boolean)))
                # The permission alternative is bounded by two different
                # adjacent main frames. Reuse the compliant main frame above
                # and create a second fully supported main frame so the helper
                # nodes are valid targets in their own right.
                adjacent_frames = [URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:frame:1")]
                adjacent2 = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:adjacent-main-frame:2")
                adjacent2_end = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:adjacent-main-frame:2:end")
                adjacent2_part = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:adjacent-main-frame:2:part")
                graph.add((adjacent2, RDF.type, NLTL.mainFrame))
                graph.add((adjacent2, RDF.type, NLTL.frame))
                graph.add((adjacent2_part, RDF.type, NLTL.frameStrengthenedPart))
                graph.add((adjacent2, NLTL.hasStrengthenedPart, adjacent2_part))
                graph.add((adjacent2, NLTL.hasUpperEnd if rid == "TRF-046" else NLTL.hasLowerEnd, adjacent2_end))
                graph.add((adjacent2_end, RDF.type, NLTL.frameEnd))
                graph.add((adjacent2_end, NLTL.hasAttachedSupportingStructure, support_node))
                adjacent_frames.append(adjacent2)
                for adjacent in adjacent_frames:
                    graph.add((member, NLTL.connectsToAdjacentMainFrame, adjacent))

    if rid == "TRF-049":
        frame_node = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:frame")
        support_node = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:support")
        attachment = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:attachment")
        bracket = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:bracket")
        graph.add((frame_node, RDF.type, NLTL.longitudinalFrame))
        graph.add((frame_node, RDF.type, NLTL.frame))
        graph.add((support_node, RDF.type, NLTL.supportingStructure))
        graph.add((attachment, RDF.type, NLTL.frameAttachment))
        graph.add((bracket, RDF.type, NLTL.connectionBracket))
        graph.add((ship, NLTL.hasComponent, frame_node))
        graph.add((frame_node, NLTL.hasFrameAttachment, attachment))
        graph.add((attachment, NLTL.hasAttachedSupportingStructure, support_node))
        graph.add((support_node, NLTL.hasSupportingStructureAttachment, attachment))
        graph.add((attachment, NLTL.hasConnectionBracket, bracket))
        graph.add((attachment, NLTL.effectiveAttachmentConfirmed, Literal(True, datatype=XSD.boolean)))
        graph.add((attachment, NLTL.similarAttachmentConstructionPresent, Literal(False, datatype=XSD.boolean)))
        graph.add((frame_node, NLTL.withinIceStrengthenedArea, Literal(True, datatype=XSD.boolean)))
        graph.add((frame_node, NLTL.passesThroughSupportingStructure, Literal(True, datatype=XSD.boolean)))
        graph.add((frame_node, NLTL.terminatesAtDeckOrIceStringer, Literal(True, datatype=XSD.boolean)))
        graph.add((frame_node, NLTL.webPlateConnectionSideCount, Literal(2, datatype=XSD.integer)))
        graph.add((frame_node, NLTL.hasSupportingWebFrame, support_node))
        bulkhead = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:bulkhead")
        graph.add((bulkhead, RDF.type, NLTL.bulkhead))
        graph.add((frame_node, NLTL.hasSupportingBulkhead, bulkhead))
        # Each identified support must share the same confirmed attachment.
        graph.add((bulkhead, NLTL.hasSupportingStructureAttachment, attachment))
        graph.add((bracket, NLTL.bracketEdgeStiffened, Literal(True, datatype=XSD.boolean)))
        graph.add((bracket, NLTL.bucklingStiffening, Literal(True, datatype=XSD.boolean)))
        for owner, prop in ((bracket, "bracketThickness"), (frame_node, "frameWebThickness")):
            qnode = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:q:{prop}:structured")
            graph.add((qnode, RDF.type, QUDT.QuantityValue))
            graph.add((qnode, QUDT.numericValue, Literal(Decimal(str(values[prop])), datatype=XSD.decimal)))
            graph.add((qnode, QUDT.unit, URIRef("http://qudt.org/vocab/unit/MilliM")))
            graph.add((owner, URIRef(BASE + prop), qnode))

    if rid == "TRF-050":
        attachment = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:frame-shell-attachment")
        graph.add((attachment, RDF.type, NLTL.frameAttachment))
        graph.add((ship, NLTL.frameShellAttachment, attachment))
        graph.add((attachment, NLTL.frameShellWeldType, NLTL.doubleContinuousWeld))
        graph.add((attachment, NLTL.scallopingPresent, Literal(values["scallopingPresent"], datatype=XSD.boolean)))
        graph.add((attachment, NLTL.shellPlateButtCrossing, Literal(values["shellPlateButtCrossing"], datatype=XSD.boolean)))

    # Design evidence belongs to the qualifying weatherdeck hatch, not merely
    # somewhere on the ship graph.
    if rid == "TRF-056":
        hatch = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:weatherdeck-hatch")
        graph.add((hatch, RDF.type, NLTL.weatherdeckHatch))
        graph.add((ship, NLTL.hasWeatherdeckHatch, hatch))
        for prop in ("hatchOpeningLength", "shipSideDeflection"):
            qnode = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:q:{prop}")
            graph.add((hatch, URIRef(BASE + prop), qnode))
        if case_kind != "FAIL":
            for prop, cls in (("hasHatchCoverDesignEvidence", "hatchCoverDesignEvidence"), ("hasHatchFittingDesignEvidence", "hatchFittingDesignEvidence")):
                evidence_node = URIRef(f"{EX_BASE}{rid}:{case_kind.lower()}:evidence:{prop}")
                graph.add((evidence_node, RDF.type, URIRef(BASE + cls)))
                graph.add((hatch, URIRef(BASE + prop), evidence_node))
    return graph


def main() -> None:
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    registry_rows = read_json(DEV / "registry" / "term_registry.json")
    registry = {item["localName"]: item for item in registry_rows}
    ontology = Graph().parse(DEV / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
    for local_name, item in registry.items():
        item["_domains"] = [str(value) for value in ontology.objects(URIRef(item["iri"]), URIRef("http://www.w3.org/2000/01/rdf-schema#domain"))]
    index_payload = read_json(DEV / "requirement_term_index.json")
    index = index_payload["requirements"]
    term_owners = index_payload.get("termOwners", {})
    preflight = read_json(BATCH / "engineering_preflight.json")["requirements"]
    evidence = {item["id"]: item for item in read_json(DEV / "evidence" / "stage1_approved.json")["requirements"]}
    allowed = {URIRef(item["iri"]) for item in registry_rows}
    allowed.update(s for s in ontology.subjects() if str(s).startswith(BASE))
    records = []
    errors = []
    for row in preflight:
        rid = row["requirement_id"]
        folder = OUT / rid
        folder.mkdir()
        for number, case_kind in enumerate(("PASS", "FAIL", "BOUNDARY"), start=1):
            graph = build_graph(rid, case_kind, index[rid], registry, term_owners.get(rid, {}))
            path = folder / f"{rid.lower()}_{number:02d}_{case_kind.lower()}.ttl"
            graph.serialize(path, format="turtle")
            parsed = Graph().parse(path, format="turtle")
            unknown = sorted({
                str(term) for triple in parsed for term in triple
                if isinstance(term, URIRef) and str(term).startswith(BASE) and term not in allowed
            })
            if unknown: errors.append({"file": str(path), "unknownVocabularyPredicates": unknown})
            expected = case_kind != "FAIL"
            scenario = row["planned_fixture_variants"]
            records.append({
                "caseId": f"B01-{rid}-{case_kind}", "requirementId": rid, "caseKind": case_kind,
                "expectedConforms": expected, "scenarioBasis": scenario, "sourcePage": evidence[rid]["page"],
                "sourceClause": evidence[rid]["clause"], "sourceFile": "RELEVANT FILES/TRAFICOM.pdf",
                "rdfFile": str(path.relative_to(MVP)), "rdfSha256": sha256(path), "tripleCount": len(parsed),
                "developmentVocabularyId": DEVELOPMENT_ID,
                "calibrationOnly": True,
            })
    catalog = {
        "batchId": "BATCH-01-FIRST-50", "status": "DEVELOPMENT_CALIBRATION_FIXTURES",
        "requirements": len(preflight), "cases": len(records), "caseRecords": records,
        "warning": "These authored fixtures are development calibration material. Final benchmark evaluation requires fresh generations under a later fixed lock and hidden fixtures.",
    }
    (OUT / "fixture_catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    validation = {"status": "PASS" if not errors else "FAIL", "requirements": len(preflight), "rdfFiles": len(records), "parseErrors": 0, "unknownVocabularyPredicateErrors": errors}
    (OUT / "validation_report.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    (OUT / "README.md").write_text(
        "# Batch 01 RDF calibration fixtures\n\n"
        "Each of the first 50 eligible TRAFICOM requirements has one conforming case, one deliberately non-conforming case, and one boundary/non-applicability case. Values use the canonical development units. Formula constants and table rows are grounded in TRAFICOM.pdf pp. 9-24.\n\n"
        "These files are visible development fixtures, not hidden final-evaluation data. The catalog binds every file by SHA-256 to its requirement, clause, source page, expected outcome, and development vocabulary identifier.\n",
        encoding="utf-8",
    )
    if errors: raise RuntimeError(json.dumps(errors, indent=2))
    print(json.dumps({"status": "PASS", "requirements": len(preflight), "rdf_files": len(records), "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
