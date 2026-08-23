from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL, SKOS, XSD


MVP = Path(__file__).resolve().parents[2]
PIPE = MVP / "SHACL_GENERATION_PIPELINE"
SOURCE = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R10"
TARGET = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R11"
SOURCE_LOCK_ID = "VOCAB-LOCK-2026-08-20-R10"
LOCK_ID = "VOCAB-LOCK-2026-08-21-R11"
CANONICAL = "https://w3id.org/nltl/vocab#"
NLTL = Namespace(CANONICAL)
QUDT = Namespace("http://qudt.org/schema/qudt/")
EXPECTED_COUNTS = {"Static": 190, "Static Calculation": 44, "Complex": 45,
                   "Dynamic": 19, "Physical Test": 15}
CATEGORY_CHANGES = {
    "I2-017": ("Static Calculation", "Complex"),
    "IMO-011": ("Static Calculation", "Complex"),
    "TRF-012": ("Static", "Complex"),
    "TRF-080": ("Static", "Static Calculation"),
    "TRF-084": ("Static", "Static Calculation"),
    "TRF-086": ("Static", "Static Calculation"),
}


def read(path: Path): return json.loads(path.read_text(encoding="utf-8"))
def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def immutable_manifest() -> dict:
    roots = [SOURCE, MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R10.xlsx",
             MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R10.lock.json",
             MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-20-R10.sha256"]
    files = {}
    for root in roots:
        candidates = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for path in candidates: files[str(path.relative_to(MVP))] = sha(path)
    aggregate = hashlib.sha256(
        "\n".join(f"{digest}  {name}" for name, digest in sorted(files.items())).encode()
    ).hexdigest()
    return {"sourceLockId": SOURCE_LOCK_ID, "fileCount": len(files),
            "aggregateSha256": aggregate, "files": files}


def term(local: str, kind: str, parent: str, label: str, concept: str, module: str,
         requirement: str, evidence: str, definition: str, *, domain: str = "",
         datatype: str = "", quantity_kind: str = "", unit_iri: str = "", unit_symbol: str = "") -> dict:
    role = {"Class": "Reusable engineering/evidence node type", "NamedIndividual": "Controlled value",
            "ObjectProperty": "Typed relationship path", "DatatypeProperty": "Typed literal property",
            "QuantityProperty": "Engineering quantity"}[kind]
    return {"aliases": [], "conceptId": concept, "confidence": "High", "datatype": datatype,
        "evidenceExcerpt": evidence, "haithamUri": "", "iri": CANONICAL + local, "kind": kind,
        "label": label, "localName": local,
        "mappingStatus": "No external equivalence claimed; source-grounded R11 benchmark term.",
        "module": module, "nameQaStatus": "Passed - ASCII-only lowerCamelCase and collision review",
        "namingBasis": "Human-approved source requirement and minimum R11 graph role",
        "namingRule": "N4/N5 - singular ASCII lowerCamelCase; relationship direction is explicit.",
        "normalizedDefinition": definition, "parentOrRange": parent, "quantityKindLabel": quantity_kind,
        "requirements": [requirement], "roleDecision": role, "sourceConceptIds": [concept],
        "sourceRefs": requirement, "stage1LocalNames": [local],
        "stage2UnitEvidence": "R11 source-grounded unit" if unit_iri else "",
        "unitDecisionStatus": "R11 source-grounded unit" if unit_iri else "Not a quantity property",
        "unitIri": unit_iri, "unitSymbol": unit_symbol, "r11Domain": CANONICAL + domain if domain else ""}


def additions(evidence_by_id: dict) -> list[dict]:
    specs = []
    categories = [
        ("transverselyFramedPlatingCategory", "Transversely framed plating category"),
        ("longitudinallyFramedPlatingCategory", "Longitudinally framed plating category"),
        ("transverseFrameWithLoadDistributingStringersCategory", "Transverse frame with load-distributing stringers category"),
        ("transverseFrameWithoutLoadDistributingStringersCategory", "Transverse frame without load-distributing stringers category"),
        ("bottomStructureFrameCategory", "Bottom structure frame category"),
        ("stringerSideLongitudinalOrWebFrameCategory", "Stringer, side longitudinal, or web frame category"),
    ]
    for number, (local, label) in enumerate(categories, 1):
        specs.append(term(local, "NamedIndividual", CANONICAL + "structuralMemberCategoryValue", label,
            f"VOC-R11-{number:04d}", "hull", "I2-018", evidence_by_id["I2-018"]["sourceText"],
            f"NORMALIZED (R11): controlled localized structural-member category value for {label.lower()}."))
    specs.extend([
        term("steelGradeRequirementCasePlating", "ObjectProperty", CANONICAL + "plating",
             "Steel grade requirement case plating", "VOC-R11-0007", "hull", "I2-048",
             evidence_by_id["I2-048"]["sourceText"],
             "NORMALIZED (R11): links a steel-grade requirement case to the plating assessed by that case.",
             domain="steelGradeRequirementCase"),
        term("thinFirstYearIceWithPossibleOldIceInclusions", "NamedIndividual", CANONICAL + "iceConditionValue",
             "Thin first-year ice with possible old-ice inclusions", "VOC-R11-0008", "operations", "IMO-002",
             evidence_by_id["IMO-002"]["sourceText"],
             "NORMALIZED (R11): controlled design-ice-condition value for at least thin first-year ice with possible old-ice inclusions."),
        term("dailyLowTemperatureObservation", "Class", CANONICAL + "benchmarkEntity",
             "Daily low temperature observation", "VOC-R11-0009", "operations", "IMO-011",
             evidence_by_id["IMO-011"]["sourceText"],
             "NORMALIZED (R11): a dated observation carrying one daily low-temperature value."),
        term("hasDailyLowTemperatureObservation", "ObjectProperty", CANONICAL + "dailyLowTemperatureObservation",
             "Has daily low temperature observation", "VOC-R11-0010", "operations", "IMO-011",
             evidence_by_id["IMO-011"]["sourceText"],
             "NORMALIZED (R11): links a ship to each dated daily low-temperature observation.", domain="ship"),
        term("dailyTemperatureObservationDate", "DatatypeProperty", str(XSD.date),
             "Daily temperature observation date", "VOC-R11-0011", "operations", "IMO-011",
             evidence_by_id["IMO-011"]["sourceText"],
             "NORMALIZED (R11): calendar date of a daily low-temperature observation.",
             domain="dailyLowTemperatureObservation", datatype="xsd:date"),
        term("hasPolarRoutePlan", "ObjectProperty", CANONICAL + "polarRoutePlan", "Has polar route plan",
             "VOC-R11-0012", "documents", "IMO-101", evidence_by_id["IMO-101"]["sourceText"],
             "NORMALIZED (R11): links a ship to its polar-route planning record.", domain="ship"),
        term("hasDischargeDistanceRecord", "ObjectProperty", CANONICAL + "dischargeDistanceRecords",
             "Has discharge distance record", "VOC-R11-0013", "operations", "IMO-117; IMO-123",
             evidence_by_id["IMO-117"]["sourceText"] + " " + evidence_by_id["IMO-123"]["sourceText"],
             "NORMALIZED (R11): links a ship to a discharge-distance record.", domain="ship"),
        term("distanceToAreaWithIceConcentrationGreaterThanOneTenth", "QuantityProperty", str(QUDT.QuantityValue),
             "Distance to area with ice concentration greater than one tenth", "VOC-R11-0014", "operations",
             "IMO-117; IMO-123", evidence_by_id["IMO-117"]["sourceText"] + " " + evidence_by_id["IMO-123"]["sourceText"],
             "NORMALIZED (R11): recorded discharge distance from an area whose ice concentration exceeds one tenth; no numerical minimum is implied.",
             domain="dischargeDistanceRecords", quantity_kind="Length",
             unit_iri="http://qudt.org/vocab/unit/MI_N", unit_symbol="nautical mile"),
        term("framingIceStrengtheningTerminationCase", "Class", CANONICAL + "benchmarkEntity",
             "Framing ice-strengthening termination case", "VOC-R11-0015", "hull", "TRF-043",
             evidence_by_id["TRF-043"]["sourceText"],
             "NORMALIZED (R11): a case recording framing-strengthening termination at an adjacent structural boundary."),
        term("hasFramingIceStrengtheningTerminationCase", "ObjectProperty", CANONICAL + "framingIceStrengtheningTerminationCase",
             "Has framing ice-strengthening termination case", "VOC-R11-0016", "hull", "TRF-043",
             evidence_by_id["TRF-043"]["sourceText"],
             "NORMALIZED (R11): links a ship to a framing ice-strengthening termination case.", domain="ship"),
        term("terminationAdjacentBoundary", "ObjectProperty", CANONICAL + "hullStructure",
             "Termination adjacent boundary", "VOC-R11-0017", "hull", "TRF-043",
             evidence_by_id["TRF-043"]["sourceText"],
             "NORMALIZED (R11): identifies the adjacent deck, tank boundary, or tank top governing termination.",
             domain="framingIceStrengtheningTerminationCase"),
        term("continuousBeamWithBracketsFrameCondition", "NamedIndividual", CANONICAL + "frameBoundaryConditionTypeValue",
             "Continuous beam with brackets frame condition", "VOC-R11-0018", "hull", "TRF-048",
             evidence_by_id["TRF-048"]["sourceText"],
             "NORMALIZED (R11): controlled boundary-condition value for a continuous frame beam with brackets."),
        term("strengtheningEnvelopeBoundary", "ObjectProperty", CANONICAL + "hullStructure",
             "Strengthening envelope boundary", "VOC-R11-0019", "hull", "TRF-063",
             evidence_by_id["TRF-063"]["sourceText"],
             "NORMALIZED (R11): links a side-propeller strengthening envelope to its structural boundary.",
             domain="sidePropellerStrengtheningEnvelope"),
        term("propellerBladeLoadCaseBlade", "ObjectProperty", CANONICAL + "propellerBlade",
             "Propeller blade load-case blade", "VOC-R11-0020", "machinery", "TRF-075",
             evidence_by_id["TRF-075"]["sourceText"],
             "NORMALIZED (R11): links a propeller-blade load case to exactly the blade assessed by the case.",
             domain="propellerBladeLoadCase"),
        term("propellerBladeLoadCaseIceBlock", "ObjectProperty", CANONICAL + "iceBlock",
             "Propeller blade load-case ice block", "VOC-R11-0021", "machinery", "TRF-075",
             evidence_by_id["TRF-075"]["sourceText"],
             "NORMALIZED (R11): links a propeller-blade load case to the ice block involved in the case.",
             domain="propellerBladeLoadCase"),
    ])
    for offset, suffix in enumerate(("C1", "C2", "C3", "C4"), 22):
        specs.append(term(f"fatigueCoefficient{suffix}", "QuantityProperty", str(QUDT.QuantityValue),
            f"Fatigue coefficient {suffix}", f"VOC-R11-{offset:04d}", "machinery", "TRF-109",
            evidence_by_id["TRF-109"]["sourceText"],
            f"NORMALIZED (R11): dimensionless Table 6-14 fatigue coefficient {suffix}.",
            domain="tableLookupCase", quantity_kind="DimensionlessRatio",
            unit_iri="http://qudt.org/vocab/unit/UNITLESS", unit_symbol="1"))
    return specs


def add_graph_term(graph: Graph, item: dict) -> None:
    iri = URIRef(item["iri"]); kind = item["kind"]
    parent = URIRef(item["parentOrRange"]); domain = URIRef(item["r11Domain"]) if item.get("r11Domain") else None
    if kind == "Class":
        graph.add((iri, RDF.type, OWL.Class)); graph.add((iri, RDFS.subClassOf, parent))
    elif kind == "NamedIndividual":
        graph.add((iri, RDF.type, parent)); graph.add((iri, RDF.type, SKOS.Concept))
    elif kind == "DatatypeProperty":
        graph.add((iri, RDF.type, OWL.DatatypeProperty)); graph.add((iri, RDFS.domain, domain)); graph.add((iri, RDFS.range, parent))
    else:
        graph.add((iri, RDF.type, OWL.ObjectProperty)); graph.add((iri, RDFS.domain, domain)); graph.add((iri, RDFS.range, parent))
    graph.add((iri, RDFS.label, Literal(item["label"], lang="en")))
    graph.add((iri, SKOS.prefLabel, Literal(item["label"], lang="en")))
    graph.add((iri, SKOS.definition, Literal(item["normalizedDefinition"], lang="en")))
    graph.add((iri, NLTL.draftConceptId, Literal(item["conceptId"])))
    for rid in item["requirements"][0].split("; "): graph.add((iri, NLTL.sourceRequirementId, Literal(rid)))
    if item.get("unitIri"): graph.add((iri, NLTL.recommendedUnit, URIRef(item["unitIri"])))


def set_contract(index: dict, rid: str, **changes) -> None:
    c = index["dependencyContracts"][rid]; c.update(changes); c["status"] = "COMPLETE"
    c["auditFlags"] = []; c["observedFailureStatus"] = ""; c.pop("deferredReason", None)


def set_index(index: dict, rid: str, terms: list[str], owners: dict, target: str, obligation: str) -> None:
    index["requirements"][rid] = sorted(set(terms)); index["termOwners"][rid] = owners
    index["requirementTargetOwner"][rid] = target; index["semanticObligations"][rid] = [obligation]


def main() -> None:
    if TARGET.exists(): raise FileExistsError(f"Refusing to overwrite existing R11 directory: {TARGET}")
    provenance = immutable_manifest()
    for directory in ("context", "evidence", "few_shots", "ontology", "registry"):
        shutil.copytree(SOURCE / directory, TARGET / directory)
    shutil.copy2(SOURCE / "requirement_term_index.json", TARGET / "requirement_term_index.json")
    (TARGET / "provenance").mkdir(parents=True); (TARGET / "validation").mkdir(parents=True)
    evidence = read(TARGET / "evidence/stage1_approved.json"); by_id = {r["id"]: r for r in evidence["requirements"]}
    index = read(TARGET / "requirement_term_index.json"); registry = read(TARGET / "registry/term_registry.json")
    old_evidence = read(SOURCE / "evidence/stage1_approved.json"); old_by = {r["id"]: r for r in old_evidence["requirements"]}

    # Exact 25-term addition and one approved existing-domain change.
    new_terms = additions(by_id); expected_new = {t["localName"] for t in new_terms}
    if len(new_terms) != 25 or expected_new & {t["localName"] for t in registry}:
        raise RuntimeError("R11 new-term inventory is not exactly 25 unique additions")
    registry.extend(new_terms)
    boundary = next(t for t in registry if t["localName"] == "frameBoundaryConditionType")
    boundary["requirements"] = sorted(set(boundary["requirements"]) | {"TRF-048"})
    boundary["sourceRefs"] += "; TRF-048 | TRAFICOM p.20 | 4.4.3"
    boundary["normalizedDefinition"] = "NORMALIZED (R11): assigns a controlled boundary-condition type to any frame."
    registry.sort(key=lambda t: t["localName"])
    graph = Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.remove((NLTL.frameBoundaryConditionType, RDFS.domain, None))
    graph.add((NLTL.frameBoundaryConditionType, RDFS.domain, NLTL.frame))
    graph.add((NLTL.frameBoundaryConditionType, NLTL.sourceRequirementId, Literal("TRF-048")))
    for item in new_terms: add_graph_term(graph, item)
    graph.serialize(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.serialize(TARGET / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    context = read(TARGET / "context/nltl_benchmark_context.jsonld")
    for item in new_terms:
        local, kind = item["localName"], item["kind"]
        if kind in {"Class", "NamedIndividual"}: context["@context"][local] = "nltl:" + local
        elif kind == "DatatypeProperty": context["@context"][local] = {"@id": "nltl:" + local, "@type": item["datatype"]}
        else: context["@context"][local] = {"@id": "nltl:" + local, "@type": "@id"}
    context["@context"] = dict(sorted(context["@context"].items()))
    write(TARGET / "context/nltl_benchmark_context.jsonld", context)

    # Exactly six category changes.
    for rid, (old, new) in CATEGORY_CHANGES.items():
        if by_id[rid]["category"] != old: raise RuntimeError(f"Unexpected R10 category for {rid}")
        by_id[rid]["category"] = new
        mode = "COMPLEX_READINESS" if new == "Complex" else "DIRECT_CALCULATION"
        by_id[rid]["activeStatus"] = "Stage 2 candidate - complex readiness" if new == "Complex" else "Stage 2 candidate - direct calculation"
        by_id[rid]["codability"] = "Complex readiness" if new == "Complex" else "Direct calculation"
        index["dependencyContracts"][rid]["verificationMode"] = mode
        index["dependencyContracts"][rid]["engineeringDecision"] = f"R11_APPROVED_{mode}"

    # I2-002 scope-only deferral.
    c = index["dependencyContracts"]["I2-002"]
    c["status"] = "DEFERRED_SCOPE_ONLY"; c["deferredReason"] = (
        "The requirement only defines applicability of UR I2 to Polar Class ships and does not independently "
        "impose a substantive compliance constraint suitable for standalone SHACL generation.")
    c["engineeringDecision"] = "R11_APPROVED_SCOPE_ONLY_DEFERRAL"
    by_id["I2-002"]["activeStatus"] = "Deferred - scope-only requirement"; by_id["I2-002"]["codability"] = "Deferred"

    # Exact contract cleanup for I2-023 and I2-035.
    index["dependencyContracts"]["I2-023"]["operandTerms"] = ["averageIcePressure", "frameSpacing", "frameSpan",
        "framingAngleOmega", "loadPatchHeight", "peakPressureFactor", "selectedHullAreaFactor", "yieldStrength"]
    index["dependencyContracts"]["I2-023"]["resultTerms"] = ["iceLoadRequiredNetPlateThickness"]
    index["dependencyContracts"]["I2-023"]["engineeringDecision"] = "R11_APPROVED_OPERAND_RESULT_CLEANUP"
    index["dependencyContracts"]["I2-035"]["operandTerms"] = ["averageIcePressure", "frameSpacing", "frameSpan",
        "peakPressureFactor", "selectedHullAreaFactor", "yieldStrength", "shearArea"]
    index["dependencyContracts"]["I2-035"]["resultTerms"] = ["requiredLongitudinalFrameShearArea"]
    index["dependencyContracts"]["I2-035"]["engineeringDecision"] = "R11_APPROVED_OPERAND_RESULT_CLEANUP"

    # Complex readiness contracts and direct-calculation reclassifications.
    set_contract(index, "I2-017", verificationMode="COMPLEX_READINESS", formulaExecutionRequired=False,
        informationalSourceFormula=index["dependencyContracts"]["I2-017"].get("formulaExpression", ""),
        requiredModelFields=["verificationMode", "operandTerms", "resultTerms", "relationshipTerms", "modelPaths"],
        directCheckSubconstraints=[])
    trf012 = index["dependencyContracts"]["TRF-012"]
    trf012.update(verificationMode="COMPLEX_READINESS", formulaExecutionRequired=False,
        operandTerms=["hasIntendedIceOperatingWaterline", "hasWaterlineProfilePoint", "longitudinalPosition", "verticalCoordinate"],
        resultTerms=["hasLowerIceWaterline"], relationshipTerms=["hasIntendedIceOperatingWaterline", "hasLowerIceWaterline", "hasWaterlineProfilePoint"],
        modelPaths=[{"fromOwner":"ship","via":"hasIntendedIceOperatingWaterline","toOwner":"iceWaterline"},
                    {"fromOwner":"ship","via":"hasLowerIceWaterline","toOwner":"iceWaterline"},
                    {"fromOwner":"iceWaterline","via":"hasWaterlineProfilePoint","toOwner":"waterlineProfilePoint"}],
        requiredModelFields=["verificationMode", "operandTerms", "resultTerms", "relationshipTerms", "modelPaths"],
        directCheckSubconstraints=[], engineeringDecision="R11_APPROVED_COMPLEX_READINESS")
    index["termOwners"]["TRF-012"].update({"hasWaterlineProfilePoint":"iceWaterline", "longitudinalPosition":"waterlineProfilePoint",
                                            "verticalCoordinate":"waterlineProfilePoint"})
    for rid in ("TRF-080", "TRF-084", "TRF-086"):
        c = index["dependencyContracts"][rid]; c["formulaExecutionRequired"] = True
        c["requiredModelFields"] = ["verificationMode", "formulaExpression", "operandTerms", "resultTerms", "comparisonModel"]
    index["dependencyContracts"]["TRF-080"].update(
        operandTerms=["iceLoadCycleCount", "propellerBladeCount"], resultTerms=["effectiveIceLoadCycleCount"],
        formulaExpression="effectiveIceLoadCycleCount = iceLoadCycleCount * propellerBladeCount")
    for rid in ("TRF-084", "TRF-086"):
        index["dependencyContracts"][rid].update(
            applicabilityTerms=["propellerType", "pitchValueKnown"],
            operandTerms=["propellerPitchAtMcrFreeRunning"], resultTerms=["propellerPitchAtMcrBollard"],
            formulaExpression="IF propellerType = 'CP' AND pitchValueKnown = false THEN propellerPitchAtMcrBollard = 0.7 * propellerPitchAtMcrFreeRunning")

    # I2-018 six controlled lookup categories.
    i2018_values = sorted(t["localName"] for t in new_terms if t["requirements"] == ["I2-018"])
    index["requirements"]["I2-018"] = sorted(set(index["requirements"]["I2-018"]) | set(i2018_values))
    index["dependencyContracts"]["I2-018"]["controlledValueTerms"] = sorted(
        set(index["dependencyContracts"]["I2-018"]["controlledValueTerms"]) | set(i2018_values))
    index["dependencyContracts"]["I2-018"]["engineeringDecision"] = "R11_APPROVED_CONTROLLED_MEMBER_CATEGORIES"

    # I2-048 case -> plating path.
    rid="I2-048"; p="steelGradeRequirementCasePlating"
    index["requirements"][rid] = sorted(set(index["requirements"][rid]) | {p})
    index["termOwners"][rid][p] = "steelGradeRequirementCase"
    c=index["dependencyContracts"][rid]; c["relationshipTerms"] = sorted(set(c["relationshipTerms"]) | {p})
    c["modelPaths"] = [{"fromOwner":"ship","via":"hasSteelGradeRequirementCase","toOwner":"steelGradeRequirementCase"},
        {"fromOwner":"steelGradeRequirementCase","via":p,"toOwner":"plating"}] + [x for x in c["modelPaths"] if x.get("via") not in {"hasSteelGradeRequirementCase",p}]
    c["ownerClasses"] = sorted(set(c["ownerClasses"]) | {"steelGradeRequirementCase","plating"}); c["engineeringDecision"]="R11_APPROVED_CASE_PLATING_PATH"

    # IMO-002 controlled Category B ice condition.
    rid="IMO-002"; value="thinFirstYearIceWithPossibleOldIceInclusions"
    index["requirements"][rid]=sorted(set(index["requirements"][rid])|{value,"iceConditionValue"})
    c=index["dependencyContracts"][rid]; c["controlledValueTerms"]=[value]; c["applicabilityTerms"]=["designIceCondition"]
    c["comparisonModel"]="IF designIceCondition = thinFirstYearIceWithPossibleOldIceInclusions and the ship is not category A, THEN shipCategory = B."
    c["engineeringDecision"]="R11_APPROVED_CATEGORY_B_ICE_CONDITION"

    # IMO-011 dated observation readiness model.
    rid="IMO-011"; terms=["ship","dailyLowTemperatureObservation","hasDailyLowTemperatureObservation",
        "dailyTemperatureObservationDate","dailyLowTemperature","dataPeriod","meanDailyLowTemperature",
        "administrationDatasetApprovalStatus","evidenceStateApproved"]
    obligation=("A ship has dated dailyLowTemperatureObservation nodes carrying dailyLowTemperature values, a dataPeriod, "
        "and a meanDailyLowTemperature result. If dataPeriod is shorter than 10 years, administrationDatasetApprovalStatus "
        "is evidenceStateApproved. The complete aggregation is external and is not reconstructed in SHACL.")
    set_index(index,rid,terms,{"hasDailyLowTemperatureObservation":"ship","dailyTemperatureObservationDate":"dailyLowTemperatureObservation",
        "dailyLowTemperature":"dailyLowTemperatureObservation","dataPeriod":"ship","meanDailyLowTemperature":"ship",
        "administrationDatasetApprovalStatus":"ship"},"ship",obligation)
    set_contract(index,rid,schemaVersion=2,verificationMode="COMPLEX_READINESS",engineeringDecision="R11_APPROVED_DATED_OBSERVATION_READINESS",
        ownerClasses=["ship","dailyLowTemperatureObservation"],directConstraintTerms=terms,
        applicabilityTerms=[],operandTerms=["dailyTemperatureObservationDate","dailyLowTemperature","dataPeriod"],
        resultTerms=["meanDailyLowTemperature"],comparisonTerms=["dataPeriod"],
        relationshipTerms=["hasDailyLowTemperatureObservation","administrationDatasetApprovalStatus"],
        evidenceTerms=["administrationDatasetApprovalStatus"],controlledValueTerms=["evidenceStateApproved"],timeTerms=["dailyTemperatureObservationDate","dataPeriod"],
        modelPaths=[{"fromOwner":"ship","via":"hasDailyLowTemperatureObservation","toOwner":"dailyLowTemperatureObservation"}],
        formulaExpression="",informationalSourceFormula=by_id[rid]["sourceText"],formulaExecutionRequired=False,
        comparisonModel=obligation,conditionalRules=[{"if":"dataPeriod < 10 years","then":"administrationDatasetApprovalStatus = evidenceStateApproved"}],
        requiredModelFields=["verificationMode","operandTerms","resultTerms","relationshipTerms","modelPaths","evidenceTerms"])

    # Generic approval-record reuse for IMO-032 and per-component IMO-049.
    approval=["hasApprovalRecord","approvalRecord","scantlingApprovalStatus","evidenceStateApproved","approvingAuthority","approvalStandard"]
    rid="IMO-032"; terms=sorted(set(index["requirements"][rid])|set(approval))
    obligation=("Each applicable ship has an approvalRecord with scantlingApprovalStatus = evidenceStateApproved, "
        "approvingAuthority, and approvalStandard. The ice-strengthened Category C branch also requires operatingIceType and operatingIceConcentration.")
    set_index(index,rid,terms,{"hasApprovalRecord":"ship","scantlingApprovalStatus":"approvalRecord","approvingAuthority":"approvalRecord",
        "approvalStandard":"approvalRecord","operatingIceType":"approvalRecord","operatingIceConcentration":"approvalRecord"},"ship",obligation)
    set_contract(index,rid,schemaVersion=1,verificationMode="DIRECT_STATIC",engineeringDecision="R11_REUSE_GENERIC_APPROVAL_RECORD",
        ownerClasses=["ship","approvalRecord"],directConstraintTerms=terms,applicabilityTerms=["shipCategory","shipIceStrengthened"],operandTerms=[],resultTerms=[],
        comparisonTerms=["scantlingApprovalStatus"],relationshipTerms=["hasApprovalRecord","scantlingApprovalStatus"],
        evidenceTerms=["hasApprovalRecord","approvingAuthority","approvalStandard"],controlledValueTerms=["evidenceStateApproved"],timeTerms=[],
        modelPaths=[{"fromOwner":"ship","via":"hasApprovalRecord","toOwner":"approvalRecord"}],formulaExpression="",comparisonModel=obligation,
        conditionalRules=[{"if":"Category C AND shipIceStrengthened = true","then":"operatingIceType and operatingIceConcentration exist on approvalRecord"}],
        requiredModelFields=["verificationMode","comparisonModel","relationshipTerms","modelPaths","evidenceTerms"])
    rid="IMO-049"; terms=sorted(set(index["requirements"][rid])|set(approval)|{"hasComponent"})
    obligation=("Every applicable machinery component reached by hasComponent has an approvalRecord with scantlingApprovalStatus = evidenceStateApproved, "
        "approvingAuthority, and approvalStandard. Applicable ice-strengthened Category C machinery also requires operatingIceType and operatingIceConcentration.")
    set_index(index,rid,terms,{"hasComponent":"ship","hasApprovalRecord":"machineryComponent","scantlingApprovalStatus":"approvalRecord",
        "approvingAuthority":"approvalRecord","approvalStandard":"approvalRecord","operatingIceType":"approvalRecord","operatingIceConcentration":"approvalRecord"},"ship",obligation)
    set_contract(index,rid,schemaVersion=1,verificationMode="DIRECT_STATIC",engineeringDecision="R11_REUSE_PER_COMPONENT_APPROVAL_RECORD",
        ownerClasses=["ship","machineryComponent","approvalRecord"],directConstraintTerms=terms,applicabilityTerms=["shipCategory","shipIceStrengthened","machineryComponentType"],
        operandTerms=[],resultTerms=[],comparisonTerms=["scantlingApprovalStatus"],relationshipTerms=["hasComponent","hasApprovalRecord","scantlingApprovalStatus"],
        evidenceTerms=["hasApprovalRecord","approvingAuthority","approvalStandard"],controlledValueTerms=["evidenceStateApproved"],timeTerms=[],
        modelPaths=[{"fromOwner":"ship","via":"hasComponent","toOwner":"machineryComponent"},{"fromOwner":"machineryComponent","via":"hasApprovalRecord","toOwner":"approvalRecord"}],
        formulaExpression="",comparisonModel=obligation,conditionalRules=[{"if":"Category C AND shipIceStrengthened = true","then":"operatingIceType and operatingIceConcentration exist on approvalRecord"}],
        requiredModelFields=["verificationMode","comparisonModel","relationshipTerms","modelPaths","evidenceTerms"])

    # Stale term replacement and route plan relation.
    rid="IMO-072"; old="continuousUseSuitabilityStatus"; new="searchlightContinuousUseSuitabilityStatus"
    index["requirements"][rid]=sorted((set(index["requirements"][rid])-{old})|{new})
    for field in ("operandTerms","resultTerms","comparisonTerms","relationshipTerms","evidenceTerms","directConstraintTerms"):
        if isinstance(index["dependencyContracts"][rid].get(field),list):
            index["dependencyContracts"][rid][field]=[new if x==old else x for x in index["dependencyContracts"][rid][field]]
    index["dependencyContracts"][rid]["engineeringDecision"]="R11_REPLACE_STALE_SEARCHLIGHT_TERM"
    rid="IMO-101"; terms=["ship","hasPolarRoutePlan","polarRoutePlan","voyagePlanningTopicCoverage"]
    obligation="A ship has a polarRoutePlan through hasPolarRoutePlan, and voyagePlanningTopicCoverage is exactly true on that plan."
    set_index(index,rid,terms,{"hasPolarRoutePlan":"ship","voyagePlanningTopicCoverage":"polarRoutePlan"},"ship",obligation)
    set_contract(index,rid,schemaVersion=1,verificationMode="DIRECT_STATIC",engineeringDecision="R11_APPROVED_POLAR_ROUTE_PLAN_PATH",
        ownerClasses=["ship","polarRoutePlan"],directConstraintTerms=terms,applicabilityTerms=[],operandTerms=[],resultTerms=[],
        comparisonTerms=["voyagePlanningTopicCoverage"],relationshipTerms=["hasPolarRoutePlan"],evidenceTerms=[],controlledValueTerms=[],timeTerms=[],
        modelPaths=[{"fromOwner":"ship","via":"hasPolarRoutePlan","toOwner":"polarRoutePlan"}],formulaExpression="",comparisonModel=obligation,
        requiredModelFields=["verificationMode","comparisonModel","relationshipTerms","modelPaths"])

    # IMO-103 existing string-valued ship-type branches.
    rid="IMO-103"; index["requirements"][rid]=sorted(set(index["requirements"][rid])|{"shipType"})
    index["termOwners"][rid]={term:"ship" for term in index["requirements"][rid] if term not in {"evidenceStateApproved"}}
    obligation=("Retain the alternate-qualified-person STCW, advanced-training, watch-coverage, and rest conditions. "
        "For shipType 'passenger ship' or 'tanker' in waters other than open or bergy waters, designated officers meet basic training. "
        "For shipType 'cargo ship other than tanker' where iceConcentration exceeds 2/10, designated officers meet basic training.")
    index["semanticObligations"][rid]=[obligation]; c=index["dependencyContracts"][rid]
    c["directConstraintTerms"]=index["requirements"][rid]; c["applicabilityTerms"]=["alternateQualifiedPersonUsed","shipType","iceCondition","iceConcentration"]
    c["comparisonModel"]=obligation; c["stringValuePolicies"]={"shipType":["passenger ship","tanker","cargo ship other than tanker"]}
    c["engineeringDecision"]="R11_REUSE_EXISTING_SHIP_TYPE_STRINGS"

    # Shared discharge-distance record model.
    for rid in ("IMO-117","IMO-123"):
        terms=sorted(set(index["requirements"][rid])|{"ship","hasDischargeDistanceRecord","dischargeDistanceRecords",
            "distanceToNearestLandIceShelfOrFastIce","distanceToAreaWithIceConcentrationGreaterThanOneTenth"})
        owners=dict(index["termOwners"].get(rid,{})); owners.update({"hasDischargeDistanceRecord":"ship",
            "distanceToNearestLandIceShelfOrFastIce":"dischargeDistanceRecords",
            "distanceToAreaWithIceConcentrationGreaterThanOneTenth":"dischargeDistanceRecords"})
        obligation=index["semanticObligations"][rid][0]
        if rid=="IMO-117": obligation += " Both discharge distances are represented on each applicable dischargeDistanceRecords node; no numerical minimum is imposed for the ice-concentration-area distance."
        else: obligation += " Both discharge distances are represented on each applicable dischargeDistanceRecords node; distanceToNearestLandIceShelfOrFastIce is at least 12 nautical miles and no numerical minimum is imposed for the ice-concentration-area distance."
        set_index(index,rid,terms,owners,"ship",obligation); c=index["dependencyContracts"][rid]
        c["directConstraintTerms"]=terms; c["relationshipTerms"]=["hasDischargeDistanceRecord"]
        c["modelPaths"]=[{"fromOwner":"ship","via":"hasDischargeDistanceRecord","toOwner":"dischargeDistanceRecords"}]
        c["comparisonTerms"]=["distanceToNearestLandIceShelfOrFastIce"] if rid=="IMO-123" else []
        c["comparisonModel"]=obligation; c["ownerClasses"]=["ship","dischargeDistanceRecords"]
        c["requiredModelFields"]=["verificationMode","comparisonModel","relationshipTerms","modelPaths"]
        c["engineeringDecision"]="R11_APPROVED_SHARED_DISCHARGE_DISTANCE_MODEL"

    # Contract-only corrections TRF-014, TRF-029.
    rid="TRF-014"; c=index["dependencyContracts"][rid]
    c["applicabilityTerms"]=["constructionDate","firstScheduledDryDockingDate","upperIceWaterlineDraught","summerLoadLineFreshWaterDraught"]
    c["comparisonModel"]=("Keep all certificate/document obligations. IF constructionDate >= literal 2007-07-01 AND summerLoadLineFreshWaterDraught is above upperIceWaterlineDraught, "
        "THEN warningTrianglePresent = true and iceClassDraughtMarkPresent = true. ELSE IF constructionDate < literal 2007-07-01 AND upperIceWaterlineDraught is below summerLoadLineFreshWaterDraught, "
        "THEN those markings exist no later than firstScheduledDryDockingDate after literal 2007-07-01.")
    c["literalConstants"]={"regulatoryCutoffDate":"2007-07-01"}; c["engineeringDecision"]="R11_APPROVED_LITERAL_DATE_CONDITIONAL"
    rid="TRF-029"; obligation=("IF directAnalysisUsed = true, THEN prescribedProcedureApplicability = false, "
        "directAnalysisApprovalStatus = evidenceStateApproved, and structuralArrangement exists.")
    index["requirements"][rid]=sorted(set(index["requirements"][rid])|{"evidenceStateApproved"}); index["semanticObligations"][rid]=[obligation]
    c=index["dependencyContracts"][rid]; c["applicabilityTerms"]=["directAnalysisUsed"]; c["comparisonTerms"]=["prescribedProcedureApplicability","directAnalysisApprovalStatus"]
    c["controlledValueTerms"]=["evidenceStateApproved"]; c["comparisonModel"]=obligation; c["conditionalRules"]=[{"if":"directAnalysisUsed = true","then":"prescribedProcedureApplicability = false; directAnalysisApprovalStatus = evidenceStateApproved; structuralArrangement exists"}]
    c["engineeringDecision"]="R11_APPROVED_DIRECT_ANALYSIS_CONDITIONAL"

    # TRF-043 termination case.
    rid="TRF-043"; add={"framingIceStrengtheningTerminationCase","hasFramingIceStrengtheningTerminationCase","terminationAdjacentBoundary","deckStructure","tankBoundaryPlating","tankTop"}
    terms=sorted(set(index["requirements"][rid])|add); obligation=("For each applicable framingIceStrengtheningTerminationCase, if extensionBeyondAdjacentDeckOrTankBoundary <= 250 mm, "
        "iceStrengtheningTerminationAtAdjacentBoundaryPermitted is true; terminationAdjacentBoundary is a deckStructure, tankBoundaryPlating, or tankTop.")
    owners=dict(index["termOwners"][rid]); owners.update({"hasFramingIceStrengtheningTerminationCase":"ship","terminationAdjacentBoundary":"framingIceStrengtheningTerminationCase",
        "extensionBeyondAdjacentDeckOrTankBoundary":"framingIceStrengtheningTerminationCase","iceStrengtheningTerminationAtAdjacentBoundaryPermitted":"framingIceStrengtheningTerminationCase"})
    set_index(index,rid,terms,owners,"ship",obligation); c=index["dependencyContracts"][rid]
    c.update(ownerClasses=["ship","framingIceStrengtheningTerminationCase"],directConstraintTerms=terms,
        applicabilityTerms=["extensionBeyondAdjacentDeckOrTankBoundary"],comparisonTerms=["extensionBeyondAdjacentDeckOrTankBoundary","iceStrengtheningTerminationAtAdjacentBoundaryPermitted"],
        relationshipTerms=["hasFramingIceStrengtheningTerminationCase","terminationAdjacentBoundary"],controlledValueTerms=["deckStructure","tankBoundaryPlating","tankTop"],
        modelPaths=[{"fromOwner":"ship","via":"hasFramingIceStrengtheningTerminationCase","toOwner":"framingIceStrengtheningTerminationCase"},
                    {"fromOwner":"framingIceStrengtheningTerminationCase","via":"terminationAdjacentBoundary","toOwner":"hullStructure"}],
        comparisonModel=obligation,conditionalRules=[{"if":"extensionBeyondAdjacentDeckOrTankBoundary <= 250 mm","then":"iceStrengtheningTerminationAtAdjacentBoundaryPermitted = true"}],
        engineeringDecision="R11_APPROVED_TERMINATION_CASE_MODEL",requiredModelFields=["comparisonModel","relationshipTerms","modelPaths"])

    # TRF-048 boundary-condition branch, without any height-positivity addition.
    rid="TRF-048"; terms=sorted(set(index["requirements"][rid])|{"frameBoundaryConditionType","frameBoundaryConditionTypeValue","continuousBeamWithBracketsFrameCondition"})
    index["requirements"][rid]=terms; index["termOwners"][rid]["frameBoundaryConditionType"]="longitudinalFrame"
    c=index["dependencyContracts"][rid]; c["applicabilityTerms"]=["frameBoundaryConditionType","significantlyDifferentBoundaryConditions"]
    c["controlledValueTerms"]=["continuousBeamWithBracketsFrameCondition"]; c["comparisonTerms"]=["frameMomentFactorM"]
    c["conditionalRules"]=[{"if":"frameBoundaryConditionType = continuousBeamWithBracketsFrameCondition AND significantlyDifferentBoundaryConditions = false","then":"frameMomentFactorM = 13.3"}]
    c["comparisonModel"] += " IF frameBoundaryConditionType = continuousBeamWithBracketsFrameCondition AND significantlyDifferentBoundaryConditions = false, THEN frameMomentFactorM = 13.3."
    c["engineeringDecision"]="R11_APPROVED_FRAME_BOUNDARY_CONDITION_BRANCH"

    # TRF-063 strengthening boundary relation.
    rid="TRF-063"; terms=sorted(set(index["requirements"][rid])|{"strengtheningEnvelopeBoundary"})
    owners=dict(index["termOwners"][rid]); owners["strengtheningEnvelopeBoundary"]="sidePropellerStrengtheningEnvelope"
    obligation="Each sidePropellerStrengtheningEnvelope has strengtheningEnvelopeBoundary class tankTop, strengtheningForwardExtent >= 1.5 m, and strengtheningAftExtent >= 1.5 m."
    set_index(index,rid,terms,owners,"ship",obligation); c=index["dependencyContracts"][rid]
    c.update(ownerClasses=["ship","sidePropellerStrengtheningEnvelope"],directConstraintTerms=terms,
        relationshipTerms=["hasSidePropellerStrengtheningEnvelope","strengtheningEnvelopeBoundary"],comparisonTerms=["strengtheningForwardExtent","strengtheningAftExtent"],
        controlledValueTerms=["tankTop"],modelPaths=[{"fromOwner":"ship","via":"hasSidePropellerStrengtheningEnvelope","toOwner":"sidePropellerStrengtheningEnvelope"},
        {"fromOwner":"sidePropellerStrengtheningEnvelope","via":"strengtheningEnvelopeBoundary","toOwner":"hullStructure"}],comparisonModel=obligation,
        engineeringDecision="R11_APPROVED_ENVELOPE_BOUNDARY_PATH",requiredModelFields=["comparisonModel","relationshipTerms","modelPaths"])

    # TRF-070 readiness cleanup only.
    rid="TRF-070"; c=index["dependencyContracts"][rid]
    c["operandTerms"]=["thrusterType","mainPropulsionThruster","propellerIceInteractionLoad","thrusterBodyIceInteractionLoad","localIcePressure"]
    c["resultTerms"]=["designConditionLocalStrengthCapacity"]; c["applicabilityTerms"]=["thrusterType","mainPropulsionThruster"]
    c["stringValuePolicies"]={"thrusterType":["azimuthing","fixed"]}
    c["directCheckSubconstraints"]=[{"id":"thrusterLocalStrengthResidual","mode":"DIRECT_CHECK",
        "description":"Externally assessed local-strength capacity meets the applicable local ice pressure.",
        "requiredTerms":["designConditionLocalStrengthCapacity","localIcePressure"],
        "comparison":"designConditionLocalStrengthCapacity >= localIcePressure"}]
    c["engineeringDecision"]="R11_APPROVED_COMPLEX_READINESS_CLEANUP"; c["formulaExpression"]=""

    # TRF-075 load case, linked blade/ice block, and exclusive force choice.
    rid="TRF-075"; terms=["ship","hasPropellerBladeLoadCase","propellerBladeLoadCase","propellerBladeLoadCaseBlade",
        "propellerBlade","propellerBladeLoadCaseIceBlock","iceBlock","backwardBladeForce","forwardBladeForce"]
    obligation="Each applicable propellerBladeLoadCase links to its propellerBlade and iceBlock and has exactly one of backwardBladeForce or forwardBladeForce."
    set_index(index,rid,terms,{"hasPropellerBladeLoadCase":"ship","propellerBladeLoadCaseBlade":"propellerBladeLoadCase",
        "propellerBladeLoadCaseIceBlock":"propellerBladeLoadCase","backwardBladeForce":"propellerBladeLoadCase","forwardBladeForce":"propellerBladeLoadCase"},"ship",obligation)
    set_contract(index,rid,schemaVersion=2,verificationMode="DIRECT_STATIC",engineeringDecision="R11_APPROVED_BLADE_LOAD_CASE_XONE",
        ownerClasses=["ship","propellerBladeLoadCase","propellerBlade","iceBlock"],directConstraintTerms=terms,applicabilityTerms=[],operandTerms=[],resultTerms=[],
        comparisonTerms=["backwardBladeForce","forwardBladeForce"],relationshipTerms=["hasPropellerBladeLoadCase","propellerBladeLoadCaseBlade","propellerBladeLoadCaseIceBlock"],
        evidenceTerms=[],controlledValueTerms=[],timeTerms=[],modelPaths=[{"fromOwner":"ship","via":"hasPropellerBladeLoadCase","toOwner":"propellerBladeLoadCase"},
        {"fromOwner":"propellerBladeLoadCase","via":"propellerBladeLoadCaseBlade","toOwner":"propellerBlade"},
        {"fromOwner":"propellerBladeLoadCase","via":"propellerBladeLoadCaseIceBlock","toOwner":"iceBlock"}],formulaExpression="",comparisonModel=obligation,
        exclusiveChoicePolicies=[{"owner":"propellerBladeLoadCase","exactlyOneOf":["backwardBladeForce","forwardBladeForce"],"encoding":"sh:xone or equivalent deterministic exclusive choice"}],
        requiredModelFields=["verificationMode","comparisonModel","relationshipTerms","modelPaths","exclusiveChoicePolicies"])

    # TRF-109 Table 6-14 C1-C4 values and Nice range only.
    rid="TRF-109"; coeff=["fatigueCoefficientC1","fatigueCoefficientC2","fatigueCoefficientC3","fatigueCoefficientC4"]
    terms=["ship","hasTableLookupCase","tableLookupCase","tableReference","propellerType","iceLoadCycleCount"]+coeff
    obligation=("For a Table 6-14 tableLookupCase: propellerType 'open' selects C1=0.000747, C2=0.0645, C3=-0.0565, C4=2.22; "
        "propellerType 'ducted' selects C1=0.000534, C2=0.0533, C3=-0.0459, C4=2.584. Require 5000000 <= iceLoadCycleCount <= 100000000. Do not calculate later rho expressions.")
    set_index(index,rid,terms,{"hasTableLookupCase":"ship","tableReference":"tableLookupCase","propellerType":"tableLookupCase",
        **{x:"tableLookupCase" for x in coeff},"iceLoadCycleCount":"ship"},"ship",obligation)
    set_contract(index,rid,schemaVersion=2,verificationMode="DIRECT_STATIC",engineeringDecision="R11_APPROVED_TABLE_6_14_COEFFICIENTS",
        ownerClasses=["ship","tableLookupCase"],directConstraintTerms=terms,applicabilityTerms=["propellerType"],operandTerms=[],resultTerms=coeff,
        comparisonTerms=["iceLoadCycleCount"]+coeff,relationshipTerms=["hasTableLookupCase","tableReference"],evidenceTerms=[],controlledValueTerms=[],timeTerms=[],
        modelPaths=[{"fromOwner":"ship","via":"hasTableLookupCase","toOwner":"tableLookupCase"}],formulaExpression="",comparisonModel=obligation,
        tableModel={"reference":"Table 6-14","open":{"C1":0.000747,"C2":0.0645,"C3":-0.0565,"C4":2.22},
                    "ducted":{"C1":0.000534,"C2":0.0533,"C3":-0.0459,"C4":2.584}},
        stringValuePolicies={"propellerType":["open","ducted"]},requiredModelFields=["verificationMode","comparisonModel","tableModel","relationshipTerms","modelPaths"])

    # TRF-133 aggregate marking nodes only.
    rid="TRF-133"; terms=set(index["requirements"][rid]); terms.discard("hasWarningTriangle"); terms.discard("warningTriangle")
    required={"warningTriangleMarking","iceClassDraughtMarking","hasWarningTriangleMarking","hasIceClassDraughtMarking",
        "warningTriangleSideLength","markingPlateThickness","markingWeldedToShipSide","reflectingMarkingColour",
        "markingPlainlyVisibleInIceConditions","letterDimensionsEqualLoadLineMark"}; terms|=required
    index["requirements"][rid]=sorted(terms); owners=index["termOwners"][rid]; owners.pop("hasWarningTriangle",None)
    owners.update({"warningTriangleSideLength":"warningTriangleMarking","letterDimensionsEqualLoadLineMark":"iceClassDraughtMarking",
        "hasWarningTriangleMarking":"ship","hasIceClassDraughtMarking":"ship","markingPlateThickness":"hullStructure",
        "markingWeldedToShipSide":"hullStructure","reflectingMarkingColour":"hullStructure","markingPlainlyVisibleInIceConditions":"hullStructure"})
    c=index["dependencyContracts"][rid]; c["directConstraintTerms"]=sorted(terms); c["ownerClasses"]=["ship","warningTriangleMarking","iceClassDraughtMarking"]
    c["relationshipTerms"]=["hasWarningTriangleMarking","hasIceClassDraughtMarking","draughtMarkAftReferencePoint","reflectingMarkingColour"]
    c["modelPaths"]=[{"fromOwner":"ship","via":"hasWarningTriangleMarking","toOwner":"warningTriangleMarking"},
        {"fromOwner":"ship","via":"hasIceClassDraughtMarking","toOwner":"iceClassDraughtMarking"},
        {"fromOwner":"iceClassDraughtMarking","via":"draughtMarkAftReferencePoint","toOwner":"markingReferencePointValue"}]
    c["aggregateMarkingPolicies"]={"warningTriangleMarking":["warningTriangleSideLength","markingPlateThickness","markingWeldedToShipSide","reflectingMarkingColour","markingPlainlyVisibleInIceConditions"],
        "iceClassDraughtMarking":["markingPlateThickness","markingWeldedToShipSide","reflectingMarkingColour","markingPlainlyVisibleInIceConditions","letterDimensionsEqualLoadLineMark"]}
    c["engineeringDecision"]="R11_APPROVED_AGGREGATE_MARKING_NODES"

    # Category/count delta and evidence/index identity.
    counts=dict(Counter(r["category"] for r in evidence["requirements"]));
    if counts != EXPECTED_COUNTS: raise RuntimeError(f"Unexpected R11 category counts: {counts}")
    changed={rid for rid in by_id if by_id[rid]["category"] != old_by[rid]["category"]}
    if changed != set(CATEGORY_CHANGES): raise RuntimeError(f"Unapproved category changes: {sorted(changed)}")
    evidence["summary"]["requirementsByCategory"] = EXPECTED_COUNTS
    evidence["summary"]["activationCounts"] = dict(Counter(r["activeStatus"] for r in evidence["requirements"]))
    evidence["summary"]["verificationPolicyLockId"] = LOCK_ID
    evidence["summary"]["verificationPolicy"] = "R11 approved source-grounded mechanical corrections"
    index["sourceLockId"] = LOCK_ID; index["version"] = "11.0"

    # R11-specific prompt copies: do not modify global/R10 prompt files.
    prompt_dir = PIPE / "prompts/r11"; prompt_dir.mkdir(parents=True)
    generator=(PIPE/"prompts/generator.txt").read_text(encoding="utf-8")
    validator=(PIPE/"prompts/validator.txt").read_text(encoding="utf-8")
    gen_anchor="    Never invent a formula, threshold, result, method, or evidence obligation."
    gen_insert=(gen_anchor+"\n    Require a calculation case, analysis case, method reference, table reference, or evidence artifact only when that structure is explicitly declared in the dependency contract. Do not infer generic calculation or method evidence merely because a Complex source contains a nonlinear formula.")
    val_anchor="This readiness boundary does not permit omission of required inputs, outputs,\nrelationships, evidence, or explicit DIRECT_CHECK items."
    val_insert=(val_anchor+"\nRequire a calculation case, analysis case, method reference, table reference, or evidence artifact only when it is explicitly declared in the dependency contract. Do not demand generic calculation or method evidence merely because a Complex source contains a nonlinear formula.")
    if gen_anchor not in generator or val_anchor not in validator: raise RuntimeError("Prompt insertion anchor missing")
    (prompt_dir/"generator.txt").write_text(generator.replace(gen_anchor,gen_insert,1),encoding="utf-8")
    (prompt_dir/"validator.txt").write_text(validator.replace(val_anchor,val_insert,1),encoding="utf-8")

    # Strip internal authoring-only domain helper from registry output and write CSV.
    for item in registry: item.pop("r11Domain",None)
    write(TARGET/"evidence/stage1_approved.json",evidence); write(TARGET/"requirement_term_index.json",index)
    write(TARGET/"registry/term_registry.json",registry)
    fields=list(read(SOURCE/"registry/term_registry.json")[0].keys())
    with (TARGET/"registry/term_registry.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore");writer.writeheader()
        for item in registry: writer.writerow({k:" | ".join(v) if isinstance(v,list) else v for k,v in item.items()})
    policy=read(TARGET/"evidence/verification_policy_r10.json"); policy.update(lockId=LOCK_ID,categoryCounts=EXPECTED_COUNTS)
    policy["r11CategoryChanges"]={rid:list(change) for rid,change in CATEGORY_CHANGES.items()}
    policy["complexReadinessClarification"]=("Calculation/analysis cases, method/table references, and evidence artifacts are required only when explicitly declared by the dependency contract; nonlinear source mathematics alone does not imply generic evidence.")
    write(TARGET/"evidence/verification_policy_r11.json",policy)
    (TARGET/"evidence/VERIFICATION_POLICY_R11.md").write_text("# R11 verification policy provenance\n\nR11 retains the five-category policy and clarifies that COMPLEX_READINESS requires calculation/analysis/method/table/evidence structures only when explicitly declared in the dependency contract. Nonlinear source mathematics alone does not imply generic evidence.\n",encoding="utf-8")
    decisions={"lockId":LOCK_ID,"sourceLockId":SOURCE_LOCK_ID,"categoryChanges":CATEGORY_CHANGES,
        "deferredScopeOnly":["I2-002"],"newCanonicalTerms":sorted(expected_new),
        "modifiedCanonicalTerms":{"frameBoundaryConditionType":{"domainBefore":"transverseFrame","domainAfter":"frame"}},
        "contractOnlyChanges":["I2-023","I2-035","IMO-032","IMO-049","IMO-072","IMO-103","TRF-014","TRF-029","TRF-070","TRF-133"],
        "apiCalls":0}
    write(TARGET/"registry/r11_source_grounded_change_decisions.json",decisions)
    write(TARGET/"provenance/r10_immutable_source_hashes.json",provenance)
    bound_relatives=["context/nltl_benchmark_context.jsonld","evidence/stage1_approved.json","evidence/verification_policy_r11.json","evidence/VERIFICATION_POLICY_R11.md",
        "ontology/nltl_benchmark_vocabulary.ttl","ontology/nltl_benchmark_vocabulary.rdf","registry/term_registry.json","registry/term_registry.csv",
        "registry/r11_source_grounded_change_decisions.json","requirement_term_index.json","provenance/r10_immutable_source_hashes.json",
        "few_shots/few_shot_pairs.jsonl","few_shots/catalog.json","few_shots/validation_report.json"]
    bound={rel:sha(TARGET/rel) for rel in bound_relatives}
    write(TARGET/"r11_prelock_binding.json",{"lockId":LOCK_ID,"status":"PRELOCK_OFFLINE_VALIDATION_ONLY","workbook":"Pending R11 workbook","workbookSha256":"",
        "boundMachineReadableArtifacts":bound,"boundRequirementIndex":{"requirement_term_index.json":bound["requirement_term_index.json"]}})
    write(TARGET/"prelock_manifest.json",{"lockId":LOCK_ID,"sourceLockId":SOURCE_LOCK_ID,"boundArtifacts":bound,
        "categoryChanges":CATEGORY_CHANGES,"categoryCounts":EXPECTED_COUNTS,"newCanonicalTerms":sorted(expected_new),
        "modifiedCanonicalTerms":decisions["modifiedCanonicalTerms"],"apiCalls":0})
    print(json.dumps({"status":"R11_PRELOCK_CREATED","lockId":LOCK_ID,"categoryCounts":counts,
        "newCanonicalTerms":len(expected_new),"modifiedCanonicalTerms":["frameBoundaryConditionType"],
        "r10ImmutableFiles":provenance["fileCount"],"apiCalls":0},indent=2))


if __name__ == "__main__": main()
