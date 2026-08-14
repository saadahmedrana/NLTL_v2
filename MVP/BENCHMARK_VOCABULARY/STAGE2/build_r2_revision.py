from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import DCTERMS, OWL, SH, SKOS


MVP = Path(__file__).resolve().parents[2]
R1 = Path(__file__).resolve().parent
R2 = MVP / "BENCHMARK_VOCABULARY" / "STAGE2_R2"
PIPELINE_INDEX_R1 = MVP / "BENCHMARK_VOCABULARY" / "PIPELINE_CONTEXT" / "master" / "requirement_term_index.json"
PIPELINE_INDEX_R2 = MVP / "BENCHMARK_VOCABULARY" / "PIPELINE_CONTEXT" / "R2" / "requirement_term_index.json"
VOCAB_BASE = "https://w3id.org/nltl/vocab#"
SHAPES_BASE = "https://w3id.org/nltl/shapes#"
VERSION = "2.2.0-stage2-r2"
LOCK_ID = "VOCAB-LOCK-2026-08-12-R2"
SOURCE_REF = "IMO-057 | IMO_POLAR_CODE p.22 | 7.3.2.1"
EVIDENCE = (
    "Fire pumps, including emergency fire pumps, water mist and water spray pumps, "
    "shall be located in compartments maintained above freezing."
)

NLTL = Namespace(VOCAB_BASE)
NSH = Namespace(SHAPES_BASE)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def term(
    concept_id: str,
    local_name: str,
    label: str,
    kind: str,
    parent_or_range: str,
    alias: str,
    definition: str,
    *,
    stage1_name: str | None = None,
) -> dict:
    is_class = kind == "Class"
    return {
        "aliases": [alias],
        "conceptId": concept_id,
        "confidence": "High",
        "datatype": "",
        "evidenceExcerpt": EVIDENCE,
        "haithamUri": "",
        "iri": VOCAB_BASE + local_name,
        "kind": kind,
        "label": label,
        "localName": local_name,
        "mappingStatus": "No verified external or Haitham exact URI; benchmark term grounded in IMO-057",
        "module": "machinery",
        "nameQaStatus": "Passed - explicit clause wording and ASCII lowerCamelCase",
        "namingBasis": "Applicable regulation explicit wording; R2 benchmark gap repair",
        "namingRule": (
            "N4 - preserve explicit regulatory entity as ASCII lowerCamelCase"
            if is_class
            else "N5 - subject-to-object relationship named has + object role in ASCII lowerCamelCase"
        ),
        "normalizedDefinition": f"NORMALIZED (R2 gap repair): {definition}",
        "parentOrRange": parent_or_range,
        "quantityKindLabel": "",
        "requirements": ["IMO-057"],
        "roleDecision": (
            "Explicit engineering entity class required for SHACL target selection"
            if is_class
            else "Object relationship required to traverse from a pump to the compartment whose temperature is constrained"
        ),
        "sourceConceptIds": [concept_id],
        "sourceRefs": SOURCE_REF,
        "stage1LocalNames": [stage1_name or local_name],
        "stage2UnitEvidence": "",
        "unitDecisionStatus": "Not a quantity property",
        "unitIri": "",
        "unitSymbol": "",
    }


R2_TERMS = [
    term(
        "VOC-R2-001",
        "compartment",
        "Compartment",
        "Class",
        VOCAB_BASE + "shipComponent",
        "compartment",
        "A ship compartment that can contain machinery equipment and carry environmental properties.",
    ),
    term(
        "VOC-0165",
        "hasContainingCompartment",
        "Has containing compartment",
        "ObjectProperty",
        VOCAB_BASE + "compartment",
        "containing_compartment; containingCompartment",
        "Links a machinery component or pump to the compartment in which it is located.",
        stage1_name="containingCompartment",
    ),
    term(
        "VOC-R2-002",
        "emergencyFirePump",
        "Emergency fire pump",
        "Class",
        VOCAB_BASE + "firePump",
        "emergency_fire_pump",
        "A fire pump explicitly identified by the regulation as an emergency fire pump.",
    ),
    term(
        "VOC-R2-003",
        "waterMistPump",
        "Water-mist pump",
        "Class",
        VOCAB_BASE + "firePump",
        "water_mist_pump",
        "A fire-protection pump explicitly identified by the regulation as a water-mist pump.",
    ),
    term(
        "VOC-R2-004",
        "waterSprayPump",
        "Water-spray pump",
        "Class",
        VOCAB_BASE + "firePump",
        "water_spray_pump",
        "A fire-protection pump explicitly identified by the regulation as a water-spray pump.",
    ),
]


