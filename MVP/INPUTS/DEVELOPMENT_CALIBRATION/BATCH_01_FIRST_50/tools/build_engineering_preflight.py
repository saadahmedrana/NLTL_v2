from __future__ import annotations

import csv
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BATCH_ROOT = HERE.parent
PROJECT_ROOT = BATCH_ROOT.parents[2]
REGISTRY = PROJECT_ROOT / "BENCHMARK_VOCABULARY/STAGE2_R2/registry/term_registry.json"
BATCH = BATCH_ROOT / "batch_definition.json"


# This is an engineering preflight, not a final R3 vocabulary declaration.
# Names in draft_new_terms remain proposals until role/range/unit/source review.
REVIEWS = {
    "TRF-001": ("NEW_TERMS", "constructionContractDate", "applicableIceClassRegulationEdition; iceClassRegulationEdition2021", "R2 index omits the date and has no controlled regulation-edition model.", "cutoff-1 day non-applicable; cutoff date pass; wrong edition fail"),
    "TRF-002": ("NEW_TERMS", "constructionContractDate", "applicableIceClassRegulationEdition; iceClassRegulationEdition2017", "Date exists but edition/value does not.", "lower boundary pass; upper boundary non-applicable; wrong edition fail"),
    "TRF-003": ("NEW_TERMS", "constructionContractDate", "applicableIceClassRegulationEdition; iceClassRegulationEdition2010", "Date exists but edition/value does not.", "both date boundaries plus wrong edition"),
    "TRF-004": ("NEW_TERMS", "constructionContractDate", "applicableIceClassRegulationEdition; iceClassRegulationEdition2008", "Date exists but edition/value does not.", "both date boundaries plus wrong edition"),
    "TRF-005": ("NEW_TERMS", "constructionContractDate; constructionStageDate", "applicableIceClassRegulationEdition; iceClassRegulationEdition2002", "Construction-stage date is the benchmark representation of keel laid/similar stage; edition model is absent.", "stage-date boundary, contract-date boundary, wrong edition"),
    "TRF-006": ("NEW_TERMS", "constructionStageDate", "applicableIceClassRegulationEdition; engineOutputRegulationEdition; iceClassRuleEdition1985; iceClassRegulationEdition2008", "Separate whole-ship rule edition from the optional owner-selected engine-output edition.", "1985 applicability pass/fail and optional 2008 engine-output branch"),
    "TRF-007": ("NEW_TERMS", "iceClass; constructionStageDate", "deliveryDate; assessmentDate; engineOutputComplianceMethod; traficom2017Section3Point2Point2Method; traficom2017Section3Point2Point4Method", "Same obligation is repeated in 1.7 as TRF-009; share vocabulary and fixtures but preserve IDs.", "before deadline, at deadline compliant, at deadline missing method"),
    "TRF-009": ("SEMANTIC_DUPLICATE", "iceClass; constructionStageDate", "deliveryDate; assessmentDate; engineOutputComplianceMethod; traficom2017Section3Point2Point2Method; traficom2017Section3Point2Point4Method", "Exact repeated obligation from clause 1.7; do not create incompatible duplicate terms.", "reuse TRF-007 fixture facts under separate requirement mapping"),
    "TRF-010": ("READY_AFTER_INDEX_CHECK", "iceClass", "", "Controlled ice-class individuals already exist in locked ontology infrastructure.", "each allowed class; invalid external value; missing value"),
    "TRF-011": ("REMODEL", "", "iceWaterline; waterlineProfilePoint; hasUpperIceWaterline; hasIntendedIceOperatingWaterline; hasWaterlineProfilePoint; longitudinalPosition; verticalCoordinate", "R2 upperIceWaterline is xsd:string and cannot verify an envelope of highest operating-waterline points.", "valid envelope, point below required maximum, missing profile"),
    "TRF-012": ("REMODEL", "", "iceWaterline; waterlineProfilePoint; hasLowerIceWaterline; hasIntendedIceOperatingWaterline; hasWaterlineProfilePoint; longitudinalPosition; verticalCoordinate", "R2 lowerIceWaterline is xsd:string and cannot verify an envelope of lowest operating-waterline points.", "valid envelope, point above required minimum, missing profile"),
    "TRF-013": ("NEW_TERMS", "shipIceStrengthened", "hasUpperIceWaterline; hasLowerIceWaterline; draughtAtForePerpendicular; draughtAtAftPerpendicular; operatingForeDraught; operatingAftDraught", "Use draught quantities on typed waterline nodes; string UIWL/LIWL is insufficient.", "inside both bounds, below lower, above upper"),
    "TRF-014": ("NEW_TERMS", "constructionDate; upperIceWaterlineDraught", "iceDraughtRestrictionDocument; classCertificate; retainedOnBoard; readilyAvailableToMaster; maximumIceClassDraughtFore; minimumIceClassDraughtFore; maximumIceClassDraughtAmidships; minimumIceClassDraughtAmidships; maximumIceClassDraughtAft; minimumIceClassDraughtAft; summerLoadLineFreshWaterDraught; warningTrianglePresent; iceClassDraughtMarkPresent; firstScheduledDryDockingDate", "Compound document/marking requirement needs distinct evidence and draught fields; do not collapse into one compliance boolean.", "document evidence, certificate content, post-2007 marking, legacy docking deadline"),
    "TRF-015": ("NEW_TERMS", "upperIceWaterlineDraught", "operatingDraught; operatingTrim; maximumPermittedIceTrim; intendedRouteSeaWaterSalinity; loadingCalculationSeaWaterSalinity", "Salinity-accounted loading is represented by comparing recorded route and calculation salinity rather than an answer-status flag.", "draught/trim within limit; exceeded limit; salinity mismatch"),
    "TRF-016": ("REMODEL", "draughtAmidships; forwardDraught; levelIceThickness; propellerHighestPointSubmerged; freezingPreventionPresent", "ballastTank; hasBallastTank; situatedAboveLowerIceWaterline; usedToReachLowerIceWaterline; hasUpperIceWaterline; waterlineDisplacement", "Existing single displacement property cannot select the greatest-displacement UIWL; ballast conditions need a target node.", "all clauses pass; exact formula boundary; low draught; missing freeze protection"),
    "TRF-017": ("NEW_TERMS", "maximumContinuousRatingPower", "propulsionMachineryContinuousOutput; propulsionOutputRestrictionApplies; restrictedPropulsionOutput; additionalPropulsionPower", "Engine output is a derived total/selected value, not merely presence of MCR.", "unrestricted total; restricted output; additional source included; incorrect total"),
    "TRF-018": ("READY_AFTER_INDEX_CHECK", "iceClass; maximumContinuousRatingPower; calculatedRequiredPower", "", "Indexed operands and canonical kW power model are sufficient.", "IA/IB/IC 1000-kW floor; IA Super 2800-kW floor; calculated requirement higher than floor"),
    "TRF-020": ("INDEX_AND_NEW_TERMS", "constructionStageDate; iceClass; maximumContinuousRatingPower; engineOutputCoefficientKe; brashIceChannelResistanceRch; propellerDiameter; propellerCount; propellerType; upperIceWaterline; lowerIceWaterline", "propulsionSystemType; conventionalPropulsionSystem; fixedPitchPropeller; controllablePitchPropeller", "Ke lookup needs propeller count and propulsion/propeller type; draught-dependent inputs must be attached to typed waterline calculation cases.", "Ke table rows, UIWL/LIWL maximum, construction cutoff, power shortfall"),
    "TRF-022": ("INDEX_AND_NEW_TERMS", "coefficientC3; coefficientC4; coefficientC5; coefficientF1; coefficientF2; coefficientF3; coefficientF4; coefficientG1; coefficientG2; coefficientG3; bowRakeAtQuarterBreadth; flareAngle; clampedHullGeometryTerm; shipLength; shipBreadth; iceClassDraught", "waterlineAngleAtQuarterBreadth", "R2 index only carries two angles; constants, geometry and coefficient-table values already exist but are not linked.", "angle calculation, exact clamp 5/20, below/above clamp, wrong constant"),
    "TRF-023": ("NEW_TERMS", "iceClass; maximumContinuousRatingPower", "applicableIceClassRegulationEdition; iceClassRuleEdition1985; requiredPowerUnder1985Rules", "Referenced 1985 minimum must be represented as an input/evidence value; no threshold is invented from the 2021 text.", "IB/IC legacy applicability, exact minimum, below minimum"),
    "TRF-024": ("NEW_TERMS", "iceClass; constructionStageDate", "deliveryDate; assessmentDate; engineOutputComplianceMethod; traficom2017Section3Point2Point2Method; traficom2017Section3Point2Point4Method", "Same deadline model as TRF-007/009.", "before deadline, at deadline valid method, missing method"),
    "TRF-025": ("INDEX_AND_NEW_TERMS", "iceClass; shipBreadth; shipLength; iceClassDraught; coefficientF1; coefficientF2; coefficientF3; coefficientF4; coefficientG1; coefficientG2; coefficientG3; bulbousBowPresent", "brashIceResistanceCoefficientC1; brashIceResistanceCoefficientC2", "Formula outputs C1/C2 are missing; all existing operands must be linked.", "IA Super no bulb exact formulas and perturbed C1/C2"),
    "TRF-026": ("INDEX_AND_NEW_TERMS", "iceClass; shipBreadth; shipLength; iceClassDraught; coefficientF1; coefficientF2; coefficientF3; coefficientF4; coefficientG1; coefficientG2; coefficientG3; bulbousBowPresent", "brashIceResistanceCoefficientC1; brashIceResistanceCoefficientC2", "Reuse TRF-025 outputs with bulb-specific constants; do not coin duplicate outputs.", "IA Super bulb exact formulas and perturbed C1/C2"),
    "TRF-027": ("INDEX_AND_UNIT_REVIEW", "coefficientC3; coefficientC4; coefficientC5; coefficientF1; coefficientF2; coefficientF3; coefficientF4; coefficientG1; coefficientG2; coefficientG3; clampedHullGeometryTerm; shipLength; shipBreadth; iceClassDraught", "", "Terms exist; verify coefficient quantity dimensions and Table 3-3 lookup provenance.", "exact constants, clamp 5/20, out-of-range raw geometry"),
    "TRF-030": ("NEW_TERMS", "upperIceWaterline; lowerIceWaterline; spacing; span; loadPatchApplicationLocation; loadPatchHeight; loadPatchLength", "directAnalysisCase; hasDirectAnalysisCase; appliedIcePressure; verticalLoadPosition; horizontalLoadPosition; combinedBendingShearCapacity; loadLengthDeterminedFromArrangement; loadLengthCoefficientCa", "Need repeatable analysis-case nodes; a single string location cannot prove several required positions and load lengths.", "complete location set, missing UIWL case, wrong 1.8p pressure, missing la exploration"),
    "TRF-031": ("READY_AFTER_INDEX_CHECK", "combinedBendingShearStress; yieldPoint; vonMisesYieldCriterion; beamTheoryUsed; allowableShearStress", "yieldShearStress", "tau_y=sigma_y/sqrt(3) should be explicit or calculated; current terms otherwise cover the rule.", "stress just below/at yield and shear 0.9 boundary"),
    "TRF-032": ("REMODEL_UNIT", "iceStrengtheningStatus", "classificationSocietyRequiredScantling; regulationRequiredScantling; selectedDesignScantling", "R2 scantling properties are strings and cannot implement the required numeric maximum.", "regulation governs; class governs; selected below maximum"),
    "TRF-034": ("EVIDENCE_MODEL", "sectionModulus; shearArea", "effectiveMemberCrossSection; memberNormalToPlating; classificationSocietySectionPropertyCalculationEvidence", "The clause defines the basis of section properties; non-normal members require traceable classification-society calculation evidence.", "normal member values; non-normal with evidence; non-normal missing evidence"),
    "TRF-035": ("NEW_TERMS", "ruleLength; classificationSociety", "classificationSocietyRuleLength", "Compare recorded L with the classification society's rule length instead of only requiring L.", "equal length and mismatch"),
    "TRF-036": ("TABLE_MODEL", "iceClass; levelIceThickness; designIceLoadHeight", "iceClassDesignParameterSet", "Table 4-1 row provenance/controlled mapping is needed to distinguish looked-up hi and h from arbitrary values.", "each ice-class row, wrong h, wrong hi"),
    "TRF-037": ("INDEX_AND_NEW_TERMS", "icePressure; nominalIcePressureP0; maximumContinuousRatingPower; shipLength", "shipSizeEngineOutputFactorCd; iceClassFactorCp; iceLoadAreaFactorCa; coefficientA; coefficientB; coefficientK", "R2 links only MCR although every factor and both equations must be available; cd has maximum 1.", "exact p, cd cap at 1, incorrect factor/product"),
    "TRF-041": ("INDEX_AND_UNIT_REVIEW", "thickness; spacing; coefficientF1; coefficientF2; icePressure; yieldStrength; corrosionAbrasionAddition", "platingFramingOrientation; transverseFraming; longitudinalFraming; platingPressure", "Generic thickness is recommended in metres while formula result is millimetres; shear/plating terms need formula-native unit alignment.", "both framing branches, exact formula boundary, low thickness"),
    "TRF-042": ("INDEX_AND_UNIT_REVIEW", "coefficientF2; designIceLoadHeight; spacing; yieldStrength; corrosionAbrasionAddition; steelGrade; materialApprovalStatus", "specialSurfaceCoatingMaintained", "Piecewise f2, grade-dependent yield strength and approved lower tc all need indexing; thickness/tc should use millimetres.", "h/s at 1 and 1.8, steel-grade values, approved/unapproved lower tc"),
    "TRF-043": ("READY_AFTER_INDEX_CHECK", "iceClass; upperBowIceBeltRequired; framingIceStrengtheningUpperExtent; upperBowIceBeltTop; extensionBeyondAdjacentDeckOrTankBoundary; iceStrengtheningTerminationAtAdjacentBoundaryPermitted", "", "Table 4-6 selection requires ice class in addition to the indexed extent terms.", "table rows, exact 250-mm boundary, 251-mm failure"),
    "TRF-044": ("INDEX_AND_UNIT_REVIEW", "sectionModulus; shearArea; yieldStrength; icePressure; spacing; designIceLoadHeight; span", "frameBoundaryConditionFactorM0; effectiveFrameSpan; frameMomentFactorMt", "m0 table selection and mt output are missing; shearArea must be formula-native cm2 rather than m2.", "m0 rows, h/l boundary, exact Z/A, low Z/A"),
    "TRF-045": ("NEW_TERMS", "span", "frameSpanWithinIceStrengtheningZone; ordinaryFrameScantlingsUsed", "Need the length within zone to calculate the <15% exception; span alone is insufficient.", "14.9% permitted, 15% not permitted, ordinary scantling use"),
    "TRF-046": ("REMODEL", "transverseFrame; frameStrengthenedPart; supportingStructure; connectionMemberScantling", "hasUpperEnd; attachedToSupportingStructure; terminatesAboveSupportingStructure; supportingStructureAtOrAboveIceBeltUpperLimit; horizontalConnectionMember; sameScantlingsAsMainFrame", "String attachment/end properties cannot verify the cross-component alternatives.", "direct attachment, permitted termination alternative, missing connection"),
    "TRF-047": ("REMODEL", "transverseFrame; frameStrengthenedPart; supportingStructure; connectionMemberScantling", "hasLowerEnd; attachedToSupportingStructure; terminatesBelowSupportingStructure; supportingStructureAtOrBelowIceBeltLowerLimit; horizontalConnectionMember; sameScantlingsAsMainFrame; mainFrameBelowIceBeltStrengthened", "Mirror TRF-046 node model for lower end and retain the extra main-frame strengthening condition.", "direct attachment, permitted lower alternative, missing strengthening"),
    "TRF-048": ("INDEX_AND_UNIT_REVIEW", "sectionModulus; actualFrameShearArea; yieldStrength; icePressure; spacing; designIceLoadHeight; span; connectionBracket; coefficientF4", "frameMomentFactorM; bracketArea; netActualFrameShearArea", "Formula operands and m assumption are missing; bracket exclusion needs explicit areas; shear outputs use cm2.", "m=13.3 default, smaller end-field m, bracket exclusion, low Z/A"),
    "TRF-049": ("REMODEL", "frame; supportingStructure; connectionBracket; frameWebPlateThickness; bucklingStiffening", "hasFrameAttachment; hasSupportingWebFrame; hasSupportingBulkhead; webPlateConnectionSideCount; bracketThickness; bracketEdgeStiffened", "Existing generic attachment records do not express all/each supporting structures or the two-sided connection requirement.", "longitudinal brackets, terminating frame bracket, through-frame two-sided connection, thin bracket"),
    "TRF-050": ("CONTROLLED_VALUE_REVIEW", "frameShellAttachment; scallopingPresent; shellPlateButtCrossing; weldType", "doubleContinuousWeld", "weldType is free text; use a controlled weld individual and encode the butt-crossing exception.", "double continuous pass, scallop without crossing fail, crossing exception"),
    "TRF-051": ("INDEX_AND_UNIT_REVIEW", "frameWebPlateThickness; yieldStrength; netThickness; corrosionAbrasionAddition", "frameProfileType; profileSection; flatBarSection; adjacentFrameHeight", "C selection and all three maxima need explicit operands; thickness terms should use millimetres.", "profile/flat-bar C branches, 9-mm floor, half-net-shell floor"),
    "TRF-052": ("CONTROLLED_VALUE_REVIEW", "frameAsymmetrical; frameWebAngleToShell; antitrippingSupportSpacing; frameSpan; iceClass; equivalentSupportStatusByDirectCalculation", "antitrippingSupportRegion; allRegions; bowRegion; midbodyRegion", "antitrippingSupportScope is free text; replace with controlled regions/set membership.", "1300-mm boundary, >4-m all regions, class/region matrix, equivalent alternative"),
    "TRF-053": ("INDEX_AND_UNIT_REVIEW", "designLineLoad; icePressure; designIceLoadHeight; span; yieldStrength; sectionModulus; shearArea", "frameMomentFactorM", "All operands must be indexed; design line load is currently kN/m while source formula uses MN/m, and shear area needs cm2.", "0.15-MN/m floor, exact Z/A, low Z/A"),
    "TRF-054": ("INDEX_AND_UNIT_REVIEW", "designLineLoad; icePressure; designIceLoadHeight; span; yieldStrength; sectionModulus; shearArea; outsideIceBeltFactor; stringerOutsideIceBeltHeight; stringerSpan", "frameMomentFactorM", "Need hs/ls operands and formula-native line-load/shear-area units.", "inside/outside factor, hs=0, near ls boundary, low Z/A"),
    "TRF-055": ("NEW_TERMS", "sectionModulus; shearArea; hatchOpeningLength; shipBreadth; designLineLoad; scantlingApprovalStatus", "narrowDeckStrip; servesAsIceStringer; veryLongHatch; permittedReducedLineLoad", "The approval exception changes p*h floor from 0.15 to not below 0.10 MN/m; distinguish approved value from generic designLineLoad.", "normal 0.15 floor, approved 0.10, below 0.10 failure"),
    "TRF-056": ("EVIDENCE_MODEL", "hatchOpeningLength; shipBreadth; shipSideDeflection; hatchCoverDesignEvidence; hatchFittingDesignEvidence", "", "No numeric deflection limit is stated; verify trigger and required design evidence without inventing a threshold.", "hatch <=B/2 non-applicable, >B/2 with evidence pass, missing evidence fail"),
    "TRF-057": ("INDEX_AND_UNIT_REVIEW", "icePressure; iceLoadHeight; webFrameSpacing; webFrameSafetyFactor; webFrameIceLoad; loadLengthParameter; minimumLineLoad", "iceLoadSourceType; iceStringerLoadSource; longitudinalFramingLoadSource", "f12=1.8, la=2S and 0.15-MN/m floor must be explicit; line-load units need alignment.", "both load sources, floor active/inactive, exact F, wrong la"),
    "TRF-058": ("INDEX_AND_NEW_TERMS", "iceLoadForce; stringerOutsideIceBeltHeight; stringerSpan", "supportedStringerOutsideIceBelt; adjustedIceLoadForce", "Distinguish original F from the outside-belt adjusted force.", "inside belt unchanged, outside factor, hs/ls boundary"),
    "TRF-059": ("INDEX_AND_UNIT_REVIEW", "shearArea; yieldStrength", "maximumCalculatedShearForce; webFrameShearFactorAlpha; webFrameCrossSectionType", "Q and alpha Table 4-8 selection are missing; output shear area must use cm2.", "alpha table rows, exact A, low A"),
}


