from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, OWL, SH, SKOS, XSD

try:
    from pyshacl import validate as pyshacl_validate
except ModuleNotFoundError:  # deterministic local fallback used in this workspace
    pyshacl_validate = None


STAGE2 = Path(os.environ.get("NLTL_STAGE2_DIR", Path(__file__).resolve().parent)).resolve()
VOCAB_BASE = "https://w3id.org/nltl-benchmark/vocab#"
NLTL = Namespace(VOCAB_BASE)
NSH = Namespace("https://w3id.org/nltl-benchmark/shapes#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")


def fail(message: str) -> None:
    raise AssertionError(message)


def name_tokens(local: str) -> set[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", local)
    spaced = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", spaced)
    spaced = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", spaced)
    return {x.lower() for x in re.split(r"[^A-Za-z0-9]+", spaced) if x}


def structural_conforms(data: Graph) -> tuple[bool, str]:
    """Evaluate the generated schema-only value patterns without rule logic.

    This local fallback covers exactly the structural patterns emitted by
    ``build_stage2.py`` and is used only when pySHACL is unavailable.
    """
    violations: list[str] = []
    for node in data.subjects(RDF.type, QUDT.QuantityValue):
        numeric = list(data.objects(node, QUDT.numericValue))
        units = list(data.objects(node, QUDT.unit))
        if len(numeric) != 1 or numeric[0].datatype != XSD.decimal:
            violations.append(f"{node}: expected exactly one xsd:decimal qudt:numericValue")
        if len(units) != 1 or not isinstance(units[0], URIRef):
            violations.append(f"{node}: expected exactly one IRI-valued qudt:unit")
    for node in data.subjects(RDF.type, SOSA.Observation):
        if len(list(data.objects(node, SOSA.hasFeatureOfInterest))) != 1:
            violations.append(f"{node}: expected one sosa:hasFeatureOfInterest")
        if len(list(data.objects(node, SOSA.observedProperty))) != 1:
            violations.append(f"{node}: expected one sosa:observedProperty")
        times = list(data.objects(node, SOSA.resultTime))
        if len(times) != 1 or times[0].datatype != XSD.dateTime:
            violations.append(f"{node}: expected one xsd:dateTime sosa:resultTime")
        result_count = len(list(data.objects(node, SOSA.hasSimpleResult))) + len(list(data.objects(node, SOSA.hasResult)))
        if result_count != 1:
            violations.append(f"{node}: expected exactly one simple or node result")
    for node in data.subjects(RDF.type, NLTL.evidenceArtifact):
        if not list(data.objects(node, DCTERMS.source)):
            violations.append(f"{node}: evidence artifact has no dcterms:source")
    return not violations, "; ".join(violations) if violations else "conforms"


def main() -> None:
    registry = json.loads((STAGE2 / "registry" / "term_registry.json").read_text())
    manifest = json.loads((STAGE2 / "stage2_manifest.json").read_text())
    context = json.loads((STAGE2 / "context" / "nltl_benchmark_context.jsonld").read_text())
    jsonld_example = json.loads((STAGE2 / "examples" / "illustrative_ship.jsonld").read_text())
    profiles = {p.stem: json.loads(p.read_text()) for p in (STAGE2 / "profiles").glob("*.json")}
    uri_evidence = json.loads((STAGE2 / "evidence" / "external_uri_verification.json").read_text())
    naming_refinements = json.loads((STAGE2 / "registry" / "naming_refinements.json").read_text())
    retired = json.loads((STAGE2 / "registry" / "retired_stage1_candidates.json").read_text())

    ontology = Graph().parse(STAGE2 / "ontology" / "nltl_benchmark_vocabulary.ttl", format="turtle")
    ontology_xml = Graph().parse(STAGE2 / "ontology" / "nltl_benchmark_vocabulary.rdf", format="xml")
    shapes = Graph().parse(STAGE2 / "shacl" / "schema_only_shapes.ttl", format="turtle")
    mappings = Graph().parse(STAGE2 / "mappings" / "haitham_exact_mappings.ttl", format="turtle")
    example = Graph().parse(STAGE2 / "examples" / "illustrative_ship.ttl", format="turtle")

    checks: list[dict] = []

    def check(name: str, condition: bool, detail: object) -> None:
        if not condition:
            fail(f"{name}: {detail}")
        checks.append({"check": name, "status": "PASS", "detail": detail})

    locals_ = [t["localName"] for t in registry]
    expected_count = manifest["terms"]
    check("canonical term count", len(registry) == expected_count, len(registry))
    stage1_ids = {
        cid for t in registry for cid in t["sourceConceptIds"] if not cid.startswith("VOC-R2-")
    } | {cid for cid in retired if not cid.startswith("VOC-R2-")}
    check("Stage 1 candidate lineage", manifest["stage1CandidateTerms"] == 823 and len(stage1_ids) == 823, len(stage1_ids))
    r2_ids = {cid for t in registry for cid in t["sourceConceptIds"] if cid.startswith("VOC-R2-")}
    check("R2 added concept lineage", len(r2_ids) == manifest.get("r2AddedConcepts", 0), sorted(r2_ids))
    check("one documented semantic merge", manifest["stage2SemanticMerges"] == 1, manifest["stage2SemanticMerges"])
    check("retired/remodelled candidates reconciled", manifest["retiredStage1Candidates"] == len(retired) and "VOC-0747" in retired, list(retired))
    check("documented naming refinements", len(naming_refinements) == manifest["stage2NamingRefinementRows"], len(naming_refinements))
    check("unique local names", len(set(locals_)) == expected_count, len(set(locals_)))
    check("ASCII lowerCamelCase", all(re.fullmatch(r"[a-z][A-Za-z0-9]*", n) for n in locals_), f"{expected_count}/{expected_count}")
    check("all names have traceability", all(t["sourceConceptIds"] and t["stage1LocalNames"] and t["requirements"] and t["aliases"] and t["sourceRefs"] for t in registry), f"{expected_count}/{expected_count}")
    old_names = {
        "aRequiredCm2", "aircraftVoiceFrequencySupportMHz", "averageImpactEnergyJ", "deadweightTonnes",
        "displacementDeltaT", "displacementUiwlT", "elongationTestPercent", "propellerSpeedMcrBollardRpm",
        "sNcurveType", "solely24HourDaylightOperation",
    }
    check("superseded names excluded from canonical set", not (set(locals_) & old_names), sorted(set(locals_) & old_names))
    unit_tokens = {"mm", "cm", "km", "kg", "tonne", "tonnes", "kn", "kpa", "mpa", "kw", "mw", "hz", "khz", "mhz", "rpm", "sec", "hour", "degc", "celsius", "pct", "joule", "joules"}
    unit_name_hits = {n: sorted(name_tokens(n) & unit_tokens) for n in locals_ if name_tokens(n) & unit_tokens}
    check("canonical local names contain no unit tokens", not unit_name_hits, unit_name_hits)
    check("generic multi-dimension fallback term excluded", "tableFallbackValue" not in locals_, "excluded and redirected")
    check("term-kind total", sum(manifest["termKinds"].values()) == expected_count, manifest["termKinds"])
    check("no answer logic flag", manifest["containsRegulatoryAnswerLogic"] is False, False)
    by_local = {t["localName"]: t for t in registry}
    check("deadweight is a unit-separated mass quantity", by_local["deadweight"]["kind"] == "QuantityProperty" and by_local["deadweight"]["unitIri"] == "http://qudt.org/vocab/unit/TON_Metric", by_local["deadweight"]["kind"])
    check("continuous-daylight applicability is Boolean", by_local["operatesOnlyInContinuousDaylight"]["datatype"] == "xsd:boolean", by_local["operatesOnlyInContinuousDaylight"]["datatype"])
    check("S-N notation has readable canonical name", by_local["stressLifeCurveType"]["kind"] == "DatatypeProperty" and by_local["stressLifeCurveType"]["datatype"] == "xsd:string", by_local["stressLifeCurveType"]["datatype"])
    false_quantity_names = {
        "administrationRequiredIceRemovalMeans", "assessedIceOperation", "asternIceOperationIntent",
        "escortedOperationLimits", "extendedDarknessOperation", "extendedPeriodOperation",
        "icebreakerEscortOperation", "independentOperationLimits", "operationalAssessmentReference",
        "polarWaterOperationalManualIceAccretionLimit", "polarWaterOperationalManualPresentOnBoard",
        "relevantPolarWaterOperationalManualProcedureOrEquipment", "requiredEquipmentOperation",
    }
    check("no substring-induced operation/administration quantities", all(by_local[n]["kind"] != "QuantityProperty" for n in false_quantity_names), sorted(n for n in false_quantity_names if by_local[n]["kind"] == "QuantityProperty"))

    declared = set()
    for t in registry:
        iri = URIRef(t["iri"])
        expected = OWL.Class if t["kind"] == "Class" else (OWL.DatatypeProperty if t["kind"] == "DatatypeProperty" else OWL.ObjectProperty)
        if (iri, RDF.type, expected) in ontology:
            declared.add(t["localName"])
    check("ontology declarations match registry", declared == set(locals_), len(declared))
    check("Turtle/RDFXML graph equivalence", set(ontology) == set(ontology_xml), {"ttl": len(ontology), "rdfxml": len(ontology_xml)})

    candidate_property_shapes = [NSH[f"{t['localName']}PropertyShape"] for t in registry if t["kind"] != "Class"]
    check("one schema property shape per property", all((s, RDF.type, SH.PropertyShape) in shapes for s in candidate_property_shapes), len(candidate_property_shapes))
    check("candidate shapes contain no cardinality answers", all(not list(shapes.objects(s, SH.minCount)) and not list(shapes.objects(s, SH.maxCount)) for s in candidate_property_shapes), "0 candidate cardinalities")
    forbidden = [SH.minInclusive, SH.maxInclusive, SH.minExclusive, SH.maxExclusive, SH.lessThan, SH.lessThanOrEquals, SH.equals, SH.disjoint, SH.hasValue, SH["in"], SH.sparql]
    forbidden_hits = sum(len(list(shapes.triples((None, p, None)))) for p in forbidden)
    check("no thresholds/formulas/answer constraints", forbidden_hits == 0, forbidden_hits)

    ctx = context.get("@context", {})
    check("protected JSON-LD context", ctx.get("@protected") is True, ctx.get("@protected"))
    check("context covers every approved name", all(n in ctx for n in locals_), sum(n in ctx for n in locals_))
    inline_jsonld = dict(jsonld_example)
    inline_jsonld["@context"] = ctx
    jsonld_graph = Graph().parse(data=json.dumps(inline_jsonld), format="json-ld")
    check("JSON-LD context expands illustrative graph", len(jsonld_graph) == len(example) and set(jsonld_graph) == set(example), {"jsonld": len(jsonld_graph), "turtle": len(example)})

    master = profiles["master"]
    master_allowed = set(master["allowedClasses"]) | set(master["allowedProperties"])
    registry_iris = {t["iri"] for t in registry}
    check("master profile exact term set", master_allowed == registry_iris, len(master_allowed))
    check("master profile requirement count", len(master["requirementIds"]) == 313, len(master["requirementIds"]))
    check("direct profile requirement count", len(profiles["direct_deterministic"]["requirementIds"]) == 240, len(profiles["direct_deterministic"]["requirementIds"]))
    check("all profiles are whitelists only", all(p["containsRequirementLogic"] is False for p in profiles.values()), list(profiles))
    check("all profile terms use master URIs", all((set(p["allowedClasses"]) | set(p["allowedProperties"])) <= registry_iris for p in profiles.values()), len(profiles))
    source_req_union = set().union(*(set(profiles[x]["requirementIds"]) for x in ("traficom", "iacs_ur_i2", "imo_polar_code", "imo_amend_2026")))
    check("source profiles cover all requirements", source_req_union == set(master["requirementIds"]), len(source_req_union))

    exact_mappings = list(mappings.triples((None, SKOS.exactMatch, None)))
    check("verified Haitham exact mapping count", len(exact_mappings) == 22, len(exact_mappings))
    equivalence_hits = len(list(mappings.triples((None, OWL.equivalentProperty, None)))) + len(list(mappings.triples((None, OWL.equivalentClass, None))))
    check("no unsafe OWL equivalence to legacy model", equivalence_hits == 0, equivalence_hits)
    check("no claimed DNV exact URI", all("dnv" not in str(o).lower() for _, _, o in mappings), "0")

    if pyshacl_validate is not None:
        conforms, _, report_text = pyshacl_validate(example, shacl_graph=shapes, ont_graph=ontology, inference="rdfs", advanced=True)
        validation_engine = "pySHACL"
    else:
        conforms, report_text = structural_conforms(example)
        validation_engine = "deterministic schema-only fallback"
    check("positive example conforms", bool(conforms), f"{validation_engine}: {report_text[:500]}")

    invalid = Graph().parse(data=f'''@prefix ex: <https://example.org/nltl-stage2-invalid/> .
@prefix nltl: <{VOCAB_BASE}> .
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:q a qudt:QuantityValue ; qudt:numericValue "1.0"^^xsd:decimal .
''', format="turtle")
    if pyshacl_validate is not None:
        invalid_conforms, _, invalid_report = pyshacl_validate(invalid, shacl_graph=shapes, ont_graph=ontology, inference="rdfs", advanced=True)
        invalid_detail = invalid_report.splitlines()[-1] if invalid_report else "rejected"
    else:
        invalid_conforms, invalid_report = structural_conforms(invalid)
        invalid_detail = f"{validation_engine}: {invalid_report}"
    check("negative missing-unit example rejected", not bool(invalid_conforms), invalid_detail)

    unit_iris = [t["unitIri"] for t in registry if t["unitIri"]]
    check("unit IRIs are absolute and syntactically clean", all(re.fullmatch(r"https?://[^\s|()]+", u) for u in unit_iris), len(unit_iris))
    verified_unit_iris = {x["uri"] for x in uri_evidence["qudtUnits"]}
    check("all asserted units are in external URI evidence", set(unit_iris) == verified_unit_iris, len(verified_unit_iris))
    check("every quantity has an explicit unit decision", all(t["unitDecisionStatus"] for t in registry if t["kind"] == "QuantityProperty"), manifest["termKinds"]["QuantityProperty"])
    no_recommended_unit = [t for t in registry if t["kind"] == "QuantityProperty" and not t["unitIri"]]
    check("only source-ambiguous viscosity lacks a global recommended unit", len(no_recommended_unit) == 3 and all("viscosity" in t["localName"].lower() and "same declared viscosity quantity kind and unit" in t["unitDecisionStatus"] for t in no_recommended_unit), [t["localName"] for t in no_recommended_unit])
    check("quantity terms use QuantityValue", all(t["parentOrRange"] == str(QUDT.QuantityValue) for t in registry if t["kind"] == "QuantityProperty"), manifest["termKinds"]["QuantityProperty"])
    controlled = {
        "iceClass": str(NLTL.iceClassValue),
        "polarClass": str(NLTL.polarClassValue),
        "shipCategory": str(NLTL.polarShipCategoryValue),
    }
    check("core regulated enumerations use IRIs", all(by_local[k]["kind"] == "ObjectProperty" and by_local[k]["parentOrRange"] == v for k, v in controlled.items()), controlled)
    if manifest.get("revision") == "R2":
        required_r2 = {
            "compartment": ("Class", str(NLTL.shipComponent)),
            "hasContainingCompartment": ("ObjectProperty", str(NLTL.compartment)),
            "emergencyFirePump": ("Class", str(NLTL.firePump)),
            "waterMistPump": ("Class", str(NLTL.firePump)),
            "waterSprayPump": ("Class", str(NLTL.firePump)),
        }
        check(
            "IMO-057 R2 terms and ranges",
            all(by_local[name]["kind"] == kind and by_local[name]["parentOrRange"] == range_ for name, (kind, range_) in required_r2.items()),
            required_r2,
        )
        check("obsolete string compartment term excluded", "containingCompartment" not in by_local, "retired with redirect")

    report = {
        "status": "PASS",
        "checksPassed": len(checks),
        "ontologyTriples": len(ontology),
        "shapeTriples": len(shapes),
        "mappingTriples": len(mappings),
        "exampleTriples": len(example),
        "termKinds": dict(Counter(t["kind"] for t in registry)),
        "checks": checks,
    }
    (STAGE2 / "validation" / "validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Stage 2 validation report", "", "Status: **PASS**", "", f"Checks passed: **{len(checks)}**", ""]
    lines += [f"- {c['check']}: PASS — {c['detail']}" for c in checks]
    (STAGE2 / "validation" / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
