from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R7"
TARGET = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R8"
LOCK_ID = "VOCAB-LOCK-2026-08-20-R8"
SOURCE_LOCK_ID = "VOCAB-LOCK-2026-08-20-R7"
RECLASSIFIED = [
    "I2-008", "I2-015", "I2-022", "I2-023", "I2-024", "I2-030", "I2-040",
    "I2-041", "I2-043", "I2-050", "I2-053", "I2-054", "I2-064", "I2-065",
    "TRF-020", "TRF-022", "TRF-025", "TRF-026", "TRF-030", "TRF-034",
    "TRF-041", "TRF-051", "TRF-060", "TRF-116",
]
EXPECTED_CATEGORIES = {
    "Static": 151,
    "Static Calculation": 65,
    "Complex": 64,
    "Dynamic": 17,
    "Physical Test": 16,
}

# These lists refine shallow R7 contracts using terms that were already indexed
# and source-linked in R7. They add no ontology or registry vocabulary.
READINESS_IO = {
    "TRF-020": {
        "operandTerms": ["constructionStageDate", "iceClass", "engineOutputCoefficientKe",
            "brashIceChannelResistanceAtLowerIceWaterline", "brashIceChannelResistanceAtUpperIceWaterline",
            "propellerDiameter", "propellerCount", "propellerPitchControlType", "propulsionSystemType",
            "upperIceWaterlineBreadth", "upperIceWaterlineLength"],
        "resultTerms": ["minimumRequiredPowerAtLowerIceWaterline", "minimumRequiredPowerAtUpperIceWaterline"],
        "relationshipTerms": ["hasLowerIceWaterline", "hasUpperIceWaterline"],
    },
    "TRF-022": {
        "operandTerms": ["bowRakeAtQuarterBreadth", "waterlineAngleAtQuarterBreadth", "shipLength",
            "iceClassDraught", "shipBreadth", "coefficientC3", "coefficientC4", "coefficientC5",
            "coefficientF1", "coefficientF2", "coefficientF3", "coefficientF4", "coefficientG1",
            "coefficientG2", "coefficientG3"],
        "resultTerms": ["flareAngle", "clampedHullGeometryTerm"],
    },
    "TRF-025": {
        "operandTerms": ["coefficientF1", "coefficientF2", "coefficientF3", "coefficientF4",
            "coefficientG1", "coefficientG2", "coefficientG3", "shipBreadth", "shipLength",
            "iceClassDraught", "iceClass", "bulbousBowPresent"],
        "resultTerms": ["brashIceResistanceCoefficientC1", "brashIceResistanceCoefficientC2"],
    },
    "TRF-026": {
        "operandTerms": ["coefficientF1", "coefficientF2", "coefficientF3", "coefficientF4",
            "coefficientG1", "coefficientG2", "coefficientG3", "shipBreadth", "shipLength",
            "iceClassDraught", "iceClass", "bulbousBowPresent"],
        "resultTerms": ["brashIceResistanceCoefficientC1", "brashIceResistanceCoefficientC2"],
    },
    "TRF-030": {
        "operandTerms": ["icePressure", "loadPatchHeight", "loadPatchLength", "iceLoadAreaFactorCa",
            "loadLengthDeterminedFromArrangement", "verticalLoadPosition", "horizontalLoadPosition"],
        "resultTerms": ["appliedIcePressure", "capacityMinimizingLoadPositionConfirmed",
            "combinedBendingAndShearEvaluated"],
        "relationshipTerms": ["hasDirectAnalysisCase"],
    },
    "TRF-034": {
        "operandTerms": ["sectionModulus", "shearArea", "memberNormalToPlating"],
        "resultTerms": ["effectiveMemberCrossSection"],
        "relationshipTerms": ["hasEffectiveMemberCrossSection",
            "hasClassificationSocietySectionPropertyCalculationEvidence"],
        "evidenceTerms": ["hasClassificationSocietySectionPropertyCalculationEvidence"],
    },
    "TRF-041": {
        "operandTerms": ["spacing", "icePressure", "platingPressure", "yieldStrength",
            "transversePlatingFactorF1", "longitudinalPlatingFactorF2", "corrosionAbrasionAddition",
            "platingFramingOrientation"],
        "resultTerms": ["requiredShellPlatingThickness"],
    },
    "TRF-051": {
        "operandTerms": ["adjacentFrameHeight", "yieldStrength", "frameProfileType",
            "netShellPlatingThickness", "corrosionAbrasionAddition", "inLieuOfFrame"],
        "resultTerms": ["frameWebThickness"],
    },
}

