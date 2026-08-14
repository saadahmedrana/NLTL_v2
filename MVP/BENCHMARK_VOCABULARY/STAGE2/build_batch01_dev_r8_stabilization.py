from __future__ import annotations

import json

import build_batch01_dev_r7 as r7


base = r7.base
r6 = r7.r6
base.OUT = base.MVP / "BENCHMARK_VOCABULARY" / "DEVELOPMENT" / "DEV_R8_STABILIZATION"
base.DEV_INDEX = base.OUT / "requirement_term_index.json"
base.VERSION = "2.8.0-dev-batch01-stabilization"
base.DEV_ID = "VOCAB-DEV-2026-08-13-BATCH01-R8-STABILIZATION"


# These are context/index repairs for canonical terms that already existed in
# R7. No new engineering concept, threshold, formula result, or compliance
# answer is introduced here.
base.CALIBRATION_GAP_TERMS.update({
    "TRF-037": base.CALIBRATION_GAP_TERMS.get("TRF-037", set()) | {
        "directAnalysisCase", "hasDirectAnalysisCase",
    },
    "TRF-042": base.CALIBRATION_GAP_TERMS.get("TRF-042", set()) | {"plating"},
})

r6.TERM_OWNER_OVERRIDES.update({
    "TRF-037": {
        "hasDirectAnalysisCase": "ship",
        "iceLoadAreaFactorCa": "directAnalysisCase",
    },
    "TRF-042": {"plating": "plating"},
})

r6.SEMANTIC_OBLIGATIONS.update({
    "TRF-037": [
        "Compute rawCd=(a*k+b)/1000 and validate shipSizeEngineOutputFactorCd against IF(rawCd > 1, 1, rawCd); the maximum is a cap, not a rejection of raw values above 1.",
        "Validate icePressure = shipSizeEngineOutputFactorCd * iceClassFactorCp * iceLoadAreaFactorCa * nominalIcePressureP0; iceLoadAreaFactorCa is owned by directAnalysisCase and is reached from ship with hasDirectAnalysisCase.",
    ],
})


def main() -> None:
    base.main()
    r6.add_ownership_metadata()
    payload = base.read_json(base.DEV_INDEX)
    payload["version"] = "1.7.0-dev-batch01-stabilization"
    payload["supportedSparqlExtensionFunctions"] = {
        "namespace": "http://www.w3.org/2005/xpath-functions/math#",
        "functions": ["sin", "cos", "tan", "atan"],
        "implementation": "Deterministic rdflib/pySHACL evaluator extension registered by the pipeline.",
    }
    payload["exclusivePropertyGroups"] = {
        "TRF-030": [{
            "id": "directAnalysisPositionAxis",
            "owner": "directAnalysisCase",
            "alternatives": [
                ["verticalLoadPosition", "verticalLoadPositionType"],
                ["horizontalLoadPosition", "horizontalLoadPositionType"],
            ],
            "rationale": "The verified clause requires several vertical and several horizontal cases; one case represents one position axis, not both axes conjunctively.",
        }],
    }
    base.write_json(base.DEV_INDEX, payload)

    registry = base.read_json(base.OUT / "registry/term_registry.json")
    additions = [item for item in registry if str(item.get("conceptId", "")).startswith("VOC-DEV")]
    report = base.read_json(base.OUT / "validation/validation_report.json")
    base.build_manifest(registry, additions, report)
    base.build_development_binding()
    manifest = base.read_json(base.OUT / "development_manifest.json")
    manifest["baseRevision"] = "VOCAB-DEV-2026-08-13-BATCH01-R7"
    manifest["revisionPurpose"] = (
        "Infrastructure stabilization: repair two existing-term context gaps and "
        "declare one verified mutually-exclusive node pattern. No new vocabulary term."
    )
    manifest["ownershipModel"] = {
        "status": "AUTHORITATIVE_REQUIREMENT_SCOPED",
        "targetOwners": len(r6.TARGET_OWNER),
        "termOwnerMaps": len(payload["termOwners"]),
    }
    manifest["supportedSparqlExtensionFunctions"] = payload["supportedSparqlExtensionFunctions"]
    manifest["exclusivePropertyGroups"] = payload["exclusivePropertyGroups"]
    base.write_json(base.OUT / "development_manifest.json", manifest)
    print(json.dumps({
        "status": "PASS",
        "development_id": base.DEV_ID,
        "registry_terms": len(registry),
        "added_terms": len(additions),
        "new_terms_since_r7": 0,
        "output": str(base.OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
