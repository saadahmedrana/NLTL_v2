from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import OWL, SKOS, XSD


MVP = Path(__file__).resolve().parents[2]
SOURCE = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R6"
TARGET = MVP / "BENCHMARK_VOCABULARY/FINAL_LOCK_R7"
LOCK_ID = "VOCAB-LOCK-2026-08-20-R7"
ROOT_BASENAME = "benchmark_vocabulary_stage2_LOCK-2026-08-20-R7"
CANONICAL = "https://w3id.org/nltl/vocab#"
NLTL = Namespace(CANONICAL)
QUDT = Namespace("http://qudt.org/schema/qudt/")

IMPLEMENTED = [
    "I2-019", "I2-024", "I2-037", "IMO-037", "TRF-013", "TRF-102",
    "TRF-112", "TRF-123", "TRF-127", "TRF-130", "I2-061", "I2-064",
    "I2-066", "IMO-001", "IMO-003", "TRF-006", "TRF-014", "TRF-050", "TRF-133",
]

CORRECTIONS = {
    "I2-009": ("HUMAN_REVIEW_UNRESOLVED", "No R7 ontology or dependency change; representation of hull-shape-independent parameter determination remains a human modelling decision."),
    "I2-019": ("EXISTING_PATH_AND_OWNER_CORRECTION", "Use structuralMember -> hasSpannedHullArea -> hullAreaValue, with hullAreaFactor on each area and selectedHullAreaFactor on the member."),
    "I2-024": ("DEPENDENCY_CONTEXT_CORRECTION", "Supply the existing interpolationPoint, interpolationPointCoordinate and interpolationPointResult structure."),
    "I2-037": ("EXISTING_LOAD_CASE_PATH_CORRECTION", "Use hasStructuralMemberLoadCase and the existing loadCase/iceLoadPatchDesignCase representation."),
    "IMO-037": ("OWNER_PATH_CORRECTION", "Place residualStabilityFactorSI on each loadingConditionCase reached through hasLoadingConditionCase."),
    "TRF-013": ("DEPENDENCY_CONTEXT_CORRECTION", "Supply existing fore/aft maximum/minimum ice-class draught bounds with upper/lower waterline paths."),
    "TRF-102": ("DEPENDENCY_CONTEXT_CORRECTION", "Supply existing propellerBladeCount as source symbol Z and complete the formula operands/results."),
    "TRF-112": ("DEPENDENCY_CONTRACT_CORRECTION", "Remove the unstated formula obligation; retain combined-load no-yield and >=1.0 bending/torsional safety-factor semantics."),
    "TRF-123": ("DEPENDENCY_CONTRACT_CORRECTION", "Use occasionalForceCaseAssessedComponent and remove the unsupported propeller-shaft-line population narrowing."),
    "TRF-127": ("DEPENDENCY_COMPARISON_CORRECTION", "Represent conditional additional-capacity sufficiency without inventing a starting-air baseline sum or term."),
    "TRF-130": ("EXISTING_CLASS_OWNER_CORRECTION", "Reuse hasComponent and inletChest; place chest-specific properties on inletChest and keep alternative selectors ship-owned."),
    "I2-061": ("RELATIONSHIP_ADDITION", "Associate a calculationCase with the hullStructure assessed by the prescribed shell-plating/local-frame procedure."),
    "I2-064": ("CONTROLLED_VALUE_ADDITION", "Add the linear calculation method controlled value under the existing calculationMethodValue class."),
    "I2-066": ("MINIMUM_WELD_NODE_MODEL", "Add a weld node and ship-to-weld path; reuse withinIceStrengthenedArea, weldTypeValue and doubleContinuousWeld."),
    "IMO-001": ("CONTROLLED_VALUE_ADDITION", "Use controlled designIceCondition values and add the medium first-year/possible old-ice-inclusions condition."),
    "IMO-003": ("CONTROLLED_VALUE_ADDITION", "Reuse controlled ice-condition infrastructure and add the less-severe-than-category-A-and-B condition."),
    "TRF-006": ("EVIDENCE_PROPERTY_ADDITION", "Add only the ship-owner request/election evidence for applying the 2008 engine-output requirements."),
    "TRF-014": ("DOCUMENT_OWNER_CORRECTION", "Bind the six existing draught values to the existing classCertificate reached by hasClassCertificate."),
    "TRF-050": ("ATTACHMENT_NODE_COMPLETION", "Add one frameAttachmentRecord class and use the existing frameAttachment relationship as its path."),
    "TRF-133": ("MARKING_RELATION_AND_SELECTOR_ADDITION", "Add the upper-edge-above-ICE-mark assertion and timber-load-line applicability selector; reuse existing reference-point values."),
}

