from __future__ import annotations

import unittest

from nltl_pipeline.cli import offline_smoke_responses
from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.retrieval.context import VocabularyRepository
from nltl_pipeline.validation.shacl import (
    ShaclStaticValidator,
    ShaclWrapperError,
    normalize_shacl_wrapper,
)


VALID_TURTLE = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix nltl: <https://w3id.org/nltl/vocab#> .
<urn:test:Shape> a sh:NodeShape ; sh:targetClass nltl:ship ; sh:closed false .
"""


class ShaclWrapperNormalizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = VocabularyRepository(PipelineConfig.load())
        cls.validator = ShaclStaticValidator(cls.vocabulary)
        cls.context = cls.vocabulary.build_context_pack("IMO26-014")

    def test_sol_normal_format_is_unchanged(self) -> None:
        raw = f"<BEGIN_SHACL>\n{VALID_TURTLE}<END_SHACL>\n"
        normalized = normalize_shacl_wrapper(raw)
        self.assertEqual(VALID_TURTLE, normalized.turtle)
        self.assertFalse(normalized.text_outside_markers)
        self.assertFalse(normalized.alternate_closing_marker_used)
        self.assertFalse(normalized.multiple_marker_mentions)

    def test_gemini_xml_style_closing_marker(self) -> None:
        original = offline_smoke_responses("IMO26-014")["generator"][1]
        raw = original.replace("<END_SHACL>", "</END_SHACL>")
        normalized = normalize_shacl_wrapper(raw)
        turtle, report = self.validator.validate_raw(raw, self.context)
        self.assertEqual(normalized.turtle, turtle)
        self.assertTrue(report.extraction_valid)
        self.assertTrue(report.alternate_closing_marker_used)
        self.assertTrue(normalized.alternate_closing_marker_used)

    def test_gpt_oss_reasoning_and_marker_mentions_outside_final_block(self) -> None:
        raw = (
            "Reasoning mentions <BEGIN_SHACL> and <END_SHACL> inline.\n"
            "<BEGIN_SHACL>\nold candidate\n<END_SHACL>\n"
            "More reasoning about marker names.\n"
            f"<BEGIN_SHACL>\n{VALID_TURTLE}<END_SHACL>\n"
            "Trailing explanation.\n"
        )
        normalized = normalize_shacl_wrapper(raw)
        self.assertEqual(VALID_TURTLE, normalized.turtle)
        self.assertTrue(normalized.text_outside_markers)
        self.assertTrue(normalized.multiple_marker_mentions)
        _turtle, report = self.validator.validate_raw(raw, self.context)
        self.assertTrue(report.text_outside_markers)
        self.assertTrue(report.multiple_marker_mentions)

    def test_ambiguous_and_nested_blocks_are_rejected(self) -> None:
        ambiguous = f"<BEGIN_SHACL>\n{VALID_TURTLE}<END_SHACL>\n</END_SHACL>\n"
        nested = f"<BEGIN_SHACL>\n<BEGIN_SHACL>\n{VALID_TURTLE}<END_SHACL>\n<END_SHACL>\n"
        for raw in (ambiguous, nested):
            with self.subTest(raw=raw), self.assertRaises(ShaclWrapperError):
                normalize_shacl_wrapper(raw)

    def test_genuinely_malformed_turtle_still_fails_deterministic_validation(self) -> None:
        normal = offline_smoke_responses("IMO26-014")["generator"][1]
        malformed = normal.replace("a sh:NodeShape ;", "a sh:NodeShape ; [ malformed", 1)
        turtle, report = self.validator.validate_raw(malformed, self.context)
        self.assertTrue(turtle)
        self.assertTrue(report.extraction_valid)
        self.assertFalse(report.turtle_valid)
        self.assertFalse(report.valid)
        self.assertTrue(any(error.startswith("Turtle parse error:") for error in report.errors))


if __name__ == "__main__":
    unittest.main()
