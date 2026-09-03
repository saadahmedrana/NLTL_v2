from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from nltl_pipeline.api.client import ScriptedResponsesClient
from nltl_pipeline.cli import make_parser, offline_smoke_responses
from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.orchestration.no_semantic_validator import NoSemanticValidatorRunner
from nltl_pipeline.orchestration.runner import PipelineRunner
from nltl_pipeline.orchestration.singleshot import render_first_generator_request


ROOT = Path(__file__).resolve().parents[1]
R13_CONFIG = ROOT / "config/pipeline.official-r13.json"


class NoSemanticValidatorTests(unittest.TestCase):
    def config_for(self, output: Path, *, syntax_repairs: int = 1) -> PipelineConfig:
        base = PipelineConfig.load(R13_CONFIG)
        raw = copy.deepcopy(base.raw)
        raw["paths"]["outputs"] = str(output)
        raw["reporting"]["excel_enabled"] = False
        raw["generation"]["maximum_syntax_repairs_per_semantic_attempt"] = syntax_repairs
        return PipelineConfig(raw=raw, config_path=base.config_path)

    def test_deterministic_pass_uses_generator_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            config = self.config_for(Path(temp_name) / "outputs")
            client = ScriptedResponsesClient({
                "generator": [offline_smoke_responses("IMO26-014")["generator"][1]],
            })
            result = NoSemanticValidatorRunner(config).run_requirement("IMO26-014", client)
            self.assertEqual("NO_SEMANTIC_VALIDATOR_DETERMINISTIC_PASS", result.status)
            self.assertTrue(result.deterministic_valid)
            self.assertEqual(["generator"], [call["role"] for call in client.calls])
            self.assertEqual(0, result.validator_calls)
            self.assertEqual(0, result.vocabulary_matcher_calls)
            self.assertEqual(0, result.regeneration_calls)

    def test_syntax_repair_remains_active_without_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            config = self.config_for(Path(temp_name) / "outputs")
            correct = offline_smoke_responses("IMO26-014")["generator"][1]
            invalid = correct.replace(
                "FILTER (?daylight = false)",
                "BIND( AS ?broken) FILTER (?daylight = false)",
            )
            client = ScriptedResponsesClient({
                "generator": [invalid],
                "syntax_repair": [correct],
            })
            result = NoSemanticValidatorRunner(config).run_requirement("IMO26-014", client)
            self.assertEqual("NO_SEMANTIC_VALIDATOR_DETERMINISTIC_PASS", result.status)
            self.assertEqual(["generator", "syntax_repair"], [call["role"] for call in client.calls])
            self.assertEqual(1, result.syntax_repair_calls)
            self.assertEqual(0, result.validator_calls)
            self.assertEqual(0, result.regeneration_calls)

    def test_deterministic_failure_does_not_trigger_semantic_regeneration_or_matcher(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            config = self.config_for(Path(temp_name) / "outputs")
            unknown_term_shape = offline_smoke_responses("IMO26-014")["generator"][0]
            client = ScriptedResponsesClient({"generator": [unknown_term_shape]})
            result = NoSemanticValidatorRunner(config).run_requirement("IMO26-014", client)
            self.assertEqual("NO_SEMANTIC_VALIDATOR_DETERMINISTIC_FAIL", result.status)
            self.assertFalse(result.deterministic_valid)
            self.assertEqual(["generator"], [call["role"] for call in client.calls])
            self.assertEqual(0, result.vocabulary_matcher_calls)
            self.assertEqual(0, result.regeneration_calls)

    def test_syntax_repair_exhaustion_is_retained_as_terminal_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            config = self.config_for(Path(temp_name) / "outputs", syntax_repairs=1)
            malformed = "Response without the required SHACL markers"
            client = ScriptedResponsesClient({
                "generator": [malformed],
                "syntax_repair": [malformed],
            })
            result = NoSemanticValidatorRunner(config).run_requirement("IMO26-014", client)
            self.assertEqual("SYNTAX_REPAIR_EXHAUSTED", result.status)
            self.assertEqual(["generator", "syntax_repair"], [call["role"] for call in client.calls])
            self.assertTrue(result.raw_response.is_file())
            diagnostics = json.loads(result.diagnostics.read_text(encoding="utf-8"))
            self.assertEqual(0, diagnostics["llmCallCounts"]["validator"])

    def test_first_request_is_identical_to_full_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            config = self.config_for(Path(temp_name) / "outputs")
            _, full_few, full_dev, full_user = render_first_generator_request(
                PipelineRunner(config), "IMO26-014"
            )
            _, ablation_few, ablation_dev, ablation_user = render_first_generator_request(
                NoSemanticValidatorRunner(config), "IMO26-014"
            )
            self.assertEqual(full_dev, ablation_dev)
            self.assertEqual(full_user, ablation_user)
            self.assertEqual(full_few, ablation_few)

    def test_cli_commands_are_isolated(self) -> None:
        parser = make_parser()
        single = parser.parse_args(["no-semantic-validator", "--requirement", "IMO26-014"])
        batch = parser.parse_args(["no-semantic-validator-batch", "--queue", "queue.json"])
        self.assertEqual("no-semantic-validator", single.command)
        self.assertEqual("no-semantic-validator-batch", batch.command)


if __name__ == "__main__":
    unittest.main()