NEW_TERMS = {
    "calculationCaseAssessedHullStructure",
    "linearCalculationMethodValue",
    "weld",
    "hasWeld",
    "mediumFirstYearIceWithPossibleOldIceInclusions",
    "iceConditionLessSevereThanCategoryAAndB",
    "ownerRequested2008EngineOutputRequirements",
    "frameAttachmentRecord",
    "warningTriangleUpperEdgeVerticallyAboveIceMark",
    "timberLoadLineMarkApplicable",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def r6_hash_manifest() -> dict:
    roots = [
        SOURCE,
        MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-19-R6.xlsx",
        MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-19-R6.lock.json",
        MVP / "benchmark_vocabulary_stage2_LOCK-2026-08-19-R6.sha256",
    ]
    files = {}
    for root in roots:
        candidates = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
        for path in candidates:
            files[str(path.relative_to(MVP))] = sha256(path)
    aggregate = hashlib.sha256("\n".join(f"{digest}  {name}" for name, digest in sorted(files.items())).encode()).hexdigest()
    return {"sourceLockId": "VOCAB-LOCK-2026-08-19-R6", "fileCount": len(files), "aggregateSha256": aggregate, "files": files}


def new_term(
    local: str, kind: str, parent_or_range: str, label: str, concept_id: str,
    module: str, requirements: list[str], source_refs: str, evidence: str,
    definition: str, role: str, datatype: str = "",
) -> dict:
    return {
        "aliases": [],
        "conceptId": concept_id,
        "confidence": "High",
        "datatype": datatype,
        "evidenceExcerpt": evidence,
        "haithamUri": "",
        "iri": CANONICAL + local,
        "kind": kind,
        "label": label,
        "localName": local,
        "mappingStatus": "No external equivalence claimed; source-grounded R7 benchmark term.",
        "module": module,
        "nameQaStatus": "Passed - ASCII-only lowerCamelCase and collision review",
        "namingBasis": "Verified regulatory wording and minimum R7 graph role",
        "namingRule": "N4/N5 - singular ASCII lowerCamelCase; relationship direction is explicit.",
        "normalizedDefinition": definition,
        "parentOrRange": parent_or_range,
        "quantityKindLabel": "",
        "requirements": requirements,
        "roleDecision": role,
        "sourceConceptIds": [concept_id],
        "sourceRefs": source_refs,
        "stage1LocalNames": [local],
        "stage2UnitEvidence": "",
        "unitDecisionStatus": "Not a quantity property",
        "unitIri": "",
        "unitSymbol": "",
    }


def additions() -> list[dict]:
    return [
        new_term(
            "calculationCaseAssessedHullStructure", "ObjectProperty", CANONICAL + "hullStructure",
            "Calculation case assessed hull structure", "VOC-R7-0001", "hull", ["I2-061"],
            "I2-061 | IACS_UR_I2 p.21 | I2.17.2",
            "Direct calculations are not to be utilised as an alternative to the analytical procedures prescribed for the shell plating and local frame requirements given in I2.4, I2.6, and I2.7.",
            "NORMALIZED (R7): links a calculation case to the shell-plating or local-frame hull structure whose prescribed analytical procedure governs that case.",
            "Typed relationship path",
        ),
        new_term(
            "linearCalculationMethodValue", "NamedIndividual", CANONICAL + "calculationMethodValue",
            "Linear calculation method", "VOC-R7-0002", "hull", ["I2-064"],
            "I2-064 | IACS_UR_I2 p.21 | I2.17.5",
            "For linear structural calculations: web plates and flange elements in compression and shear shall meet the applicable buckling criteria.",
            "NORMALIZED (R7): controlled calculation-method value selecting the linear structural calculation branch in I2.17.5.",
            "Controlled value",
        ),
        new_term(
            "weld", "Class", CANONICAL + "benchmarkEntity", "Weld", "VOC-R7-0003", "hull", ["I2-066"],
            "I2-066 | IACS_UR_I2 p.21 | I2.18.2",
            "All welding within ice-strengthened areas is to be of the double continuous type.",
            "NORMALIZED (R7): an individual weld whose scope and controlled weld type can be verified.",
            "Reusable engineering node type",
        ),
        new_term(
            "hasWeld", "ObjectProperty", CANONICAL + "weld", "Has weld", "VOC-R7-0004", "hull", ["I2-066"],
            "I2-066 | IACS_UR_I2 p.21 | I2.18.2",
            "All welding within ice-strengthened areas is to be of the double continuous type.",
            "NORMALIZED (R7): links a ship to each weld in scope for the I2.18.2 welding requirement.",
            "Typed relationship path",
        ),
        new_term(
            "mediumFirstYearIceWithPossibleOldIceInclusions", "NamedIndividual", CANONICAL + "iceConditionValue",
            "Medium first-year ice with possible old-ice inclusions", "VOC-R7-0005", "operations", ["IMO-001"],
            "IMO-001 | IMO_POLAR_CODE p.11 | 1.2.1",
            "Category A ship means a ship designed for operation in polar waters in at least medium first-year ice, which may include old ice inclusions.",
            "NORMALIZED (R7): controlled design-ice-condition value for at least medium first-year ice with possible old-ice inclusions.",
            "Controlled value",
        ),
        new_term(
            "iceConditionLessSevereThanCategoryAAndB", "NamedIndividual", CANONICAL + "iceConditionValue",
            "Ice condition less severe than categories A and B", "VOC-R7-0006", "operations", ["IMO-003"],
            "IMO-003 | IMO_POLAR_CODE p.11 | 1.2.3",
            "Category C ship means a ship designed to operate in open water or in ice conditions less severe than those included in categories A and B.",
            "NORMALIZED (R7): controlled design-ice-condition value for the source-defined less-severe-than-category-A-and-B branch.",
            "Controlled value",
        ),
        new_term(
            "ownerRequested2008EngineOutputRequirements", "DatatypeProperty", str(XSD.boolean),
            "Owner requested 2008 engine output requirements", "VOC-R7-0007", "regulation", ["TRF-006"],
            "TRF-006 | TRAFICOM p.8 | 2.1",
            "On the owner's request, the requirements of the 2008 Ice Class Regulations may, however, be applied to the engine output of such ships.",
            "NORMALIZED (R7): true when the owner has requested application of the 2008 Ice Class Regulations to engine output for the specified ship cohort.",
            "Typed literal evidence", "xsd:boolean",
        ),
        new_term(
            "frameAttachmentRecord", "Class", CANONICAL + "benchmarkEntity", "Frame attachment record",
            "VOC-R7-0008", "hull", ["TRF-050"], "TRF-050 | TRAFICOM p.21 | 4.4.4.2",
            "The frames shall be attached to the shell by a double continuous weld. No scalloping is allowed (except when crossing shell plate butts).",
            "NORMALIZED (R7): reified frame-to-shell attachment node that owns weld-type, scalloping and shell-plate-butt evidence.",
            "Reusable engineering node type",
        ),
        new_term(
            "warningTriangleUpperEdgeVerticallyAboveIceMark", "DatatypeProperty", str(XSD.boolean),
            "Warning triangle upper edge vertically above ICE mark", "VOC-R7-0009", "hull", ["TRF-133"],
            "TRF-133 | TRAFICOM p.65 | Annex III",
            "The upper edge of the warning triangle must be located vertically above the ICE mark.",
            "NORMALIZED (R7): true when the warning-triangle upper edge is vertically above the ICE mark as required by Annex III.",
            "Typed literal spatial assertion", "xsd:boolean",
        ),
        new_term(
            "timberLoadLineMarkApplicable", "DatatypeProperty", str(XSD.boolean),
            "Timber load line mark applicable", "VOC-R7-0010", "hull", ["TRF-133"],
            "TRF-133 | TRAFICOM p.65 | Annex III",
            "The ice class draught mark must be located 540 mm abaft of the centre of the load line ring or 540 mm abaft of the vertical line of the timber load line mark, if applicable.",
            "NORMALIZED (R7): selects the timber-load-line reference branch when the timber load line mark applies.",
            "Typed literal applicability selector", "xsd:boolean",
        ),
    ]


def add_graph_term(graph: Graph, row: dict) -> None:
    subject = NLTL[row["localName"]]
    kind = row["kind"]
    parent = URIRef(row["parentOrRange"])
    if kind == "Class":
        graph.add((subject, RDF.type, OWL.Class))
        graph.add((subject, RDFS.subClassOf, parent))
    elif kind == "NamedIndividual":
        graph.add((subject, RDF.type, OWL.NamedIndividual))
        graph.add((subject, RDF.type, parent))
    elif kind == "ObjectProperty":
        graph.add((subject, RDF.type, OWL.ObjectProperty))
        domain = {
            "calculationCaseAssessedHullStructure": NLTL.calculationCase,
            "hasWeld": NLTL.ship,
        }[row["localName"]]
        graph.add((subject, RDFS.domain, domain))
        graph.add((subject, RDFS.range, parent))
    elif kind == "DatatypeProperty":
        graph.add((subject, RDF.type, OWL.DatatypeProperty))
        domain = {
            "ownerRequested2008EngineOutputRequirements": NLTL.ship,
            "warningTriangleUpperEdgeVerticallyAboveIceMark": NLTL.warningTriangleMarking,
            "timberLoadLineMarkApplicable": NLTL.ship,
        }[row["localName"]]
        graph.add((subject, RDFS.domain, domain))
        graph.add((subject, RDFS.range, parent))
    graph.add((subject, RDFS.label, Literal(row["label"], lang="en")))
    graph.add((subject, SKOS.prefLabel, Literal(row["label"], lang="en")))
    graph.add((subject, SKOS.definition, Literal(row["normalizedDefinition"], lang="en")))
    graph.add((subject, NLTL.draftConceptId, Literal(row["conceptId"])))
    for requirement_id in row["requirements"]:
        graph.add((subject, NLTL.sourceRequirementId, Literal(requirement_id)))


def associate(registry_by_local: dict[str, dict], local: str, requirement_id: str, source_ref: str) -> None:
    row = registry_by_local[local]
    if requirement_id not in row["requirements"]:
        row["requirements"].append(requirement_id)
        row["requirements"].sort()
    refs = [part.strip() for part in row.get("sourceRefs", "").split(";") if part.strip()]
    if not any(part.startswith(requirement_id + " |") for part in refs):
        refs.append(source_ref)
        row["sourceRefs"] = "; ".join(refs)


def set_domain(graph: Graph, local: str, owner: str) -> None:
    graph.set((NLTL[local], RDFS.domain, NLTL[owner]))


def patch_ontology_registry_context() -> None:
    registry_path = TARGET / "registry/term_registry.json"
    registry = read_json(registry_path)
    registry_by_local = {row["localName"]: row for row in registry}
    existing = set(registry_by_local)
    if NEW_TERMS & existing:
        raise RuntimeError(f"Refusing R7 duplicate terms: {sorted(NEW_TERMS & existing)}")
    graph = Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    for row in additions():
        registry.append(row)
        registry_by_local[row["localName"]] = row
        add_graph_term(graph, row)

    # Existing-property semantic refinements approved for R7.
    set_domain(graph, "hullAreaFactor", "hullAreaValue")
    set_domain(graph, "residualStabilityFactorSI", "loadingConditionCase")
    # The six draught properties are legitimately used by TRF-013 on the ship
    # and by TRF-014 on classCertificate through requirement-level owner maps.
    # Remove the old overly narrow benchmarkEntity domain: classCertificate is
    # an evidence artifact, so requirement-level ownership is authoritative.
    for local in (
        "maximumIceClassDraughtFore", "maximumIceClassDraughtAmidships", "maximumIceClassDraughtAft",
        "minimumIceClassDraughtFore", "minimumIceClassDraughtAmidships", "minimumIceClassDraughtAft",
    ):
        graph.remove((NLTL[local], RDFS.domain, None))
    for local in (
        "seaInletLocation", "recommendedChestVolume", "seaChestVolume", "iceAccumulationSpaceAboveInlet",
        "fullCapacityDischargePipeConnected", "strainerOpenArea", "strainerOpenAreaRatio", "inletPipeArea",
        "nearCentrelineAndWellAftIfPossible", "alternatingCoolingWaterIntakeAndDischarge",
    ):
        set_domain(graph, local, "inletChest")
    set_domain(graph, "frameShellWeldType", "frameAttachmentRecord")
    set_domain(graph, "scallopingPresent", "frameAttachmentRecord")
    set_domain(graph, "shellPlateButtCrossing", "frameAttachmentRecord")
    graph.set((NLTL.frameAttachment, RDFS.domain, NLTL.frame))
    graph.set((NLTL.frameAttachment, RDFS.range, NLTL.frameAttachmentRecord))
    registry_by_local["frameAttachment"].update({
        "parentOrRange": CANONICAL + "frameAttachmentRecord",
        "normalizedDefinition": "NORMALIZED (R7): links a frame to its reified frameAttachmentRecord node.",
        "mappingStatus": "Source-grounded R7 range refinement; canonical local name preserved.",
    })

    # Convert two free-string selectors to existing controlled-value structures.
    graph.remove((NLTL.designIceCondition, RDF.type, OWL.DatatypeProperty))
    graph.add((NLTL.designIceCondition, RDF.type, OWL.ObjectProperty))
    graph.set((NLTL.designIceCondition, RDFS.domain, NLTL.ship))
    graph.set((NLTL.designIceCondition, RDFS.range, NLTL.iceConditionValue))
    design = registry_by_local["designIceCondition"]
    design.update({
        "kind": "ObjectProperty", "datatype": "", "parentOrRange": CANONICAL + "iceConditionValue",
        "roleDecision": "Controlled-value relationship",
        "normalizedDefinition": "NORMALIZED (R7): assigns a controlled source-defined design ice condition to a ship.",
        "mappingStatus": "Source-grounded R7 controlled-value refinement; canonical local name preserved.",
    })
    graph.remove((NLTL.weldType, RDF.type, OWL.DatatypeProperty))
    graph.add((NLTL.weldType, RDF.type, OWL.ObjectProperty))
    graph.set((NLTL.weldType, RDFS.domain, NLTL.weld))
    graph.set((NLTL.weldType, RDFS.range, NLTL.weldTypeValue))
    weld_type = registry_by_local["weldType"]
    weld_type.update({
        "kind": "ObjectProperty", "datatype": "", "parentOrRange": CANONICAL + "weldTypeValue",
        "roleDecision": "Controlled-value relationship",
        "normalizedDefinition": "NORMALIZED (R7): assigns a controlled weld type to an individual weld.",
        "mappingStatus": "Source-grounded R7 controlled-value refinement; canonical local name preserved.",
    })

    # Record reuse of existing canonical terms in the newly corrected contexts.
    references = {
        "I2-024": ["interpolationPoint", "interpolationPointCoordinate", "interpolationPointResult"],
        "I2-037": ["hasStructuralMemberLoadCase", "hasStructuralMember", "loadCase"],
        "TRF-013": ["maximumIceClassDraughtFore", "maximumIceClassDraughtAft", "minimumIceClassDraughtFore", "minimumIceClassDraughtAft"],
        "TRF-102": ["propellerBladeCount"],
        "TRF-130": ["inletChest", "hasComponent"],
        "I2-066": ["withinIceStrengthenedArea", "doubleContinuousWeld", "weldType", "weldTypeValue"],
        "IMO-003": ["openWaterIceCondition"],
        "TRF-014": ["hasClassCertificate", "classCertificate"],
        "TRF-050": ["frameAttachment"],
    }
    evidence = read_json(TARGET / "evidence/stage1_approved.json")
    req_by_id = {row["id"]: row for row in evidence["requirements"]}
    for rid, locals_ in references.items():
        req = req_by_id[rid]
        ref = f"{rid} | {req['sourceSheet']} p.{req['page']} | {req['clause']}"
        for local in locals_:
            if local in registry_by_local:
                associate(registry_by_local, local, rid, ref)

    registry.sort(key=lambda row: row["localName"])
    write_json(registry_path, registry)
    fields = list(registry[0].keys())
    with (TARGET / "registry/term_registry.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in registry:
            writer.writerow({key: " | ".join(value) if isinstance(value, list) else value for key, value in row.items()})

    ontology = URIRef(CANONICAL.rstrip("#"))
    graph.set((ontology, OWL.versionIRI, URIRef("https://w3id.org/nltl/vocab/2.17.0-stage2-final-r7")))
    graph.set((ontology, OWL.versionInfo, Literal("2.17.0-stage2-final-r7")))
    graph.serialize(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.serialize(TARGET / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    ttl = Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.ttl", format="turtle")
    rdf = Graph().parse(TARGET / "ontology/nltl_benchmark_vocabulary.rdf", format="xml")
    if not isomorphic(ttl, rdf):
        raise RuntimeError("R7 Turtle and RDF/XML are not isomorphic")

    context_path = TARGET / "context/nltl_benchmark_context.jsonld"
    context = read_json(context_path)
    mapping = context.get("@context", context)
    mapping["designIceCondition"] = {"@id": "nltl:designIceCondition", "@type": "@id"}
    mapping["weldType"] = {"@id": "nltl:weldType", "@type": "@id"}
    for row in additions():
        if row["kind"] == "ObjectProperty":
            mapping[row["localName"]] = {"@id": "nltl:" + row["localName"], "@type": "@id"}
        elif row["kind"] == "DatatypeProperty":
            mapping[row["localName"]] = {"@id": "nltl:" + row["localName"], "@type": row["datatype"]}
        else:
            mapping[row["localName"]] = "nltl:" + row["localName"]
    write_json(context_path, context)


def ensure_terms(index: dict, rid: str, terms: list[str]) -> None:
    index["requirements"][rid] = sorted(set(index["requirements"][rid]) | set(terms))


def drop_terms(index: dict, rid: str, terms: list[str]) -> None:
    index["requirements"][rid] = sorted(set(index["requirements"][rid]) - set(terms))


def patch_contracts() -> None:
    path = TARGET / "requirement_term_index.json"
    index = read_json(path)
    c = index["dependencyContracts"]
    original_i2009 = json_hash(c["I2-009"])

    ensure_terms(index, "I2-019", ["hasStructuralMember", "structuralMember", "hasSpannedHullArea", "hullAreaValue", "hullAreaFactor", "selectedHullAreaFactor"])
    drop_terms(index, "I2-019", ["spansHullArea"])
    c["I2-019"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_REUSE_SPANNED_HULL_AREA_PATH",
        "ownerClasses": ["ship", "structuralMember", "hullAreaValue"],
        "operandTerms": ["hullAreaFactor"], "resultTerms": ["selectedHullAreaFactor"],
        "comparisonTerms": ["hullAreaFactor", "selectedHullAreaFactor"],
        "relationshipTerms": ["hasStructuralMember", "hasSpannedHullArea"],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasStructuralMember", "toOwner": "structuralMember"},
            {"fromOwner": "structuralMember", "via": "hasSpannedHullArea", "toOwner": "hullAreaValue"},
        ],
        "formulaExpression": "For each structuralMember, selectedHullAreaFactor equals the maximum hullAreaFactor over every hullAreaValue reached by hasSpannedHullArea.",
        "requiredModelFields": ["operandTerms", "resultTerms", "comparisonTerms", "relationshipTerms", "modelPaths", "formulaExpression"],
    })
    index["termOwners"]["I2-019"] = {
        "hasStructuralMember": "ship", "hasSpannedHullArea": "structuralMember",
        "hullAreaFactor": "hullAreaValue", "selectedHullAreaFactor": "structuralMember",
    }

    ensure_terms(index, "I2-024", ["interpolationPoint", "interpolationPointCoordinate", "interpolationPointResult"])
    c["I2-024"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_REUSE_COMPLETE_INTERPOLATION_POINT_MODEL",
        "ownerClasses": ["ship", "obliquePlatingInterpolationCase", "interpolationPoint"],
        "operandTerms": ["framingAngle", "interpolationPointCoordinate", "interpolationPointResult", "longitudinalFramingNetPlateThickness", "transverseFramingNetPlateThickness"],
        "resultTerms": ["interpolatedNetPlateThickness"],
        "comparisonTerms": ["framingAngle", "interpolatedNetPlateThickness"],
        "relationshipTerms": ["hasObliquePlatingInterpolationCase", "interpolationLowerEndpoint", "interpolationUpperEndpoint"],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasObliquePlatingInterpolationCase", "toOwner": "obliquePlatingInterpolationCase"},
            {"fromOwner": "obliquePlatingInterpolationCase", "via": "interpolationLowerEndpoint", "toOwner": "interpolationPoint"},
            {"fromOwner": "obliquePlatingInterpolationCase", "via": "interpolationUpperEndpoint", "toOwner": "interpolationPoint"},
        ],
        "formulaExpression": "For 20 deg < framingAngle < 70 deg, interpolatedNetPlateThickness is the linear interpolation of interpolationPointResult between the lower and upper interpolationPointCoordinate endpoints.",
        "requiredModelFields": ["operandTerms", "resultTerms", "relationshipTerms", "modelPaths", "formulaExpression"],
    })
    index["termOwners"]["I2-024"].update({
        "hasObliquePlatingInterpolationCase": "ship", "framingAngle": "obliquePlatingInterpolationCase",
        "interpolationLowerEndpoint": "obliquePlatingInterpolationCase", "interpolationUpperEndpoint": "obliquePlatingInterpolationCase",
        "interpolationPointCoordinate": "interpolationPoint", "interpolationPointResult": "interpolationPoint",
        "interpolatedNetPlateThickness": "obliquePlatingInterpolationCase",
    })

    ensure_terms(index, "I2-037", ["hasStructuralMember", "structuralMember", "hasStructuralMemberLoadCase", "loadCase"])
    c["I2-037"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_REUSE_STRUCTURAL_MEMBER_LOAD_CASE_PATH",
        "ownerClasses": ["ship", "structuralMember", "loadCase", "iceLoadPatchDesignCase"],
        "operandTerms": ["combinedShearBendingEffect", "memberCapacity", "loadPatchApplicationLocation"],
        "resultTerms": ["memberCapacityMinimizationConfirmed"],
        "relationshipTerms": ["hasStructuralMember", "hasStructuralMemberLoadCase", "hasIceLoadPatchDesignCase"],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasStructuralMember", "toOwner": "structuralMember"},
            {"fromOwner": "structuralMember", "via": "hasStructuralMemberLoadCase", "toOwner": "loadCase"},
            {"fromOwner": "ship", "via": "hasIceLoadPatchDesignCase", "toOwner": "iceLoadPatchDesignCase"},
        ],
        "evidenceTerms": ["memberCapacityMinimizationConfirmed"],
        "requiredModelFields": ["operandTerms", "relationshipTerms", "modelPaths", "evidenceTerms", "comparisonModel"],
    })
    index["termOwners"]["I2-037"] = {
        "hasStructuralMember": "ship", "hasStructuralMemberLoadCase": "structuralMember",
        "hasIceLoadPatchDesignCase": "ship", "combinedShearBendingEffect": "loadCase",
        "loadPatchApplicationLocation": "loadCase", "memberCapacity": "structuralMember",
        "memberCapacityMinimizationConfirmed": "iceLoadPatchDesignCase",
    }

    c["IMO-037"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_PER_LOADING_CONDITION_RESIDUAL_STABILITY_FACTOR",
        "ownerClasses": ["ship", "loadingConditionCase"],
        "operandTerms": ["alternativeInstrumentApplicable", "loadingConditionIdentifier", "residualStabilityFactorSI"],
        "resultTerms": ["alternativeInstrumentResidualStabilityStatus", "residualStabilityFactorSI"],
        "comparisonTerms": ["residualStabilityFactorSI", "alternativeInstrumentResidualStabilityStatus"],
        "relationshipTerms": ["hasLoadingConditionCase", "hasLoadingConditionResultEvidence", "shipCategory"],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasLoadingConditionCase", "toOwner": "loadingConditionCase"},
            {"fromOwner": "loadingConditionCase", "via": "hasLoadingConditionResultEvidence", "toOwner": "evidenceArtifact"},
        ],
        "formulaExpression": "For every loadingConditionCase, residualStabilityFactorSI = 1 unless alternativeInstrumentApplicable is true and alternativeInstrumentResidualStabilityStatus is compliant for that case.",
        "requiredModelFields": ["applicabilityTerms", "operandTerms", "resultTerms", "comparisonTerms", "relationshipTerms", "modelPaths", "formulaExpression"],
    })
    index["termOwners"]["IMO-037"].update({
        "hasLoadingConditionCase": "ship", "loadingConditionIdentifier": "loadingConditionCase",
        "residualStabilityFactorSI": "loadingConditionCase", "alternativeInstrumentApplicable": "loadingConditionCase",
        "alternativeInstrumentResidualStabilityStatus": "loadingConditionCase",
    })

    trf013_bounds = ["maximumIceClassDraughtFore", "maximumIceClassDraughtAft", "minimumIceClassDraughtFore", "minimumIceClassDraughtAft"]
    ensure_terms(index, "TRF-013", trf013_bounds)
    c["TRF-013"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_RETRIEVE_EXISTING_FORE_AFT_DRAUGHT_BOUNDS",
        "applicabilityTerms": ["shipIceStrengthened", "iceClass"],
        "operandTerms": ["operatingForeDraught", "operatingAftDraught"] + trf013_bounds,
        "comparisonTerms": ["operatingForeDraught", "operatingAftDraught"] + trf013_bounds,
        "relationshipTerms": ["hasUpperIceWaterline", "hasLowerIceWaterline", "iceClass"],
        "formulaExpression": "minimumIceClassDraughtFore <= operatingForeDraught <= maximumIceClassDraughtFore and minimumIceClassDraughtAft <= operatingAftDraught <= maximumIceClassDraughtAft.",
        "requiredModelFields": ["applicabilityTerms", "operandTerms", "comparisonTerms", "relationshipTerms", "formulaExpression"],
        "selectorPolicies": [{"selectorTerms": ["shipIceStrengthened"], "requiredValue": True, "missingEvidence": "VIOLATION", "absenceMeansFalse": False}],
    })
    index["termOwners"]["TRF-013"].update({term: "ship" for term in trf013_bounds})

    ensure_terms(index, "TRF-102", ["propellerBladeCount"])
    c["TRF-102"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_RETRIEVE_EXISTING_PROPELLER_BLADE_COUNT_Z",
        "operandTerms": ["bladeExpandedAreaRatio", "propellerBladeCount", "leadingEdgeChordPortionAtZeroPointEightRadius", "trailingEdgeChordPortionAtZeroPointEightRadius", "extremeIceForce"],
        "resultTerms": ["bladeFailureSpindleTorqueFactor", "bladeFailureSpindleTorque", "maximumSpindleTorque"],
        "comparisonTerms": ["bladeFailureSpindleTorqueFactor", "maximumSpindleTorque"],
        "relationshipTerms": ["approvedSpindleTorqueStressAnalysis"],
        "evidenceTerms": ["approvedSpindleTorqueStressAnalysis"],
        "formulaExpression": "bladeFailureSpindleTorqueFactor = max(0.3, 0.7*(1 - ((4*bladeExpandedAreaRatio)/propellerBladeCount)^3)); bladeFailureSpindleTorque = max(leadingEdgeChordPortionAtZeroPointEightRadius, 0.8*trailingEdgeChordPortionAtZeroPointEightRadius)*bladeFailureSpindleTorqueFactor*extremeIceForce, unless approvedSpindleTorqueStressAnalysis directly determines maximumSpindleTorque.",
        "requiredModelFields": ["operandTerms", "resultTerms", "comparisonTerms", "relationshipTerms", "evidenceTerms", "formulaExpression"],
    })
    index["termOwners"]["TRF-102"].update({
        "propellerBladeCount": "ship", "extremeIceForce": "ship", "bladeFailureSpindleTorque": "ship", "maximumSpindleTorque": "ship",
    })

    c["TRF-112"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_SOURCE_DIRECT_NO_YIELD_AND_SAFETY_FACTOR_MODEL",
        "ownerClasses": ["ship", "propellerShaftLineComponent", "loadCase"],
        "applicabilityTerms": ["shaftLineLoadCaseType"],
        "operandTerms": ["bladeFailureUltimateLoad", "combinedAxialBendingTorsionLoad"],
        "resultTerms": ["bendingYieldSafetyFactor", "torsionalYieldSafetyFactor"],
        "comparisonTerms": ["bendingYieldSafetyFactor", "torsionalYieldSafetyFactor"],
        "relationshipTerms": ["hasPropellerShaftLineComponent", "hasPropulsionLoadCase", "shaftLineLoadCaseType"],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasPropellerShaftLineComponent", "toOwner": "propellerShaftLineComponent"},
            {"fromOwner": "ship", "via": "hasPropulsionLoadCase", "toOwner": "loadCase"},
        ],
        "controlledValueTerms": ["bladeFailureLoadCase"],
        "formulaExpression": "",
        "requiredModelFields": ["applicabilityTerms", "resultTerms", "comparisonTerms", "relationshipTerms", "modelPaths", "controlledValueTerms", "comparisonModel"],
    })
    index["termOwners"]["TRF-112"].update({
        "hasPropellerShaftLineComponent": "ship", "hasPropulsionLoadCase": "ship", "shaftLineLoadCaseType": "loadCase",
        "bladeFailureUltimateLoad": "loadCase", "combinedAxialBendingTorsionLoad": "loadCase",
        "bendingYieldSafetyFactor": "propellerShaftLineComponent", "torsionalYieldSafetyFactor": "propellerShaftLineComponent",
    })

    drop_terms(index, "TRF-123", ["hasPropellerShaftLineComponent", "propellerShaftLineComponent"])
    c["TRF-123"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_OCCASIONAL_FORCE_CASE_POPULATION_CORRECTION",
        "ownerClasses": ["ship", "occasionalForceLoadCase", "shipComponent", "materialProperties"],
        "operandTerms": ["occasionalForceComponentStress", "componentMaterialYieldStrength", "componentYieldSafetyFactor"],
        "resultTerms": ["componentYieldSafetyFactor"],
        "comparisonTerms": ["occasionalForceComponentStress", "componentMaterialYieldStrength", "componentYieldSafetyFactor"],
        "relationshipTerms": ["hasOccasionalForceLoadCase", "occasionalForceCaseAssessedComponent", "hasMaterialProperties"],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasOccasionalForceLoadCase", "toOwner": "occasionalForceLoadCase"},
            {"fromOwner": "occasionalForceLoadCase", "via": "occasionalForceCaseAssessedComponent", "toOwner": "shipComponent"},
            {"fromOwner": "shipComponent", "via": "hasMaterialProperties", "toOwner": "materialProperties"},
        ],
        "evidenceTerms": ["propellerBladeExcludedFromOccasionalForceScope"],
        "formulaExpression": "",
        "requiredModelFields": ["operandTerms", "comparisonTerms", "relationshipTerms", "modelPaths", "evidenceTerms", "comparisonModel"],
    })

    c["TRF-127"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_SOURCE_DIRECT_ADDITIONAL_CAPACITY_SUFFICIENCY",
        "applicabilityTerms": ["airReceiverServesAdditionalPurpose"],
        "operandTerms": ["airReceiverCapacity", "additionalPurposeRequiredAirCapacity"],
        "resultTerms": ["additionalPurposeRequiredAirCapacity"],
        "comparisonTerms": ["airReceiverCapacity", "additionalPurposeRequiredAirCapacity"],
        "formulaExpression": "",
        "comparisonModel": "If airReceiverServesAdditionalPurpose is true, the existing airReceiverCapacity shall be sufficient for additionalPurposeRequiredAirCapacity. No starting-air baseline sum is stated or inferred.",
        "selectorPolicies": [{"selectorTerms": ["airReceiverServesAdditionalPurpose"], "requiredValue": True, "missingEvidence": "VIOLATION", "absenceMeansFalse": False}],
        "requiredModelFields": ["applicabilityTerms", "operandTerms", "comparisonTerms", "selectorPolicies", "comparisonModel"],
    })

    ensure_terms(index, "TRF-130", ["hasComponent", "inletChest"])
    c["TRF-130"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_REUSE_INLET_CHEST_COMPONENT_MODEL",
        "ownerClasses": ["ship", "inletChest"],
        "applicabilityTerms": ["coolingWaterChestVolumeAndHeightRequirementsCannotBeMet", "coolingWaterChestAlternativeArrangementUsed"],
        "operandTerms": ["totalRelevantEnginePower", "maximumContinuousRatingPower", "recommendedChestVolume", "seaChestVolume", "strainerOpenArea", "inletPipeArea", "strainerOpenAreaRatio"],
        "resultTerms": ["recommendedChestVolume", "strainerOpenAreaRatio"],
        "comparisonTerms": ["recommendedChestVolume", "totalRelevantEnginePower", "strainerOpenArea", "inletPipeArea", "strainerOpenAreaRatio"],
        "relationshipTerms": ["hasComponent"],
        "modelPaths": [{"fromOwner": "ship", "via": "hasComponent", "toOwner": "shipComponent"}],
        "formulaExpression": "For every inletChest, recommendedChestVolume is approximately totalRelevantEnginePower/750 and strainerOpenArea >= 4*inletPipeArea. At least one hasComponent object typed inletChest is required; if the volume/height selector is true, at least two smaller inletChest components with alternatingCoolingWaterIntakeAndDischarge true are required.",
        "selectorPolicies": [{"selectorTerms": ["coolingWaterChestVolumeAndHeightRequirementsCannotBeMet"], "missingEvidence": "VIOLATION", "absenceMeansFalse": False}],
        "branchEvidencePolicies": [{"selectorTerm": "coolingWaterChestVolumeAndHeightRequirementsCannotBeMet", "selectorValue": True, "evidenceTerms": ["coolingWaterChestAlternativeArrangementUsed", "alternatingCoolingWaterIntakeAndDischarge"]}],
        "requiredModelFields": ["applicabilityTerms", "operandTerms", "resultTerms", "comparisonTerms", "relationshipTerms", "modelPaths", "formulaExpression"],
    })
    index["termOwners"]["TRF-130"] = {
        "hasComponent": "ship", "totalRelevantEnginePower": "ship", "maximumContinuousRatingPower": "ship",
        "coolingWaterChestVolumeAndHeightRequirementsCannotBeMet": "ship", "coolingWaterChestAlternativeArrangementUsed": "ship",
        "seaInletLocation": "inletChest", "nearCentrelineAndWellAftIfPossible": "inletChest",
        "recommendedChestVolume": "inletChest", "seaChestVolume": "inletChest", "iceAccumulationSpaceAboveInlet": "inletChest",
        "fullCapacityDischargePipeConnected": "inletChest", "strainerOpenArea": "inletChest", "inletPipeArea": "inletChest",
        "strainerOpenAreaRatio": "inletChest", "alternatingCoolingWaterIntakeAndDischarge": "inletChest",
    }

    ensure_terms(index, "I2-061", ["calculationCaseAssessedHullStructure", "hullStructure", "plating", "structuralMember"])
    c["I2-061"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_CALCULATION_CASE_PRESCRIBED_SCOPE_PATH",
        "ownerClasses": ["ship", "calculationCase", "hullStructure"],
        "applicabilityTerms": ["calculationMethod"], "operandTerms": ["thickness"],
        "relationshipTerms": ["hasCalculationCase", "calculationMethod", "calculationCaseAssessedHullStructure"],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasCalculationCase", "toOwner": "calculationCase"},
            {"fromOwner": "calculationCase", "via": "calculationCaseAssessedHullStructure", "toOwner": "hullStructure"},
        ],
        "controlledValueTerms": ["directCalculationMethodValue", "prescribedAnalyticalProcedure"],
        "comparisonModel": "For shell-plating or local-frame hullStructure nodes governed by I2.4, I2.6 or I2.7, directCalculationMethodValue shall not replace prescribedAnalyticalProcedure.",
        "requiredModelFields": ["applicabilityTerms", "relationshipTerms", "modelPaths", "controlledValueTerms", "comparisonModel"],
    })
    index["termOwners"]["I2-061"].update({
        "hasCalculationCase": "ship", "calculationMethod": "calculationCase",
        "calculationCaseAssessedHullStructure": "calculationCase", "thickness": "hullStructure",
    })

    ensure_terms(index, "I2-064", ["linearCalculationMethodValue", "calculationMethodValue"])
    c["I2-064"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_LINEAR_METHOD_CONTROLLED_SELECTOR",
        "applicabilityTerms": ["calculationMethod", "linearCalculationMethodValue"],
        "relationshipTerms": ["hasCalculationCase", "calculationMethod", "hasStructuralMember", "hasStructuralMemberFlange", "hasStructuralMemberWeb"],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasCalculationCase", "toOwner": "calculationCase"},
            {"fromOwner": "ship", "via": "hasStructuralMember", "toOwner": "structuralMember"},
            {"fromOwner": "structuralMember", "via": "hasStructuralMemberFlange", "toOwner": "structuralMemberFlange"},
            {"fromOwner": "structuralMember", "via": "hasStructuralMemberWeb", "toOwner": "structuralMemberWeb"},
        ],
        "controlledValueTerms": ["linearCalculationMethodValue"],
        "requiredModelFields": ["applicabilityTerms", "operandTerms", "resultTerms", "relationshipTerms", "modelPaths", "controlledValueTerms", "comparisonModel"],
        "selectorPolicies": [{"selectorTerms": ["calculationMethod"], "requiredValue": "linearCalculationMethodValue", "missingEvidence": "VIOLATION", "absenceMeansFalse": False}],
    })

    ensure_terms(index, "I2-066", ["weld", "hasWeld", "withinIceStrengthenedArea", "weldTypeValue", "doubleContinuousWeld"])
    c["I2-066"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_MINIMUM_WELD_NODE_AND_SCOPE_MODEL",
        "ownerClasses": ["ship", "weld"],
        "applicabilityTerms": ["withinIceStrengthenedArea"],
        "relationshipTerms": ["hasWeld", "weldType"],
        "modelPaths": [{"fromOwner": "ship", "via": "hasWeld", "toOwner": "weld"}],
        "controlledValueTerms": ["doubleContinuousWeld"],
        "comparisonModel": "Every weld with withinIceStrengthenedArea true shall have weldType doubleContinuousWeld.",
        "selectorPolicies": [{"selectorTerms": ["withinIceStrengthenedArea"], "requiredValue": True, "missingEvidence": "VIOLATION", "absenceMeansFalse": False}],
        "requiredModelFields": ["applicabilityTerms", "relationshipTerms", "modelPaths", "controlledValueTerms", "comparisonModel"],
    })
    index["termOwners"]["I2-066"] = {"hasWeld": "ship", "withinIceStrengthenedArea": "weld", "weldType": "weld"}

    ensure_terms(index, "IMO-001", ["iceConditionValue", "mediumFirstYearIceWithPossibleOldIceInclusions", "polarShipCategoryA"])
    c["IMO-001"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_CONTROLLED_DESIGN_ICE_CONDITION_CATEGORY_A",
        "applicabilityTerms": ["designIceCondition"],
        "relationshipTerms": ["designIceCondition", "shipCategory"],
        "controlledValueTerms": ["mediumFirstYearIceWithPossibleOldIceInclusions", "polarShipCategoryA"],
        "comparisonModel": "If designIceCondition is mediumFirstYearIceWithPossibleOldIceInclusions, shipCategory shall be polarShipCategoryA.",
        "requiredModelFields": ["applicabilityTerms", "relationshipTerms", "controlledValueTerms", "comparisonModel"],
        "selectorPolicies": [{"selectorTerms": ["designIceCondition"], "requiredValue": "mediumFirstYearIceWithPossibleOldIceInclusions", "missingEvidence": "VIOLATION", "absenceMeansFalse": False}],
    })
    index["termOwners"]["IMO-001"] = {"designIceCondition": "ship", "shipCategory": "ship"}

    ensure_terms(index, "IMO-003", ["iceConditionValue", "openWaterIceCondition", "iceConditionLessSevereThanCategoryAAndB", "polarShipCategoryC"])
    c["IMO-003"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_CONTROLLED_DESIGN_ICE_CONDITION_CATEGORY_C",
        "applicabilityTerms": ["designIceCondition"],
        "relationshipTerms": ["designIceCondition", "shipCategory"],
        "controlledValueTerms": ["openWaterIceCondition", "iceConditionLessSevereThanCategoryAAndB", "polarShipCategoryC"],
        "comparisonModel": "If designIceCondition is openWaterIceCondition or iceConditionLessSevereThanCategoryAAndB, shipCategory shall be polarShipCategoryC.",
        "requiredModelFields": ["applicabilityTerms", "relationshipTerms", "controlledValueTerms", "comparisonModel"],
        "selectorPolicies": [{"selectorTerms": ["designIceCondition"], "allowedValues": ["openWaterIceCondition", "iceConditionLessSevereThanCategoryAAndB"], "missingEvidence": "VIOLATION", "absenceMeansFalse": False}],
    })
    index["termOwners"]["IMO-003"] = {"designIceCondition": "ship", "shipCategory": "ship"}

    ensure_terms(index, "TRF-006", ["ownerRequested2008EngineOutputRequirements"])
    c["TRF-006"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_OWNER_REQUEST_ENGINE_OUTPUT_EDITION_SELECTOR",
        "applicabilityTerms": ["constructionStageDate", "ownerRequested2008EngineOutputRequirements"],
        "relationshipTerms": ["applicableIceClassRegulationEdition", "engineOutputRegulationEdition", "iceClass"],
        "controlledValueTerms": ["iceClassRuleEdition1985", "iceClassRegulationEdition2008"],
        "comparisonModel": "For the stated 1986-11-01 to 2003-09-01 construction-stage cohort, applicableIceClassRegulationEdition remains iceClassRuleEdition1985; engineOutputRegulationEdition may be iceClassRegulationEdition2008 only when ownerRequested2008EngineOutputRequirements is true.",
        "selectorPolicies": [{"selectorTerms": ["ownerRequested2008EngineOutputRequirements"], "missingEvidence": "VIOLATION", "absenceMeansFalse": False}],
        "requiredModelFields": ["applicabilityTerms", "relationshipTerms", "controlledValueTerms", "selectorPolicies", "comparisonModel"],
    })
    index["termOwners"]["TRF-006"].update({"ownerRequested2008EngineOutputRequirements": "ship"})

    c["TRF-014"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_CLASS_CERTIFICATE_DRAUGHT_VALUE_OWNERS",
        "ownerClasses": ["ship", "classCertificate"],
        "operandTerms": [
            "maximumIceClassDraughtFore", "maximumIceClassDraughtAmidships", "maximumIceClassDraughtAft",
            "minimumIceClassDraughtFore", "minimumIceClassDraughtAmidships", "minimumIceClassDraughtAft",
        ],
        "relationshipTerms": ["hasClassCertificate", "hasIceDraughtRestrictionDocument", "iceClass"],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasClassCertificate", "toOwner": "classCertificate"},
            {"fromOwner": "ship", "via": "hasIceDraughtRestrictionDocument", "toOwner": "iceDraughtRestrictionDocument"},
        ],
        "evidenceTerms": ["hasClassCertificate", "hasIceDraughtRestrictionDocument", "retainedOnBoard", "readilyAvailableToMaster"],
        "requiredModelFields": ["operandTerms", "relationshipTerms", "modelPaths", "evidenceTerms", "comparisonModel"],
    })
    for term in (
        "maximumIceClassDraughtFore", "maximumIceClassDraughtAmidships", "maximumIceClassDraughtAft",
        "minimumIceClassDraughtFore", "minimumIceClassDraughtAmidships", "minimumIceClassDraughtAft",
    ):
        index["termOwners"]["TRF-014"][term] = "classCertificate"
    index["termOwners"]["TRF-014"]["hasClassCertificate"] = "ship"

    ensure_terms(index, "TRF-050", ["frame", "frameAttachmentRecord", "frameAttachment", "weldTypeValue"])
    drop_terms(index, "TRF-050", ["frameShellAttachment"])
    index["requirementTargetOwner"]["TRF-050"] = "frameAttachmentRecord"
    c["TRF-050"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_FRAME_ATTACHMENT_RECORD_MODEL",
        "ownerClasses": ["frame", "frameAttachmentRecord"],
        "applicabilityTerms": ["shellPlateButtCrossing"],
        "relationshipTerms": ["frameAttachment", "frameShellWeldType"],
        "modelPaths": [{"fromOwner": "frame", "via": "frameAttachment", "toOwner": "frameAttachmentRecord"}],
        "controlledValueTerms": ["doubleContinuousWeld"],
        "comparisonModel": "Every frameAttachmentRecord shall have frameShellWeldType doubleContinuousWeld and scallopingPresent false, except that the scalloping prohibition does not apply when shellPlateButtCrossing is true.",
        "requiredModelFields": ["applicabilityTerms", "relationshipTerms", "modelPaths", "controlledValueTerms", "comparisonModel"],
        "selectorPolicies": [{"selectorTerms": ["shellPlateButtCrossing"], "missingEvidence": "VIOLATION", "absenceMeansFalse": False}],
    })
    index["termOwners"]["TRF-050"] = {
        "frameAttachment": "frame", "frameShellWeldType": "frameAttachmentRecord",
        "scallopingPresent": "frameAttachmentRecord", "shellPlateButtCrossing": "frameAttachmentRecord",
    }

    ensure_terms(index, "TRF-133", ["warningTriangleUpperEdgeVerticallyAboveIceMark", "timberLoadLineMarkApplicable"])
    c["TRF-133"].update({
        "schemaVersion": 7, "engineeringDecision": "R7_WARNING_TRIANGLE_VERTICAL_RELATION_AND_TIMBER_SELECTOR",
        "ownerClasses": ["ship", "warningTriangleMarking", "iceClassDraughtMarking"],
        "applicabilityTerms": ["hasIceClassDraughtMarking", "iceClass", "timberLoadLineMarkApplicable"],
        "operandTerms": ["draughtMarkAftOffset", "markingPlateThickness", "verticalOffsetAboveSummerFreshWaterLoadLine", "warningTriangleSideLength"],
        "relationshipTerms": ["hasIceClassDraughtMarking", "hasWarningTriangleMarking", "draughtMarkAftReferencePoint", "reflectingMarkingColour"],
        "modelPaths": [
            {"fromOwner": "ship", "via": "hasIceClassDraughtMarking", "toOwner": "iceClassDraughtMarking"},
            {"fromOwner": "ship", "via": "hasWarningTriangleMarking", "toOwner": "warningTriangleMarking"},
            {"fromOwner": "iceClassDraughtMarking", "via": "draughtMarkAftReferencePoint", "toOwner": "markingReferencePointValue"},
        ],
        "controlledValueTerms": ["loadLineRingCentreReference", "timberLoadLineVerticalReference", "redReflectingMarkingColour", "yellowReflectingMarkingColour"],
        "evidenceTerms": ["warningTriangleUpperEdgeVerticallyAboveIceMark"],
        "selectorPolicies": [{"selectorTerms": ["timberLoadLineMarkApplicable"], "missingEvidence": "VIOLATION", "absenceMeansFalse": False}],
        "branchEvidencePolicies": [{"selectorTerm": "timberLoadLineMarkApplicable", "selectorValue": True, "evidenceTerms": ["draughtMarkAftReferencePoint", "timberLoadLineVerticalReference"]}],
        "comparisonModel": "warningTriangleUpperEdgeVerticallyAboveIceMark shall be true. If timberLoadLineMarkApplicable is true, draughtMarkAftReferencePoint shall be timberLoadLineVerticalReference; otherwise it shall be loadLineRingCentreReference. All existing Annex III dimensions and marking constraints remain unchanged.",
        "requiredModelFields": ["applicabilityTerms", "operandTerms", "relationshipTerms", "modelPaths", "controlledValueTerms", "evidenceTerms", "selectorPolicies", "comparisonModel"],
    })
    index["termOwners"]["TRF-133"].update({
        "timberLoadLineMarkApplicable": "ship",
        "warningTriangleUpperEdgeVerticallyAboveIceMark": "warningTriangleMarking",
        "hasWarningTriangleMarking": "ship",
    })

    if json_hash(c["I2-009"]) != original_i2009:
        raise RuntimeError("I2-009 contract changed despite explicit R7 prohibition")
    index["sourceLockId"] = LOCK_ID
    index["version"] = "7.0"
    index["termCount"] = len(read_json(TARGET / "registry/term_registry.json"))
    write_json(path, index)


