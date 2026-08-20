from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R8"
TARGET = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R9"
SOURCE_LOCK_ID = "VOCAB-LOCK-2026-08-20-R8"
LOCK_ID = "VOCAB-LOCK-2026-08-20-R9"

CATEGORY_CHANGES = {
    # Complex -> Static
    "TRF-029": ("Complex", "Static"), "TRF-040": ("Complex", "Static"),
    "TRF-075": ("Complex", "Static"), "TRF-103": ("Complex", "Static"),
    "IMO-018": ("Complex", "Static"), "IMO-021": ("Complex", "Static"),
    "IMO-027": ("Complex", "Static"), "IMO-028": ("Complex", "Static"),
    "IMO-030": ("Complex", "Static"), "IMO-031": ("Complex", "Static"),
    "IMO-032": ("Complex", "Static"), "IMO-034": ("Complex", "Static"),
    "IMO-048": ("Complex", "Static"), "IMO-049": ("Complex", "Static"),
    "IMO-065": ("Complex", "Static"), "IMO-068": ("Complex", "Static"),
    "IMO-099": ("Complex", "Static"), "IMO-100": ("Complex", "Static"),
    "IMO-101": ("Complex", "Static"), "IMO-103": ("Complex", "Static"),
    "IMO-110": ("Complex", "Static"), "IMO-114": ("Complex", "Static"),
    "IMO-117": ("Complex", "Static"), "IMO-119": ("Complex", "Static"),
    "IMO-123": ("Complex", "Static"), "IMO26-007": ("Complex", "Static"),
    "IMO26-008": ("Complex", "Static"), "IMO26-011": ("Complex", "Static"),
    "IMO26-017": ("Complex", "Static"), "IMO26-018": ("Complex", "Static"),
    # Complex -> Static Calculation
    "TRF-039": ("Complex", "Static Calculation"),
    "I2-003": ("Complex", "Static Calculation"),
    # Complex -> Dynamic
    "TRF-092": ("Complex", "Dynamic"),
    # Physical Test -> Complex
    "TRF-028": ("Physical Test", "Complex"),
    # Static -> Complex
    "TRF-114": ("Static", "Complex"), "I2-013": ("Static", "Complex"),
    "I2-052": ("Static", "Complex"), "I2-062": ("Static", "Complex"),
    # Static -> Static Calculation
    "TRF-130": ("Static", "Static Calculation"),
    # Static Calculation -> Complex
    "TRF-070": ("Static Calculation", "Complex"),
    "TRF-111": ("Static Calculation", "Complex"),
    "TRF-112": ("Static Calculation", "Complex"),
    "TRF-118": ("Static Calculation", "Complex"),
    "TRF-123": ("Static Calculation", "Complex"),
    "IMO-037": ("Static Calculation", "Complex"),
    # Static Calculation -> Dynamic
    "TRF-096": ("Static Calculation", "Dynamic"),
    # Static Calculation -> Static
    "TRF-036": ("Static Calculation", "Static"),
    "TRF-049": ("Static Calculation", "Static"),
    "TRF-077": ("Static Calculation", "Static"),
    "TRF-088": ("Static Calculation", "Static"),
    "I2-009": ("Static Calculation", "Static"),
    "I2-010": ("Static Calculation", "Static"),
    "I2-029": ("Static Calculation", "Static"),
    "I2-048": ("Static Calculation", "Static"),
    "I2-055": ("Static Calculation", "Static"),
    "IMO-108": ("Static Calculation", "Static"),
    "IMO-109": ("Static Calculation", "Static"),
    "IMO-111": ("Static Calculation", "Static"),
    "IMO-115": ("Static Calculation", "Static"),
    "IMO-116": ("Static Calculation", "Static"),
    "IMO-120": ("Static Calculation", "Static"),
    "IMO-124": ("Static Calculation", "Static"),
}

EXPECTED_CATEGORIES = {
    "Static": 192,
    "Static Calculation": 45,
    "Complex": 42,
    "Dynamic": 19,
    "Physical Test": 15,
}

MODE_BY_CATEGORY = {
    "Static": "DIRECT_STATIC",
    "Static Calculation": "DIRECT_CALCULATION",
    "Complex": "COMPLEX_READINESS",
    "Dynamic": "DYNAMIC_DEFERRED",
    "Physical Test": "PHYSICAL_TEST_DEFERRED",
}

