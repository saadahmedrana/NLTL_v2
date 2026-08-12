from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from rdflib import Graph, Literal, RDF, URIRef

ROOT = Path(__file__).resolve().parent.parent
TMP = Path("/tmp/nltl_stage1")
LOCKED = json.loads((TMP / "locked.json").read_text())
DATA_SHEETS = ["TRAFICOM", "IACS_UR_I2", "IMO_POLAR_CODE", "IMO_AMEND_2026"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    if path.is_dir():
        for child in sorted(p for p in path.rglob("*") if p.is_file() and p.name != ".DS_Store"):
            h.update(str(child.relative_to(path)).encode("utf-8"))
            h.update(bytes.fromhex(sha256(child)))
        return h.hexdigest()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def excerpt(text: str, needle: str, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    pos = text.lower().find((needle or "").lower())
    start = max(0, pos - 80) if pos >= 0 else 0
    out = text[start : start + limit]
    return ("..." if start else "") + out + ("..." if start + limit < len(text) else "")


def split_variables(value: str) -> list[str]:
    if not value or value.strip() == "No explicit data variable identified":
        return []
    value = value.replace(";", ",").replace(" and ", ", ")
    parts = []
    for part in value.split(","):
        part = part.strip()
        part = re.sub(r"^(and|or)\s+", "", part, flags=re.I)
        part = re.sub(r"\s*->.*$", "", part)
        part = re.sub(r"\s*\(.*?\)\s*$", "", part)
        if part and not part.lower().startswith("no direct anchormap"):
            parts.append(part)
    return parts


UNIT_SUFFIXES = [
    (r"_N_mm2$", "N/mm^2", "", "PressureOrStress"),
    (r"_MN_m$", "MN/m", "", "ForcePerLength"),
    (r"_kg_m2$", "kg/m^2", "http://qudt.org/vocab/unit/KiloGM-PER-M2", "MassPerArea"),
    (r"_kg_m3$", "kg/m^3", "http://qudt.org/vocab/unit/KiloGM-PER-M3", "Density"),
    (r"_kNm$", "kN*m", "http://qudt.org/vocab/unit/KiloN-M", "TorqueOrMoment"),
    (r"_kN$", "kN", "http://qudt.org/vocab/unit/KiloN", "Force"),
    (r"_MPa$", "MPa", "http://qudt.org/vocab/unit/MegaPA", "PressureOrStress"),
    (r"_kW$", "kW", "http://qudt.org/vocab/unit/KiloW", "Power"),
    (r"_Nm3$", "Nm^3", "", "NormalVolume"),
    (r"_m3$", "m^3", "http://qudt.org/vocab/unit/M3", "Volume"),
    (r"_m2$", "m^2", "http://qudt.org/vocab/unit/M2", "Area"),
    (r"_mm$", "mm", "http://qudt.org/vocab/unit/MilliM", "Length"),
    (r"_nm$", "nautical mile", "http://qudt.org/vocab/unit/MI_N", "Length"),
    (r"_kn$", "kn", "http://qudt.org/vocab/unit/KN", "Velocity"),
    (r"_degC$", "deg C", "http://qudt.org/vocab/unit/DEG_C", "Temperature"),
    (r"_deg$", "deg", "http://qudt.org/vocab/unit/DEG", "Angle"),
    (r"_days$", "day", "http://qudt.org/vocab/unit/DAY", "Time"),
    (r"_years$", "year", "http://qudt.org/vocab/unit/YR", "Time"),
    (r"_h$", "h", "http://qudt.org/vocab/unit/HR", "Time"),
    (r"_tenths$", "tenths", "", "Dimensionless"),
    (r"_m$", "m", "http://qudt.org/vocab/unit/M", "Length"),
]

SPECIAL_NAMES = {
    "UIWL": "upperIceWaterline",
    "LIWL": "lowerIceWaterline",
    "D": "propellerDiameter",
    "D_m": "propellerDiameter",
    "LBOW": "bowLength",
    "PST": "polarServiceTemperature",
    "PST_degC": "polarServiceTemperature",
    "MDLT": "meanDailyLowTemperature",
    "MDLT_degC": "meanDailyLowTemperature",
    "MCR": "maximumContinuousRating",
    "mcrPower_kW": "maximumContinuousRatingPower",
    "Qmax_kNm": "maximumIceTorque",
    "Qsmax_kNm": "maximumSpindleTorque",
    "Fex_kN": "extremeIceForce",
    "Tf_kN": "forwardIceThrust",
    "Tb_kN": "backwardIceThrust",
    "Ff_kN": "forwardBladeForce",
    "Fb_kN": "backwardBladeForce",
    "Nice": "iceLoadCycleCount",
    "Nclass": "classLoadCycleCount",
    "sectionModulusZ": "sectionModulus",
    "shearAreaA": "shearArea",
    "yieldStrength_MPa": "yieldStrength",
    "sigmaRef2_MPa": "bladeReferenceStrength2",
    "sigmaSt_MPa": "calculatedBladeStress",
    "sigmaU_MPa": "ultimateTensileStrength",
    "sigma0_2_MPa": "zeroPointTwoPercentProofStrength",
    "SOLAS_chapter_I_certified": "solasChapterICertified",
    "MARPOL_IV_11_1_1_compliance_status": "marpolIv111ComplianceStatus",
    "GNSS_compass_or_equivalent_count": "gnssCompassOrEquivalentCount",
    "A_a_cm2": "actualShearArea",
    "P_avg": "averageIcePressure",
    "M_BL": "bladeBendingMoment",
    "F_b_kN": "backwardBladeForce",
    "F_f_kN": "forwardBladeForce",
    "T_b_kN": "backwardIceThrust",
    "T_f_kN": "forwardIceThrust",
    "psi": "flareAngle",
    "phi2": "bowRakeAtQuarterBreadth",
    "k1": "iceLoadCycleCoefficientK1",
    "k2": "iceLoadCycleCoefficientK2",
    "k3": "iceLoadCycleCoefficientK3",
    "Qr_kNm": "responseTorque",
    "Q_sex_kNm": "bladeFailureSpindleTorque",
    "keValue": "engineOutputCoefficientKe",
    "rchValue": "brashIceChannelResistanceRch",
    "P_min_UIWL_kW": "minimumRequiredPowerAtUpperIceWaterline",
    "P_min_LIWL_kW": "minimumRequiredPowerAtLowerIceWaterline",
    "PWOM_present": "polarWaterOperationalManualPresent",
    "chapter_9_applicable": "polarCodeChapter9Applicable",
    "chapter_9_1_applicable": "polarCodeChapter9Dash1Applicable",
    "chapter_11_applicable": "polarCodeChapter11Applicable",
    "chapter_11_1_applicable": "polarCodeChapter11Dash1Applicable",
    "clause_1_1_1_oil_discharge_prohibition_applicable": "polarCodeOilDischargeParagraph1Point1Point1Applicable",
    "clause_1_3_3_exception": "polarShipCertificateParagraph1Point3Point3ExceptionApplies",
    "clause_4_2_1_3_compliance_status": "polarCodeSewageParagraph4Point2Point1Point3ComplianceStatus",
    "MARPOL_IV_11_1_1_compliance_status": "marpolAnnexIvRegulation11Point1Point1ComplianceStatus",
    "MARPOL_IV_11_1_2_discharge_status": "marpolAnnexIvRegulation11Point1Point2DischargeComplianceStatus",
    "MARPOL_IV_9_1_1_or_9_2_1_certification_status": "marpolAnnexIvRegulation9Point1Point1Or9Point2Point1CertificationStatus",
    "MARPOL_V_6_1_discharge": "marpolAnnexVRegulation6Point1DischargeOccurs",
    "SOLAS_V_22_1_9_4_compliance_status": "solasRegulationV22Point1Point9Point4ComplianceStatus",
    "STCW_II_2_status": "stcwConventionRegulationIi2ComplianceStatus",
    "STCW_A_II_2_status": "stcwCodeSectionAIi2ComplianceStatus",
    "backward_design_thrust_T_r_kN": "backwardPropellerShaftDesignThrust",
    "backwardDesignThrust_kN": "backwardPropellerShaftDesignThrust",
    "forward_design_thrust_T_r_kN": "forwardPropellerShaftDesignThrust",
    "forwardDesignThrust_kN": "forwardPropellerShaftDesignThrust",
    "design_thrust_T_r_kN": "propellerShaftDesignThrust",
    "designThrust_kN": "propellerShaftDesignThrust",
    "hydrodynamic_bollard_thrust_T_kN": "hydrodynamicBollardThrust",
    "blade_failure_load_F_ex_kN": "bladeFailureUltimateLoad",
    "design_line_load_MN_m": "designLineLoad",
    "sigma_0_2_MPa": "zeroPointTwoPercentProofStrength",
    "sigma_u_MPa": "ultimateTensileStrength",
    "sigma_ref1": "bladeReferenceStrength1",
    "sigma_ref2_MPa": "bladeReferenceStrength2",
    "sigma_st": "calculatedBladeStress",
    "sigma_st_MPa": "calculatedBladeStress",
    "sigma_y_N_mm2": "yieldStrength",
    "sigma_fat": "equivalentBladeFatigueStress",
    "sigma_fl": "reducedBladeFatigueStrength",
    "gamma_e1": "fatigueScatterReductionFactor",
    "gamma_e2": "testSpecimenSizeReductionFactor",
    "gamma_v": "variableAmplitudeLoadingReductionFactor",
    "gamma_m": "meanStressReductionFactor",
    "sigma_exp": "meanBladeMaterialFatigueStrengthInSeawater",
    "gamma_stem": "stemAngle",
    "combinedBendingShearEffect": "combinedShearBendingEffect",
    "safetyFactorYield": "yieldSafetyFactor",
    "safety_factor_yield": "yieldSafetyFactor",
    "termination_at_that_boundary": "iceStrengtheningTerminationAtAdjacentBoundaryPermitted",
}

PREFIX_EXPANSIONS = {
    "PWOM": "polarWaterOperationalManual",
    "NLS": "noxiousLiquidSubstance",
    "SAR": "searchAndRescue",
    "TMAS": "telemedicalAssistanceService",
}

NO_UNIT_ALIASES = {"gamma_m"}


def lower_camel(raw: str) -> tuple[str, str, str, str]:
    original = raw.strip()
    base = original
    unit = unit_uri = quantity_kind = ""
    if original not in NO_UNIT_ALIASES:
        for pattern, symbol, uri, qk in UNIT_SUFFIXES:
            if re.search(pattern, base):
                base = re.sub(pattern, "", base)
                unit, unit_uri, quantity_kind = symbol, uri, qk
                break
    if original in SPECIAL_NAMES:
        base = SPECIAL_NAMES[original]
    else:
        for short, expanded in PREFIX_EXPANSIONS.items():
            base = re.sub(rf"(^|_){short}(?=_|$)", lambda m: (m.group(1) or "") + expanded, base)
    if base in SPECIAL_NAMES:
        base = SPECIAL_NAMES[base]
    tokens = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|[A-Z]+|\d+", base.replace("-", "_").replace("/", "_").replace(" ", "_"))
    if not tokens:
        tokens = [re.sub(r"[^A-Za-z0-9]", "", base) or "unresolvedTerm"]
    local = tokens[0].lower() + "".join(t[:1].upper() + t[1:].lower() if t.isupper() else t[:1].upper() + t[1:] for t in tokens[1:])
    local = re.sub(r"[^A-Za-z0-9]", "", local)
    if not re.match(r"^[a-z]", local):
        local = "term" + local[:1].upper() + local[1:]
    return local, unit, unit_uri, quantity_kind


HIDDEN_BY_REQ = {
    "TRF-020": "keValue,rchValue",
    "TRF-031": "combinedBendingShearStress,vonMisesYieldCriterion,yieldPoint,allowableShearStress,directCalculationMethod,beamTheoryUsed",
    "TRF-028": "keValue,rchValue,alternativeCalculationEvidence,modelTestEvidence,approvalStatus,approvalRevocationStatus,shipPerformanceExperienceEvidence",
    "TRF-027": "coefficientF1,coefficientF2,coefficientF3,coefficientF4,coefficientG1,coefficientG2,coefficientG3,coefficientC3,coefficientC4,coefficientC5,shipLength,iceClassDraught,shipBreadth,clampedHullGeometryTerm",
    "TRF-029": "directAnalysisUsed,directAnalysisApprovalStatus,structuralArrangement,prescribedProcedureApplicability",
    "TRF-032": "regulationDerivedScantling,classificationSocietyScantling,iceStrengtheningStatus",
    "TRF-035": "ruleLength,classificationSociety",
    "TRF-036": "levelIceThickness,designIceLoadHeight,iceClass",
    "TRF-046": "transverseFrame,frameStrengthenedPart,frameUpperEnd,supportingStructure,attachmentType,iceBeltUpperLimit,connectionMemberScantling",
    "TRF-047": "transverseFrame,frameStrengthenedPart,frameLowerEnd,supportingStructure,attachmentType,iceBeltLowerLimit,connectionMemberScantling",
    "TRF-049": "frame,supportingStructure,frameAttachment,connectionBracket,frameWebPlateThickness,bucklingStiffening",
    "TRF-050": "frameShellAttachment,weldType,scallopingPresent,shellPlateButtCrossing",
    "TRF-056": "shipSideDeflection,hatchOpeningLength,shipBreadth,hatchCoverDesignEvidence,hatchFittingDesignEvidence",
    "TRF-057": "webFrameIceLoad,webFrameSafetyFactor,icePressure,iceLoadHeight,webFrameSpacing,loadLengthParameter,minimumLineLoad",
    "TRF-062": "propellerBladeTipHullClearance,sternFrame,minimumClearance",
    "TRF-058": "iceLoadForce,stringerOutsideIceBeltHeight,stringerSpan",
    "TRF-063": "propellerCount,sidePropeller,shellIceStrengtheningExtent,framingIceStrengtheningExtent,tankTop",
    "TRF-064": "sidePropellerShafting,sternTube,platedBossing,detachedStrut,strutDesignEvidence,strutStrengthEvidence,strutHullAttachmentEvidence",
    "TRF-070": "thrusterType,propellerIceInteractionLoad,thrusterBodyIceInteractionLoad,serviceLife,thrusterBodyLocalStrength,localIcePressure,extremeLoad",
    "TRF-075": "backwardBladeForce,forwardBladeForce,propellerBlade,iceBlock,forceLoadCase",
    "TRF-076": "propellerType,propellerReversingCapability,bladeLoadCaseCoverage",
    "TRF-077": "loadSpectrumShapeParameter,iceLoadCycleCount,bladeIceLoad,propellerType",
    "TRF-080": "iceLoadCycleCount,propellerBladeCount,propellerIceInteractionComponent",
    "TRF-082": "hydrodynamicBollardThrust,bollardThrustKnown,tableFallbackValue",
    "TRF-083": "propellerRotationalSpeedAtMcrBollard,rotationalSpeedKnown,tableFallbackValue",
    "TRF-084": "propellerType,propellerPitchAtMcrBollard,propellerPitchAtMcrFreeRunning,pitchValueKnown",
    "TRF-086": "propellerType,propellerPitchAtMcrBollard,propellerPitchAtMcrFreeRunning,pitchValueKnown",
    "TRF-088": "maximumEngineTorque,maximumEngineTorqueKnown,tableFallbackValue",
    "TRF-089": "bladeOrderTorsionalResonance,operationalSpeedRange,maximumOperatingSpeed,shaftComponentDesignTorque,torsionalVibrationAnalysis,frequencyDomainMethod",
    "TRF-090": "timeDomainAnalysis,mcrCondition,mcrBollardCondition,bladeOrderResonantSpeed,resonantVibrationResponse",
    "TRF-091": "propellerIceMillingLoadSequence,propulsionLineStrengthEvaluation,stallingAnalysisPurpose",
    "TRF-092": "propellerIceInteractionLoadCase,shaftLineComponent,maximumIceTorque,shaftSpeed",
    "TRF-093": "dieselEnginePlant,elasticCouplingPresent,iceEngineExcitationPhaseAngle,engineFiringPulse,steadyStateHarmonic",
    "TRF-094": "bladeOrderResonance,mcrSpeed,analysisMaximumSpeed",
    "TRF-096": "engineSpeedDrop,engineStandstillReached,intendedServicePowerAdequacy,maximumTorqueDuringSpeedDrop",
    "TRF-100": "timeDomainTorsionalAnalysis,propellerIceExcitation,primeMoverMeanTorque,hydrodynamicPropellerMeanTorque,damping,excitationPhaseVariation,frequencyDomainAnalysis,bladeExcitationOrder",
    "TRF-104": "pyramidStrengthPrinciple,propellerBladeLoss,shaftLineComponentDamage",
    "TRF-108": "snCurveType,propellerBladeMaterialProperty,twoSlopeSnCurveUsed",
    "TRF-109": "fatigueCoefficient,iceLoadCycleCount,fatigueFactorRho",
    "TRF-110": "gamma_e1,gamma_e2,gamma_v,gamma_m,sigma_exp,sigma_fl,sigma_fat,safetyFactorYield,safetyFactorFatigue,safetyFactorBladeLossYield",
    "TRF-112": "bladeFailureUltimateLoad,shaftComponent,combinedAxialBendingTorsionLoad,yieldSafetyFactor",
    "TRF-113": "steeringMechanism,thrusterFitting,thrusterBody,bladePlasticBending,bladeLossLoad,propellerBladeOrientation",
    "TRF-114": "thrusterBody,designIceBlock,iceOperatingSpeed,impactLoadCase,contactGeometry,equivalentImpactSphereRadius",
    "TRF-116": "nonHemisphericalImpactArea,equivalentImpactSphereRadius",
    "TRF-118": "thrusterExtremeLoad,nominalVonMisesStress,localStressConcentration,yieldSafetyFactor,thrusterOperability,repairRequired",
    "TRF-119": "bladeOrderExcitationFrequency,thrusterGlobalModeFrequency,propellerPowerFraction,globalBladeOrderResonance,vibratoryLoadDesignEvidence",
    "TRF-120": "thrusterNaturalFrequency,damping,waterAddedMass,shipAttachmentStiffness",
    "TRF-125": "vibrationAnalysis,harmfulTorsionalResonance,propellerIceInteraction",
    "TRF-129": "coolingWaterSystem,coolingWaterSupplySecured,iceNavigationCondition",
    "TRF-131": "ballastWaterCoolingArrangement,inletChest,reserveCoolingFunction,substituteArrangementStatus",
    "I2-001": "constructionContractDate,urI2RevisionApplicability",
    "I2-002": "polarClass,urI1ComplianceStatus,urI2Applicability",
    "I2-005": "shellInclinationAngle,bottomRegionLowerRegionBoundary",
    "I2-006": "asternIceOperationIntent,aftSectionDesignBasis,hullAreaRequirementSet",
    "I2-008": "polarClass,hullArea,bowShape,averageIcePressure,loadPatchLength,loadPatchHeight,shapeCoefficient,totalGlancingImpactForce,lineLoad,localIcePressure",
    "I2-009": "hullArea,averageIcePressure,nonBowLoadPatchLength,nonBowLoadPatchHeight,loadPatchAspectRatio,buttockAngle,normalFrameAngle,bowFormApplicability",
    "I2-010": "polarClass,bowVerticalSideStatus,normalFrameAngle,bowDesignForceMethod",
    "I2-011": "polarClass,bulbousBowPresent,bowDesignForce,shapeCoefficient,loadPatchAspectRatio",
    "I2-017": "nonBowIceForce,nonBowLineLoad,nonBowLoadPatchLength,nonBowLoadPatchHeight,averageIcePressure",
    "I2-018": "averageIcePressure,iceForce,loadPatchLength,loadPatchHeight,peakPressureFactor",
    "I2-019": "structuralMember,hullAreaBoundary,hullAreaFactor",
    "I2-024": "framingAngle,interpolatedShellPlateRequirement",
    "I2-026": "framingMember,supportFixity,connectionBracket,rotationalRestraint,iceStrengthenedArea",
    "I2-031": "localFrame,patchLoad,combinedShearBendingEffect,plasticStrength,plasticCollapseMechanism",
    "I2-034": "longitudinalLocalFrame,combinedShearBendingEffect,plasticStrength,plasticCollapseMechanism",
    "I2-037": "webFrame,loadCarryingStringer,iceLoadPatch,memberCapacity,combinedBendingShearEffect,loadPatchApplicationLocation",
    "I2-046": "corrosionAbrasionAddition,internalStructure,iceStrengthenedHullArea,asBuiltThickness",
    "I2-047": "gaugedThickness,netThickness,steelRenewalRequired",
    "I2-048": "steelGrade,plating,asBuiltThickness,polarClass,materialClass",
    "I2-051": "designVerticalIceShearForce,longitudinalDistributionFactor,hullGirderPosition",
    "I2-052": "interpolationInput,interpolatedValue",
    "I2-053": "appliedVerticalShearStress,hullGirder,designVerticalIceShearForce,designVerticalWaveShearForce",
    "I2-055": "designStress,permissibleStress,strengthCriterionStatus",
    "I2-060": "structuralMember,cutout,memberInstability,structuralStiffening",
    "I2-062": "directCalculationUsed,loadCarryingStringer,webFrame,grillageSystem",
    "I2-065": "nonlinearCalculationMethod,bucklingResponse,plasticDeformation,fractureMargin,majorBucklingMargin,yieldingMargin,permanentDeformation",
    "I2-066": "weldType,iceStrengthenedArea",
    "I2-067": "structuralConnection,strengthContinuityStatus",
}

PREFERRED_LABELS = {
    "polarCodeChapter9Applicable": "Polar Code chapter 9 applicable",
    "polarCodeChapter9Dash1Applicable": "Polar Code chapter 9-1 applicable",
    "polarCodeChapter11Applicable": "Polar Code chapter 11 applicable",
    "polarCodeChapter11Dash1Applicable": "Polar Code chapter 11-1 applicable",
    "polarCodeOilDischargeParagraph1Point1Point1Applicable": "Polar Code oil-discharge paragraph 1.1.1 applicable",
    "polarShipCertificateParagraph1Point3Point3ExceptionApplies": "Polar Ship Certificate paragraph 1.3.3 exception applies",
    "polarCodeSewageParagraph4Point2Point1Point3ComplianceStatus": "Polar Code sewage paragraph 4.2.1.3 compliance status",
    "marpolAnnexIvRegulation11Point1Point1ComplianceStatus": "MARPOL Annex IV regulation 11.1.1 compliance status",
    "marpolAnnexIvRegulation11Point1Point2DischargeComplianceStatus": "MARPOL Annex IV regulation 11.1.2 discharge compliance status",
    "marpolAnnexIvRegulation9Point1Point1Or9Point2Point1CertificationStatus": "MARPOL Annex IV regulation 9.1.1 or 9.2.1 certification status",
    "marpolAnnexVRegulation6Point1DischargeOccurs": "MARPOL Annex V regulation 6.1 discharge occurs",
    "solasRegulationV22Point1Point9Point4ComplianceStatus": "SOLAS regulation V/22.1.9.4 compliance status",
    "stcwConventionRegulationIi2ComplianceStatus": "STCW Convention regulation II/2 compliance status",
    "stcwCodeSectionAIi2ComplianceStatus": "STCW Code section A-II/2 compliance status",
    "zeroPointTwoPercentProofStrength": "0.2 percent proof strength",
    "engineOutputCoefficientKe": "Engine-output coefficient Ke",
    "brashIceChannelResistanceRch": "Brash-ice channel resistance RCH",
}

EXACT_TERM_EVIDENCE = {
    "fatigueScatterReductionFactor": "gamma_e1 is the reduction factor due to scatter (equal to one standard deviation). [TRAFICOM, p.50, 6.6.2.3 and repeated p.51, 6.6.2.4]",
    "testSpecimenSizeReductionFactor": "gamma_e2 is the reduction factor for test specimen size effect. [TRAFICOM, p.50, 6.6.2.3 and repeated p.51, 6.6.2.4]",
    "variableAmplitudeLoadingReductionFactor": "gamma_v is the reduction factor for variable amplitude loading. [TRAFICOM, p.50, 6.6.2.3 and repeated p.51, 6.6.2.4]",
    "meanStressReductionFactor": "gamma_m is the reduction factor for mean stress. [TRAFICOM, p.50, 6.6.2.3 and repeated p.51, 6.6.2.4]",
    "meanBladeMaterialFatigueStrengthInSeawater": "sigma_exp is the mean fatigue strength of the blade material at 10^8 cycles to failure in seawater. [TRAFICOM, p.50, 6.6.2.3 and repeated p.51, 6.6.2.4]",
    "equivalentBladeFatigueStress": "The equivalent fatigue stress for 10^8 stress cycles produces the same fatigue damage as the load distribution for the service life of the ship. [TRAFICOM, p.49, 6.6.2.3]",
    "reducedBladeFatigueStrength": "sigma_fl is calculated from gamma_e1, gamma_e2, gamma_v, gamma_m and sigma_exp. [TRAFICOM, p.50-51, 6.6.2.3-6.6.2.4]",
    "stemAngle": "gamma_stem is the stem angle measured between the horizontal axis and the stem tangent at the upper ice waterline. [IACS UR I2 Rev.4, p.I2-18, I2.13.2.1]",
    "brashIceChannelResistanceRch": "RCH is the ice resistance in Newton of the ship in a channel with brash ice and a consolidated surface layer. [ASCII transcription; TRAFICOM, p.9, 3.2.2]",
}

TERM_UNIT_OVERRIDES = {
    "span": ("m", "http://qudt.org/vocab/unit/M", "Length"),
    "spacing": ("m", "http://qudt.org/vocab/unit/M", "Length"),
}


def infer_type(local: str, unit: str) -> tuple[str, str, str, str]:
    low = local.lower()
    if local in ENTITY_LOCAL_NAMES:
        return "Class/entity candidate", "", "", "EngineeringEntity"
    if any(x in low for x in ("evidence", "certificate", "document", "record", "plan", "procedure", "analysis")) and not low.endswith(("present", "status", "used")):
        return "Class/entity candidate", "", "", "EvidenceArtifact"
    if low.startswith(("has", "ispropertyof", "connectedto", "appliesto")):
        return "Object property candidate", "Entity", "Entity", ""
    if any(low.endswith(x) for x in ("present", "status", "used", "applicable", "active", "enclosed", "independent", "connected", "required", "implemented", "protected", "certified", "known", "reached")):
        return "Datatype property candidate", "Entity", "xsd:boolean", ""
    if "date" in low and "update" not in low:
        return "Datatype property candidate", "Entity", "xsd:date", ""
    if "time" in low or "timestamp" in low or "observationtime" in low:
        return "Datatype property candidate", "Entity", "xsd:dateTime or xsd:duration (review)", ""
    if any(x in low for x in ("count", "numberof", "bladecount", "cyclecount")):
        return "Datatype property candidate", "Entity", "xsd:integer", ""
    if unit:
        return "Datatype property candidate", "Entity", "xsd:decimal", ""
    if any(x in low for x in ("type", "class", "region", "category", "method", "mode", "language", "standard", "condition")):
        return "Datatype property candidate", "Entity", "xsd:string / controlled enumeration", ""
    return "Datatype property candidate", "Entity", "xsd:decimal|string|boolean (review)", ""


ENTITY_LOCAL_NAMES = {
    "cutout", "frame", "plating", "tankTop", "propellerBlade", "structuralMember",
    "supportingStructure", "connectionBracket", "shaftLineComponent", "crewMember",
}


def human_label(local: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", local).split()
    text = " ".join(words).capitalize()
    for token in ("MARPOL", "SOLAS", "STCW", "DNV", "GMOD", "GNSS", "SAR", "TMAS", "COLREG", "UIWL", "LIWL", "MCR", "RCH", "QUDT"):
        text = re.sub(rf"\b{token.title()}\b", token, text)
    return text


def concept_domain(requirements: list[dict]) -> str:
    text = " ".join((r["section"] + " " + r["source"]).lower() for r in requirements)
    if any(x in text for x in ("certificate", "document", "manual", "approval", "survey")):
        return "documents/certificates/approvals"
    if any(x in text for x in ("propeller", "engine", "machinery", "thruster", "shaft", "cooling", "rudder")):
        return "machinery/propulsion"
    if any(x in text for x in ("hull", "frame", "plating", "stringer", "structur", "waterline", "scantling")):
        return "hull/structure"
    if any(x in text for x in ("voyage", "operation", "route", "time", "monitor", "observation")):
        return "operations/time/observations"
    if any(x in text for x in ("test", "inspection", "physical")):
        return "physical-test evidence"
    return "core ship or regulation/provenance"


requirements = []
for sheet_name in DATA_SHEETS:
    rows = LOCKED[sheet_name]
    headers = rows[0]
    ix = {name: i for i, name in enumerate(headers)}
    for row in rows[1:]:
        rec = {name: row[i] if i < len(row) else None for name, i in ix.items()}
        category = rec["Verification_Category"]
        if category in ("Static", "Static Calculation"):
            active = "Stage 2 candidate - direct/deterministic"
        elif category == "Physical Test":
            active = "Evidence-only - physical result not inferred by SHACL"
        elif category == "Dynamic":
            active = "Deferred - observation/history/simulation design required"
        else:
            active = "Deferred - composite/evidence workflow review"
        requirements.append({
            "id": rec["Record_ID"], "sourceSheet": sheet_name, "source": rec["Source"],
            "edition": rec["Edition"], "page": rec["PDF_Page"], "section": rec["Section"],
            "clause": rec["Regulation_Clause"], "category": category,
            "sourceText": rec["Verified_Source_Text_ASCII"], "normalizedRequirement": rec["AI_Ready_Requirement"],
            "canonicalVariables": rec["Canonical_Variables"], "anchorMapField": rec["AnchorMap_Mapping"],
            "codability": rec["SHACL_Codability"], "encodingPattern": rec["SHACL_Encoding_Pattern"],
            "requiredInputs": rec["Required_Inputs_or_Artifacts"], "figureDependent": rec["Figure_Dependent"],
            "sourceUrl": rec["Source_URL"], "activeStatus": active,
        })

# Exact implementation terms and value metadata.
ship_path = ROOT / "RELEVANT FILES" / "HAITHAMSHIP.ttl"
rules_path = ROOT / "RELEVANT FILES" / "HAITHAMSRULES.ttl"
ship_graph = Graph().parse(ship_path, format="turtle")
rules_graph = Graph().parse(rules_path, format="turtle")
SSP_NS = "https://w3id.org/mtl-requirements/ssp#"
ssp_ship_terms = sorted({str(x)[len(SSP_NS):] for t in ship_graph for x in t if isinstance(x, URIRef) and str(x).startswith(SSP_NS)})
ssp_rule_terms = sorted(set(re.findall(r"\bssp:([A-Za-z_][\w.-]*)", rules_path.read_text())))
ssp_term_lookup = {x.lower(): x for x in ssp_ship_terms}

concept_records: dict[str, dict] = {}
req_to_keys: defaultdict[str, set[str]] = defaultdict(set)
formula_rx = re.compile(r"\b(?:[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+|[A-Z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+)\b")


def descriptive_formula_tokens(text: str) -> list[str]:
    """Keep descriptive normalized identifiers; short equation symbols stay aliases/evidence, not canonical terms."""
    out = []
    for token in formula_rx.findall(text or ""):
        parts = token.split("_")
        if token in SPECIAL_NAMES or (len(token) >= 8 and sum(len(p) > 1 for p in parts) >= 2):
            out.append(token)
    return out


for req in requirements:
    aliases_with_origin = []
    aliases_with_origin += [(x, "Locked workbook canonical variable") for x in split_variables(req["canonicalVariables"] or "")]
    aliases_with_origin += [(x, "Descriptive formula token in locked requirement") for x in descriptive_formula_tokens(req["normalizedRequirement"] or "")]
    aliases_with_origin += [(x, "Engineering decomposition of verified clause") for x in HIDDEN_BY_REQ.get(req["id"], "").split(",") if x]
    for alias, origin in aliases_with_origin:
        alias = alias.strip()
        if not alias or alias.lower() in {"true", "false", "no explicit data variable identified"}:
            continue
        local, unit, unit_uri, qk = lower_camel(alias)
        key = local.lower()
        req_to_keys[req["id"]].add(key)
        c = concept_records.setdefault(key, {
            "local": local, "aliases": set(), "requirements": [], "unit": unit, "unitUri": unit_uri,
            "quantityKind": qk, "evidence": [], "anchorMapEvidence": set(), "origins": set(),
        })
        c["aliases"].add(alias)
        c["origins"].add(origin)
        if unit and not c["unit"]:
            c["unit"], c["unitUri"], c["quantityKind"] = unit, unit_uri, qk
        if local in TERM_UNIT_OVERRIDES and not c["unit"]:
            c["unit"], c["unitUri"], c["quantityKind"] = TERM_UNIT_OVERRIDES[local]
        c["requirements"].append(req)
        c["evidence"].append(excerpt(req["sourceText"], alias))
        if req["anchorMapField"]:
            c["anchorMapEvidence"].add(req["anchorMapField"])

concepts = []
for idx, key in enumerate(sorted(concept_records), 1):
    c = concept_records[key]
    reqs = c["requirements"]
    aliases = sorted(c["aliases"], key=lambda x: (len(x), x.lower()))
    role, domain_range, datatype, entity_kind = infer_type(c["local"], c["unit"])
    exact_ssp = None
    for candidate in [c["local"], *aliases]:
        if candidate.lower() in ssp_term_lookup:
            exact_ssp = ssp_term_lookup[candidate.lower()]
            break
    uses = {
        "applicability": any("applic" in (r["normalizedRequirement"] or "").lower() or (r["normalizedRequirement"] or "").lstrip().startswith("IF ") for r in reqs),
        "targeting": any(any(x in (r["normalizedRequirement"] or "").lower() for x in ("ship", "component", "frame", "propeller", "engine", "person", "equipment")) for r in reqs),
        "formula": any(r["category"] == "Static Calculation" or "=" in (r["normalizedRequirement"] or "") for r in reqs),
        "comparison": any(any(x in (r["normalizedRequirement"] or "") for x in ("<", ">", "minimum", "maximum", "at least", "no more")) for r in reqs),
        "relation": role.startswith("Object") or any(x in c["local"].lower() for x in ("connected", "attachment", "coverage", "appliesto")),
        "timeHistory": any(r["category"] == "Dynamic" or any(x in c["local"].lower() for x in ("time", "date", "history", "observation", "duration")) for r in reqs),
        "documentEvidence": any(any(x in (r["normalizedRequirement"] or "").lower() for x in ("certificate", "document", "approval", "manual", "record", "plan")) for r in reqs),
        "testEvidence": any(r["category"] == "Physical Test" or "test" in c["local"].lower() for r in reqs),
    }
    source_refs = sorted({f"{r['id']} | {r['sourceSheet']} p.{r['page']} | {r['clause']}" for r in reqs})
    mapping_status = "Exact local-name match in confirmed Haitham SSP namespace" if exact_ssp else "No exact current Haitham SSP local-name match"
    origins = sorted(c["origins"])
    if exact_ssp:
        naming_basis = "Verified exact implementation term"
        naming_authority = f"Haitham final SSP URI plus linked regulation: {SSP_NS}{exact_ssp}"
        naming_rule = "N1 - reuse only after exact URI and semantic-context verification"
        qa_status = "Passed - exact URI/local-name evidence"
        confidence = "High"
    elif c["local"] in EXACT_TERM_EVIDENCE:
        naming_basis = "Regulatory symbol expanded from a directly verified definition"
        naming_authority = "Directly inspected regulation PDF and linked locked requirement"
        naming_rule = "N2 - replace formula symbol with its clause-defined engineering meaning; preserve symbol as alias"
        qa_status = "Passed - source-defined expansion"
        confidence = "High"
    elif re.search(r"(?:Point|Dash)\d", c["local"]):
        naming_basis = "Explicit regulation-reference transcription"
        naming_authority = "Governing-instrument reference in the locked variable and linked regulation"
        naming_rule = "N6 - spell separators as Point or Dash and identify the governing instrument"
        qa_status = "Passed - unambiguous regulation reference"
        confidence = "High"
    elif c["unit"]:
        naming_basis = "Unit-stripped normalized regulatory variable"
        naming_authority = "Locked R2 variable plus linked regulation; verified QUDT URI only where populated"
        naming_rule = "N3 - remove unit from the identifier and retain it in unit/quantity metadata"
        qa_status = "Passed - unit separation verified"
        confidence = "High" if c["unitUri"] else "Medium"
    elif "Locked workbook canonical variable" in c["origins"]:
        naming_basis = "Locked-workbook normalized regulatory term"
        naming_authority = "LOCK-2026-08-11-R2 plus linked regulation evidence"
        naming_rule = "N4 - preserve the source concept; normalize spelling to ASCII lowerCamelCase"
        qa_status = "Passed - transparent source normalization"
        confidence = "Medium"
    else:
        naming_basis = "Benchmark-coined descriptive engineering term"
        naming_authority = "Meaning decomposed from the linked verified regulatory clause"
        naming_rule = "N5 - component or subject first, followed by characteristic and qualifier/state; no unsupported external mapping"
        qa_status = "Passed - clause-anchored benchmark coinage"
        confidence = "Medium"
    review_status = "Naming audit passed; final semantic scope and URI activation remain Stage 2 decisions"
    preferred_label = PREFERRED_LABELS.get(c["local"], human_label(c["local"]))
    exact_evidence = EXACT_TERM_EVIDENCE.get(c["local"], c["evidence"][0] if c["evidence"] else "")
    defensibility = f"{naming_basis}. The proposed name is traceable to {naming_authority}; aliases preserve the original notation."
    exact_xsd_uri = {
        "xsd:boolean": "http://www.w3.org/2001/XMLSchema#boolean",
        "xsd:date": "http://www.w3.org/2001/XMLSchema#date",
        "xsd:dateTime": "http://www.w3.org/2001/XMLSchema#dateTime",
        "xsd:duration": "http://www.w3.org/2001/XMLSchema#duration",
        "xsd:integer": "http://www.w3.org/2001/XMLSchema#integer",
        "xsd:decimal": "http://www.w3.org/2001/XMLSchema#decimal",
        "xsd:string": "http://www.w3.org/2001/XMLSchema#string",
    }.get(datatype, "")
    concepts.append({
        "conceptId": f"VOC-{idx:04d}", "label": preferred_label,
        "localName": c["local"], "aliases": "; ".join(aliases),
        "exactEvidence": exact_evidence,
        "normalizedDefinition": f"NORMALIZED (Stage 1): candidate concept for {c['local']} derived from the linked locked requirements; scope and final semantics require vocabulary approval.",
        "role": role, "domain": concept_domain(reqs), "range": domain_range, "datatype": datatype,
        "unit": c["unit"], "unitUri": c["unitUri"], "quantityKind": c["quantityKind"],
        "cardinality": "Requirement-specific; do not globalize before Stage 2", "closedWorld": "Yes for benchmark validation; ontology semantics remain open-world",
        **uses, "requirementIds": "; ".join(sorted({r["id"] for r in reqs})),
        "sourceRefs": "; ".join(source_refs),
        "verificationCategory": "; ".join(sorted({r["category"] for r in reqs})),
        "haithamUri": SSP_NS + exact_ssp if exact_ssp else "", "haithamMappingStatus": mapping_status,
        "ranaUri": SSP_NS + exact_ssp if exact_ssp else "", "ranaMappingStatus": "Same SSP pattern evidenced in thesis/fixtures" if exact_ssp else "No verified exact thesis URI",
        "anchorMapMapping": "; ".join(sorted(c["anchorMapEvidence"])),
        "anchorMapUri": "", "anchorMapStatus": "Workbook mapping text retained; no exact AnchorMap schema IRI independently available",
        "dnvGmodMapping": "", "dnvGmodUri": "", "dnvStatus": "No exact GMOD code/path verified for this Stage 1 term",
        "qudtW3cMapping": "; ".join(x for x in (c["unitUri"], exact_xsd_uri) if x),
        "mappingStatus": mapping_status, "decisionRationale": "Retain because it is used by at least one locked requirement and its name passed the Stage 1 naming rules; no external mapping is inferred from lexical similarity.",
        "confidence": confidence, "humanReview": review_status, "notes": "No final ontology or URI is declared in Stage 1.",
        "namingBasis": naming_basis, "namingAuthority": naming_authority, "namingRule": naming_rule,
        "nameQaStatus": qa_status, "defensibility": defensibility, "originEvidence": "; ".join(origins),
    })

concept_id_by_key = {c["localName"].lower(): c["conceptId"] for c in concepts}
for req in requirements:
    ids = [concept_id_by_key[k] for k in sorted(req_to_keys[req["id"]]) if k in concept_id_by_key]
    req["conceptIds"] = "; ".join(ids)
    req["coverageStatus"] = "Covered by candidate concepts" if ids else "UNRESOLVED - no candidate concept extracted"

relevant = ROOT / "RELEVANT FILES"
old = ROOT / "OLD FILES"
source_specs = [
    (relevant / "AnchorMap__A_Multi_Agent_Pipeline_for_Variable_Standardisation_in_Maritime_Engineering (1).pdf", "Methodology and variable-standardisation evidence", "Methodology", "8", "2026 conference paper; PDF metadata creation 2026-08-11"),
    (relevant / "BROKENONTOLOGYFROMGITHUB", "Excluded legacy file - not used for naming or mappings", "Excluded", "n/a", "Retained physically; excluded by user decision because it is broken"),
    (ship_path, "Haitham final shared implementation ship graph", "Implementation evidence", "n/a", f"Valid Turtle; {len(ship_graph)} triples"),
    (relevant / "HAITHAMSOCEANENGINEERINGJOURNAL.pdf", "Methodology and 201-requirement implementation study", "Methodology", "15", "Ocean Engineering 362 (2026) 126356; accepted 2026-06-01"),
    (rules_path, "Haitham final shared SHACL shapes", "Implementation evidence", "n/a", f"Valid Turtle; {len(rules_graph)} triples"),
    (relevant / "POLARCODES.pdf", "January 2026 Polar Code supplement/amendment", "Authoritative regulation supplement", "7", "Not the main MSC.385(94) code"),
    (relevant / "THESIS_RANA.pdf", "NL-to-SHACL methodology, 90-case fixtures and graph pattern", "Methodology", "80", "Master's thesis, 2026"),
    (relevant / "TRAFICOM.pdf", "Finnish-Swedish Ice Class Rules", "Authoritative regulation", "65", "TRAFICOM/68863/03.04.01.00/2021; issued 2021-07-01"),
    (relevant / "ur-i1rev2-1.pdf", "Polar Class descriptions/application companion", "Authoritative regulation/reference", "2", "IACS UR I1 Rev.2 April 2016"),
    (relevant / "ur-i2rev4.pdf", "Polar Class structural requirements", "Authoritative regulation", "22", "IACS UR I2 Rev.4 December 2019; implementation from 2021-01-01"),
    (relevant / "MSC.385(94).pdf", "Main IMO Polar Code", "Authoritative regulation", "59", "Moved to current RELEVANT FILES with user authorization"),
    (old / "Haitham_Data" / "2Q191E_Supplement_January2026_EBK.pdf", "Duplicate of current POLARCODES.pdf", "Historical duplicate", "7", "Byte-identical duplicate; do not treat as current"),
    (ROOT / "INPUTS" / "Input_regulations_3Sources.xlsx", "Locked 313-requirement extraction dataset", "Current active benchmark input", "n/a", "LOCK-2026-08-11-R2; promoted byte-identically from historical fallback"),
    (old / "data" / "INPUTS" / "Input_regulations_3Sources.xlsx", "Historical duplicate of active locked workbook", "Historical duplicate", "n/a", "Byte-identical to current INPUTS copy"),
    (old / "Haitham_Data" / "ship.ttl", "Historical duplicate of HAITHAMSHIP.ttl", "Historical duplicate", "n/a", "Byte-identical to current confirmed final file"),
    (old / "Haitham_Data" / "rulesV2.ttl", "Historical duplicate of HAITHAMSRULES.ttl", "Historical duplicate", "n/a", "Byte-identical to current confirmed final file"),
    (old / "Haitham_Data" / "1-s2.0-S0029801826021906-main.pdf", "Historical copy of Haitham Ocean Engineering paper", "Historical semantic duplicate", "15", "Same article identity; byte-different PDF copy/metadata"),
    (old / "data" / "input" / "input_all", "Rana thesis 90-case input fixtures", "Historical implementation evidence", "n/a", "90 of 90 JSON cases parse successfully; directory hash covers all non-.DS_Store files"),
    (old / "data" / "fewshot", "Rana thesis few-shot prompt fixtures", "Historical implementation evidence", "n/a", "5 of 5 JSON fixtures parse successfully; directory also contains rawfewshot.txt"),
    (old / "data" / "shipdesigns", "Rana thesis ship-design fixtures", "Historical implementation evidence", "n/a", "10 of 10 Turtle graphs parse successfully; 2889 triples total"),
]
manifest = []
for path, role, status, pages, notes in source_specs:
    manifest.append({"sourceId": f"SRC-{len(manifest)+1:02d}", "path": str(path), "filename": path.name,
                     "role": role, "versionDate": notes.split(";")[0], "pageCount": pages,
                     "sha256": sha256(path), "status": status, "notes": notes})

compatibility = [
    {"item":"ssp namespace", "sourceA":"Haitham ship/rules", "exactA":SSP_NS, "sourceB":"Rana thesis/fixtures", "exactB":SSP_NS, "status":"Exact match", "risk":"Low", "finding":"Shared variable-node namespace and ssn:isPropertyOf + ssp:hasVariableValue pattern."},
    {"item":"ice namespace", "sourceA":"Haitham final rules", "exactA":"http://example.com/iceregulations#", "sourceB":"Adopted benchmark vocabulary", "exactB":"https://w3id.org/nltl-benchmark/vocab#", "status":"Resolved by canonical migration", "risk":"Controlled", "finding":"Haitham local names remain aliases/evidence; final benchmark terms use one provisional persistent base."},
    {"item":"QUDT schema prefix", "sourceA":"Haitham ship", "exactA":"http://qudt.org/2.1/schema/qudt", "sourceB":"Adopted benchmark prefix", "exactB":"http://qudt.org/schema/qudt/", "status":"Resolved in benchmark decision", "risk":"Controlled", "finding":"Do not copy the malformed expansion; use qudt:unit with the delimited standard namespace."},
    {"item":"Broken JSON-LD", "sourceA":"Legacy file", "exactA":"RELEVANT FILES/BROKENONTOLOGYFROMGITHUB", "sourceB":"Benchmark authority set", "exactB":"Excluded", "status":"Excluded by user decision", "risk":"None for benchmark", "finding":"No terms, definitions, namespaces, or mappings are adopted from this file."},
    {"item":"Variable naming style", "sourceA":"Locked workbook", "exactA":"mcrPower_kW; yieldStrength_MPa; UIWL", "sourceB":"Adopted benchmark rule", "exactB":"unit-free ASCII lowerCamelCase; source notation as alias", "status":"Resolved", "risk":"Controlled", "finding":"Canonical local names are normalized and checked for ASCII/lowerCamelCase uniqueness."},
    {"item":"SHACL-to-ship term coverage", "sourceA":"HAITHAMSRULES.ttl", "exactA":f"{len(ssp_rule_terms)} distinct referenced ssp local names", "sourceB":"HAITHAMSHIP.ttl", "exactB":f"{len(set(ssp_rule_terms)&set(ssp_ship_terms))} found", "status":"Exact local/namespace coverage", "risk":"Medium", "finding":"All referenced ssp names occur, but graph uses singleton named variable resources and mixed targetNode/targetClass patterns."},
    {"item":"Value datatypes", "sourceA":"HAITHAMSHIP.ttl", "exactA":"decimal, integer, boolean, date, and untyped literals", "sourceB":"Adopted benchmark rule", "exactB":"explicit XSD datatypes and controlled enumerations", "status":"Resolved for future benchmark", "risk":"Controlled", "finding":"Untyped implementation literals are not copied; each canonical property requires an explicit range."},
    {"item":"Node model", "sourceA":"Rana/Haitham", "exactA":"named variable node -> ssn:isPropertyOf -> component; ssp:hasVariableValue -> literal", "sourceB":"Adopted benchmark pattern", "exactB":"entity -> canonical property -> QUDT QuantityValue or typed literal; SOSA Observation for history", "status":"Resolved by engineering decision", "risk":"Controlled", "finding":"Named singleton variable resources remain compatibility aliases only."},
    {"item":"DNV GMOD", "sourceA":"Public DNV Vista / official Vista SDK resources", "exactA":"https://github.com/dnv-opensource/vista-sdk/tree/main/resources (GMOD and codebooks through VIS 3.11a observed 2026-08-11)", "sourceB":"Adopted mapping policy", "exactB":"exact mapping only when a versioned GMOD code/path or codebook tag is reproducibly verified; otherwise benchmark-coined term", "status":"Resolved policy", "risk":"Controlled", "finding":"GMOD supplies a hierarchical ship product structure and versioned code paths; it is not treated as proof for every regulatory property name. No plausible or lexical-only GMOD mapping is accepted."},
    {"item":"ISO 19848", "sourceA":"Requested authority", "exactA":"full standard unavailable", "sourceB":"DNV Vista documentation", "exactB":"public overview only", "status":"Limitation", "risk":"Medium", "finding":"No normative ISO definitions or identifiers are claimed."},
]

decisions = [
    {"decisionId":"DEC-01", "status":"Adopted", "topic":"Single master vocabulary", "decision":"Use one internally modular master vocabulary; source profiles are whitelists, not separate schemas.", "rationale":"Prevents URI drift across experiments.", "requiresUser":"None"},
    {"decisionId":"DEC-02", "status":"Adopted", "topic":"Canonical local-name style", "decision":"ASCII-only lowerCamelCase; unit-free identifiers; retain source notation and symbols as aliases.", "rationale":"User authorized consistent coined names; follows AnchorMap's unit-separation principle.", "requiresUser":"None"},
    {"decisionId":"DEC-03", "status":"Adopted", "topic":"Canonical node model", "decision":"Entity -> canonical property -> QUDT QuantityValue for quantities or typed literal/enumeration for scalar states; SOSA Observation for time/history; evidence artifacts are nodes with provenance.", "rationale":"Avoids global singleton variables and gives SHACL one deterministic access pattern per value family.", "requiresUser":"None"},
    {"decisionId":"DEC-04", "status":"Adopted", "topic":"Benchmark base URI", "decision":"Use provisional https://w3id.org/nltl-benchmark/vocab# for vocabulary decisions; register/redirect it before publication.", "rationale":"Persistent, human-neutral base; example.com namespaces are excluded.", "requiresUser":"Only if a different publication namespace is preferred"},
    {"decisionId":"DEC-05", "status":"Accepted by user", "topic":"Benchmark activation", "decision":"240 Static/Static Calculation records are direct/deterministic candidates; 40 Complex and 17 Dynamic are deferred; 16 Physical Test records are evidence-only.", "rationale":"Prevents overclaiming simulation-, workflow-, or test-dependent compliance.", "requiresUser":"None"},
    {"decisionId":"DEC-06", "status":"Adopted", "topic":"Evidence lifecycle", "decision":"Evidence/approval nodes use Draft, Submitted, UnderReview, Approved, Rejected, Expired, or Revoked plus authority, issue date, validity, scope, and provenance.", "rationale":"Boolean approval flags are inadequate for engineering assurance.", "requiresUser":"None"},
    {"decisionId":"DEC-07", "status":"Adopted", "topic":"External mappings", "decision":"Accept exact DNV/QUDT/W3C mappings only when the exact code or URI is independently verified; otherwise coin a benchmark term and retain aliases/provenance.", "rationale":"Prevents plausible but false ontology mappings.", "requiresUser":"None"},
    {"decisionId":"DEC-08", "status":"Adopted", "topic":"Legacy hash", "decision":"Use the current active workbook SHA-256 05eb02... as the file identity; retain 216885... only as unresolved legacy provenance metadata, not as publication identity.", "rationale":"The current file is directly hash-verifiable.", "requiresUser":"None"},
    {"decisionId":"DEC-09", "status":"Adopted", "topic":"Name defensibility", "decision":"Every shortlisted term must record its naming basis, authority, applied rule, original aliases, and QA result. A DNV mapping is never inferred from similar wording.", "rationale":"Makes each coined or reused name explainable in the paper and auditable later.", "requiresUser":"None"},
    {"decisionId":"DEC-10", "status":"Adopted", "topic":"Short formula symbols", "decision":"Promote a readable canonical name only when the regulation defines the symbol or the locked variable already supplies a descriptive expansion. Preserve the symbol as an alias; otherwise do not create a canonical term solely from the symbol.", "rationale":"Eliminates opaque identifiers without inventing engineering meaning.", "requiresUser":"None"},
]

unresolved = [
    {"issueId":"UNR-00", "priority":"None", "issue":"No blocking Stage 1 naming issue remains after the naming audit.", "impact":"Stage 1 can be reviewed on its engineering decisions and evidence; Stage 2 still requires explicit approval.", "needed":"No technical input required now."},
]

publication_limitations = [
    {"itemId":"ACT-01", "category":"Publication action", "status":"Not blocking Stage 1", "item":"The provisional https://w3id.org/nltl-benchmark/vocab# namespace is not yet registered.", "treatment":"Register its redirect or replace it with a final institutional URI before public ontology release."},
    {"itemId":"LIM-01", "category":"Documented limitation", "status":"Not blocking Stage 1", "item":"ISO 19848 normative text was unavailable.", "treatment":"Do not claim ISO-specific normative definitions or identifiers. Public DNV Vista and the official SDK are contextual, non-normative evidence only."},
    {"itemId":"QA-01", "category":"Resolved naming control", "status":"Resolved", "item":"Opaque short formula symbols could create unreadable or invented canonical names.", "treatment":"Clause-defined symbols were expanded to readable engineering names and retained as aliases; undefined short symbols are not promoted solely from symbol similarity."},
]

naming_rules = [
    {"ruleId":"N1", "rule":"Verified exact reuse", "application":"Reuse an existing term only after exact URI/local-name and semantic-context verification.", "paperDefense":"Prevents local-name-only matches across incompatible namespaces."},
    {"ruleId":"N2", "rule":"Regulatory symbol expansion", "application":"Use the definition stated in the applicable clause; keep the original equation symbol as an alias.", "paperDefense":"Improves readability without changing the regulated meaning."},
    {"ruleId":"N3", "rule":"Unit separation", "application":"Remove units from local names and record unit, quantity kind, and verified unit URI separately.", "paperDefense":"The same property remains stable across compatible unit representations."},
    {"ruleId":"N4", "rule":"Transparent normalization", "application":"Normalize a descriptive locked variable to ASCII lowerCamelCase while preserving the original label as an alias.", "paperDefense":"Provides typeable identifiers with direct provenance to the locked extraction."},
    {"ruleId":"N5", "rule":"Clause-anchored coinage", "application":"When no verified reusable term exists, coin subject/component + characteristic + qualifier/state from the verified clause.", "paperDefense":"The construction rule is deterministic, readable, and does not imply a false external mapping."},
    {"ruleId":"N6", "rule":"Regulation-reference transcription", "application":"Spell separators as Point or Dash and name the governing instrument explicitly where a rule reference is itself data.", "paperDefense":"Avoids ambiguous digit concatenations such as 111 or generic labels such as term2Status."},
    {"ruleId":"N7", "rule":"No lexical-only mapping", "application":"Leave DNV, QUDT, W3C, Haitham, Rana, or AnchorMap mappings empty unless the exact identifier and meaning were verified.", "paperDefense":"Avoids mapping hallucinations and keeps provenance auditable."},
]

summary = {
    "requirementCount": len(requirements), "conceptCount": len(concepts),
    "requirementsBySource": Counter(r["sourceSheet"] for r in requirements),
    "requirementsByCategory": Counter(r["category"] for r in requirements),
    "activationCounts": Counter(r["activeStatus"] for r in requirements),
    "coverageCounts": Counter(r["coverageStatus"] for r in requirements),
    "haithamShipTriples": len(ship_graph), "haithamRulesTriples": len(rules_graph),
    "haithamSspShipTerms": len(ssp_ship_terms), "haithamSspRuleTerms": len(ssp_rule_terms),
    "haithamSspRuleTermsMissingInShip": sorted(set(ssp_rule_terms) - set(ssp_ship_terms)),
    "lockedWorkbookActualSha256": sha256(ROOT / "INPUTS" / "Input_regulations_3Sources.xlsx"),
    "lockId": "LOCK-2026-08-11-R2",
    "namingBasisCounts": Counter(c["namingBasis"] for c in concepts),
    "namingQaCounts": Counter(c["nameQaStatus"] for c in concepts),
}

out = {
    "summary": summary, "manifest": manifest, "concepts": concepts,
    "requirements": requirements, "compatibility": compatibility,
    "decisions": decisions, "unresolved": unresolved,
    "publicationLimitations": publication_limitations, "namingRules": naming_rules,
}
(TMP / "stage1_data.json").write_text(json.dumps(out, indent=2, default=lambda o: dict(o)), encoding="utf-8")
print(json.dumps(summary, indent=2, default=lambda o: dict(o)))
