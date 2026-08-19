from __future__ import annotations

import unittest

from nltl_pipeline.cli import offline_smoke_responses
from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.retrieval.context import VocabularyRepository
from nltl_pipeline.validation.shacl import ShaclStaticValidator, extract_shacl


class ShaclValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = VocabularyRepository(PipelineConfig.load())
        cls.validator = ShaclStaticValidator(cls.vocabulary)
        cls.context = cls.vocabulary.build_context_pack("IMO26-014")

    def test_extract_rejects_markdown_or_extra_text(self) -> None:
        with self.assertRaises(ValueError):
            extract_shacl("Explanation\n<BEGIN_SHACL>@prefix sh: <http://www.w3.org/ns/shacl#> .<END_SHACL>")

    def test_unknown_query_term_is_detected(self) -> None:
        wrong = offline_smoke_responses("IMO26-014")["generator"][0]
        _turtle, report = self.validator.validate_raw(wrong, self.context)
        self.assertFalse(report.valid)
        self.assertIn(
            "https://w3id.org/nltl/vocab#visualIceDetectionLightCount",
            report.unknown_canonical_iris,
        )

    def test_correct_shape_passes_all_static_gates(self) -> None:
        correct = offline_smoke_responses("IMO26-014")["generator"][1]
        _turtle, report = self.validator.validate_raw(correct, self.context)
        self.assertTrue(report.valid, report.errors)
        self.assertTrue(report.meta_shacl_valid)
        self.assertTrue(report.vocabulary_valid)

    def test_unapproved_query_namespace_is_detected(self) -> None:
        correct = offline_smoke_responses("IMO26-014")["generator"][1]
        altered = correct.replace(
            "PREFIX nltl: <https://w3id.org/nltl/vocab#>",
            "PREFIX nltl: <https://w3id.org/nltl/vocab#>\nPREFIX bad: <https://example.invalid/vocab#>",
        ).replace(
            "$this nltl:operatesOnlyInContinuousDaylight ?daylight .",
            "$this nltl:operatesOnlyInContinuousDaylight ?daylight .\n$this bad:invented ?x .",
        )
        _turtle, report = self.validator.validate_raw(altered, self.context)
        self.assertFalse(report.valid)
        self.assertIn("https://example.invalid/vocab#", report.suspicious_external_iris)

    def test_embedded_sparql_prefix_must_be_declared_in_query(self) -> None:
        correct = offline_smoke_responses("IMO26-014")["generator"][1]
        altered = correct.replace(
            "FILTER (?daylight = false)",
            'BIND("2020-01-01"^^xsd:date AS ?date)\n                FILTER (?daylight = false)',
        )
        _turtle, report = self.validator.validate_raw(altered, self.context)
        self.assertFalse(report.valid)
        self.assertTrue(any("prefix xsd:" in item for item in report.errors), report.errors)

    def test_comparison_operator_is_not_misread_as_angle_iri(self) -> None:
        correct = offline_smoke_responses("IMO26-014")["generator"][1]
        altered = correct.replace(
            "FILTER (?daylight = false)",
            "FILTER (?daylight = false && 0 <= 1)",
        )
        _turtle, report = self.validator.validate_raw(altered, self.context)
        self.assertTrue(report.valid, report.errors)
        self.assertEqual([], report.suspicious_external_iris)

    def test_invalid_embedded_sparql_is_rejected_before_acceptance(self) -> None:
        correct = offline_smoke_responses("IMO26-014")["generator"][1]
        altered = correct.replace(
            "FILTER (?daylight = false)",
            "BIND( AS ?broken) FILTER (?daylight = false)",
        )
        _turtle, report = self.validator.validate_raw(altered, self.context)
        self.assertFalse(report.valid)
        self.assertTrue(any("SHACL-SPARQL parse error" in item for item in report.errors), report.errors)
        self.assertTrue(self.validator.is_syntax_failure(report))

    def test_syntax_repair_diagnostics_exclude_semantic_lint_and_locate_query(self) -> None:
        correct = offline_smoke_responses("IMO26-014")["generator"][1]
        altered = correct.replace(
            "FILTER (?daylight = false)",
            "BIND(SQRT(4) AS ?root) FILTER (?daylight = false)",
        )
        context = self.vocabulary.build_context_pack("IMO26-014")
        context.selection["dependencyContract"] = dict(context.selection["dependencyContract"])
        context.selection["dependencyContract"].update({
            "status": "COMPLETE",
            "relationshipTerms": ["hasComponent"],
        })
        turtle, report = self.validator.validate_raw(altered, context)
        self.assertTrue(any("dependency relationship" in item for item in report.errors), report.errors)
        diagnostics = self.validator.syntax_repair_diagnostics(altered, turtle, report)
        self.assertFalse(
            any("dependency relationship" in item for item in diagnostics["syntaxErrors"]),
            diagnostics,
        )
        self.assertTrue(diagnostics["offendingRegions"], diagnostics)
        self.assertIn("SQRT", diagnostics["offendingRegions"][0]["offendingLine"])

    def test_complete_contract_relationship_is_deterministically_required(self) -> None:
        correct = offline_smoke_responses("IMO26-014")["generator"][1]
        context = self.vocabulary.build_context_pack("IMO26-014")
        context.selection["dependencyContract"] = dict(context.selection["dependencyContract"])
        context.selection["dependencyContract"].update({
            "status": "COMPLETE",
            "relationshipTerms": ["hasComponent"],
        })
        _turtle, report = self.validator.validate_raw(correct, context)
        self.assertFalse(report.valid)
        self.assertTrue(any("dependency relationship" in item for item in report.errors), report.errors)

    def test_shacl_forbidden_values_clause_is_rejected_by_runtime_smoke(self) -> None:
        correct = offline_smoke_responses("IMO26-014")["generator"][1]
        altered = correct.replace(
            "SELECT DISTINCT $this",
            "SELECT DISTINCT $this",
        ).replace(
            "WHERE {",
            "WHERE { VALUES ?forbidden { 1 }",
            1,
        )
        _turtle, report = self.validator.validate_raw(altered, self.context)
        self.assertFalse(report.valid)
        self.assertTrue(any("runtime smoke" in item and "VALUES" in item for item in report.errors), report.errors)

    def test_combinatorial_query_is_rejected_before_expensive_evaluation(self) -> None:
        correct = offline_smoke_responses("IMO26-014")["generator"][1]
        repeated = " UNION ".join("{ BIND(%d AS ?x%d) }" % (i, i) for i in range(14))
        altered = correct.replace(
            "$this nltl:operatesOnlyInContinuousDaylight ?daylight .",
            "$this nltl:operatesOnlyInContinuousDaylight ?daylight .\n" + repeated,
        )
        _turtle, report = self.validator.validate_raw(altered, self.context)
        self.assertFalse(report.valid)
        self.assertTrue(any("complexity limit" in item for item in report.errors), report.errors)

    def test_optional_inside_filter_not_exists_is_rejected(self) -> None:
        correct = offline_smoke_responses("IMO26-014")["generator"][1]
        altered = correct.replace(
            "WHERE {",
            "WHERE { FILTER NOT EXISTS { OPTIONAL { $this nltl:operatesOnlyInContinuousDaylight ?nested . } }",
            1,
        )
        _turtle, report = self.validator.validate_raw(altered, self.context)
        self.assertFalse(report.valid)
        self.assertTrue(any("OPTIONAL inside FILTER NOT EXISTS" in item for item in report.errors), report.errors)

    def test_registered_xpath_math_function_executes(self) -> None:
        config = PipelineConfig.load()
        vocabulary = VocabularyRepository(config)
        validator = ShaclStaticValidator(vocabulary)
        context = vocabulary.build_context_pack("TRF-022")
        turtle = '''@prefix gen: <urn:nltl:generated-shape:> .
@prefix nltl: <https://w3id.org/nltl/vocab#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
gen:S a sh:NodeShape ; sh:targetClass nltl:ship ; sh:sparql [
  sh:select """PREFIX math: <http://www.w3.org/2005/xpath-functions/math#>
  SELECT $this WHERE { BIND(math:sin(0.0) AS ?result) FILTER(?result != 0.0) }"""
] .'''
        report = validator.validate_turtle(turtle, context)
        self.assertTrue(report.valid, report.errors)

    def test_numeric_has_value_on_qudt_numeric_value_is_rejected(self) -> None:
        config = PipelineConfig.load()
        vocabulary = VocabularyRepository(config)
        validator = ShaclStaticValidator(vocabulary)
        context = vocabulary.build_context_pack("TRF-022")
        turtle = '''@prefix gen: <urn:nltl:generated-shape:> .
@prefix nltl: <https://w3id.org/nltl/vocab#> .
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
gen:S a sh:NodeShape ; sh:targetClass nltl:ship ; sh:property [
  sh:path nltl:coefficientC3 ; sh:node [ sh:property [
    sh:path qudt:numericValue ; sh:hasValue "845"^^xsd:decimal
  ] ]
] .'''
        report = validator.validate_turtle(turtle, context)
        self.assertFalse(report.valid)
        self.assertTrue(any("lexical-form brittle" in item for item in report.errors), report.errors)

    def test_declared_exclusive_property_groups_cannot_be_conjunctive(self) -> None:
        config = PipelineConfig.load()
        vocabulary = VocabularyRepository(config)
        validator = ShaclStaticValidator(vocabulary)
        context = vocabulary.build_context_pack("TRF-030")
        context.selection["exclusivePropertyGroups"] = [{
            "id": "syntheticVerifiedAlternative",
            "alternatives": [["verticalLoadPosition"], ["horizontalLoadPosition"]],
        }]
        turtle = '''@prefix gen: <urn:nltl:generated-shape:> .
@prefix nltl: <https://w3id.org/nltl/vocab#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
gen:S a sh:NodeShape ; sh:targetClass nltl:directAnalysisCase ;
  sh:property [ sh:path nltl:verticalLoadPosition ; sh:minCount 1 ],
              [ sh:path nltl:horizontalLoadPosition ; sh:minCount 1 ] .'''
        report = validator.validate_turtle(turtle, context)
        self.assertFalse(report.valid)
        self.assertTrue(any("Mutually exclusive property alternatives" in item for item in report.errors), report.errors)


if __name__ == "__main__":
    unittest.main()
