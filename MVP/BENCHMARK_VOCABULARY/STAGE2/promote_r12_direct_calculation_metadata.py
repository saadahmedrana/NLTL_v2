from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


MVP = Path(__file__).resolve().parents[2]
PIPE = MVP / "SHACL_GENERATION_PIPELINE"
SOURCE = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R11"
TARGET = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R12"
SOURCE_LOCK_ID = "VOCAB-LOCK-2026-08-21-R11"
LOCK_ID = "VOCAB-LOCK-2026-08-21-R12"
EXPECTED_COUNTS = {"Static": 191, "Static Calculation": 43, "Complex": 45,
                   "Dynamic": 19, "Physical Test": 15}

CALCULATION_METADATA = {
    "I2-011": (["bowDesignForceMethodI2Point3Point2Point1PartIii", "bowDesignForceMethodI2Point3Point2Point1PartIv", "shapeCoefficient", "loadPatchAspectRatio"], ["bowDesignForce"]),
    "I2-047": (["gaugedThickness", "netThickness"], ["steelRenewalRequired"]),
    "IMO-012": (["lowestMdlt"], ["polarServiceTemperature"]),
    "IMO-019": (["lowestMdlt"], ["polarServiceTemperature"]),
    "IMO-033": (["continuousSurfaceProjectedArea", "continuousSurfaceStaticMoment"], ["discontinuousSurfaceProjectedArea", "discontinuousSurfaceStaticMoment"]),
    "IMO-075": (["personsOnBoard"], ["availableSurvivalEquipmentCapacity"]),
    "IMO-077": (["personsCapacityRequirement", "additionalEquipmentCapacityRequirement", "loadedSurvivalCraftRequirement"], ["survivalCraftAvailableCapacity", "launchingApplianceCapacity"]),
    "IMO-079": (["personsOnBoard", "maximumExpectedRescueTime"], ["availableEmergencyRationPerson"]),
    "TRF-016": (["displacementAtUpperIceWaterline", "levelIceThickness"], ["forwardDraught"]),
    "TRF-018": (["calculatedRequiredPower"], ["maximumContinuousRatingPower"]),
    "TRF-027": (["shipLength", "iceClassDraught", "shipBreadth"], ["clampedHullGeometryTerm"]),
    "TRF-031": (["yieldPoint", "combinedBendingShearStress"], ["yieldShearStress"]),
    "TRF-037": (["shipSizeEngineOutputCoefficientA", "shipSizeEngineOutputCoefficientK", "shipSizeEngineOutputCoefficientB", "iceClassFactorCp", "iceLoadAreaFactorCa", "nominalIcePressureP0"], ["shipSizeEngineOutputFactorCd", "icePressure"]),
    "TRF-042": (["designIceLoadHeight", "spacing"], ["longitudinalPlatingFactorF2"]),
    "TRF-044": (["icePressure", "spacing", "designIceLoadHeight", "span", "frameBoundaryConditionFactorM0", "yieldStrength"], ["frameMomentFactorMt", "sectionModulus", "requiredShearArea"]),
    "TRF-048": (["icePressure", "designIceLoadHeight", "spacing", "span", "frameMomentFactorM", "yieldStrength"], ["longitudinalFrameLoadDistributionFactorF4", "sectionModulus", "requiredShearArea"]),
    "TRF-053": (["icePressure", "designIceLoadHeight", "span", "frameMomentFactorM", "yieldStrength"], ["designLineLoad", "sectionModulus", "requiredShearArea"]),
    "TRF-054": (["icePressure", "designIceLoadHeight", "span", "frameMomentFactorM", "yieldStrength", "distanceToIceBelt", "stringerSpan"], ["designLineLoad", "outsideIceBeltFactor", "sectionModulus", "requiredShearArea"]),
    "TRF-057": (["icePressure", "iceLoadHeight", "webFrameSpacing"], ["webFrameIceLoad"]),
    "TRF-058": (["iceLoadForce", "stringerOutsideIceBeltHeight", "stringerSpan"], ["adjustedIceLoadForce"]),
    "TRF-059": (["maximumCalculatedShearForce", "webFrameShearFactorAlpha", "yieldStrength", "freeFlangeToWebAreaRatio"], ["requiredShearArea"]),
    "TRF-081": (["forwardBladeForce", "backwardBladeForce", "hydrodynamicBollardThrust"], ["forwardIceThrust", "backwardIceThrust", "forwardPropellerShaftDesignThrust", "backwardPropellerShaftDesignThrust", "propellerShaftDesignThrust"]),
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def immutable_manifest() -> dict:
    roots = [SOURCE, MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-21-R11.xlsx",
             MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-21-R11.lock.json",
             MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-21-R11.sha256"]
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
        raise FileExistsError(f"Refusing to overwrite existing R12 directory: {TARGET}")
    provenance = immutable_manifest()
    for directory in ("context", "evidence", "few_shots", "ontology", "registry"):
        shutil.copytree(SOURCE / directory, TARGET / directory)
    shutil.copy2(SOURCE / "requirement_term_index.json", TARGET / "requirement_term_index.json")
    (TARGET / "provenance").mkdir(parents=True)
    (TARGET / "validation").mkdir(parents=True)

    evidence = read(TARGET / "evidence/stage1_approved.json")
    source_evidence = read(SOURCE / "evidence/stage1_approved.json")
    by_id = {row["id"]: row for row in evidence["requirements"]}
    before = {row["id"]: row for row in source_evidence["requirements"]}
    index = read(TARGET / "requirement_term_index.json")

    # The only approved category change.
    if by_id["TRF-055"]["category"] != "Static Calculation":
        raise RuntimeError("Unexpected R11 category for TRF-055")
    by_id["TRF-055"]["category"] = "Static"
    by_id["TRF-055"]["activeStatus"] = "Stage 2 candidate - direct/deterministic static verification"
    trf055 = index["dependencyContracts"]["TRF-055"]
    trf055.update(
        verificationMode="DIRECT_STATIC",
        encodingPattern="Direct comparison with approved conditional exception",
        engineeringDecision="R12_APPROVED_DIRECT_STATIC_EXISTING_VALUE_COMPARISONS",
        operandTerms=[], resultTerms=[],
        applicabilityTerms=["abreastOfHatch", "narrowDeckStrip", "servesAsIceStringer", "veryLongHatchOpening"],
        comparisonTerms=["actualSectionModulus", "requiredSectionModulus", "actualShearArea", "requiredShearArea",
                         "permittedReducedLineLoad", "reducedLineLoadApprovedByClassificationSociety"],
        directConstraintTerms=list(index["requirements"]["TRF-055"]),
        comparisonModel=("actualSectionModulus >= requiredSectionModulus AND actualShearArea >= requiredShearArea. "
                         "For the approved very-long-hatch reduced-line-load exception, "
                         "0.10 <= permittedReducedLineLoad < 0.15 AND "
                         "reducedLineLoadApprovedByClassificationSociety = true."),
        requiredModelFields=["verificationMode", "comparisonModel", "directConstraintTerms"],
    )

    # Exact numerical operand/result metadata supplied by the user.
    for rid, (operands, results) in CALCULATION_METADATA.items():
        contract = index["dependencyContracts"][rid]
        if contract.get("verificationMode") != "DIRECT_CALCULATION" or contract.get("status") != "COMPLETE":
            raise RuntimeError(f"Unexpected R11 calculation contract state for {rid}")
        contract["operandTerms"] = operands
        contract["resultTerms"] = results
        contract["requiredModelFields"] = sorted(set(contract.get("requiredModelFields", [])) |
                                                  {"operandTerms", "resultTerms", "comparisonModel"})
        missing = sorted(set(operands + results) - set(index["requirements"][rid]))
        if rid == "TRF-048" and missing == ["requiredShearArea"]:
            index["requirements"][rid] = sorted(set(index["requirements"][rid]) | {"requiredShearArea"})
            index["termOwners"][rid]["requiredShearArea"] = "longitudinalFrame"
            missing = []
        if missing:
            raise RuntimeError(f"Specified calculation metadata is absent from the R11 index for {rid}: {missing}")

    # Remove only the stale TRF-059 requirement-specific sectionModulus reference.
    rid = "TRF-059"
    index["requirements"][rid] = [term for term in index["requirements"][rid] if term != "sectionModulus"]
    index["termOwners"][rid].pop("sectionModulus", None)
    for field in ("legacyIndexedTerms", "directConstraintTerms", "applicabilityTerms", "comparisonTerms",
                  "relationshipTerms", "evidenceTerms", "controlledValueTerms", "timeTerms"):
        if isinstance(index["dependencyContracts"][rid].get(field), list):
            index["dependencyContracts"][rid][field] = [term for term in index["dependencyContracts"][rid][field]
                                                         if term != "sectionModulus"]
    index["dependencyContracts"][rid]["engineeringDecision"] = "R12_REMOVE_STALE_SECTION_MODULUS_INDEX_TERM"

    counts = dict(Counter(row["category"] for row in evidence["requirements"]))
    if counts != EXPECTED_COUNTS:
        raise RuntimeError(f"Unexpected R12 category counts: {counts}")
    changed = {rid for rid in by_id if by_id[rid]["category"] != before[rid]["category"]}
    if changed != {"TRF-055"}:
        raise RuntimeError(f"Unapproved category changes: {sorted(changed)}")

    registry_before = (SOURCE / "registry/term_registry.json").read_bytes()
    ontology_ttl_before = (SOURCE / "ontology/nltl_benchmark_vocabulary.ttl").read_bytes()
    ontology_rdf_before = (SOURCE / "ontology/nltl_benchmark_vocabulary.rdf").read_bytes()
    if (TARGET / "registry/term_registry.json").read_bytes() != registry_before or \
       (TARGET / "ontology/nltl_benchmark_vocabulary.ttl").read_bytes() != ontology_ttl_before or \
       (TARGET / "ontology/nltl_benchmark_vocabulary.rdf").read_bytes() != ontology_rdf_before:
        raise RuntimeError("R12 unexpectedly changed ontology/registry vocabulary")

    evidence["summary"]["requirementsByCategory"] = EXPECTED_COUNTS
    evidence["summary"]["activationCounts"] = dict(Counter(row["activeStatus"] for row in evidence["requirements"]))
    evidence["summary"]["verificationPolicyLockId"] = LOCK_ID
    evidence["summary"]["verificationPolicy"] = "R12 DIRECT_CALCULATION contract-metadata cleanup"
    index["sourceLockId"] = LOCK_ID
    index["version"] = "12.0"
    write(TARGET / "evidence/stage1_approved.json", evidence)
    write(TARGET / "requirement_term_index.json", index)

    policy = read(TARGET / "evidence/verification_policy_r11.json")
    policy.update(lockId=LOCK_ID, categoryCounts=EXPECTED_COUNTS)
    policy["r12CategoryChanges"] = {"TRF-055": ["Static Calculation", "Static"]}
    policy["directCalculationCompletenessRule"] = {
        "appliesWhen": "status = COMPLETE and verificationMode = DIRECT_CALCULATION",
        "requiredNonEmptyFields": ["operandTerms", "resultTerms", "comparisonModel"],
        "automaticMetadataInventionPermitted": False,
    }
    write(TARGET / "evidence/verification_policy_r12.json", policy)
    (TARGET / "evidence/VERIFICATION_POLICY_R12.md").write_text(
        "# R12 verification policy provenance\n\nR12 mechanically corrects TRF-055 and supplied DIRECT_CALCULATION metadata. "
        "Every future COMPLETE DIRECT_CALCULATION contract must contain non-empty operandTerms, resultTerms, and comparisonModel. "
        "Validation must stop rather than invent missing metadata. No API transport or retry behavior changed.\n",
        encoding="utf-8",
    )
    decisions = {
        "lockId": LOCK_ID, "sourceLockId": SOURCE_LOCK_ID,
        "categoryChanges": {"TRF-055": ["Static Calculation", "Static"]},
        "metadataRequirements": sorted(CALCULATION_METADATA),
        "staleIndexedTermRemoval": {"requirementId": "TRF-059", "localName": "sectionModulus"},
        "newCanonicalTerms": [], "removedCanonicalTerms": [], "modifiedCanonicalTerms": {},
        "apiTransportChanges": 0, "apiCalls": 0,
    }
    write(TARGET / "registry/r12_direct_calculation_metadata_decisions.json", decisions)
    write(TARGET / "provenance/r11_immutable_source_hashes.json", provenance)

    bound_relatives = [
        "context/nltl_benchmark_context.jsonld", "evidence/stage1_approved.json",
        "evidence/verification_policy_r12.json", "evidence/VERIFICATION_POLICY_R12.md",
        "ontology/nltl_benchmark_vocabulary.ttl", "ontology/nltl_benchmark_vocabulary.rdf",
        "registry/term_registry.json", "registry/term_registry.csv",
        "registry/r12_direct_calculation_metadata_decisions.json", "requirement_term_index.json",
        "provenance/r11_immutable_source_hashes.json", "few_shots/few_shot_pairs.jsonl",
        "few_shots/catalog.json", "few_shots/validation_report.json",
    ]
    bound = {relative: sha(TARGET / relative) for relative in bound_relatives}
    write(TARGET / "r12_prelock_binding.json", {
        "lockId": LOCK_ID, "status": "PRELOCK_OFFLINE_VALIDATION_ONLY",
        "workbook": "Pending R12 workbook", "workbookSha256": "",
        "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {"requirement_term_index.json": bound["requirement_term_index.json"]},
    })
    write(TARGET / "prelock_manifest.json", {
        "lockId": LOCK_ID, "sourceLockId": SOURCE_LOCK_ID, "boundArtifacts": bound,
        "categoryChanges": decisions["categoryChanges"], "categoryCounts": EXPECTED_COUNTS,
        "newCanonicalTerms": [], "removedCanonicalTerms": [], "modifiedCanonicalTerms": {}, "apiCalls": 0,
    })
    print(json.dumps({"status": "R12_PRELOCK_CREATED", "lockId": LOCK_ID,
                      "categoryCounts": counts, "metadataContracts": len(CALCULATION_METADATA),
                      "vocabularyDelta": 0, "r11ImmutableFiles": provenance["fileCount"], "apiCalls": 0}, indent=2))


if __name__ == "__main__":
    main()
