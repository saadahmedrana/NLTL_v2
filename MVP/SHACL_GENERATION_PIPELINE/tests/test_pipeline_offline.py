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
