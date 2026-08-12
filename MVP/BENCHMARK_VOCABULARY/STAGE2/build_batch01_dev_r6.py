from __future__ import annotations

import json
from pathlib import Path

import build_batch01_dev_revision as base


base.OUT = base.MVP / "BENCHMARK_VOCABULARY" / "DEVELOPMENT" / "DEV_R6_BATCH01"
base.DEV_INDEX = base.OUT / "requirement_term_index.json"
base.VERSION = "2.6.0-dev-batch01"
base.DEV_ID = "VOCAB-DEV-2026-08-13-BATCH01-R6"

NEW_CLASSES = {"mainTransverseFrame", "intermediateTransverseFrame"}
NEW_OBJECT_PROPERTIES = {
    "hasStrengthenedPart": "frameStrengthenedPart",
    "hasSupportingStructureAttachment": "frameAttachment",
}
NEW_QUANTITIES = {"upperIceWaterlineReferencePosition", "lowerIceWaterlineReferencePosition"}
NEW_BOOLEANS = {
    "similarAttachmentConstructionPresent", "veryLongHatchOpening",
    "reducedLineLoadApprovedByClassificationSociety", "reachesTankTopOrBelowFloorTop",
}

base.SUPPORT_TERMS.update(NEW_CLASSES | set(NEW_OBJECT_PROPERTIES) | NEW_QUANTITIES | NEW_BOOLEANS)
base.CLASS_TERMS.update(NEW_CLASSES)
base.PARENT_CLASSES.update({
    "mainTransverseFrame": "transverseFrame",
    "intermediateTransverseFrame": "transverseFrame",
})
base.OBJECT_RANGES.update(NEW_OBJECT_PROPERTIES)
base.EXPLICIT_QUANTITY_TERMS.update(NEW_QUANTITIES)
base.BOOLEAN_TERMS.update(NEW_BOOLEANS)
base.METRE_TERMS.update(NEW_QUANTITIES)
base.PROPERTY_DOMAINS.update({
    "upperIceWaterlineReferencePosition": "directAnalysisCase",
    "lowerIceWaterlineReferencePosition": "directAnalysisCase",
    "hasStrengthenedPart": "frame",
    "hasSupportingStructureAttachment": "supportingStructure",
    "similarAttachmentConstructionPresent": "frameAttachment",
    "veryLongHatchOpening": "narrowDeckStrip",
    "reducedLineLoadApprovedByClassificationSociety": "narrowDeckStrip",
    "reachesTankTopOrBelowFloorTop": "frame",
})
base.CALIBRATION_GAP_TERMS.update({
    "TRF-015": base.CALIBRATION_GAP_TERMS["TRF-015"] | {"gramPerKilogramSalinityUnit"},
    "TRF-030": base.CALIBRATION_GAP_TERMS["TRF-030"] | NEW_QUANTITIES,
    "TRF-043": base.CALIBRATION_GAP_TERMS["TRF-043"] | {"reachesTankTopOrBelowFloorTop"},
    "TRF-044": {"mainTransverseFrame", "intermediateTransverseFrame"},
    "TRF-047": base.CALIBRATION_GAP_TERMS["TRF-047"] | {"hasStrengthenedPart"},
    "TRF-049": base.CALIBRATION_GAP_TERMS["TRF-049"] | {
        "similarAttachmentConstructionPresent", "hasSupportingStructureAttachment",
    },
    "TRF-055": base.CALIBRATION_GAP_TERMS["TRF-055"] | {
        "veryLongHatchOpening", "reducedLineLoadApprovedByClassificationSociety",
    },
})


# Requirement-scoped ownership is authoritative for RDF construction and SHACL
# generation. Global rdfs:domain remains a broad semantic declaration where a
# property is legitimately reused by more than one engineering entity.
TARGET_OWNER = {
    **{f"TRF-{number:03d}": "ship" for number in range(1, 33)},
    "TRF-034": "effectiveMemberCrossSection",
    "TRF-035": "ship",
    "TRF-036": "iceClassDesignParameterSet",
    "TRF-037": "ship",
    "TRF-041": "plating",
    "TRF-042": "plating",
    "TRF-043": "frame",
    "TRF-044": "transverseFrame",
    "TRF-045": "frame",
    "TRF-046": "frame",
    "TRF-047": "frame",
    "TRF-048": "longitudinalFrame",
    "TRF-049": "frame",
    "TRF-050": "frameAttachment",
    "TRF-051": "hullStructure",
    "TRF-052": "frame",
    "TRF-053": "iceStringer",
    "TRF-054": "iceStringer",
    "TRF-055": "narrowDeckStrip",
    "TRF-056": "weatherdeckHatch",
    "TRF-057": "webFrame",
    "TRF-058": "webFrame",
    "TRF-059": "webFrame",
}

