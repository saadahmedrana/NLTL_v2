from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path
from nltl_pipeline.models import ContextPack, StaticValidationReport, ValidatorIssue
from nltl_pipeline.orchestration.repair import RepairMemory, issue_key
from nltl_pipeline.prompts import PromptFactory

def issue(category="UNIT_CONVERSION", location="thickness", guard="Preserve normalized units"):
    return ValidatorIssue(category, location, "Wrong current behavior", "Fix only this behavior", guard, True, False)

class FullRepairV2UnitTests(unittest.TestCase):
    def setUp(self):
        self.context = ContextPack({"requirement_id":"R"}, [{"iri":"urn:x"}], [], {}, {}, {})

    def test_initial_payload_has_fewshots_and_no_previous_candidate(self):
        payload=json.loads(PromptFactory().generator_user(self.context,[{"exampleId":"E"}],"","urn:g:"))
        self.assertIn("fewShotExamples", payload); self.assertNotIn("previousCandidateShacl", payload)
        self.assertNotIn("behavioral", json.dumps(payload).lower())

    def test_repair_payload_has_exact_one_candidate_no_fewshots_or_legacy_history(self):
        payload=json.loads(PromptFactory().semantic_repair_user(self.context,"@prefix x:<urn:x:> .",[issue()],["guard"],"urn:g:"))
        self.assertEqual(payload["previousCandidateShacl"], "@prefix x:<urn:x:> .")
        self.assertNotIn("fewShotExamples", payload); self.assertNotIn("priorFeedbackHistory", payload)
        self.assertNotIn("repairFeedback", payload); self.assertEqual(payload["pastMistakesToAvoid"], ["guard"])

    def test_repair_memory_resolves_retains_adds_and_deduplicates(self):
        memory=RepairMemory(); a=issue(); b=issue("WRONG_PATH","owner","Preserve owner path")
        memory.transition([a,b]); c=issue("CARDINALITY","count","Preserve required count")
        memory.transition([b,c])
        self.assertEqual({issue_key(x) for x in memory.current_issues},{issue_key(b),issue_key(c)})
        self.assertEqual(memory.guards,["Preserve normalized units"])
        memory.transition([b,c]); self.assertEqual(memory.guards,["Preserve normalized units"])

    def test_reappearing_issue_supersedes_passive_guard(self):
        memory=RepairMemory(); a=issue(); memory.transition([a]); memory.transition([])
        self.assertTrue(memory.guards); memory.transition([a]); self.assertFalse(memory.guards)

    def test_validator_payload_separates_guards_and_omits_prior_feedback(self):
        report=StaticValidationReport(True,True,True,True,True,True,True,True)
        payload=json.loads(PromptFactory().validator_user(self.context,"ttl",report,[],[],["guard"]))
        self.assertEqual(payload["pastMistakesToAvoid"],["guard"])
        self.assertNotIn("priorFeedbackHistory",payload)

    def test_all_official_configs_are_explicit_and_isolated(self):
        root=Path(__file__).resolve().parents[1]
        configs=sorted((root/"experiments/FULL_REPAIR_V2/CONFIGS").glob("*.json"))
        self.assertEqual(len(configs),10)
        for number,path in enumerate(configs,1):
            data=json.loads(path.read_text())
            self.assertEqual(data["architecture"],"FULL_REPAIR_V2")
            self.assertEqual(data["generation_run"],f"RUN_{number:02d}")
            self.assertEqual(data["generation"]["maximum_semantic_attempts"],4)
            self.assertIn(f"FULL_REPAIR_V2/RUN_{number:02d}",data["paths"]["outputs"])

    def test_official_evaluator_policy_can_only_select_accepted_final_artifact(self):
        evaluation=Path(__file__).resolve().parents[1]/"evaluation"
        if str(evaluation) not in sys.path: sys.path.insert(0,str(evaluation))
        from experiment_runner.core import EXPERIMENTS
        policy=EXPERIMENTS["FULL_REPAIR_V2"]
        self.assertEqual(policy["artifact_type"],"final_accepted_shape")
        self.assertEqual(policy["usable_statuses"],{"GENERATION_ACCEPTED"})
        self.assertNotEqual(policy["artifact_type"],"last_candidate_diagnostic")

if __name__ == "__main__": unittest.main()
