from __future__ import annotations

import json

import build_batch01_dev_r6 as r6


base = r6.base
base.OUT = base.MVP / "BENCHMARK_VOCABULARY" / "DEVELOPMENT" / "DEV_R7_BATCH01"
base.DEV_INDEX = base.OUT / "requirement_term_index.json"
base.VERSION = "2.7.0-dev-batch01"
base.DEV_ID = "VOCAB-DEV-2026-08-13-BATCH01-R7"

# Clause 3.2.2 explicitly requires B to be determined at UIWL. This term is
# coined because no verified existing registry term expresses that operand.
NEW_QUANTITIES = {"upperIceWaterlineBreadth"}
base.SUPPORT_TERMS.update(NEW_QUANTITIES)
base.EXPLICIT_QUANTITY_TERMS.update(NEW_QUANTITIES)
base.METRE_TERMS.update(NEW_QUANTITIES)
base.PROPERTY_DOMAINS["upperIceWaterlineBreadth"] = "iceWaterline"

base.CALIBRATION_GAP_TERMS.update({
    "TRF-020": base.CALIBRATION_GAP_TERMS.get("TRF-020", set()) | {
        "hasUpperIceWaterline", "hasLowerIceWaterline", "iceWaterline",
        "upperIceWaterlineLength", "upperIceWaterlineBreadth",
    },
    "TRF-025": base.CALIBRATION_GAP_TERMS.get("TRF-025", set()) | {
        "newtonPerMetreToPowerOnePointFiveUnit",
    },
    "TRF-046": base.CALIBRATION_GAP_TERMS.get("TRF-046", set()) | {"hasStrengthenedPart"},
})

r6.TERM_OWNER_OVERRIDES.update({
    "TRF-011": {
        "hasUpperIceWaterline": "ship",
        "hasIntendedIceOperatingWaterline": "ship",
        "hasWaterlineProfilePoint": "iceWaterline",
        "longitudinalPosition": "waterlineProfilePoint",
        "verticalCoordinate": "waterlineProfilePoint",
    },
    "TRF-020": {
        "hasUpperIceWaterline": "ship", "hasLowerIceWaterline": "ship",
        "upperIceWaterlineLength": "iceWaterline",
        "upperIceWaterlineBreadth": "iceWaterline",
    },
    "TRF-030": {
        "hasDirectAnalysisCase": "ship",
        "capacityMinimizingLoadPositionConfirmed": "directAnalysisCase",
        "combinedBendingAndShearEvaluated": "directAnalysisCase",
        "verticalLoadPosition": "directAnalysisCase",
        "verticalLoadPositionType": "directAnalysisCase",
        "horizontalLoadPosition": "directAnalysisCase",
        "horizontalLoadPositionType": "directAnalysisCase",
        "loadPatchLength": "directAnalysisCase",
        "iceLoadAreaFactorCa": "directAnalysisCase",
        "upperIceWaterlineReferencePosition": "directAnalysisCase",
        "lowerIceWaterlineReferencePosition": "directAnalysisCase",
    },
    "TRF-046": {
        "hasStrengthenedPart": "frame",
        "hasUpperEnd": "frame",
        "hasAttachedSupportingStructure": "frameEnd",
        "hasTerminationAboveSupportingStructure": "frameEnd",
        "hasHorizontalConnectionMember": "frameEnd",
        "connectsToAdjacentMainFrame": "horizontalConnectionMember",
        "sameScantlingsAsMainFrame": "horizontalConnectionMember",
        "supportingStructureAtOrAboveIceBeltUpperLimit": "supportingStructure",
        "ordinaryFrameScantlingsUsed": "frameStrengthenedPart",
    },
    "TRF-049": {
        "hasFrameAttachment": "frame",
        "hasAttachedSupportingStructure": "frameAttachment",
        "hasSupportingStructureAttachment": "supportingStructure",
        "effectiveAttachmentConfirmed": "frameAttachment",
        "similarAttachmentConstructionPresent": "frameAttachment",
        "hasConnectionBracket": "frameAttachment",
        "bracketThickness": "connectionBracket",
        "bracketEdgeStiffened": "connectionBracket",
        "bucklingStiffening": "connectionBracket",
    },
})