def prepare_directories() -> None:
    for name in (
        "context", "evidence", "examples", "mappings", "ontology", "profiles",
        "qa_workbook", "registry", "shacl", "validation",
    ):
        (R2 / name).mkdir(parents=True, exist_ok=True)


def build_evidence() -> dict:
    evidence = read_json(R1 / "evidence" / "stage1_approved.json")
    for requirement in evidence["requirements"]:
        if requirement["id"] == "IMO-057":
            ids = [item.strip() for item in str(requirement.get("conceptIds", "")).split(";") if item.strip()]
            ids.extend(item for item in ("VOC-R2-001", "VOC-R2-002", "VOC-R2-003", "VOC-R2-004") if item not in ids)
            requirement["conceptIds"] = "; ".join(ids)
            requirement["r2VocabularyRepair"] = {
                "lockId": LOCK_ID,
                "reason": "Pilot generation proved that a string-valued compartment name cannot express the required pump-to-compartment temperature path.",
                "addedConceptIds": ["VOC-R2-001", "VOC-R2-002", "VOC-R2-003", "VOC-R2-004"],
                "remodelledConceptId": "VOC-0165",
            }
            break
    evidence["r2Revision"] = {
        "lockId": LOCK_ID,
        "scope": "IMO-057 vocabulary/model repair only",
        "sourceEvidence": SOURCE_REF,
        "regulatoryWordingChanged": False,
    }
    write_json(R2 / "evidence" / "stage1_approved.json", evidence)
    shutil.copy2(R1 / "evidence" / "external_uri_verification.json", R2 / "evidence" / "external_uri_verification.json")
    return evidence