# Existing R8 terms that are source-linked elsewhere in the same locked registry.
# These are index additions only; the ontology and registry remain byte-identical.
EXISTING_TERM_INDEX_ADDITIONS = {
    "TRF-103": [
        "bladeFailureSpindleTorqueFactor",
        "leadingEdgeChordPortionAtZeroPointEightRadius",
        "trailingEdgeChordPortionAtZeroPointEightRadius",
    ],
    "TRF-039": [
        "additionalPropulsionPower", "iceLoadAreaFactorCa", "loadLengthParameter",
    ],
    "I2-003": ["upperIceWaterlineLength", "upperIceWaterlineLengthLUI"],
}

# The human-approved category is applied, but these two direct-calculation
# contracts remain deferred because R8 cannot represent the complete obligation.
VOCABULARY_BLOCKERS = {
    "TRF-039": (
        "R8/R9 has the c_a/load-length and propulsion terms, but no canonical property/value path for the "
        "source-required hull-area pressure factor c_p selected from Table 4-3."
    ),
    "I2-003": (
        "R8/R9 has upperIceWaterlineLength and upperIceWaterlineLengthLUI, but no canonical selector/evidence "
        "representation for the source-required unusual-stern-or-bow special-consideration branch."
    ),
}

COMPLEX_IO_REFINEMENTS = {
    "TRF-028": {
        "operandTerms": [],
        "resultTerms": ["engineOutputCoefficientKe", "brashIceChannelResistanceRch"],
        "evidenceTerms": ["alternativeCalculationEvidence", "modelTestEvidence", "approvalStatus",
                          "approvalRevocationStatus", "shipPerformanceExperienceEvidence"],
        "inputsSatisfiedByEvidenceOnly": True,
    },
    "TRF-114": {"resultTerms": ["thrusterResistanceCapacity"]},
    "I2-013": {
        "operandTerms": ["classificationSocietyAccelerationEvidence"],
        "resultTerms": ["inertialLoadDesignConsiderationEvidence"],
    },
    "I2-052": {
        "resultTerms": ["interpolatedLongitudinalDistributionFactor", "interpolatedValue"],
    },
    "I2-062": {
        "operandTerms": ["loadCarryingStringer", "webFrame", "grillageSystem"],
        "resultTerms": ["directCalculationUsed"],
    },
    "TRF-070": {"resultTerms": ["designConditionLocalStrengthCapacity"]},
}

DIRECT_CHECKS = {
    "TRF-114": [{"id": "thrusterResistanceCheck", "mode": "DIRECT_CHECK",
                 "description": "Externally assessed thruster resistance capacity satisfies the impact demand.",
                 "requiredTerms": ["thrusterResistanceCapacity", "thrusterIceImpactDemand"]}],
    "I2-013": [{"id": "inertialLoadEvidenceCheck", "mode": "DIRECT_CHECK",
                "description": "Required acceleration and inertial-load design evidence are present.",
                "requiredTerms": ["classificationSocietyAccelerationEvidence",
                                  "inertialLoadDesignConsiderationEvidence"]}],
    "I2-062": [{"id": "directCalculationRecorded", "mode": "DIRECT_CHECK",
                "description": "The source-required direct calculation is recorded as used.",
                "requiredTerms": ["directCalculationUsed"]}],
    "TRF-070": [{"id": "thrusterLocalStrengthResidual", "mode": "DIRECT_CHECK",
                 "description": "Externally assessed local strength capacity withstands the applicable local ice pressure.",
                 "requiredTerms": ["designConditionLocalStrengthCapacity", "localIcePressure"]}],
    "TRF-111": [{"id": "shaftSafetyFactors", "mode": "DIRECT_CHECK",
                 "description": "Externally calculated load-case safety factors meet the explicit source minima.",
                 "requiredTerms": ["componentYieldSafetyFactor", "fatigueSafetyFactor"]}],
    "TRF-112": [{"id": "combinedLoadYieldResidual", "mode": "DIRECT_CHECK",
                 "description": "Externally calculated bending and torsional safety factors meet the explicit source minima.",
                 "requiredTerms": ["bendingYieldSafetyFactor", "torsionalYieldSafetyFactor"]}],
    "TRF-118": [{"id": "thrusterOperabilityResidual", "mode": "DIRECT_CHECK",
                 "description": "Externally assessed operability is maintained and repair is not required.",
                 "requiredTerms": ["assessmentOperabilityMaintained", "assessmentRepairRequired"]}],
    "TRF-123": [{"id": "occasionalForceStressResidual", "mode": "DIRECT_CHECK",
                 "description": "Externally calculated component stress remains within material yield limits and safety margin.",
                 "requiredTerms": ["occasionalForceComponentStress", "componentMaterialYieldStrength",
                                   "componentYieldSafetyFactor"]}],
    "IMO-037": [{"id": "residualStabilityOutcome", "mode": "DIRECT_CHECK",
                 "description": "Each external loading-condition result satisfies the factor or permitted alternative-instrument outcome.",
                 "requiredTerms": ["residualStabilityFactorSI", "alternativeInstrumentResidualStabilityStatus"]}],
}

