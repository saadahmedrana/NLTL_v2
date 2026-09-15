from __future__ import annotations
import copy
import json
import tempfile
import unittest
from pathlib import Path
from nltl_pipeline.api.client import ScriptedResponsesClient
from nltl_pipeline.cli import offline_smoke_responses
from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.errors import ConfigurationError
from nltl_pipeline.orchestration.runner import PipelineRunner

ACCEPT = '{"accept":true,"activate_variable_matcher":false,"currentIssues":[]}'
ISSUE = '{"accept":false,"activate_variable_matcher":false,"currentIssues":[{"category":"APPLICABILITY","location":"main shape","problem":"The applicability branch is inverted.","required_change":"Invert only the applicability comparison.","regression_guard":"Preserve the corrected applicability branch.","blocking":true,"needs_vocabulary_resolution":false}]}'

class OfflinePipelineTests(unittest.TestCase):
    def config(self, temp_name, attempts=4):
        base=PipelineConfig.load(); raw=copy.deepcopy(base.raw)
        raw["paths"]["outputs"]=str(Path(temp_name)/"FULL_REPAIR_V2"/"RUN_01")
        raw["reporting"]["excel_enabled"]=False; raw["generation"]["maximum_semantic_attempts"]=attempts
        raw["generation_run"]="RUN_01"; return PipelineConfig(raw=raw,config_path=base.config_path)

    def test_syntax_repair_propagates_repaired_ttl_and_accepts(self):
        with tempfile.TemporaryDirectory() as name:
            config=self.config(name,2); correct=offline_smoke_responses("IMO26-014")["generator"][1]
            invalid=correct.replace("FILTER (?daylight = false)","BIND( AS ?broken) FILTER (?daylight = false)")
            client=ScriptedResponsesClient({"generator":[invalid],"syntax_repair":[correct],"validator":[ACCEPT]})
            result=PipelineRunner(config).run_requirement("IMO26-014",client)
            self.assertTrue(result.accepted); self.assertEqual([c["role"] for c in client.calls],["generator","syntax_repair","validator"])

    def test_semantic_repair_uses_only_immediately_previous_candidate(self):
        with tempfile.TemporaryDirectory() as name:
            config=self.config(name,2); shape=offline_smoke_responses("IMO26-014")["generator"][1]
            client=ScriptedResponsesClient({"generator":[shape,shape],"validator":[ISSUE,ACCEPT]})
            result=PipelineRunner(config).run_requirement("IMO26-014",client)
            self.assertTrue(result.accepted)
            repair=json.loads([c for c in client.calls if "previousCandidateShacl" in c["user"]][0]["user"])
            self.assertEqual(repair["previousCandidateShacl"],shape.split("<BEGIN_SHACL>\n",1)[1].split("<END_SHACL>",1)[0].strip()+"\n")
            self.assertNotIn("fewShotExamples",repair); self.assertNotIn("priorFeedbackHistory",repair)

    def test_static_invalid_skips_validator_and_preserves_candidate(self):
        with tempfile.TemporaryDirectory() as name:
            config=self.config(name,1); responses=offline_smoke_responses("IMO26-014")
            client=ScriptedResponsesClient({"generator":[responses["generator"][0]],"vocabulary_matcher":responses["vocabulary_matcher"]})
            result=PipelineRunner(config).run_requirement("IMO26-014",client)
            self.assertFalse(result.accepted); self.assertNotIn("validator",[c["role"] for c in client.calls])
            self.assertTrue((result.run_directory/"artifacts/attempt_01/candidate_shape.ttl").is_file())
            metadata=json.loads((result.run_directory/"diagnostics/last_candidate_metadata.json").read_text())
            self.assertFalse(metadata["official_final_shape"]); self.assertFalse((result.run_directory/"final/final_shape.ttl").exists())

    def test_offline_full_repair_smoke(self):
        with tempfile.TemporaryDirectory() as name:
            result=PipelineRunner(self.config(name)).run_requirement("IMO26-014",ScriptedResponsesClient(offline_smoke_responses("IMO26-014")))
            self.assertTrue(result.accepted); self.assertEqual(result.attempts,2)
            repair=(result.run_directory/"artifacts/attempt_02/semantic_repair_prompt.txt").read_text()
            self.assertIn("previousCandidateShacl",repair); self.assertIn("currentIssues",repair)
            self.assertNotIn("fewShotExamples",repair); self.assertNotIn("priorFeedbackHistory",repair)

    def test_matcher_no_match_continues_until_repair_budget(self):
        with tempfile.TemporaryDirectory() as name:
            responses=offline_smoke_responses("IMO26-014"); no_match='{"match_found":false,"canonical_local_name":"","canonical_iri":"","feedback_appendix":"No defensible locked match."}'
            client=ScriptedResponsesClient({"generator":responses["generator"],"vocabulary_matcher":[no_match],"validator":[ACCEPT]})
            result=PipelineRunner(self.config(name,2)).run_requirement("IMO26-014",client)
            self.assertTrue(result.accepted); self.assertEqual(result.attempts,2)
            first=json.loads((result.run_directory/"artifacts/attempt_01/attempt_metadata.json").read_text())
            self.assertEqual(first["matcher_status"],"MATCHER_NO_MATCH")

    def test_stall_and_oscillation_enable_only_final_escape_hatch(self):
        with tempfile.TemporaryDirectory() as name:
            a=offline_smoke_responses("IMO26-014")["generator"][1]
            b=a.replace("Two means of illumination are required", "At least two illumination means are required")
            client=ScriptedResponsesClient({"generator":[a,b,a,a],"validator":[ISSUE,ISSUE,ISSUE,ACCEPT]})
            result=PipelineRunner(self.config(name,4)).run_requirement("IMO26-014",client)
            self.assertTrue(result.accepted); self.assertEqual(result.attempts,4)
            m3=json.loads((result.run_directory/"artifacts/attempt_03/attempt_metadata.json").read_text())
            m4=json.loads((result.run_directory/"artifacts/attempt_04/attempt_metadata.json").read_text())
            self.assertTrue(m3["oscillation_detected"]); self.assertEqual(m4["mode"],"FRESH_REGENERATION_ESCAPE_HATCH")
            self.assertEqual(sum("Fresh regeneration escape hatch" in c["user"] for c in client.calls),1)

    def test_r9_source_blocked_before_llm(self):
        config_path=Path(__file__).resolve().parents[1]/"config/pipeline.dev-r9.json"
        with tempfile.TemporaryDirectory() as name:
            base=PipelineConfig.load(config_path); raw=copy.deepcopy(base.raw); raw["paths"]["outputs"]=str(Path(name)/"o")
            config=PipelineConfig(raw=raw,config_path=base.config_path); client=ScriptedResponsesClient({})
            with self.assertRaisesRegex(ConfigurationError,"BLOCKED_SOURCE_OR_MODEL_DEPENDENCY"):
                PipelineRunner(config).run_requirement("I2-053",client,allow_deferred=True)

if __name__ == "__main__": unittest.main()
