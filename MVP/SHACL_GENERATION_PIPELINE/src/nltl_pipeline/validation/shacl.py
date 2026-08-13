from __future__ import annotations

import re
from typing import Any

import pyshacl
from rdflib import BNode, Graph, Literal, RDF, URIRef
from rdflib.namespace import OWL, RDFS, SH, XSD
from rdflib.plugins.sparql.parser import parseQuery

from ..models import ContextPack, StaticValidationReport
from ..retrieval.context import NLTL, VocabularyRepository
from .sparql_extensions import MATH_NAMESPACE, register_math_functions


register_math_functions()


BEGIN = "<BEGIN_SHACL>"
END = "<END_SHACL>"
QUDT_NUMERIC_VALUE = URIRef("http://qudt.org/schema/qudt/numericValue")
FULL_NLTL_IRI_RE = re.compile(r"<((?:https://w3id\.org/nltl-benchmark/vocab#)[A-Za-z_][A-Za-z0-9_]*)>")
CURIE_RE = re.compile(r"\bnltl:([A-Za-z_][A-Za-z0-9_]*)\b")
PREFIX_RE = re.compile(r"\bPREFIX\s+([A-Za-z_][A-Za-z0-9_-]*):\s*<([^>]+)>", re.IGNORECASE)
# Require an absolute-IRI scheme immediately after '<'.  A broad '<...>'
# expression incorrectly consumed SPARQL comparison operators such as '<=' up
# to the next closing '>' in the query.
ANGLE_IRI_RE = re.compile(r"<([A-Za-z][A-Za-z0-9+.-]*:[^<>\s]*)>")

APPROVED_EXTERNAL_NAMESPACES = (
    str(RDF),
    str(RDFS),
    str(OWL),
    str(SH),
    str(XSD),
    "http://qudt.org/schema/qudt/",
    "http://qudt.org/vocab/unit/",
    "http://www.w3.org/ns/sosa/",
    "http://www.w3.org/ns/ssn/",
    "http://www.w3.org/2004/02/skos/core#",
    "http://purl.org/dc/terms/",
    MATH_NAMESPACE,
    "urn:nltl:generated-shape:",
    "https://w3id.org/nltl-benchmark/generated-shapes/",
)

TARGET_PREDICATES = {
    SH.targetClass,
    SH.targetNode,
    SH.targetSubjectsOf,
    SH.targetObjectsOf,
    SH.target,
}
CONSTRAINT_PREDICATES = {
    SH.property,
    SH.sparql,
    SH.node,
    SH.datatype,
    SH["class"],
    SH.minCount,
    SH.maxCount,
    SH.minInclusive,
    SH.maxInclusive,
    SH.minExclusive,
    SH.maxExclusive,
    SH.hasValue,
    SH["in"],
    SH["or"],
    SH["and"],
    SH["not"],
    SH["xone"],
    SH.equals,
    SH.disjoint,
    SH.lessThan,
    SH.lessThanOrEquals,
    SH.qualifiedValueShape,
}


def extract_shacl(raw: str) -> str:
    if raw.count(BEGIN) != 1 or raw.count(END) != 1:
        raise ValueError("Generator response must contain exactly one BEGIN_SHACL and END_SHACL marker")
    start = raw.index(BEGIN) + len(BEGIN)
    end = raw.index(END, start)
    if raw[:raw.index(BEGIN)].strip() or raw[end + len(END):].strip():
        raise ValueError("Generator response contains text outside SHACL markers")
    text = raw[start:end].strip()
    if not text:
        raise ValueError("Generated SHACL block is empty")
    if "```" in text:
        raise ValueError("Generated SHACL contains a Markdown fence")
    return text + "\n"