def build_registry() -> list[dict]:
    registry = [item for item in read_json(R1 / "registry" / "term_registry.json") if item["localName"] != "containingCompartment"]
    registry.extend(R2_TERMS)
    registry.sort(key=lambda item: item["localName"])
    write_json(R2 / "registry" / "term_registry.json", registry)
    fields = [
        "conceptId", "sourceConceptIds", "stage1LocalNames", "localName", "iri", "label", "kind", "parentOrRange", "datatype", "module",
        "roleDecision", "unitSymbol", "unitIri", "quantityKindLabel", "unitDecisionStatus", "stage2UnitEvidence", "aliases", "requirements",
        "sourceRefs", "namingBasis", "namingRule", "nameQaStatus", "confidence", "haithamUri",
    ]
    with (R2 / "registry" / "term_registry.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in registry:
            row = {key: item.get(key, "") for key in fields}
            for key in ("sourceConceptIds", "stage1LocalNames", "aliases", "requirements"):
                row[key] = "; ".join(item[key])
            writer.writerow(row)

    refinements = read_json(R1 / "registry" / "naming_refinements.json")
    refinements.append({
        "stage1LocalName": "containingCompartment",
        "stage2LocalName": "hasContainingCompartment",
        "action": "R2 role-and-name remodel",
        "reason": "The clause requires an object path to a compartment node; retain the old source label as an alias and do not change the old URI's datatype meaning silently.",
    })
    write_json(R2 / "registry" / "naming_refinements.json", refinements)
    retired = read_json(R1 / "registry" / "retired_stage1_candidates.json")
    retired["VOC-0165"] = {
        "stage1LocalName": "containingCompartment",
        "reason": "The R1 DatatypeProperty could only store a compartment label string and could not support the IMO-057 pump-to-compartment-to-temperature path.",
        "requirementRedirects": {"IMO-057": "hasContainingCompartment"},
    }
    write_json(R2 / "registry" / "retired_stage1_candidates.json", retired)
    return registry


def add_term_to_ontology(graph: Graph, item: dict) -> None:
    iri = URIRef(item["iri"])
    if item["kind"] == "Class":
        graph.add((iri, RDF.type, OWL.Class))
        graph.add((iri, RDFS.subClassOf, URIRef(item["parentOrRange"])))
    else:
        graph.add((iri, RDF.type, OWL.ObjectProperty))
        graph.add((iri, RDFS.domain, NLTL.machineryComponent))
        graph.add((iri, RDFS.range, URIRef(item["parentOrRange"])))
    graph.add((iri, RDFS.label, Literal(item["label"], lang="en")))
    graph.add((iri, SKOS.prefLabel, Literal(item["label"], lang="en")))
    graph.add((iri, NLTL.draftConceptId, Literal(item["conceptId"])))
    graph.add((iri, NLTL.stage1LocalName, Literal(item["stage1LocalNames"][0])))
    graph.add((iri, NLTL.module, NLTL.moduleMachinery))
    graph.add((iri, NLTL.roleDecisionBasis, Literal(item["roleDecision"])))
    graph.add((iri, NLTL.namingBasis, Literal(item["namingBasis"])))
    graph.add((iri, NLTL.namingRule, Literal(item["namingRule"])))
    graph.add((iri, NLTL.unitDecisionStatus, Literal(item["unitDecisionStatus"])))
    graph.add((iri, SKOS.definition, Literal(item["normalizedDefinition"], lang="en")))
    graph.add((iri, NLTL.sourceReference, Literal(item["sourceRefs"])))
    graph.add((iri, NLTL.evidenceExcerpt, Literal(item["evidenceExcerpt"])))
    graph.add((iri, NLTL.sourceRequirementId, Literal("IMO-057")))
    for alias in item["aliases"]:
        graph.add((iri, SKOS.altLabel, Literal(alias)))
        graph.add((iri, NLTL.sourceAlias, Literal(alias)))


def build_ontology() -> None:
    graph = Graph().parse(R1 / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
    old = NLTL.containingCompartment
    graph.remove((old, None, None))
    graph.add((old, OWL.deprecated, Literal(True)))
    graph.add((old, DCTERMS.isReplacedBy, NLTL.hasContainingCompartment))
    graph.add((old, SKOS.changeNote, Literal("Retired in R2: the R1 string-valued term could not express the IMO-057 object path.")))
    for item in R2_TERMS:
        add_term_to_ontology(graph, item)
    for ontology in graph.subjects(RDF.type, OWL.Ontology):
        graph.remove((ontology, OWL.versionInfo, None))
        graph.remove((ontology, OWL.versionIRI, None))
        graph.add((ontology, OWL.versionInfo, Literal(VERSION)))
        graph.add((ontology, OWL.versionIRI, URIRef(f"https://w3id.org/nltl/vocab/{VERSION}")))
    graph.serialize(R2 / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
    graph.serialize(R2 / "ontology" / "nltl_benchmark_vocabulary.rdf", format="xml")


def build_context() -> None:
    payload = read_json(R1 / "context" / "nltl_benchmark_context.jsonld")
    context = payload["@context"]
    context.pop("containingCompartment", None)
    context.update({
        "compartment": "nltl:compartment",
        "hasContainingCompartment": {"@id": "nltl:hasContainingCompartment", "@type": "@id"},
        "emergencyFirePump": "nltl:emergencyFirePump",
        "waterMistPump": "nltl:waterMistPump",
        "waterSprayPump": "nltl:waterSprayPump",
    })
    write_json(R2 / "context" / "nltl_benchmark_context.jsonld", payload)


def build_shapes() -> None:
    graph = Graph().parse(R1 / "shacl" / "schema_only_shapes.ttl", format="turtle")
    old_shape = NSH.containingCompartmentPropertyShape
    graph.remove((None, None, old_shape))
    graph.remove((old_shape, None, None))
    shape = NSH.hasContainingCompartmentPropertyShape
    graph.add((shape, RDF.type, SH.PropertyShape))
    graph.add((shape, SH.path, NLTL.hasContainingCompartment))
    graph.add((shape, SH.name, Literal("Has containing compartment", lang="en")))
    graph.add((shape, SH.description, Literal("Schema-only object-path constraint; requirement-specific cardinality and temperature logic are intentionally excluded.")))
    graph.add((shape, SH["class"], NLTL.compartment))
    graph.add((shape, SH.nodeKind, SH.IRI))
    graph.add((NSH.benchmarkEntityShape, SH.property, shape))
    graph.serialize(R2 / "shacl" / "schema_only_shapes.ttl", format="turtle")


def build_profiles(registry: list[dict]) -> dict[str, dict]:
    old = VOCAB_BASE + "containingCompartment"
    additions_class = {item["iri"] for item in R2_TERMS if item["kind"] == "Class"}
    additions_property = {item["iri"] for item in R2_TERMS if item["kind"] != "Class"}
    profiles = {}
    for path in sorted((R1 / "profiles").glob("*.json")):
        payload = read_json(path)
        had_old = old in payload["allowedProperties"]
        payload["allowedProperties"] = sorted(set(payload["allowedProperties"]) - {old})
        if had_old or path.stem == "master":
            payload["allowedClasses"] = sorted(set(payload["allowedClasses"]) | additions_class)
            payload["allowedProperties"] = sorted(set(payload["allowedProperties"]) | additions_property)
        payload["vocabularyVersion"] = VERSION
        payload["termCount"] = len(payload["allowedClasses"]) + len(payload["allowedProperties"])
        if path.stem == "master":
            payload["activationBoundary"] = f"All {len(registry)} canonical R2 terms; R2 repairs the IMO-057 node model without adding requirement answer logic"
        write_json(R2 / "profiles" / path.name, payload)
        profiles[path.stem] = payload
    return profiles


def build_requirement_index(registry: list[dict]) -> None:
    payload = read_json(PIPELINE_INDEX_R1)
    payload["version"] = "1.1.0"
    payload["sourceLockId"] = LOCK_ID
    payload["termCount"] = len(registry)
    payload["requirements"]["IMO-057"] = sorted({
        "firePump", "emergencyFirePump", "waterMistPump", "waterSprayPump",
        "compartment", "hasContainingCompartment", "maintainedTemperature",
    })
    write_json(PIPELINE_INDEX_R2, payload)


def build_manifest(evidence: dict, registry: list[dict], profiles: dict[str, dict]) -> None:
    r1_manifest = read_json(R1 / "stage2_manifest.json")
    counts = Counter(item["kind"] for item in registry)
    modules = Counter(item["module"] for item in registry)
    datatypes = Counter(item["parentOrRange"] for item in registry if item["kind"] == "DatatypeProperty")
    manifest = dict(r1_manifest)
    manifest.update({
        "revision": "R2",
        "version": VERSION,
        "terms": len(registry),
        "stage2NamingRefinementRows": 13,
        "retiredStage1Candidates": 2,
        "r2AddedConcepts": 4,
        "r2RepairRequirement": "IMO-057",
        "r2RepairDecision": "Replace the retired string-valued containingCompartment representation with an object path and explicit pump/compartment classes.",
        "stage1ApprovedSnapshotSha256": sha256(R2 / "evidence" / "stage1_approved.json"),
        "termKinds": dict(counts),
        "modules": dict(modules),
        "datatypes": dict(datatypes),
        "profiles": {name: {"termCount": item["termCount"], "requirementCount": len(item["requirementIds"])} for name, item in profiles.items()},
    })
    write_json(R2 / "stage2_manifest.json", manifest)


def write_docs(registry: list[dict]) -> None:
    (R2 / "README.md").write_text(
        "# NLTL benchmark vocabulary - Stage 2 R2\n\n"
        "R2 is a non-overwriting revision of R1 for the IMO-057 pilot-discovered node-model gap. "
        "It retires the active string-valued `containingCompartment` term, introduces "
        "`hasContainingCompartment`, `compartment`, `emergencyFirePump`, `waterMistPump`, and "
        "`waterSprayPump`, and preserves the verified regulatory wording and all R1 artifacts.\n",
        encoding="utf-8",
    )
    (R2 / "STAGE2_REPORT.md").write_text(
        "# Stage 2 R2 controlled vocabulary report\n\n"
        f"Canonical active terms: **{len(registry)}**.\n\n"
        "The repair is structural vocabulary only. It contains no temperature threshold, cardinality, "
        "applicability outcome, SHACL answer logic, or expected RDF result. The exact IMO-057 wording "
        f"is retained from `{SOURCE_REF}`. R1 remains unchanged and independently reproducible.\n",
        encoding="utf-8",
    )


def main() -> None:
    prepare_directories()
    evidence = build_evidence()
    registry = build_registry()
    build_ontology()
    build_context()
    build_shapes()
    shutil.copy2(R1 / "mappings" / "haitham_exact_mappings.ttl", R2 / "mappings" / "haitham_exact_mappings.ttl")
    shutil.copy2(R1 / "examples" / "illustrative_ship.ttl", R2 / "examples" / "illustrative_ship.ttl")
    shutil.copy2(R1 / "examples" / "illustrative_ship.jsonld", R2 / "examples" / "illustrative_ship.jsonld")
    profiles = build_profiles(registry)
    build_requirement_index(registry)
    build_manifest(evidence, registry, profiles)
    write_docs(registry)
    print(json.dumps({
        "status": "BUILT",
        "revision": "R2",
        "terms": len(registry),
        "r2_directory": str(R2),
        "requirement_index": str(PIPELINE_INDEX_R2),
    }, indent=2))


if __name__ == "__main__":
    main()
