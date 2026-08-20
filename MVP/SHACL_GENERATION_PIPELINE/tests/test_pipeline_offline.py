from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from nltl_pipeline.api.client import ScriptedResponsesClient
from nltl_pipeline.cli import offline_smoke_responses
from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.errors import ConfigurationError
from nltl_pipeline.orchestration.runner import PipelineRunner
from nltl_pipeline.retrieval.context import VocabularyRepository


class OfflinePipelineTests(unittest.TestCase):
    def test_syntax_repair_does_not_consume_semantic_attempt_or_call_validator_early(self) -> None:
        base = PipelineConfig.load()
        with tempfile.TemporaryDirectory() as temp_name:
            raw = copy.deepcopy(base.raw)
            raw["paths"]["outputs"] = str(Path(temp_name) / "outputs")
            raw["reporting"]["excel_enabled"] = False
            raw["generation"]["maximum_semantic_attempts"] = 1
            raw["generation"]["maximum_syntax_repairs_per_semantic_attempt"] = 1
            config = PipelineConfig(raw=raw, config_path=base.config_path)
            vocabulary = VocabularyRepository(config)
            runner = PipelineRunner(config, vocabulary)
            correct = offline_smoke_responses("IMO26-014")["generator"][1]
            invalid = correct.replace("FILTER (?daylight = false)", "BIND( AS ?broken) FILTER (?daylight = false)")
            client = ScriptedResponsesClient({
                "generator": [invalid],
                "syntax_repair": [correct],
                "validator": ['{"accept":true,"activate_variable_matcher":false,"feedback":"Syntax repaired; semantics preserved."}'],
            })
            result = runner.run_requirement("IMO26-014", client)
            self.assertTrue(result.accepted)
            self.assertEqual(result.attempts, 1)
            self.assertEqual(["generator", "syntax_repair", "validator"], [call["role"] for call in client.calls])
            events = (result.run_directory / "events.jsonl").read_text(encoding="utf-8")
            self.assertIn('"semantic_attempt_consumed":false', events)

    def test_validator_feedback_reversal_heuristic_keeps_explicit_explanation_support(self) -> None:
        self.assertTrue(PipelineRunner._feedback_reverses_without_explanation(
            ["Require hasComponent on every branch."],
            "Remove hasComponent from every branch.",
        ))
        self.assertFalse(PipelineRunner._feedback_reverses_without_explanation(
            ["Require hasComponent on every branch."],
            "REVERSAL: Remove hasComponent because the corrected contract makes the property ship-owned.",
        ))

    def test_history_guard_does_not_confuse_unrelated_or_preserved_directives(self) -> None:
        self.assertFalse(PipelineRunner._feedback_reverses_without_explanation(
            ["Remove sh:minCount 1 from nltl:hasMemberSupport."],
            "Require simpleFrameSupport when no trigger exists; do not add sh:minCount 1 to nltl:hasMemberSupport.",
        ))
        self.assertFalse(PipelineRunner._feedback_reverses_without_explanation(
            ["Retarget validation to the ship; do not use structuralMember as an independent target."],
            "Add nltl:frameProfileType on the ship; do not relocate it to structuralMember.",
        ))

    def test_i2_030_style_refinement_is_non_blocking_and_uses_no_response_retry(self) -> None:
        base = PipelineConfig.load()
        with tempfile.TemporaryDirectory() as temp_name:
            raw = copy.deepcopy(base.raw)
            raw["paths"]["outputs"] = str(Path(temp_name) / "outputs")
            raw["reporting"]["excel_enabled"] = False
            raw["generation"]["maximum_semantic_attempts"] = 2
            raw["api"]["validator_response_retries"] = 1
            config = PipelineConfig(raw=raw, config_path=base.config_path)
            correct = offline_smoke_responses("IMO26-014")["generator"][1]
            client = ScriptedResponsesClient({
                "generator": [correct, correct],
                "validator": [
                    '{"accept":false,"activate_variable_matcher":false,"feedback":"validate the member inputs"}',
                    '{"accept":true,"activate_variable_matcher":false,"feedback":"do not validate all ship members; validate the case-linked member"}',
                ],
            })
            result = PipelineRunner(config).run_requirement("IMO26-014", client)
            self.assertTrue(result.accepted)
            self.assertEqual(result.attempts, 2)
            self.assertEqual(
                ["generator", "validator", "generator", "validator"],
                [call["role"] for call in client.calls],
            )
            events = (result.run_directory / "events.jsonl").read_text(encoding="utf-8")
            self.assertNotIn('"event_type":"validator_reconciliation_required"', events)

    def test_imo_057_style_true_oscillation_is_diagnostic_not_blocking(self) -> None:
        base = PipelineConfig.load()
        with tempfile.TemporaryDirectory() as temp_name:
            raw = copy.deepcopy(base.raw)
            raw["paths"]["outputs"] = str(Path(temp_name) / "outputs")
            raw["reporting"]["excel_enabled"] = False
            raw["generation"]["maximum_semantic_attempts"] = 2
            raw["api"]["validator_response_retries"] = 1
            config = PipelineConfig(raw=raw, config_path=base.config_path)
            correct = offline_smoke_responses("IMO26-014")["generator"][1]
            client = ScriptedResponsesClient({
                "generator": [correct, correct],
                "validator": [
                    '{"accept":false,"activate_variable_matcher":false,"feedback":"remove the xsd:decimal-only constraint"}',
                    '{"accept":true,"activate_variable_matcher":false,"feedback":"require xsd:decimal"}',
                ],
            })
            result = PipelineRunner(config).run_requirement("IMO26-014", client)
            self.assertTrue(result.accepted)
            self.assertEqual(result.attempts, 2)
            self.assertEqual(
                ["generator", "validator", "generator", "validator"],
                [call["role"] for call in client.calls],
            )
            events = (result.run_directory / "events.jsonl").read_text(encoding="utf-8")
            self.assertIn('"event_type":"validator_feedback_possible_reversal"', events)
            self.assertIn('"blocking":false', events)
            self.assertIn('"semantic_attempt_consumed":false', events)
            self.assertNotIn('"event_type":"validator_reconciliation_required"', events)

    def test_full_matcher_repair_route_without_api_or_excel(self) -> None:
        base = PipelineConfig.load()
        with tempfile.TemporaryDirectory() as temp_name:
            raw = copy.deepcopy(base.raw)
            raw["paths"]["outputs"] = str(Path(temp_name) / "outputs")
            raw["reporting"]["excel_enabled"] = False
            config = PipelineConfig(raw=raw, config_path=base.config_path)
            vocabulary = VocabularyRepository(config)
            runner = PipelineRunner(config, vocabulary)
            client = ScriptedResponsesClient(offline_smoke_responses("IMO26-014"))
            result = runner.run_requirement("IMO26-014", client)
            self.assertTrue(result.accepted)
            self.assertEqual(result.attempts, 2)
            self.assertTrue(result.final_shape and result.final_shape.is_file())
            events = (result.run_directory / "events.jsonl").read_text(encoding="utf-8")
            self.assertIn('"event_type":"matcher_decision"', events)
            self.assertIn('"status":"GENERATION_ACCEPTED"', events)
            validator_prompt = (
                result.run_directory / "artifacts/attempt_01/validator_prompt_01.txt"
            ).read_text(encoding="utf-8")
            self.assertNotIn("fullCanonicalVocabularyIndex", validator_prompt)
            self.assertIn("retrievedRelevantVocabulary", validator_prompt)
            self.assertIn("candidateUsedCanonicalTerms", validator_prompt)
            self.assertIn("mismatchCandidates", validator_prompt)
            self.assertLess(len(validator_prompt.encode("utf-8")), 50_000)

    def test_r9_source_blocked_requirement_stops_before_any_llm_call(self) -> None:
        config_path = Path(__file__).resolve().parents[1] / "config/pipeline.dev-r9.json"
        base = PipelineConfig.load(config_path)
        with tempfile.TemporaryDirectory() as temp_name:
            raw = copy.deepcopy(base.raw)
            raw["paths"]["outputs"] = str(Path(temp_name) / "outputs")
            raw["reporting"]["excel_enabled"] = False
            config = PipelineConfig(raw=raw, config_path=base.config_path)
            runner = PipelineRunner(config)
            client = ScriptedResponsesClient({})
            with self.assertRaisesRegex(ConfigurationError, "BLOCKED_SOURCE_OR_MODEL_DEPENDENCY"):
                runner.run_requirement("I2-053", client, allow_deferred=True)
            self.assertFalse(Path(raw["paths"]["outputs"]).exists())


if __name__ == "__main__":
    unittest.main()
