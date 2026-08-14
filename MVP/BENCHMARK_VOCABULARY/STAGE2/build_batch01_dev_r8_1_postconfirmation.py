from __future__ import annotations

import csv
import json

from rdflib import Graph, URIRef

import build_batch01_dev_r8_stabilization as r8


base = r8.base
r6 = r8.r6
base.OUT = base.MVP / "BENCHMARK_VOCABULARY" / "DEVELOPMENT" / "DEV_R8_1_POSTCONFIRMATION"
base.DEV_INDEX = base.OUT / "requirement_term_index.json"
base.VERSION = "2.8.1-dev-batch01-postconfirmation"
base.DEV_ID = "VOCAB-DEV-2026-08-13-BATCH01-R8.1-POSTCONFIRMATION"
C_OUTPUT_TERMS = {"brashIceResistanceCoefficientC1", "brashIceResistanceCoefficientC2"}


def assign_derived_force_units() -> None:
    registry_path = base.OUT / "registry/term_registry.json"
    registry = base.read_json(registry_path)
    for item in registry:
        if item["localName"] in C_OUTPUT_TERMS:
            item["unitSymbol"] = "N"
            item["unitIri"] = "http://qudt.org/vocab/unit/N"
            item["quantityKindLabel"] = "Force"
            item["unitDecisionStatus"] = "Derived from the verified dimensional form of TRAFICOM formulas 3.2.4/3.2.5"
            item["stage2UnitEvidence"] = "TRAFICOM p.10 clauses 3.2.4/3.2.5: every additive C1/C2 formula term resolves to newtons."
    base.write_json(registry_path, registry)

    csv_path = base.OUT / "registry/term_registry.csv"
    with csv_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        fields = list(rows[0]) if rows else []
    for item in rows:
        if item["localName"] in C_OUTPUT_TERMS:
            item["unitSymbol"] = "N"
            item["unitIri"] = "http://qudt.org/vocab/unit/N"
            item["quantityKindLabel"] = "Force"
            item["unitDecisionStatus"] = "Derived from the verified dimensional form of TRAFICOM formulas 3.2.4/3.2.5"
            item["stage2UnitEvidence"] = "TRAFICOM p.10 clauses 3.2.4/3.2.5: every additive C1/C2 formula term resolves to newtons."
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    predicate = URIRef(base.BASE + "recommendedUnit")
    for filename, rdf_format in (("nltl_benchmark_vocabulary.ttl", "turtle"), ("nltl_benchmark_vocabulary.rdf", "xml")):
        path = base.OUT / "ontology" / filename
        graph = Graph().parse(path, format=rdf_format)
        for local_name in C_OUTPUT_TERMS:
            subject = URIRef(base.BASE + local_name)
            graph.remove((subject, predicate, None))
            graph.add((subject, predicate, URIRef("http://qudt.org/vocab/unit/N")))
        graph.serialize(path, format=rdf_format)


def main() -> None:
    base.main()
    assign_derived_force_units()
    r6.add_ownership_metadata()
    payload = base.read_json(base.DEV_INDEX)
    payload["version"] = "1.7.1-dev-batch01-postconfirmation"
    payload["supportedSparqlExtensionFunctions"] = {
        "namespace": "http://www.w3.org/2005/xpath-functions/math#",
        "functions": ["sin", "cos", "tan", "atan"],
        "implementation": "Deterministic rdflib/pySHACL evaluator extension registered by the pipeline.",
    }
    # The confirmation validator correctly observed that the clause does not
    # prohibit recording both coordinates on a case. R8's exclusivity metadata
    # was therefore too strong and is removed in this post-confirmation revision.
    payload["exclusivePropertyGroups"] = {}
    payload["requirements"]["TRF-022"] = [
        name for name in payload["requirements"]["TRF-022"]
        if name != "constructionStageDate"
    ]
    payload.get("termOwners", {}).get("TRF-022", {}).pop("constructionStageDate", None)
    base.write_json(base.DEV_INDEX, payload)

    registry = base.read_json(base.OUT / "registry/term_registry.json")
    additions = [item for item in registry if str(item.get("conceptId", "")).startswith("VOC-DEV")]
    report = base.read_json(base.OUT / "validation/validation_report.json")
    base.build_manifest(registry, additions, report)
    base.build_development_binding()
    manifest = base.read_json(base.OUT / "development_manifest.json")
    manifest["baseRevision"] = "VOCAB-DEV-2026-08-13-BATCH01-R8-STABILIZATION"
    manifest["revisionPurpose"] = (
        "Post-confirmation development correction: derived N units for C1/C2 and removal "
        "of an over-strong direct-analysis coordinate exclusivity declaration. No new term."
    )
    manifest["postConfirmationCorrections"] = [
        "Assign QUDT unit:N to brashIceResistanceCoefficientC1 and C2 from verified formula dimensions.",
        "Remove TRF-030 exclusivePropertyGroups because the regulation does not prohibit both coordinates on one case.",
        "Remove constructionStageDate from TRF-022 because clause 3.2.2 contains no date-based applicability branch.",
    ]
    base.write_json(base.OUT / "development_manifest.json", manifest)
    print(json.dumps({
        "status": "PASS",
        "development_id": base.DEV_ID,
        "registry_terms": len(registry),
        "new_terms_since_r8": 0,
        "output": str(base.OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