r6.SEMANTIC_OBLIGATIONS.update({
    "TRF-011": [
        "Validate bidirectional pointwise equality between UIWL and the maximum verticalCoordinate among intended ice-operating waterline points at each longitudinalPosition; use one bounded grouped subquery or aggregation, not mirrored nested EXISTS branches.",
    ],
    "TRF-014": [
        "Draught increases downward: a summer load line at a higher level than UIWL has a numerically smaller draught.",
        "For a pre-1 July 2007 ship, complete warning-triangle and draught-mark evidence passes without requiring firstScheduledDryDockingDate; otherwise the marking is required when the first scheduled dry docking after the cutoff is due or past.",
    ],
    "TRF-020": [
        "Require sufficient constructionStageDate and controlled iceClass evidence before selecting applicable/non-applicable branches.",
        "Calculate minimum power separately at UIWL and LIWL from the corresponding draught-dependent resistance inputs, but use upperIceWaterlineLength and upperIceWaterlineBreadth for both calculations; require maximumContinuousRatingPower to be at least the greater result.",
    ],
    "TRF-022": [
        "Use the supported XPath math-function IRIs math:sin, math:tan, and math:atan from http://www.w3.org/2005/xpath-functions/math# for psi = atan(tan(phi2)/sin(alpha)); include degree/radian conversion, singular-input rejection, and tolerance comparison.",
        "Apply Table 3-2 constants and clamp ((L*T)/B^2)^3 to the inclusive interval [5,20].",
    ],
    "TRF-025": [
        "Apply only to IA Super ships with bulbousBowPresent=false; require exactly one controlled iceClass and one boolean bulbousBowPresent before branch selection.",
        "Validate C1 and C2 in their original value domains with numerical tolerance and reject non-positive L, B, or T operands.",
    ],
    "TRF-026": [
        "Require exactly one controlled iceClass first. Non-IA-Super ships are non-applicable without bulb data; IA Super requires exactly one bulbousBowPresent value, false is non-applicable, and true activates the C1/C2 formula checks.",
    ],
    "TRF-027": [
        "Require exactly one controlled iceClass before applicability branching; apply the Table 3-3 and clamped-geometry rules only to IA Super or IA ships with constructionStageDate before 1 September 2003.",
    ],
    "TRF-030": [
        "Represent several vertical and horizontal directAnalysisCase nodes. Each case owns its position, combined bending/shear evidence, and capacity-minimizing evidence.",
        "When load length is not determined from the arrangement, require several distinct directAnalysisCase nodes, each containing both its loadPatchLength and corresponding iceLoadAreaFactorCa; the shared case node is the canonical pairing structure.",
    ],
    "TRF-037": [
        "Compute rawCd=(a*k+b)/1000 and validate shipSizeEngineOutputFactorCd against IF(rawCd > 1, 1, rawCd); the maximum is a cap, not a rejection of raw values above 1.",
    ],
    "TRF-042": [
        "Use tolerance max(1e-6*ABS(expected),1e-12), not the sum of relative and absolute tolerances, for derived f2 comparison.",
        "Constrain materialApprovalStatus to the canonical evidenceState range when a lower corrosion addition is justified by approved maintained coating evidence.",
    ],
    "TRF-046": [
        "Require the strengthened upper end to attach to an eligible supporting structure. The at-or-above-ice-belt condition qualifies only the ordinary-scantlings and intermediate-frame horizontal-member permissions; it is not an unconditional attachment requirement.",
    ],
    "TRF-049": [
        "Target frame subclasses directly and keep attachment evidence on frameAttachment: effectiveAttachmentConfirmed, similarAttachmentConstructionPresent, hasAttachedSupportingStructure, and hasConnectionBracket.",
        "Use SHACL Core for local presence, datatype, cardinality, and unit checks; reserve bounded SPARQL for shared attachment identity and bracketThickness >= frameWebThickness.",
    ],
})


def main() -> None:
    base.main()
    r6.add_ownership_metadata()
    payload = base.read_json(base.DEV_INDEX)
    payload["version"] = "1.6.0-dev-batch01"
    payload["supportedSparqlExtensionFunctions"] = {
        "namespace": "http://www.w3.org/2005/xpath-functions/math#",
        "functions": ["sin", "cos", "tan", "atan"],
        "implementation": "Deterministic rdflib/pySHACL evaluator extension registered by the pipeline.",
    }
    base.write_json(base.DEV_INDEX, payload)
    registry = base.read_json(base.OUT / "registry/term_registry.json")
    additions = [item for item in registry if str(item.get("conceptId", "")).startswith("VOC-DEV")]
    report = base.read_json(base.OUT / "validation/validation_report.json")
    base.build_manifest(registry, additions, report)
    base.build_development_binding()
    manifest = base.read_json(base.OUT / "development_manifest.json")
    manifest["baseRevision"] = "VOCAB-DEV-2026-08-13-BATCH01-R6"
    manifest["ownershipModel"] = {
        "status": "AUTHORITATIVE_REQUIREMENT_SCOPED",
        "targetOwners": len(r6.TARGET_OWNER),
        "termOwnerMaps": len(payload["termOwners"]),
    }
    manifest["supportedSparqlExtensionFunctions"] = payload["supportedSparqlExtensionFunctions"]
    base.write_json(base.OUT / "development_manifest.json", manifest)
    print(json.dumps({
        "status": "PASS", "development_id": base.DEV_ID,
        "registry_terms": len(registry), "added_terms": len(additions),
        "output": str(base.OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