DIRECT_CHECKS = {
    "I2-064": [
        {"id": "webShearStressLimit", "mode": "DIRECT_CHECK",
         "description": "nominal shear stress is less than yield strength divided by fixed constant sqrt(3)",
         "requiredTerms": ["nominalShearStress", "yieldStrength"]},
        {"id": "flangeVonMisesLimit", "mode": "DIRECT_CHECK",
         "description": "nominal flange von Mises stress is less than 1.15 times yield strength",
         "requiredTerms": ["nominalFlangeVonMisesStress", "yieldStrength"]},
    ],
    "TRF-020": [
        {"id": "installedPowerAtLeastExternalMinimum", "mode": "DIRECT_CHECK",
         "description": "maximum continuous rating is at least both externally calculated minimum powers",
         "requiredTerms": ["maximumContinuousRatingPower", "minimumRequiredPowerAtLowerIceWaterline",
             "minimumRequiredPowerAtUpperIceWaterline"]},
    ],
    "TRF-051": [
        {"id": "absoluteNineMillimetreMinimum", "mode": "DIRECT_CHECK",
         "description": "frame web thickness is at least the source-stated fixed 9 mm minimum",
         "requiredTerms": ["frameWebThickness"]},
    ],
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def immutable_manifest() -> dict:
    roots = [
        SOURCE,
        MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R7.xlsx",
        MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R7.lock.json",
        MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R7.sha256",
    ]
    files = {}
    for root in roots:
        candidates = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for path in candidates:
            files[str(path.relative_to(MVP))] = sha(path)
    aggregate = hashlib.sha256(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(files.items())).encode()
    ).hexdigest()
    return {"sourceLockId": SOURCE_LOCK_ID, "fileCount": len(files),
            "aggregateSha256": aggregate, "files": files}


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite existing R8 directory: {TARGET}")
    for directory in ("context", "evidence", "ontology", "registry"):
        shutil.copytree(SOURCE / directory, TARGET / directory)
    shutil.copy2(SOURCE / "requirement_term_index.json", TARGET / "requirement_term_index.json")
    (TARGET / "provenance").mkdir(parents=True)
    (TARGET / "validation").mkdir(parents=True)

    evidence = read(TARGET / "evidence/stage1_approved.json")
    index = read(TARGET / "requirement_term_index.json")
    by_id = {row["id"]: row for row in evidence["requirements"]}
    before = {rid: by_id[rid]["category"] for rid in RECLASSIFIED}
    if set(before.values()) != {"Static Calculation"}:
        raise RuntimeError(f"R8 source classifications are not exactly Static Calculation: {before}")

    for rid in RECLASSIFIED:
        requirement = by_id[rid]
        requirement["category"] = "Complex"
        contract = index["dependencyContracts"][rid]
        contract["verificationMode"] = "COMPLEX_READINESS"
        contract["schemaVersion"] = max(8, int(contract.get("schemaVersion", 1)))
        contract["informationalSourceFormula"] = contract.get("formulaExpression") or contract.get("comparisonModel", "")
        contract["formulaExecutionRequired"] = False
        contract["directCheckSubconstraints"] = DIRECT_CHECKS.get(rid, [])
        contract["verificationPolicyBasis"] = (
            "Source/formalism-driven R8 policy; classification was not derived from model success or failure."
        )
        for key, values in READINESS_IO.get(rid, {}).items():
            contract[key] = values
        if rid == "I2-064" and "bucklingCriteriaSatisfied" not in contract["evidenceTerms"]:
            contract["evidenceTerms"].append("bucklingCriteriaSatisfied")
        required = list(contract.get("requiredModelFields", []))
        for field in ("verificationMode", "operandTerms", "resultTerms"):
            if field not in required:
                required.append(field)
        contract["requiredModelFields"] = required
        contract["engineeringDecision"] = "R8_COMPLEX_READINESS_SOURCE_FORMULA_INFORMATIONAL"

        if rid == "I2-008":
            contract["status"] = "COMPLETE"
            contract["auditFlags"] = []
            contract["observedFailureStatus"] = ""
            contract["engineeringDecision"] = "R8_COMPLEX_READINESS_UMBRELLA_INPUT_RESULT_STRUCTURE_COMPLETE"
        if rid == "I2-053":
            contract["operandTerms"] = ["designVerticalIceShearForce", "designVerticalWaveShearForce",
                "hullGirderLongitudinalPositionFromAft"]
            contract["resultTerms"] = ["appliedVerticalShearStress"]
            contract["status"] = "BLOCKED_SOURCE_OR_MODEL_DEPENDENCY"
            contract["deferredReason"] = (
                "R7 has the force, position, and applied-stress terms, but no complete canonical owner/path/analysis-case "
                "structure for applying the externally delegated UR S11.5.4.2 procedure along the hull girder."
            )
            contract["requiredMethodReference"] = "IACS UR S11.5.4.2 (externally delegated engineering procedure)"
            requirement["activeStatus"] = "Deferred - complex readiness owner/path incomplete"
            requirement["codability"] = "Deferred"
        else:
            contract["status"] = "COMPLETE"
            contract["auditFlags"] = []
            contract["observedFailureStatus"] = ""
            requirement["activeStatus"] = "Stage 2 candidate - complex readiness"
            requirement["codability"] = "Complex readiness"

        # Keep every formula, operand, output, unit-bearing term, table, path,
        # applicability and evidence field; only the execution obligation changes.
        for key in ("formulaExpression", "comparisonModel", "operandTerms", "resultTerms",
                    "relationshipTerms", "modelPaths", "applicabilityTerms", "evidenceTerms", "tableModel"):
            contract.setdefault(key, [] if key.endswith("Terms") or key == "modelPaths" else "")
        indexed = set(index["requirements"][rid])
        referenced = set(contract["operandTerms"] + contract["resultTerms"] + contract["relationshipTerms"]
                         + contract["applicabilityTerms"] + contract["evidenceTerms"]
                         + contract.get("controlledValueTerms", []))
        for check in contract["directCheckSubconstraints"]:
            referenced.update(check["requiredTerms"])
        missing = sorted(referenced - indexed)
        if missing:
            index["requirements"][rid] = sorted(indexed | set(missing))

    evidence["summary"]["requirementsByCategory"] = EXPECTED_CATEGORIES
    evidence["summary"]["activationCounts"] = dict(Counter(row["activeStatus"] for row in evidence["requirements"]))
    evidence["summary"]["verificationPolicyLockId"] = LOCK_ID
    evidence["summary"]["verificationPolicy"] = "R8 source/formalism-driven direct-check versus complex-readiness policy"
    index["sourceLockId"] = LOCK_ID
    index["version"] = "8.0"

    category_counts = Counter(row["category"] for row in evidence["requirements"])
    if dict(category_counts) != EXPECTED_CATEGORIES:
        raise RuntimeError(f"Unexpected R8 categories: {dict(category_counts)}")
    changed = [row["id"] for row in evidence["requirements"] if row["category"] != "Static Calculation"
               and row["id"] in RECLASSIFIED]
    if set(changed) != set(RECLASSIFIED) or len(changed) != 24:
        raise RuntimeError("R8 did not reclassify exactly the approved 24 requirements")

    policy = {
        "lockId": LOCK_ID,
        "status": "FROZEN_VERIFICATION_POLICY",
        "basis": "Source/formalism-driven; not derived from model success or failure.",
        "static": "Direct SHACL verification.",
        "staticCalculation": {
            "mode": "DIRECT_CHECK",
            "supportedSubset": ["+", "-", "*", "/", "direct comparisons", "min/max",
                "simple piecewise branches", "integer powers", "fixed constants", "ordinary table selection"],
            "fixedConstantRule": "A fixed constant such as sqrt(3) alone does not make a requirement Complex.",
        },
        "complex": {
            "mode": "COMPLEX_READINESS",
            "triggers": ["square/root operations on variable expressions", "fractional or negative powers",
                "trigonometric or inverse-trigonometric operations", "interpolation",
                "nonlinear/direct structural analysis", "externally delegated engineering calculation procedures",
                "other numerical methods outside the declared basic subset"],
            "shaclShouldVerify": ["applicability", "required inputs", "owners and paths", "datatypes and units",
                "calculation or analysis structures", "table, method, and evidence references",
                "externally computed result/output availability", "explicit DIRECT_CHECK subconstraints"],
            "shaclMustNotBeRequiredTo": "Reconstruct the full nonlinear, interpolated, trigonometric, root/power, or externally delegated engineering calculation.",
        },
        "reclassifiedRequirementIds": RECLASSIFIED,
        "categoryCounts": EXPECTED_CATEGORIES,
        "apiCalls": 0,
    }
    write(TARGET / "evidence/verification_policy_r8.json", policy)
    (TARGET / "evidence/VERIFICATION_POLICY_R8.md").write_text(
        "# R8 verification policy\n\n"
        "This policy is source/formalism-driven and was not derived from model success or failure.\n\n"
        "Static uses direct SHACL verification. Static Calculation uses direct numerical verification only for "
        "the supported basic arithmetic subset: +, -, *, /, comparisons, min/max, simple piecewise branches, "
        "integer powers, fixed constants, and ordinary table selection. A fixed constant such as sqrt(3) alone "
        "does not make a requirement Complex.\n\n"
        "Complex uses COMPLEX_READINESS when direct source compliance requires roots on variable expressions, "
        "fractional or negative powers, trigonometry, interpolation, nonlinear/direct structural analysis, "
        "externally delegated procedures, or another method outside the basic subset. Formulae remain semantic "
        "metadata. SHACL verifies applicability, inputs, owners/paths, datatypes/units, calculation/evidence "
        "structures, outputs, and explicit DIRECT_CHECK residuals; it is not required to reconstruct the full "
        "engineering calculation.\n",
        encoding="utf-8",
    )
    write(TARGET / "evidence/stage1_approved.json", evidence)
    write(TARGET / "requirement_term_index.json", index)
    provenance = immutable_manifest()
    write(TARGET / "provenance/r7_immutable_source_hashes.json", provenance)
    decisions = {
        "lockId": LOCK_ID, "sourceLockId": SOURCE_LOCK_ID, "apiCalls": 0,
        "reclassifiedRequirementIds": RECLASSIFIED,
        "ontologyChanged": False, "registryChanged": False,
        "newCanonicalTerms": [],
        "i2_008EligibilityDecision": "COMPLETE and eligible for COMPLEX_READINESS using existing bow-subregion case/input/result structure.",
        "i2_053EligibilityDecision": "DEFERRED because the existing terms lack a complete canonical owner/path/analysis-case structure for the delegated UR S11.5.4.2 procedure.",
    }
    write(TARGET / "registry/r8_change_decisions.json", decisions)

    bound_relatives = [
        "context/nltl_benchmark_context.jsonld", "evidence/stage1_approved.json",
        "evidence/verification_policy_r8.json", "evidence/VERIFICATION_POLICY_R8.md",
        "ontology/nltl_benchmark_vocabulary.ttl", "ontology/nltl_benchmark_vocabulary.rdf",
        "registry/term_registry.json", "registry/term_registry.csv", "registry/r8_change_decisions.json",
        "requirement_term_index.json", "provenance/r7_immutable_source_hashes.json",
    ]
    bound = {relative: sha(TARGET / relative) for relative in bound_relatives}
    binding = {
        "lockId": LOCK_ID,
        "status": "PRELOCK_OFFLINE_VALIDATION_ONLY",
        "workbook": "Pending R8 workbook",
        "workbookSha256": "",
        "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {"requirement_term_index.json": bound["requirement_term_index.json"]},
    }
    write(TARGET / "r8_prelock_binding.json", binding)
    write(TARGET / "prelock_manifest.json", {
        "lockId": LOCK_ID, "sourceLockId": SOURCE_LOCK_ID,
        "boundArtifacts": bound, "reclassifiedRequirementIds": RECLASSIFIED,
        "categoryCounts": EXPECTED_CATEGORIES, "newCanonicalTerms": [], "apiCalls": 0,
    })
    print(json.dumps({
        "status": "R8_PRELOCK_CREATED", "lockId": LOCK_ID,
        "reclassified": len(RECLASSIFIED), "categories": dict(category_counts),
        "ontologyChanged": sha(TARGET / "ontology/nltl_benchmark_vocabulary.ttl") != sha(SOURCE / "ontology/nltl_benchmark_vocabulary.ttl"),
        "registryChanged": sha(TARGET / "registry/term_registry.json") != sha(SOURCE / "registry/term_registry.json"),
        "r7ImmutableFiles": provenance["fileCount"], "apiCalls": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