POLICY_INDEPENDENCE = (
    "The category policy is based on the source requirement and intrinsic verification method. "
    "It is independent of whether any particular LLM model previously succeeded or failed to generate a SHACL shape."
)


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
        MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R8.xlsx",
        MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R8.lock.json",
        MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R8.sha256",
    ]
    files = {}
    for root in roots:
        candidates = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
        for path in candidates:
            files[str(path.relative_to(MVP))] = sha(path)
    aggregate = hashlib.sha256(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(files.items())).encode()
    ).hexdigest()
    return {"sourceLockId": SOURCE_LOCK_ID, "fileCount": len(files),
            "aggregateSha256": aggregate, "files": files}


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite existing R9 directory: {TARGET}")
    if len(CATEGORY_CHANGES) != 62:
        raise RuntimeError("R9 mapping must contain exactly 62 unique requirements")
    for directory in ("context", "evidence", "ontology", "registry"):
        shutil.copytree(SOURCE / directory, TARGET / directory)
    shutil.copy2(SOURCE / "requirement_term_index.json", TARGET / "requirement_term_index.json")
    (TARGET / "provenance").mkdir(parents=True)
    (TARGET / "validation").mkdir(parents=True)

    evidence = read(TARGET / "evidence/stage1_approved.json")
    index = read(TARGET / "requirement_term_index.json")
    registry = read(TARGET / "registry/term_registry.json")
    available = {term["localName"] for term in registry}
    # Ontology-only infrastructure and controlled values are also canonical.
    from rdflib import Graph, URIRef
    graph = Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    for subject in set(graph.subjects()):
        text = str(subject)
        if text.startswith("https://w3id.org/nltl/vocab#"):
            available.add(text.rsplit("#", 1)[1])

    by_id = {row["id"]: row for row in evidence["requirements"]}
    if set(CATEGORY_CHANGES) - set(by_id):
        raise RuntimeError("R9 mapping contains unknown requirement IDs")
    old_categories = {rid: by_id[rid]["category"] for rid in CATEGORY_CHANGES}
    wrong_old = {rid: (old_categories[rid], expected_old)
                 for rid, (expected_old, _new) in CATEGORY_CHANGES.items()
                 if old_categories[rid] != expected_old}
    if wrong_old:
        raise RuntimeError(f"R8 categories do not match approved R9 mapping: {wrong_old}")

    change_rows = []
    for rid, (old_category, new_category) in CATEGORY_CHANGES.items():
        requirement = by_id[rid]
        contract = index["dependencyContracts"][rid]
        requirement["category"] = new_category
        contract["verificationMode"] = MODE_BY_CATEGORY[new_category]
        # Classification routing does not alter the graph-model schema. Keep
        # the R8 structural-validation level rather than turning legacy direct
        # contracts into owner/path revisions by changing a version number.
        contract["schemaVersion"] = int(contract.get("schemaVersion", 1))
        contract["verificationPolicyBasis"] = POLICY_INDEPENDENCE
        contract["engineeringDecision"] = f"R9_HUMAN_APPROVED_{MODE_BY_CATEGORY[new_category]}"
        contract.setdefault("formulaExpression", "")
        contract.setdefault("comparisonModel", "")
        contract.setdefault("tableModel", "")
        for field in ("applicabilityTerms", "operandTerms", "resultTerms", "comparisonTerms",
                      "relationshipTerms", "evidenceTerms", "controlledValueTerms", "timeTerms", "modelPaths"):
            contract.setdefault(field, [])

        additions = EXISTING_TERM_INDEX_ADDITIONS.get(rid, [])
        absent = sorted(set(additions) - available)
        if absent:
            raise RuntimeError(f"Approved R9 index additions are absent from R8 vocabulary for {rid}: {absent}")
        index["requirements"][rid] = sorted(set(index["requirements"][rid]) | set(additions))
        source_obligation = requirement.get("normalizedRequirement") or requirement.get("sourceText") or ""
        if not source_obligation:
            raise RuntimeError(f"Requirement lacks a source-grounded normalized obligation: {rid}")
        index.setdefault("semanticObligations", {})[rid] = [source_obligation]

        if new_category == "Static":
            contract["directConstraintTerms"] = list(index["requirements"][rid])
            contract["comparisonModel"] = contract.get("comparisonModel") or source_obligation
            contract["formulaExecutionRequired"] = False
            contract["requiredModelFields"] = ["verificationMode", "comparisonModel", "directConstraintTerms"]
            contract["status"] = "COMPLETE"
            contract["auditFlags"] = []
            contract["observedFailureStatus"] = ""
            contract.pop("deferredReason", None)
            requirement["activeStatus"] = "Stage 2 candidate - direct static"
            requirement["codability"] = "Direct static"
        elif new_category == "Static Calculation":
            contract["directConstraintTerms"] = list(index["requirements"][rid])
            contract["comparisonModel"] = contract.get("comparisonModel") or source_obligation
            contract["formulaExecutionRequired"] = True
            contract["requiredModelFields"] = ["verificationMode", "comparisonModel", "directConstraintTerms"]
            if rid in VOCABULARY_BLOCKERS:
                contract["status"] = "DEFERRED_VOCABULARY_INSUFFICIENT"
                contract["deferredReason"] = VOCABULARY_BLOCKERS[rid]
                requirement["activeStatus"] = "Deferred - existing vocabulary insufficient"
                requirement["codability"] = "Deferred"
            else:
                contract["status"] = "COMPLETE"
                contract["auditFlags"] = []
                contract["observedFailureStatus"] = ""
                contract.pop("deferredReason", None)
                requirement["activeStatus"] = "Stage 2 candidate - direct calculation"
                requirement["codability"] = "Direct calculation"
        elif new_category == "Complex":
            for field, value in COMPLEX_IO_REFINEMENTS.get(rid, {}).items():
                contract[field] = value
            contract["informationalSourceFormula"] = (
                contract.get("formulaExpression") or contract.get("comparisonModel") or source_obligation
            )
            contract["formulaExecutionRequired"] = False
            contract["directCheckSubconstraints"] = DIRECT_CHECKS.get(rid, contract.get("directCheckSubconstraints", []))
            required = ["verificationMode", "resultTerms"]
            if not contract.get("inputsSatisfiedByEvidenceOnly"):
                required.append("operandTerms")
            contract["requiredModelFields"] = required
            contract["status"] = "COMPLETE"
            contract["auditFlags"] = []
            contract["observedFailureStatus"] = ""
            contract.pop("deferredReason", None)
            requirement["activeStatus"] = "Stage 2 candidate - complex readiness"
            requirement["codability"] = "Complex readiness"
        elif new_category == "Dynamic":
            contract["status"] = "DEFERRED_DYNAMIC_RUNTIME"
            contract["formulaExecutionRequired"] = False
            contract["deferredReason"] = (
                "Dynamic verification remains outside the current static SHACL generation scope; "
                "R9 does not introduce a runtime solver."
            )
            requirement["activeStatus"] = "Deferred - observation/history/simulation design required"
            requirement["codability"] = "Deferred"
        else:
            raise RuntimeError(f"Unexpected target category in approved mapping: {new_category}")

        declared = set(contract.get("directConstraintTerms", []))
        for key in ("applicabilityTerms", "operandTerms", "resultTerms", "comparisonTerms",
                    "relationshipTerms", "evidenceTerms", "controlledValueTerms", "timeTerms"):
            declared.update(contract.get(key, []))
        for check in contract.get("directCheckSubconstraints", []):
            declared.update(check.get("requiredTerms", []))
        absent = sorted(declared - available)
        if absent:
            raise RuntimeError(f"R9 contract references absent vocabulary for {rid}: {absent}")
        index["requirements"][rid] = sorted(set(index["requirements"][rid]) | declared)

        change_rows.append({
            "requirementId": rid,
            "oldCategory": old_category,
            "newCategory": new_category,
            "verificationMode": contract["verificationMode"],
            "contractStatus": contract["status"],
            "generationEligibility": "DEFERRED" if contract["status"] != "COMPLETE" or new_category in {"Dynamic", "Physical Test"} else "ELIGIBLE",
            "vocabularySufficient": rid not in VOCABULARY_BLOCKERS,
            "deferredReason": contract.get("deferredReason", ""),
        })

    # Preserve R8 semantics for all unchanged categories while making routing explicit.
    for requirement in evidence["requirements"]:
        rid = requirement["id"]
        if rid in CATEGORY_CHANGES:
            continue
        contract = index["dependencyContracts"][rid]
        if requirement["category"] == "Static" and contract.get("status") == "COMPLETE":
            contract.setdefault("verificationMode", "DIRECT_STATIC")
        elif requirement["category"] == "Static Calculation" and contract.get("status") == "COMPLETE":
            contract.setdefault("verificationMode", "DIRECT_CALCULATION")
        elif requirement["category"] == "Dynamic":
            contract.setdefault("verificationMode", "DYNAMIC_DEFERRED")
        elif requirement["category"] == "Physical Test":
            contract.setdefault("verificationMode", "PHYSICAL_TEST_DEFERRED")

    counts = dict(Counter(row["category"] for row in evidence["requirements"]))
    if counts != EXPECTED_CATEGORIES:
        raise RuntimeError(f"Unexpected R9 category counts: {counts}")
    r8_evidence = read(SOURCE / "evidence/stage1_approved.json")
    r8_by_id = {row["id"]: row for row in r8_evidence["requirements"]}
    actual_changed = {rid for rid in by_id if by_id[rid]["category"] != r8_by_id[rid]["category"]}
    if actual_changed != set(CATEGORY_CHANGES):
        raise RuntimeError("R9 category delta is not exactly the approved 62 requirements")

    evidence["summary"]["requirementsByCategory"] = EXPECTED_CATEGORIES
    evidence["summary"]["activationCounts"] = dict(Counter(row["activeStatus"] for row in evidence["requirements"]))
    evidence["summary"]["verificationPolicyLockId"] = LOCK_ID
    evidence["summary"]["verificationPolicy"] = "R9 complete five-category source/intrinsic-method policy"
    index["sourceLockId"] = LOCK_ID
    index["version"] = "9.0"

    policy = {
        "lockId": LOCK_ID,
        "status": "FROZEN_FIVE_CATEGORY_POLICY",
        "independenceStatement": POLICY_INDEPENDENCE,
        "categories": {
            "Static": {"verificationMode": "DIRECT_STATIC", "definition":
                "Direct verification from static RDF design state without deriving a new engineering result."},
            "Static Calculation": {"verificationMode": "DIRECT_CALCULATION", "supportedSubset":
                ["addition", "subtraction", "multiplication", "division", "direct comparisons", "min/max",
                 "simple piecewise branches", "integer powers", "fixed constants", "ordinary table lookup/selection"],
                "fixedConstantRule": "A fixed constant such as sqrt(3) does not make a requirement Complex."},
            "Complex": {"verificationMode": "COMPLEX_READINESS", "fullProcedureReconstructed": False,
                "checks": ["applicability", "required inputs", "owners and paths", "units and datatypes",
                           "calculation or analysis case", "method or evidence", "required outputs/results",
                           "explicit DIRECT_CHECK residuals"]},
            "Dynamic": {"verificationMode": "DYNAMIC_DEFERRED",
                "definition": "Intrinsic time, sequence, operating-state, event-response, or transient/runtime behavior."},
            "Physical Test": {"verificationMode": "PHYSICAL_TEST_DEFERRED",
                "definition": "Intrinsic evidence from an actual physical test, trial, inspection, or measured demonstration."},
        },
        "reclassifiedRequirementIds": sorted(CATEGORY_CHANGES),
        "categoryCounts": EXPECTED_CATEGORIES,
        "apiCalls": 0,
    }
    write(TARGET / "evidence/stage1_approved.json", evidence)
    write(TARGET / "requirement_term_index.json", index)
    write(TARGET / "evidence/verification_policy_r9.json", policy)
    (TARGET / "evidence/VERIFICATION_POLICY_R9.md").write_text(
        "# R9 five-category verification policy\n\n" + POLICY_INDEPENDENCE + "\n\n"
        "- Static -> DIRECT_STATIC: direct static RDF checks without deriving an engineering result.\n"
        "- Static Calculation -> DIRECT_CALCULATION: +, -, *, /, comparisons, min/max, simple piecewise "
        "branches, integer powers, fixed constants, and ordinary table lookup/selection. A fixed sqrt(3) "
        "constant alone is not Complex.\n"
        "- Complex -> COMPLEX_READINESS: verify applicability, inputs, owners/paths, units/datatypes, analysis "
        "case/method/evidence, outputs/results, and explicit DIRECT_CHECK residuals; do not reconstruct the "
        "advanced engineering procedure.\n"
        "- Dynamic -> DYNAMIC_DEFERRED: preserve runtime/transient semantics; R9 adds no runtime solver.\n"
        "- Physical Test -> PHYSICAL_TEST_DEFERRED: preserve physical evidence semantics; R9 adds no test solver.\n",
        encoding="utf-8",
    )
    write(TARGET / "registry/r9_classification_change_decisions.json", {
        "lockId": LOCK_ID, "sourceLockId": SOURCE_LOCK_ID, "changeCount": len(change_rows),
        "changes": sorted(change_rows, key=lambda row: row["requirementId"]),
        "vocabularyBlockers": VOCABULARY_BLOCKERS,
        "ontologyChanged": False, "registryChanged": False, "newCanonicalTerms": [], "apiCalls": 0,
    })
    provenance = immutable_manifest()
    write(TARGET / "provenance/r8_immutable_source_hashes.json", provenance)

    bound_relatives = [
        "context/nltl_benchmark_context.jsonld", "evidence/stage1_approved.json",
        "evidence/verification_policy_r9.json", "evidence/VERIFICATION_POLICY_R9.md",
        "ontology/nltl_benchmark_vocabulary.ttl", "ontology/nltl_benchmark_vocabulary.rdf",
        "registry/term_registry.json", "registry/term_registry.csv",
        "registry/r9_classification_change_decisions.json", "requirement_term_index.json",
        "provenance/r8_immutable_source_hashes.json",
    ]
    bound = {relative: sha(TARGET / relative) for relative in bound_relatives}
    write(TARGET / "r9_prelock_binding.json", {
        "lockId": LOCK_ID, "status": "PRELOCK_OFFLINE_VALIDATION_ONLY",
        "workbook": "Pending R9 workbook", "workbookSha256": "",
        "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {"requirement_term_index.json": bound["requirement_term_index.json"]},
    })
    write(TARGET / "prelock_manifest.json", {
        "lockId": LOCK_ID, "sourceLockId": SOURCE_LOCK_ID,
        "boundArtifacts": bound, "categoryChanges": CATEGORY_CHANGES,
        "categoryCounts": EXPECTED_CATEGORIES, "newCanonicalTerms": [], "apiCalls": 0,
    })
    print(json.dumps({
        "status": "R9_PRELOCK_CREATED", "lockId": LOCK_ID,
        "categoryChanges": len(change_rows), "categoryCounts": counts,
        "vocabularyBlockers": sorted(VOCABULARY_BLOCKERS),
        "ontologyChanged": sha(TARGET / "ontology/nltl_benchmark_vocabulary.ttl") != sha(SOURCE / "ontology/nltl_benchmark_vocabulary.ttl"),
        "registryChanged": sha(TARGET / "registry/term_registry.json") != sha(SOURCE / "registry/term_registry.json"),
        "r8ImmutableFiles": provenance["fileCount"], "apiCalls": 0,
    }, indent=2))


if __name__ == "__main__":
    main()
