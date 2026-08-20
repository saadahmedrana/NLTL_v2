from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL, SKOS


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R9"
TARGET = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R10"
SOURCE_LOCK_ID = "VOCAB-LOCK-2026-08-20-R9"
LOCK_ID = "VOCAB-LOCK-2026-08-20-R10"
CANONICAL = "https://w3id.org/nltl/vocab#"
NLTL = Namespace(CANONICAL)
EXPECTED_COUNTS = {"Static": 194, "Static Calculation": 43, "Complex": 42,
                   "Dynamic": 19, "Physical Test": 15}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def immutable_manifest() -> dict:
    roots = [SOURCE, MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R9.xlsx",
             MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R9.lock.json",
             MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R9.sha256"]
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


def new_term() -> dict:
    return {
        "aliases": [], "conceptId": "VOC-R10-0001", "confidence": "High", "datatype": "",
        "evidenceExcerpt": "[TRF-078] The number of load cycles per propeller blade in the load spectrum shall be N_ice = k_1*k_2*k_3*N_class*n_n (6.14), where N_class is given in Table 6-6 and the propeller location factor k_1 is given in Table 6-7.",
        "haithamUri": "", "iri": CANONICAL + "tableLookupPropellerLocation",
        "kind": "ObjectProperty", "label": "Table lookup propeller location",
        "localName": "tableLookupPropellerLocation",
        "mappingStatus": "No external equivalence claimed; source-grounded R10 benchmark relationship.",
        "module": "machinery", "nameQaStatus": "Passed - ASCII-only lowerCamelCase and collision review",
        "namingBasis": "Verified Table 6-7 propeller-location selection-key role",
        "namingRule": "N4/N5 - singular ASCII lowerCamelCase; relationship direction is explicit.",
        "normalizedDefinition": "NORMALIZED (R10): binds a table lookup case to the applicable propeller-location controlled value used to select the Table 6-7 factor.",
        "parentOrRange": CANONICAL + "propellerLocationValue", "quantityKindLabel": "",
        "requirements": ["TRF-078"], "roleDecision": "Typed relationship path",
        "sourceConceptIds": ["VOC-R10-0001"], "sourceRefs": "TRF-078 | TRAFICOM p.36 | 6.5.1.9",
        "stage1LocalNames": ["tableLookupPropellerLocation"], "stage2UnitEvidence": "",
        "unitDecisionStatus": "Not a quantity property", "unitIri": "", "unitSymbol": "",
    }


def set_contract(index: dict, rid: str, **changes) -> None:
    contract = index["dependencyContracts"][rid]
    contract.update(changes)
    contract["status"] = "COMPLETE"
    contract["auditFlags"] = []
    contract["observedFailureStatus"] = ""
    contract.pop("deferredReason", None)


def main() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite existing R10 directory: {TARGET}")
    provenance = immutable_manifest()
    for directory in ("context", "evidence", "few_shots", "ontology", "registry"):
        shutil.copytree(SOURCE / directory, TARGET / directory)
    shutil.copy2(SOURCE / "requirement_term_index.json", TARGET / "requirement_term_index.json")
    (TARGET / "provenance").mkdir(parents=True)
    (TARGET / "validation").mkdir(parents=True)

    evidence = read(TARGET / "evidence/stage1_approved.json")
    index = read(TARGET / "requirement_term_index.json")
    registry = read(TARGET / "registry/term_registry.json")
    by_id = {row["id"]: row for row in evidence["requirements"]}
    r9_index = read(SOURCE / "requirement_term_index.json")
    r9_evidence = read(SOURCE / "evidence/stage1_approved.json")

    # Exact vocabulary delta: one modified domain and one new relationship.
    section = next(t for t in registry if t["localName"] == "sectionCalculationCaseStructuralMember")
    section["requirements"] = sorted(set(section["requirements"]) | {"I2-029"})
    section["sourceRefs"] += "; I2-029 | IACS_UR_I2 p.10 | I2.5.6"
    section["normalizedDefinition"] = (
        "NORMALIZED (R10): links a calculation case to the structural member whose section inclusion, "
        "shear-area inclusion, and fitted-flange conditions are evaluated."
    )
    registry.append(new_term())
    registry.sort(key=lambda term: term["localName"])

    graph = Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    section_iri = NLTL.sectionCalculationCaseStructuralMember
    graph.remove((section_iri, RDFS.domain, None))
    graph.add((section_iri, RDFS.domain, NLTL.calculationCase))
    graph.add((section_iri, NLTL.sourceRequirementId, Literal("I2-029")))
    table_prop = NLTL.tableLookupPropellerLocation
    graph.add((table_prop, RDF.type, OWL.ObjectProperty))
    graph.add((table_prop, RDFS.label, Literal("Table lookup propeller location", lang="en")))
    graph.add((table_prop, SKOS.prefLabel, Literal("Table lookup propeller location", lang="en")))
    graph.add((table_prop, RDFS.domain, NLTL.tableLookupCase))
    graph.add((table_prop, RDFS.range, NLTL.propellerLocationValue))
    graph.add((table_prop, SKOS.definition, Literal(
        "NORMALIZED (R10): binds a table lookup case to the applicable propeller-location controlled value used to select the Table 6-7 factor.", lang="en")))
    graph.add((table_prop, NLTL.draftConceptId, Literal("VOC-R10-0001")))
    graph.add((table_prop, NLTL.sourceRequirementId, Literal("TRF-078")))
    graph.serialize(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.serialize(TARGET / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")

    context = read(TARGET / "context/nltl_benchmark_context.jsonld")
    context["@context"]["tableLookupPropellerLocation"] = {
        "@id": "nltl:tableLookupPropellerLocation", "@type": "@id"
    }
    context["@context"] = dict(sorted(context["@context"].items(), key=lambda item: item[0]))
    write(TARGET / "context/nltl_benchmark_context.jsonld", context)

    # I2-029: calculation-case-specific member pairing and only the approved Boolean obligations.
    i2029_terms = [
        "attachedShellPlatingExcludedFromShearArea", "attachedShellPlatingIncludedInSectionModulus",
        "calculationCase", "flangeFitted", "flangeMaterialIncludedInShearArea",
        "hasCalculationCase", "sectionCalculationCaseStructuralMember", "ship", "structuralMember",
    ]
    index["requirements"]["I2-029"] = i2029_terms
    index["requirementTargetOwner"]["I2-029"] = "ship"
    index["termOwners"]["I2-029"] = {
        "attachedShellPlatingExcludedFromShearArea": "calculationCase",
        "attachedShellPlatingIncludedInSectionModulus": "calculationCase",
        "calculationCase": "calculationCase", "flangeFitted": "structuralMember",
        "flangeMaterialIncludedInShearArea": "calculationCase", "hasCalculationCase": "ship",
        "sectionCalculationCaseStructuralMember": "calculationCase", "ship": "ship",
        "structuralMember": "structuralMember",
    }
    i2029_obligation = (
        "For each applicable calculationCase: attachedShellPlatingIncludedInSectionModulus is true; "
        "attachedShellPlatingExcludedFromShearArea is true; flangeMaterialIncludedInShearArea is explicitly "
        "represented; and if flangeMaterialIncludedInShearArea is true, the structuralMember linked through "
        "sectionCalculationCaseStructuralMember has flangeFitted true."
    )
    index["semanticObligations"]["I2-029"] = [i2029_obligation]
    set_contract(index, "I2-029", schemaVersion=2, verificationMode="DIRECT_STATIC",
        engineeringDecision="R10_APPROVED_CASE_TO_MEMBER_PATH_CORRECTION",
        ownerClasses=["ship", "calculationCase", "structuralMember"],
        directConstraintTerms=i2029_terms,
        applicabilityTerms=[], operandTerms=[], resultTerms=[],
        comparisonTerms=["attachedShellPlatingIncludedInSectionModulus",
                         "attachedShellPlatingExcludedFromShearArea",
                         "flangeMaterialIncludedInShearArea", "flangeFitted"],
        relationshipTerms=["hasCalculationCase", "sectionCalculationCaseStructuralMember"],
        modelPaths=[
            {"fromOwner": "ship", "via": "hasCalculationCase", "toOwner": "calculationCase"},
            {"fromOwner": "calculationCase", "via": "sectionCalculationCaseStructuralMember", "toOwner": "structuralMember"},
        ], evidenceTerms=[], controlledValueTerms=[], timeTerms=[], formulaExpression="",
        formulaExecutionRequired=False, encodingPattern="Conditional/applicability constraint",
        comparisonModel=i2029_obligation,
        conditionalRules=[{
            "if": "flangeMaterialIncludedInShearArea = true on the calculationCase",
            "then": "the structuralMember linked by sectionCalculationCaseStructuralMember has flangeFitted = true",
        }], requiredModelFields=["verificationMode", "comparisonModel", "relationshipTerms", "modelPaths"])

    # TRF-078: two explicit lookup cases plus unchanged basic formula.
    trf078_terms = [
        "hasTableLookupCase", "iceClass", "iceClassValue", "iceLoadCycleCoefficientK2",
        "iceLoadCycleCoefficientK3", "iceLoadCycleCount", "propellerBladeLoadSpectrumCountFactor",
        "propellerLocationValue", "selectedIceClassCycleCount", "selectedPropellerLocationFactor",
        "ship", "tableLookupCase", "tableLookupPropellerLocation", "tableReference",
        "tableReferenceValue", "traficomTable6Dash6", "traficomTable6Dash7",
    ]
    index["requirements"]["TRF-078"] = trf078_terms
    index["requirementTargetOwner"]["TRF-078"] = "ship"
    index["termOwners"]["TRF-078"] = {
        "hasTableLookupCase": "ship", "iceClass": "tableLookupCase",
        "selectedIceClassCycleCount": "tableLookupCase",
        "selectedPropellerLocationFactor": "tableLookupCase",
        "tableLookupPropellerLocation": "tableLookupCase", "tableReference": "tableLookupCase",
        "iceLoadCycleCount": "ship", "iceLoadCycleCoefficientK2": "ship",
        "iceLoadCycleCoefficientK3": "ship", "propellerBladeLoadSpectrumCountFactor": "ship",
    }
    trf078_obligation = (
        "For Table 6-6, a tableLookupCase has tableReference traficomTable6Dash6, uses iceClass as its "
        "selection key, and has selectedIceClassCycleCount. For Table 6-7, a tableLookupCase has "
        "tableReference traficomTable6Dash7, uses tableLookupPropellerLocation as its selection key, and has "
        "selectedPropellerLocationFactor. Each applicable lookup case is typed tableLookupCase and has exactly "
        "one tableReference. Compute N_ice = k1 * k2 * k3 * N_class * n_n."
    )
    index["semanticObligations"]["TRF-078"] = [trf078_obligation]
    set_contract(index, "TRF-078", schemaVersion=2, verificationMode="DIRECT_CALCULATION",
        engineeringDecision="R10_APPROVED_TABLE_LOOKUP_SELECTION_RELATION",
        ownerClasses=["ship", "tableLookupCase", "iceClassValue", "propellerLocationValue", "tableReferenceValue"],
        directConstraintTerms=trf078_terms, applicabilityTerms=[],
        operandTerms=["selectedPropellerLocationFactor", "iceLoadCycleCoefficientK2",
                      "iceLoadCycleCoefficientK3", "selectedIceClassCycleCount",
                      "propellerBladeLoadSpectrumCountFactor"], resultTerms=["iceLoadCycleCount"],
        comparisonTerms=[], relationshipTerms=["hasTableLookupCase", "tableReference", "iceClass",
                                               "tableLookupPropellerLocation"], evidenceTerms=[],
        controlledValueTerms=["traficomTable6Dash6", "traficomTable6Dash7"], timeTerms=[],
        modelPaths=[
            {"fromOwner": "ship", "via": "hasTableLookupCase", "toOwner": "tableLookupCase"},
            {"fromOwner": "tableLookupCase", "via": "tableReference", "toOwner": "tableReferenceValue"},
            {"fromOwner": "tableLookupCase", "via": "iceClass", "toOwner": "iceClassValue"},
            {"fromOwner": "tableLookupCase", "via": "tableLookupPropellerLocation", "toOwner": "propellerLocationValue"},
        ], formulaExpression="N_ice = k1 * k2 * k3 * N_class * n_n", formulaExecutionRequired=True,
        comparisonModel=trf078_obligation,
        tableModel=("Table 6-6 case: tableReference=traficomTable6Dash6, iceClass selection key, "
                    "selectedIceClassCycleCount result. Table 6-7 case: tableReference=traficomTable6Dash7, "
                    "tableLookupPropellerLocation selection key, selectedPropellerLocationFactor result."),
        cardinalityPolicies=[{"term": "tableReference", "owner": "tableLookupCase", "minCount": 1, "maxCount": 1}],
        requiredModelFields=["verificationMode", "formulaExpression", "tableModel", "relationshipTerms", "modelPaths"])

    # TRF-128: direct conditional charging-time limits, not a capacity formula.
    by_id["TRF-128"].update(category="Static", activeStatus="Stage 2 candidate - direct static",
                              codability="Direct static", encodingPattern="Conditional direct time limit")
    trf128_terms = ["compressorChargeTime", "iceClass", "iceClassIaSuper",
                    "propulsionEngineReversalRequiredForAstern"]
    index["requirements"]["TRF-128"] = trf128_terms
    index["requirementTargetOwner"]["TRF-128"] = "ship"
    index["termOwners"]["TRF-128"] = {term: "ship" for term in
        ("compressorChargeTime", "iceClass", "propulsionEngineReversalRequiredForAstern")}
    trf128_obligation = (
        "If iceClass is IA Super and propulsionEngineReversalRequiredForAstern is true, compressorChargeTime "
        "must be at most 0.5 hour; otherwise compressorChargeTime must be at most 1 hour."
    )
    index["semanticObligations"]["TRF-128"] = [trf128_obligation]
    set_contract(index, "TRF-128", schemaVersion=2, verificationMode="DIRECT_STATIC",
        engineeringDecision="R10_APPROVED_DIRECT_TIME_LIMIT", ownerClasses=["ship"],
        directConstraintTerms=trf128_terms,
        applicabilityTerms=["iceClass", "propulsionEngineReversalRequiredForAstern"],
        operandTerms=[], resultTerms=[], comparisonTerms=["compressorChargeTime"], relationshipTerms=["iceClass"],
        evidenceTerms=[], controlledValueTerms=["iceClassIaSuper"], timeTerms=["compressorChargeTime"],
        modelPaths=[{"fromOwner": "ship", "via": "iceClass", "toOwner": "iceClassValue"}],
        formulaExpression="", formulaExecutionRequired=False, encodingPattern="Conditional direct time limit",
        comparisonModel=trf128_obligation,
        conditionalRules=[
            {"if": "iceClass = iceClassIaSuper AND propulsionEngineReversalRequiredForAstern = true",
             "then": "compressorChargeTime <= 0.5 hour"},
            {"else": "compressorChargeTime <= 1 hour"},
        ], requiredModelFields=["verificationMode", "comparisonModel", "applicabilityTerms", "timeTerms"])

    # TRF-028: retain the term in context/index; remove it only from mandatory evidence.
    trf028 = index["dependencyContracts"]["TRF-028"]
    trf028["evidenceTerms"] = ["alternativeCalculationEvidence", "modelTestEvidence",
                               "approvalStatus", "approvalRevocationStatus"]
    trf028["engineeringDecision"] = "R10_REMOVE_NONMANDATORY_PERFORMANCE_EXPERIENCE_EVIDENCE"

    # TRF-056: direct applicability comparison with owner-correct paths and evidence.
    by_id["TRF-056"].update(category="Static", activeStatus="Stage 2 candidate - direct static",
                              codability="Direct static", encodingPattern="Conditional direct static constraint")
    trf056_terms = ["hasHatchCoverDesignEvidence", "hasHatchFittingDesignEvidence", "hasWeatherdeckHatch",
                    "hatchCoverDesignEvidence", "hatchFittingDesignEvidence", "hatchOpeningLength",
                    "ship", "shipBreadth", "shipSideDeflection", "weatherdeckHatch"]
    index["requirements"]["TRF-056"] = trf056_terms
    index["requirementTargetOwner"]["TRF-056"] = "ship"
    index["termOwners"]["TRF-056"] = {
        "hasWeatherdeckHatch": "ship", "shipBreadth": "ship", "hatchOpeningLength": "weatherdeckHatch",
        "shipSideDeflection": "weatherdeckHatch", "hasHatchCoverDesignEvidence": "weatherdeckHatch",
        "hasHatchFittingDesignEvidence": "weatherdeckHatch", "hatchCoverDesignEvidence": "hatchCoverDesignEvidence",
        "hatchFittingDesignEvidence": "hatchFittingDesignEvidence", "weatherdeckHatch": "weatherdeckHatch",
        "ship": "ship",
    }
    trf056_obligation = (
        "If hatchOpeningLength of a weatherdeck hatch is greater than shipBreadth divided by 2, shipSideDeflection "
        "must be considered or represented and both hasHatchCoverDesignEvidence and hasHatchFittingDesignEvidence "
        "must exist for that hatch."
    )
    index["semanticObligations"]["TRF-056"] = [trf056_obligation]
    set_contract(index, "TRF-056", schemaVersion=2, verificationMode="DIRECT_STATIC",
        engineeringDecision="R10_APPROVED_DIRECT_HATCH_APPLICABILITY", ownerClasses=["ship", "weatherdeckHatch"],
        directConstraintTerms=trf056_terms, applicabilityTerms=["hatchOpeningLength", "shipBreadth"],
        operandTerms=[], resultTerms=[], comparisonTerms=["hatchOpeningLength", "shipBreadth", "shipSideDeflection"],
        relationshipTerms=["hasWeatherdeckHatch", "hasHatchCoverDesignEvidence", "hasHatchFittingDesignEvidence"],
        evidenceTerms=["hasHatchCoverDesignEvidence", "hasHatchFittingDesignEvidence"], controlledValueTerms=[],
        timeTerms=[], modelPaths=[
            {"fromOwner": "ship", "via": "hasWeatherdeckHatch", "toOwner": "weatherdeckHatch"},
            {"fromOwner": "weatherdeckHatch", "via": "hasHatchCoverDesignEvidence", "toOwner": "hatchCoverDesignEvidence"},
            {"fromOwner": "weatherdeckHatch", "via": "hasHatchFittingDesignEvidence", "toOwner": "hatchFittingDesignEvidence"},
        ], formulaExpression="", formulaExecutionRequired=False,
        encodingPattern="Conditional direct static constraint", comparisonModel=trf056_obligation,
        conditionalRules=[{"if": "hatchOpeningLength > shipBreadth / 2",
                           "then": "shipSideDeflection represented and hatch-cover plus hatch-fitting design evidence exists"}],
        requiredModelFields=["verificationMode", "comparisonModel", "relationshipTerms", "modelPaths"])

    # Exact category delta and immutable TRF-048 semantics.
    counts = dict(Counter(row["category"] for row in evidence["requirements"]))
    if counts != EXPECTED_COUNTS:
        raise RuntimeError(f"Unexpected R10 category counts: {counts}")
    r9_by_id = {row["id"]: row for row in r9_evidence["requirements"]}
    category_changed = {rid for rid in by_id if by_id[rid]["category"] != r9_by_id[rid]["category"]}
    if category_changed != {"TRF-056", "TRF-128"}:
        raise RuntimeError(f"Unapproved category delta: {sorted(category_changed)}")
    for key in ("requirements", "termOwners", "requirementTargetOwner", "semanticObligations"):
        if index[key].get("TRF-048") != r9_index[key].get("TRF-048"):
            raise RuntimeError(f"TRF-048 changed unexpectedly in {key}")
    if index["dependencyContracts"]["TRF-048"] != r9_index["dependencyContracts"]["TRF-048"]:
        raise RuntimeError("TRF-048 contract changed unexpectedly")

    evidence["summary"]["requirementsByCategory"] = EXPECTED_COUNTS
    evidence["summary"]["activationCounts"] = dict(Counter(r["activeStatus"] for r in evidence["requirements"]))
    evidence["summary"]["verificationPolicyLockId"] = LOCK_ID
    evidence["summary"]["verificationPolicy"] = "R10 mechanical corrections; R9 five-category policy retained"
    index["sourceLockId"] = LOCK_ID
    index["version"] = "10.0"

    policy = read(TARGET / "evidence/verification_policy_r9.json")
    policy.update(lockId=LOCK_ID, categoryCounts=EXPECTED_COUNTS)
    policy["r10ApprovedCategoryChanges"] = {"TRF-056": ["Static Calculation", "Static"],
                                             "TRF-128": ["Static Calculation", "Static"]}
    policy["futureCleanupItem"] = (
        "Some COMPLETE DIRECT_CALCULATION contracts have empty operandTerms/resultTerms; global cleanup was explicitly outside R10 scope."
    )
    write(TARGET / "evidence/verification_policy_r10.json", policy)
    (TARGET / "evidence/VERIFICATION_POLICY_R10.md").write_text(
        "# R10 verification-policy provenance\n\nR10 retains the frozen R9 five-category policy. "
        "Only TRF-056 and TRF-128 move from Static Calculation / DIRECT_CALCULATION to Static / DIRECT_STATIC, "
        "as mechanically approved. No other category changes were made.\n", encoding="utf-8")

    write(TARGET / "evidence/stage1_approved.json", evidence)
    write(TARGET / "requirement_term_index.json", index)
    write(TARGET / "registry/term_registry.json", registry)
    fields = list(read(SOURCE / "registry/term_registry.json")[0].keys())
    with (TARGET / "registry/term_registry.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for term in registry:
            writer.writerow({key: " | ".join(value) if isinstance(value, list) else value
                             for key, value in term.items()})

    decisions = {
        "lockId": LOCK_ID, "sourceLockId": SOURCE_LOCK_ID, "status": "APPROVED_MECHANICAL_R10",
        "affectedRequirementIds": ["I2-029", "TRF-028", "TRF-056", "TRF-078", "TRF-128"],
        "categoryChanges": {"TRF-056": ["Static Calculation", "Static"],
                            "TRF-128": ["Static Calculation", "Static"]},
        "newCanonicalTerms": ["tableLookupPropellerLocation"],
        "modifiedCanonicalTerms": {"sectionCalculationCaseStructuralMember": {
            "domainBefore": "localFrameSectionCalculationCase", "domainAfter": "calculationCase"}},
        "trf028MandatoryEvidenceBefore": ["alternativeCalculationEvidence", "modelTestEvidence", "approvalStatus",
                                          "approvalRevocationStatus", "shipPerformanceExperienceEvidence"],
        "trf028MandatoryEvidenceAfter": trf028["evidenceTerms"],
        "trf048Unchanged": True, "apiCalls": 0,
    }
    write(TARGET / "registry/r10_mechanical_change_decisions.json", decisions)
    write(TARGET / "provenance/r9_immutable_source_hashes.json", provenance)

    bound_relatives = [
        "context/nltl_benchmark_context.jsonld", "evidence/stage1_approved.json",
        "evidence/verification_policy_r10.json", "evidence/VERIFICATION_POLICY_R10.md",
        "ontology/nltl_benchmark_vocabulary.ttl", "ontology/nltl_benchmark_vocabulary.rdf",
        "registry/term_registry.json", "registry/term_registry.csv",
        "registry/r10_mechanical_change_decisions.json", "requirement_term_index.json",
        "provenance/r9_immutable_source_hashes.json", "few_shots/few_shot_pairs.jsonl",
        "few_shots/catalog.json", "few_shots/validation_report.json",
    ]
    bound = {relative: sha(TARGET / relative) for relative in bound_relatives}
    write(TARGET / "r10_prelock_binding.json", {"lockId": LOCK_ID,
        "status": "PRELOCK_OFFLINE_VALIDATION_ONLY", "workbook": "Pending R10 workbook",
        "workbookSha256": "", "boundMachineReadableArtifacts": bound,
        "boundRequirementIndex": {"requirement_term_index.json": bound["requirement_term_index.json"]}})
    write(TARGET / "prelock_manifest.json", {"lockId": LOCK_ID, "sourceLockId": SOURCE_LOCK_ID,
        "boundArtifacts": bound, "categoryChanges": decisions["categoryChanges"],
        "categoryCounts": EXPECTED_COUNTS, "newCanonicalTerms": ["tableLookupPropellerLocation"],
        "modifiedCanonicalTerms": decisions["modifiedCanonicalTerms"], "apiCalls": 0})
    print(json.dumps({"status": "R10_PRELOCK_CREATED", "lockId": LOCK_ID,
        "categoryCounts": counts, "newCanonicalTerms": ["tableLookupPropellerLocation"],
        "modifiedCanonicalTerms": ["sectionCalculationCaseStructuralMember"],
        "r9ImmutableFiles": provenance["fileCount"], "apiCalls": 0}, indent=2))


if __name__ == "__main__":
    main()