def main() -> None:
    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registry_names = {row["localName"] for row in registry}
    batch_ids = [row["requirement_id"] for row in batch["requirements"]]
    missing_reviews = [rid for rid in batch_ids if rid not in REVIEWS]
    extra_reviews = [rid for rid in REVIEWS if rid not in batch_ids]
    if missing_reviews or extra_reviews:
        raise RuntimeError(f"Review coverage mismatch: missing={missing_reviews}, extra={extra_reviews}")

    rows = []
    for requirement in batch["requirements"]:
        rid = requirement["requirement_id"]
        decision, existing_text, new_text, issue, variants = REVIEWS[rid]
        existing = [item.strip() for item in existing_text.split(";") if item.strip()]
        new = [item.strip() for item in new_text.split(";") if item.strip()]
        invalid_existing = [item for item in existing if item not in registry_names]
        already_existing_new = [item for item in new if item in registry_names]
        indexed = set(requirement["r2_indexed_terms"])
        rows.append({
            "sequence": requirement["sequence"],
            "requirement_id": rid,
            "page": requirement["page"],
            "clause": requirement["clause"],
            "decision": decision,
            "existing_terms_to_link": existing,
            "draft_new_terms": new,
            "existing_terms_not_currently_indexed": sorted(set(existing) - indexed),
            "invalid_existing_term_claims": invalid_existing,
            "draft_terms_already_in_r2": already_existing_new,
            "engineering_issue": issue,
            "planned_fixture_variants": variants,
            "review_status": "ENGINEERING_PREFLIGHT_COMPLETE",
        })
    payload = {
        "batch_id": batch["batch_id"],
        "source_lock_id": batch["source_lock_id"],
        "status": "Preflight decisions - not a final vocabulary declaration",
        "reviewed_requirement_count": len(rows),
        "requirements": rows,
    }
    (BATCH_ROOT / "engineering_preflight.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    headers = [
        "sequence", "requirement_id", "page", "clause", "decision",
        "existing_terms_to_link", "draft_new_terms", "existing_terms_not_currently_indexed",
        "invalid_existing_term_claims", "draft_terms_already_in_r2", "engineering_issue",
        "planned_fixture_variants", "review_status",
    ]
    with (BATCH_ROOT / "engineering_preflight.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            export = dict(row)
            for key in (
                "existing_terms_to_link", "draft_new_terms", "existing_terms_not_currently_indexed",
                "invalid_existing_term_claims", "draft_terms_already_in_r2",
            ):
                export[key] = " | ".join(row[key])
            writer.writerow(export)
    print(json.dumps({
        "reviewed": len(rows),
        "decisions": {key: sum(1 for row in rows if row["decision"] == key) for key in sorted({row["decision"] for row in rows})},
        "unique_draft_terms": len({item for row in rows for item in row["draft_new_terms"]}),
        "invalid_existing_claims": sorted({item for row in rows for item in row["invalid_existing_term_claims"]}),
        "draft_terms_already_in_r2": sorted({item for row in rows for item in row["draft_terms_already_in_r2"]}),
    }, indent=2))


if __name__ == "__main__":
    main()