class ShaclStaticValidator:
    def __init__(self, vocabulary: VocabularyRepository) -> None:
        self.vocabulary = vocabulary

    @staticmethod
    def _query_canonical_iris(text: str) -> set[str]:
        result = set(FULL_NLTL_IRI_RE.findall(text))
        result.update(NLTL + local for local in CURIE_RE.findall(text))
        for prefix, namespace in PREFIX_RE.findall(text):
            if namespace != NLTL:
                continue
            pattern = re.compile(rf"\b{re.escape(prefix)}:([A-Za-z_][A-Za-z0-9_]*)\b")
            result.update(NLTL + local for local in pattern.findall(text))
        return result

    def validate_raw(self, raw: str, context: ContextPack) -> tuple[str, StaticValidationReport]:
        try:
            turtle = extract_shacl(raw)
        except ValueError as exc:
            return "", StaticValidationReport(
                valid=False,
                extraction_valid=False,
                turtle_valid=False,
                shacl_structure_valid=False,
                meta_shacl_valid=False,
                vocabulary_valid=False,
                datatype_unit_valid=False,
                target_path_valid=False,
                errors=[str(exc)],
            )
        return turtle, self.validate_turtle(turtle, context)

    def validate_turtle(self, turtle: str, context: ContextPack) -> StaticValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        graph = Graph()
        try:
            graph.parse(data=turtle, format="turtle")
        except Exception as exc:
            return StaticValidationReport(
                valid=False,
                extraction_valid=True,
                turtle_valid=False,
                shacl_structure_valid=False,
                meta_shacl_valid=False,
                vocabulary_valid=False,
                datatype_unit_valid=False,
                target_path_valid=False,
                errors=[f"Turtle parse error: {exc}"],
            )

        node_shapes = set(graph.subjects(RDF.type, SH.NodeShape))
        property_shapes = set(graph.subjects(RDF.type, SH.PropertyShape))
        shapes = node_shapes | property_shapes
        shacl_structure_valid = bool(shapes)
        if not shapes:
            errors.append("No sh:NodeShape or sh:PropertyShape is declared")
        targeted = {shape for shape in shapes if any((shape, predicate, None) in graph for predicate in TARGET_PREDICATES)}
        target_path_valid = bool(targeted)
        if shapes and not targeted:
            errors.append("No declared shape has an explicit SHACL target")
        constrained = {shape for shape in shapes if any((shape, predicate, None) in graph for predicate in CONSTRAINT_PREDICATES)}
        if shapes and not constrained:
            shacl_structure_valid = False
            errors.append("Declared shapes contain no recognizable SHACL constraint")

        meta_shacl_valid = True
        try:
            conforms, _report_graph, report_text = pyshacl.validate(
                Graph(),
                shacl_graph=graph,
                meta_shacl=True,
                inference="none",
                advanced=True,
            )
            if not conforms:
                meta_shacl_valid = False
                errors.append("Meta-SHACL validation failed: " + str(report_text).strip()[:1500])
        except Exception as exc:
            meta_shacl_valid = False
            errors.append(f"Meta-SHACL execution error: {exc}")

        # An empty data graph does not activate targetClass/targetSubjectsOf/
        # targetObjectsOf constraints, so an invalid embedded query can escape
        # the Meta-SHACL call above.  Activate every declared target on a tiny
        # synthetic graph and require the engine to return a real report graph.
        # Conformance is irrelevant here: missing synthetic values should cause
        # normal violations, while query/algebra failures must block acceptance.
        smoke_data = Graph()
        smoke_focus = URIRef("urn:nltl:static-smoke:focus")
        smoke_aux = URIRef("urn:nltl:static-smoke:aux")
        for _shape, _predicate, target_class in graph.triples((None, SH.targetClass, None)):
            if isinstance(target_class, URIRef):
                smoke_data.add((smoke_focus, RDF.type, target_class))
        for _shape, _predicate, target_node in graph.triples((None, SH.targetNode, None)):
            if isinstance(target_node, URIRef):
                smoke_data.add((target_node, RDF.type, OWL.Thing))
        for _shape, _predicate, target_property in graph.triples((None, SH.targetSubjectsOf, None)):
            if isinstance(target_property, URIRef):
                smoke_data.add((smoke_focus, target_property, smoke_aux))
        for _shape, _predicate, target_property in graph.triples((None, SH.targetObjectsOf, None)):
            if isinstance(target_property, URIRef):
                smoke_data.add((smoke_aux, target_property, smoke_focus))
        try:
            _smoke_conforms, smoke_report_graph, smoke_report_text = pyshacl.validate(
                smoke_data,
                shacl_graph=graph,
                meta_shacl=True,
                inference="none",
                advanced=True,
            )
            if not isinstance(smoke_report_graph, Graph):
                meta_shacl_valid = False
                errors.append("SHACL runtime smoke check failed: " + str(smoke_report_text).strip()[:1500])
        except Exception as exc:
            meta_shacl_valid = False
            errors.append(f"SHACL runtime smoke execution error: {exc}")

        all_known = {term["iri"] for term in self.vocabulary.full_compact_index()}
        scoped = set(context.allowed_iris)
        used_nltl = {str(node) for node in graph.all_nodes() if isinstance(node, URIRef) and str(node).startswith(NLTL)}
        query_texts: list[str] = []
        for literal in graph.objects(None, SH.select):
            if isinstance(literal, Literal):
                query_texts.append(str(literal))
        for literal in graph.objects(None, SH.ask):
            if isinstance(literal, Literal):
                query_texts.append(str(literal))
        for query_text in query_texts:
            used_nltl.update(self._query_canonical_iris(query_text))
            union_count = len(re.findall(r"\bUNION\b", query_text, re.IGNORECASE))
            negative_branch_count = len(re.findall(r"\bFILTER\s+NOT\s+EXISTS\b", query_text, re.IGNORECASE))
            if union_count > 12 or negative_branch_count > 20:
                errors.append(
                    "Embedded SHACL-SPARQL exceeds the portable complexity limit "
                    f"(UNION={union_count}, FILTER NOT EXISTS={negative_branch_count}); "
                    "use SHACL Core constraints and one bounded formula query"
                )
            if re.search(r"FILTER\s+NOT\s+EXISTS\s*\{[\s\S]*?\bOPTIONAL\s*\{", query_text, re.IGNORECASE):
                errors.append(
                    "Embedded SHACL-SPARQL nests OPTIONAL inside FILTER NOT EXISTS; "
                    "use SHACL Core for required fields and a bounded positive formula pattern"
                )
            if re.search(r"(?<![:A-Za-z0-9_])(SIN|COS|TAN|ATAN)\s*\(", query_text, re.IGNORECASE):
                errors.append(
                    "Bare trigonometric SPARQL functions are unsupported; use the registered "
                    "XPath math IRIs math:sin, math:cos, math:tan, and math:atan"
                )
            try:
                parseQuery(query_text)
            except Exception as exc:
                errors.append(f"Embedded SHACL-SPARQL parse error: {exc}")
            declared_prefixes = {prefix.lower() for prefix, _namespace in PREFIX_RE.findall(query_text)}
            for prefix in ("nltl", "xsd", "rdf", "rdfs", "owl", "sh", "qudt", "unit", "math"):
                if re.search(rf"\b{prefix}:[A-Za-z_]", query_text, re.IGNORECASE) and prefix not in declared_prefixes:
                    errors.append(
                        f"Embedded SHACL-SPARQL uses prefix {prefix}: without declaring it inside the query"
                    )
        unknown = sorted(used_nltl - all_known)
        out_of_scope = sorted((used_nltl & all_known) - scoped)
        if unknown:
            errors.append("Unknown canonical benchmark IRI(s): " + ", ".join(unknown))
        if out_of_scope:
            errors.append("Known benchmark IRI(s) outside the generator allow-list: " + ", ".join(out_of_scope))

        required_owner = str(context.selection.get("requiredTargetOwner") or "")
        if required_owner and required_owner != "benchmarkEntity":
            broad_target = URIRef(NLTL + "benchmarkEntity")
            if any((shape, SH.targetClass, broad_target) in graph for shape in shapes):
                errors.append(
                    "Shape targets generic benchmarkEntity despite the authoritative "
                    f"requirement target owner {required_owner}"
                )

        suspicious: set[str] = set()
        for node in graph.all_nodes():
            if not isinstance(node, URIRef):
                continue
            iri = str(node)
            if iri.startswith(NLTL) or any(iri.startswith(prefix) for prefix in APPROVED_EXTERNAL_NAMESPACES):
                continue
            suspicious.add(iri)
        for query_text in query_texts:
            for iri in ANGLE_IRI_RE.findall(query_text):
                if iri == NLTL or iri.startswith(NLTL):
                    continue
                if any(iri.startswith(prefix) for prefix in APPROVED_EXTERNAL_NAMESPACES):
                    continue
                suspicious.add(iri)
        if suspicious:
            errors.append("Unapproved external/generated IRI(s): " + ", ".join(sorted(suspicious)))

        by_iri = {term["iri"]: term for term in self.vocabulary.full_compact_index()}
        datatype_unit_valid = True
        for property_shape, _, path_node in graph.triples((None, SH.path, None)):
            if not isinstance(path_node, URIRef) or str(path_node) not in by_iri:
                continue
            record = by_iri[str(path_node)]
            if record["kind"] not in {"DatatypeProperty", "ObjectProperty", "QuantityProperty"}:
                target_path_valid = False
                errors.append(f"sh:path incorrectly uses non-property IRI {path_node}")
            declared_datatypes = [str(item) for item in graph.objects(property_shape, SH.datatype)]
            expected_datatype = record.get("datatype")
            if expected_datatype:
                expected_full = str(XSD) + expected_datatype.split(":", 1)[1] if expected_datatype.startswith("xsd:") else expected_datatype
                if declared_datatypes and expected_full not in declared_datatypes:
                    datatype_unit_valid = False
                    errors.append(
                        f"Datatype mismatch for {record['localName']}: expected {expected_full}, found {declared_datatypes}"
                    )
            if record["kind"] == "QuantityProperty" and declared_datatypes:
                datatype_unit_valid = False
                errors.append(
                    f"Quantity property {record['localName']} must point to a QUDT QuantityValue node, not a direct literal datatype"
                )

        # Numeric RDF literal equality is datatype-and-lexical-form sensitive.
        # Equivalent values such as 845 and 845.0 can therefore compare unequal
        # under sh:hasValue. Bounds and tolerances are portable across serializers.
        numeric_datatypes = {
            XSD.decimal, XSD.double, XSD.float, XSD.integer, XSD.long, XSD.int,
            XSD.short, XSD.byte, XSD.nonNegativeInteger, XSD.positiveInteger,
            XSD.nonPositiveInteger, XSD.negativeInteger, XSD.unsignedLong,
            XSD.unsignedInt, XSD.unsignedShort, XSD.unsignedByte,
        }
        for property_shape in graph.subjects(SH.path, QUDT_NUMERIC_VALUE):
            for required_value in graph.objects(property_shape, SH.hasValue):
                if isinstance(required_value, Literal) and required_value.datatype in numeric_datatypes:
                    datatype_unit_valid = False
                    errors.append(
                        "Numeric qudt:numericValue uses sh:hasValue, which is lexical-form brittle; "
                        "use equal inclusive numeric bounds for an exact regulatory constant or "
                        "an explicit tolerance interval for a derived result"
                    )

        for group in context.selection.get("exclusivePropertyGroups", []):
            alternatives = group.get("alternatives", []) if isinstance(group, dict) else []
            if len(alternatives) < 2:
                continue
            alternative_iris = [
                {URIRef(NLTL + str(local_name)) for local_name in alternative}
                for alternative in alternatives
            ]
            for parent in set(graph.subjects(SH.property, None)):
                mandatory_paths: set[URIRef] = set()
                for property_shape in graph.objects(parent, SH.property):
                    path = graph.value(property_shape, SH.path)
                    minimum = graph.value(property_shape, SH.minCount)
                    if isinstance(path, URIRef) and isinstance(minimum, Literal):
                        try:
                            if int(minimum) >= 1:
                                mandatory_paths.add(path)
                        except (TypeError, ValueError):
                            pass
                if all(mandatory_paths & alternative for alternative in alternative_iris):
                    shacl_structure_valid = False
                    errors.append(
                        f"Mutually exclusive property alternatives in {group.get('id', 'declared group')} "
                        "are mandatory on the same node shape; encode separate positive branches or case shapes"
                    )
                    break

        for shape, _, target_class in graph.triples((None, SH.targetClass, None)):
            if isinstance(target_class, URIRef) and str(target_class) in by_iri:
                if by_iri[str(target_class)]["kind"] != "Class":
                    target_path_valid = False
                    errors.append(f"sh:targetClass uses non-class IRI {target_class}")

        allowed_units = {str(item.get("recommendedUnit")) for item in context.terms if item.get("recommendedUnit")}
        used_units = {
            str(node)
            for node in graph.all_nodes()
            if isinstance(node, URIRef) and str(node).startswith("http://qudt.org/vocab/unit/")
        }
        unexpected_units = sorted(used_units - allowed_units)
        if unexpected_units:
            datatype_unit_valid = False
            errors.append("QUDT unit not permitted by the scoped term metadata: " + ", ".join(unexpected_units))

        vocabulary_valid = not unknown and not out_of_scope and not suspicious
        valid = all((
            shacl_structure_valid,
            meta_shacl_valid,
            vocabulary_valid,
            datatype_unit_valid,
            target_path_valid,
            not errors,
        ))
        return StaticValidationReport(
            valid=valid,
            extraction_valid=True,
            turtle_valid=True,
            shacl_structure_valid=shacl_structure_valid,
            meta_shacl_valid=meta_shacl_valid,
            vocabulary_valid=vocabulary_valid,
            datatype_unit_valid=datatype_unit_valid,
            target_path_valid=target_path_valid,
            errors=errors,
            warnings=warnings,
            used_canonical_iris=sorted(used_nltl),
            unknown_canonical_iris=unknown,
            out_of_scope_canonical_iris=out_of_scope,
            suspicious_external_iris=sorted(suspicious),
        )