def write_provenance(r6_manifest: dict) -> None:
    evidence = read_json(TARGET / "evidence/stage1_approved.json")
    reqs = {row["id"]: row for row in evidence["requirements"]}
    records = []
    for rid, (classification, action) in CORRECTIONS.items():
        req = reqs[rid]
        records.append({
            "requirementId": rid, "implemented": rid in IMPLEMENTED,
            "classification": classification, "action": action,
            "source": req["source"], "page": req["page"], "clause": req["clause"],
            "sourceText": req["sourceText"], "normalizedRequirement": req["normalizedRequirement"],
        })
    write_json(TARGET / "registry/r7_change_decisions.json", records)
    write_json(TARGET / "evidence/r7_source_grounded_corrections.json", {
        "lockId": LOCK_ID, "sourceLockId": "VOCAB-LOCK-2026-08-19-R6",
        "status": "IMPLEMENTED_SOURCE_GROUNDED_ONLY", "apiCalls": 0,
        "implementedRequirementIds": IMPLEMENTED,
        "intentionallyUnchangedHumanReview": ["I2-009"],
        "newCanonicalTerms": sorted(NEW_TERMS), "records": records,
    })
    write_json(TARGET / "provenance/r6_immutable_source_hashes.json", r6_manifest)


def prepare() -> None:
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite existing R7 directory: {TARGET}")
    r6_manifest = r6_hash_manifest()
    shutil.copytree(
        SOURCE, TARGET,
        ignore=shutil.ignore_patterns("*.xlsx", "*.sha256", "*.lock.json", "*.inspect.ndjson", "final_lock_workbook_previews"),
    )
    for stale in (
        TARGET / "validation/r6_offline_validation.json",
        TARGET / "validation/r6_namespace_and_integrity_report.json",
        TARGET / "r6_prelock_binding.json",
    ):
        if stale.exists():
            stale.unlink()
    patch_ontology_registry_context()
    patch_contracts()
    write_provenance(r6_manifest)

    bound_paths = [
        "registry/term_registry.json", "registry/term_registry.csv", "registry/r7_change_decisions.json",
        "ontology/nltl_benchmark_vocabulary.ttl", "ontology/nltl_benchmark_vocabulary.rdf",
        "context/nltl_benchmark_context.jsonld", "evidence/stage1_approved.json",
        "evidence/r7_source_grounded_corrections.json", "requirement_term_index.json",
        "provenance/r6_immutable_source_hashes.json",
    ]
    registry = read_json(TARGET / "registry/term_registry.json")
    index = read_json(TARGET / "requirement_term_index.json")
    prelock = {
        "lockId": LOCK_ID,
        "status": "PREPARED_PENDING_OFFLINE_VALIDATION_AND_WORKBOOK",
        "sourceLockId": "VOCAB-LOCK-2026-08-19-R6", "supersedes": "VOCAB-LOCK-2026-08-19-R6",
        "scope": "Approved source-grounded R7 corrections for 19 requirements; I2-009 preserved unresolved; no pipeline or prompt changes.",
        "counts": {
            "requirements": 313, "generationEligibleRequirements": 238,
            "registryTerms": len(registry), "newVocabularyTerms": len(NEW_TERMS),
            "implementedRequirementCorrections": len(IMPLEMENTED), "humanReviewUnchanged": 1,
        },
        "newCanonicalTerms": sorted(NEW_TERMS),
        "boundArtifacts": {relative: sha256(TARGET / relative) for relative in bound_paths},
        "r6ImmutableAggregateSha256": r6_manifest["aggregateSha256"],
        "apiCalls": 0,
    }
    write_json(TARGET / "prelock_manifest.json", prelock)
    write_json(TARGET / "r7_prelock_binding.json", {
        "lockId": LOCK_ID, "status": "PRELOCK_OFFLINE_VALIDATION_ONLY",
        "workbook": "Pending R7 workbook", "workbookSha256": "",
        "boundMachineReadableArtifacts": prelock["boundArtifacts"],
        "boundRequirementIndex": {"requirement_term_index.json": prelock["boundArtifacts"]["requirement_term_index.json"]},
    })
    print(json.dumps({
        "status": "PREPARED", "target": str(TARGET), "sourceLock": "VOCAB-LOCK-2026-08-19-R6",
        "registryTerms": len(registry), "newTerms": sorted(NEW_TERMS),
        "completeContracts": sum(c.get("status") == "COMPLETE" for c in index["dependencyContracts"].values()),
        "apiCalls": 0,
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare"])
    args = parser.parse_args()
    prepare()
