from __future__ import annotations
import json
import unittest
from nltl_pipeline.errors import ResponseContractError
from nltl_pipeline.validation.contracts import (
    normalize_validator_response,
    parse_matcher_decision,
    parse_validator_decision,
)

ISSUE = {"category":"UNIT_CONVERSION","location":"ThicknessShape","problem":"Millimetres and metres are compared directly.","required_change":"Convert millimetres to metres before comparison.","regression_guard":"Preserve metre-normalized thickness comparison.","blocking":True,"needs_vocabulary_resolution":False}

def decision(*, accept=False, matcher=False, issues=None):
    return json.dumps({"accept":accept,"activate_variable_matcher":matcher,"currentIssues":[ISSUE] if issues is None else issues}, separators=(",", ":"))

class ContractTests(unittest.TestCase):
    def test_structured_issue_parses_without_legacy_feedback(self):
        vocabulary_issue=dict(ISSUE); vocabulary_issue["needs_vocabulary_resolution"]=True
        parsed = parse_validator_decision(decision(matcher=True,issues=[vocabulary_issue]))
        self.assertEqual(parsed.current_issues[0].category, "UNIT_CONVERSION")
    def test_malformed_issue_structure_fails_strictly(self):
        malformed=dict(ISSUE); malformed.pop("location")
        with self.assertRaises(ResponseContractError): parse_validator_decision(decision(issues=[malformed]))
    def test_accept_cannot_contain_blocking_issues(self):
        with self.assertRaises(ResponseContractError): parse_validator_decision(decision(accept=True))
    def test_accept_cannot_activate_matcher(self):
        with self.assertRaises(ResponseContractError): parse_validator_decision(decision(accept=True, matcher=True, issues=[]))
    def test_reject_requires_blocking_issue(self):
        item=dict(ISSUE); item["blocking"]=False
        with self.assertRaises(ResponseContractError): parse_validator_decision(decision(issues=[item]))
    def test_issue_booleans_are_strict(self):
        item=dict(ISSUE); item["blocking"]=1
        with self.assertRaises(ResponseContractError): parse_validator_decision(decision(issues=[item]))
    def test_vague_blocking_feedback_fails(self):
        item=dict(ISSUE); item["problem"]="This could be improved."
        with self.assertRaises(ResponseContractError): parse_validator_decision(decision(issues=[item]))
    def test_matcher_contract_requires_empty_identity_on_no_match(self):
        with self.assertRaises(ResponseContractError): parse_matcher_decision('{"match_found":false,"canonical_local_name":"x","canonical_iri":"","feedback_appendix":"No."}')

    def test_plain_sol_style_validator_object_remains_unchanged(self):
        raw = decision()
        normalized = normalize_validator_response(raw)
        self.assertEqual(normalized.decision_text, raw)
        self.assertFalse(normalized.text_outside_decision_block)
        self.assertFalse(normalized.multiple_candidate_decision_blocks)

    def test_gpt_oss_reasoning_before_final_object_is_ignored_not_modified(self):
        final = decision()
        raw = "We need inspect the constraint carefully.\nThe verdict follows.\n" + final
        parsed = parse_validator_decision(raw)
        normalized = normalize_validator_response(raw)
        self.assertFalse(parsed.accept)
        self.assertEqual(normalized.decision_text, final)
        self.assertEqual(normalized.text_before_decision_block, "We need inspect the constraint carefully.\nThe verdict follows.\n")
        self.assertTrue(parsed.text_outside_decision_block)

    def test_validator_explanation_whitespace_is_not_rewritten(self):
        item = dict(ISSUE)
        item["problem"] = "  Exact explanation whitespace is retained.  "
        parsed = parse_validator_decision(decision(issues=[item]))
        self.assertEqual(parsed.current_issues[0].problem, item["problem"])

    def test_gpt_oss_pretty_candidate_then_final_object_uses_final_and_records_multiple(self):
        earlier_issue = dict(ISSUE)
        earlier_issue["problem"] = "Earlier wording from analysis."
        earlier = json.dumps({
            "accept": False,
            "activate_variable_matcher": False,
            "currentIssues": [earlier_issue],
        }, indent=2)
        final_issue = dict(ISSUE)
        final_issue["problem"] = "Final wording must be preserved exactly."
        final = decision(issues=[final_issue])
        raw = "Analysis:\n" + earlier + "\nReturn it in one line.\n" + final
        parsed = parse_validator_decision(raw)
        normalized = normalize_validator_response(raw)
        self.assertEqual(normalized.decision_text, final)
        self.assertEqual(parsed.current_issues[0].problem, "Final wording must be preserved exactly.")
        self.assertTrue(parsed.multiple_candidate_decision_blocks)
        self.assertEqual(parsed.candidate_decision_block_count, 2)

    def test_conflicting_candidate_decisions_are_rejected(self):
        accepted = decision(accept=True, issues=[])
        rejected = decision()
        with self.assertRaisesRegex(ResponseContractError, "Conflicting"):
            parse_validator_decision(accepted + "\nFinal answer:\n" + rejected)

    def test_incomplete_trailing_decision_is_rejected_without_falling_back(self):
        raw = decision() + '\nCorrection: {"accept":'
        with self.assertRaisesRegex(ResponseContractError, "Incomplete trailing"):
            parse_validator_decision(raw)

    def test_nested_decision_objects_are_ambiguous(self):
        inner = json.loads(decision())
        outer = {"accept": False, "activate_variable_matcher": False, "currentIssues": [inner]}
        with self.assertRaisesRegex(ResponseContractError, "nested"):
            parse_validator_decision(json.dumps(outer, separators=(",", ":")))

    def test_missing_decision_is_rejected(self):
        with self.assertRaisesRegex(ResponseContractError, "No complete"):
            parse_validator_decision("Reasoning only; no decision object follows.")

if __name__ == "__main__": unittest.main()
