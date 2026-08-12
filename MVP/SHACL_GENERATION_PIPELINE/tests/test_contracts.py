from __future__ import annotations

import unittest

from nltl_pipeline.errors import ResponseContractError
from nltl_pipeline.validation.contracts import parse_matcher_decision, parse_validator_decision


class ContractTests(unittest.TestCase):
    def test_validator_contract_accepts_exact_one_line_json(self) -> None:
        decision = parse_validator_decision(
            '{"accept":false,"activate_variable_matcher":true,"feedback":"Use the canonical term."}'
        )
        self.assertFalse(decision.accept)
        self.assertTrue(decision.activate_variable_matcher)

    def test_validator_contract_rejects_extra_keys(self) -> None:
        with self.assertRaises(ResponseContractError):
            parse_validator_decision(
                '{"accept":true,"activate_variable_matcher":false,"feedback":"","extra":1}'
            )

    def test_validator_contract_rejects_multiline(self) -> None:
        with self.assertRaises(ResponseContractError):
            parse_validator_decision(
                '{"accept":false,\n"activate_variable_matcher":false,"feedback":"Fix it."}'
            )

    def test_validator_contract_rejects_contradictory_activation(self) -> None:
        with self.assertRaises(ResponseContractError):
            parse_validator_decision(
                '{"accept":true,"activate_variable_matcher":true,"feedback":""}'
            )

    def test_matcher_contract_requires_empty_identity_on_no_match(self) -> None:
        with self.assertRaises(ResponseContractError):
            parse_matcher_decision(
                '{"match_found":false,"canonical_local_name":"x","canonical_iri":"","feedback_appendix":"No."}'
            )


if __name__ == "__main__":
    unittest.main()

