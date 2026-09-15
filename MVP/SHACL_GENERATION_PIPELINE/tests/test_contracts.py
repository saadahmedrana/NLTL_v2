from __future__ import annotations
import json
import unittest
from nltl_pipeline.errors import ResponseContractError
from nltl_pipeline.validation.contracts import parse_matcher_decision, parse_validator_decision

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

if __name__ == "__main__": unittest.main()