TERM_OWNER_OVERRIDES = {
    "TRF-011": {"hasUpperIceWaterline": "ship", "hasIntendedIceOperatingWaterline": "ship"},
    "TRF-012": {"hasLowerIceWaterline": "ship", "hasIntendedIceOperatingWaterline": "ship"},
    "TRF-013": {"hasUpperIceWaterline": "ship", "hasLowerIceWaterline": "ship", "hasIntendedIceOperatingWaterline": "ship"},
    "TRF-016": {
        "hasUpperIceWaterline": "ship", "hasLowerIceWaterline": "ship", "hasBallastTank": "ship",
        "situatedAboveLowerIceWaterline": "ballastTank", "usedToReachLowerIceWaterline": "ballastTank",
        "freezingPreventionPresent": "ballastTank",
    },
    "TRF-030": {"hasDirectAnalysisCase": "ship"},
    "TRF-034": {
        "hasEffectiveMemberCrossSection": "hullStructure",
        "hasClassificationSocietySectionPropertyCalculationEvidence": "effectiveMemberCrossSection",
        "memberNormalToPlating": "hullStructure",
    },
    "TRF-036": {"hasIceClassDesignParameterSet": "ship", "iceClass": "ship"},
    "TRF-046": {"hasUpperEnd": "frame", "hasHorizontalConnectionMember": "frameEnd"},
    "TRF-047": {"hasLowerEnd": "frame", "hasHorizontalConnectionMember": "frameEnd"},
    "TRF-049": {
        "hasFrameAttachment": "frame", "hasSupportingStructureAttachment": "supportingStructure",
        "hasConnectionBracket": "frameAttachment", "bracketThickness": "connectionBracket",
        "bracketEdgeStiffened": "connectionBracket", "bucklingStiffening": "connectionBracket",
    },
    "TRF-056": {"hasWeatherdeckHatch": "ship"},
}

SEMANTIC_OBLIGATIONS = {
    "TRF-011": ["Validate that the UIWL is the pointwise upper envelope of all intended ice-operating waterlines; presence alone is insufficient."],
    "TRF-012": ["Validate that the LIWL is the pointwise lower envelope of all intended ice-operating waterlines; presence alone is insufficient."],
    "TRF-014": ["Draught increases downward: a summer load line at a higher level than UIWL has a numerically smaller draught."],
    "TRF-030": ["Represent several vertical and horizontal direct-analysis cases and corresponding load-length/area-factor pairs."],
    "TRF-041": ["Use the applicable transverse or longitudinal plating formula and reject missing operands; do not target generic benchmarkEntity."],
    "TRF-043": ["Apply Table 4-6 minima by default and model the <=250 mm termination allowance only as an explicit exception."],
}


def add_ownership_metadata() -> None:
    path = base.DEV_INDEX
    payload = base.read_json(path)
    term_owners = {}
    target_owners = {}
    for rid, terms in payload["requirements"].items():
        if rid not in TARGET_OWNER:
            continue
        target = TARGET_OWNER[rid]
        target_owners[rid] = target
        overrides = TERM_OWNER_OVERRIDES.get(rid, {})
        term_owners[rid] = {name: overrides.get(name, target) for name in terms}
    payload["version"] = "1.5.0-dev-batch01"
    payload["requirementTargetOwner"] = target_owners
    payload["termOwners"] = term_owners
    payload["semanticObligations"] = SEMANTIC_OBLIGATIONS
    base.write_json(path, payload)


def main() -> None:
    base.main()
    add_ownership_metadata()
    registry = base.read_json(base.OUT / "registry/term_registry.json")
    additions = [item for item in registry if str(item.get("conceptId", "")).startswith("VOC-DEV")]
    report = base.read_json(base.OUT / "validation/validation_report.json")
    base.build_manifest(registry, additions, report)
    base.build_development_binding()
    manifest = base.read_json(base.OUT / "development_manifest.json")
    manifest["ownershipModel"] = {
        "status": "AUTHORITATIVE_REQUIREMENT_SCOPED",
        "targetOwners": len(TARGET_OWNER),
        "termOwnerMaps": len(base.read_json(base.DEV_INDEX)["termOwners"]),
    }
    manifest["baseRevision"] = "VOCAB-DEV-2026-08-12-BATCH01-R5"
    base.write_json(base.OUT / "development_manifest.json", manifest)
    print(json.dumps({
        "status": "PASS", "development_id": base.DEV_ID,
        "registry_terms": len(registry), "ownership_profiles": len(TARGET_OWNER),
        "output": str(base.OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
