from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from nltl_pipeline.api.client import ScriptedResponsesClient
from nltl_pipeline.cli import make_parser, offline_smoke_responses
from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.orchestration.runner import PipelineRunner
from nltl_pipeline.orchestration.singleshot import (
    ContextualSingleShotRunner,
    render_first_generator_request,
)


ROOT = Path(__file__).resolve().parents[1]
R13_CONFIG = ROOT / "config" / "pipeline.official-r13.json"


class ContextualSingleShotTests(unittest.TestCase):
    def config_for(self, output: Path) -> PipelineConfig:
        base = PipelineConfig.load(R13_CONFIG)
        raw = copy.deepcopy(base.raw)
        raw["paths"]["outputs"] = str(output)
        raw["reporting"]["excel_enabled"] = False
        return PipelineConfig(raw=raw, config_path=base.config_path)

    def test_valid_output_makes_exactly_one_generator_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            config = self.config_for(Path(temp_name) / "outputs")
            client = ScriptedResponsesClient({
                "generator": [offline_smoke_responses("IMO26-014")["generator"][1]],
            })
            result = ContextualSingleShotRunner(config).run_requirement("IMO26-014", client)

            self.assertEqual(["generator"], [item["role"] for item in client.calls])
            self.assertEqual(1, result.generator_calls)
            self.assertEqual(0, result.validator_calls)
            self.assertEqual(0, result.vocabulary_matcher_calls)
            self.assertEqual(0, result.syntax_repair_calls)
            self.assertEqual(0, result.regeneration_calls)
            self.assertTrue(result.raw_response.is_file())
            self.assertTrue(result.extracted_shape and result.extracted_shape.is_file())
            self.assertTrue(result.diagnostics.is_file())

            events = [
                json.loads(line)
                for line in (result.run_directory / "events.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            completed_roles = [
                event["role"] for event in events if event["event_type"] == "api_call_completed"
            ]
            self.assertEqual(["generator"], completed_roles)
            self.assertFalse(any(event["event_type"] == "matcher_search" for event in events))
            self.assertFalse(any(event["event_type"] == "syntax_repair_started" for event in events))

    def test_malformed_markers_are_retained_without_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            config = self.config_for(Path(temp_name) / "outputs")
            raw_response = "Here is malformed Turtle without the required response markers."
            client = ScriptedResponsesClient({"generator": [raw_response]})
            result = ContextualSingleShotRunner(config).run_requirement("IMO26-014", client)

            self.assertEqual(raw_response, result.raw_response.read_text(encoding="utf-8"))
            self.assertIsNone(result.extracted_shape)
            self.assertEqual("FAIL", result.extraction_status)
            self.assertEqual("NOT_RUN", result.rdf_parse_status)
            self.assertEqual(["generator"], [item["role"] for item in client.calls])

    def test_first_request_renderer_matches_full_pipeline_construction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            config = self.config_for(Path(temp_name) / "outputs")
            full = PipelineRunner(config)
            single = ContextualSingleShotRunner(config)
            _, full_few_shots, full_developer, full_user = render_first_generator_request(
                full, "IMO26-014"
            )
            _, single_few_shots, single_developer, single_user = render_first_generator_request(
                single, "IMO26-014"
            )
            self.assertEqual(full_developer, single_developer)
            self.assertEqual(full_user, single_user)
            self.assertEqual(full_few_shots, single_few_shots)
            self.assertEqual("NONE", json.loads(single_user)["repairFeedback"])

    def test_cli_exposes_isolated_single_and_batch_commands(self) -> None:
        parser = make_parser()
        single = parser.parse_args(["contextual-single-shot", "--requirement", "IMO26-014"])
        batch = parser.parse_args(["contextual-single-shot-batch", "--queue", "queue.json"])
        self.assertEqual("contextual-single-shot", single.command)
        self.assertEqual("contextual-single-shot-batch", batch.command)


if __name__ == "__main__":
    unittest.main()
