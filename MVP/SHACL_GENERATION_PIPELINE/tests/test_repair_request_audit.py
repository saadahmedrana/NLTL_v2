from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from nltl_pipeline.orchestration.repair_request_audit import (
    RepairRequestIntegrityError, check_previous_code, text_hash,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_repair_requests import audit_config

CONFIG = ROOT / "experiments/FULL_REPAIR_V2/CONFIGS/pipeline.full-repair-v2-run01.json"


class PreviousCodeChecks(unittest.TestCase):
    def test_full_unicode_candidate_is_preserved_byte_for_byte(self):
        text = "# HEAD α\n" + "# unchanged code β\n" * 10000 + "# TAIL Ω\n"
        for field in ["previousCandidateShacl", "candidateResponse"]:
            payload = json.loads(json.dumps({field: text}, ensure_ascii=True))
            result = check_previous_code(payload, field, text, text_hash(text))
            self.assertEqual(result["embedded_candidate_sha256"], text_hash(text))
            self.assertEqual(result["previous_candidate_utf8_bytes"], len(text.encode("utf-8")))

    def test_absence_empty_staleness_and_truncation_fail_closed(self):
        text = "previous complete graph\n# tail"
        for field in ["previousCandidateShacl", "candidateResponse"]:
            for payload in [{}, {field: ""}, {field: "earlier graph"}, {field: text[:-1]}]:
                with self.subTest(field=field, payload=payload):
                    with self.assertRaises(RepairRequestIntegrityError):
                        check_previous_code(payload, field, text, text_hash(text))

    def test_independent_reference_hash_cannot_be_recomputed_from_stale_payload(self):
        with self.assertRaisesRegex(RepairRequestIntegrityError, "reference hash is stale"):
            check_previous_code({"previousCandidateShacl": "older graph"},
                                "previousCandidateShacl", "older graph", text_hash("newest graph"))


class SelectedRunnerOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name) / "audit"
        cls.summary = audit_config(CONFIG, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def ledgers(self, *, failures=False):
        for scenario in self.summary["scenarios"]:
            if bool(scenario["fault"]) == failures:
                yield scenario, json.loads(Path(scenario["request_ledger"]).read_text())

    def test_selected_config_is_exact_and_only_non_generation_overrides_exist(self):
        original = json.loads(CONFIG.read_text())
        self.assertEqual(self.summary["config_sha256"], text_hash(CONFIG.read_text()))
        self.assertEqual(self.summary["generation_run"], "RUN_01")
        self.assertEqual(self.summary["architecture"], "FULL_REPAIR_V2")
        for effective in self.output.glob("*/effective_config.json"):
            payload = json.loads(effective.read_text())
            payload["paths"]["outputs"] = original["paths"]["outputs"]
            payload["reporting"]["excel_enabled"] = original["reporting"]["excel_enabled"]
            self.assertEqual(payload, original)

    def test_all_normal_repair_routes_are_checked_and_version_bound(self):
        modes = set()
        for _, requests in self.ledgers():
            for request in requests:
                self.assertTrue(request["checked"])
                modes.add(request["mode"])
                if request["mode"] in {"STATIC_REPAIR", "SEMANTIC_CANDIDATE_REPAIR", "MATCHER_ASSISTED_REPAIR", "SYNTAX_REPAIR"}:
                    self.assertTrue(request["previous_candidate_complete"])
                    self.assertEqual(request["previous_candidate_sha256"], request["feedback_candidate_sha256"])
                    self.assertEqual(request["embedded_candidate_sha256"], request["previous_candidate_sha256"])
                    self.assertTrue(request["feedback_version_matches"])
        self.assertTrue({"STATIC_REPAIR", "SEMANTIC_CANDIDATE_REPAIR", "MATCHER_ASSISTED_REPAIR", "SYNTAX_REPAIR"} <= modes)

    def test_canonical_findings_survive_match_and_no_match_routes(self):
        seen = set()
        for _, requests in self.ledgers():
            for request in requests:
                if request.get("canonical_findings"):
                    seen.add(request["mode"])
                    payload = json.loads(request["user"])
                    for finding in request["canonical_findings"]:
                        self.assertIn(finding, payload["currentIssues"])
        self.assertEqual(seen, {"MATCHER_ASSISTED_REPAIR", "STATIC_REPAIR"})

    def test_escape_hatch_is_not_mislabeled_as_code_repair(self):
        requests = [r for _, rs in self.ledgers() for r in rs if r.get("fresh_regeneration")]
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["mode"], "FRESH_REGENERATION_ESCAPE_HATCH")
        self.assertNotIn("previousCandidateShacl", json.loads(requests[0]["user"]))

    def test_complete_rendered_requests_and_large_tail_are_saved(self):
        found = False
        for _, requests in self.ledgers():
            for request in requests:
                path = Path(request["runner_prompt_artifact"])
                self.assertEqual(path.read_text(), request["developer"] + "\n\n--- USER INPUT ---\n" + request["user"])
                if request.get("previous_candidate_utf8_bytes", 0) > 100000:
                    found = True
                    text = json.loads(request["user"])["previousCandidateShacl"]
                    self.assertIn("HEAD_CANARY_α", text)
                    self.assertIn("TAIL_CANARY_Ω", text)
        self.assertTrue(found)

    def test_fault_injections_are_rejected_before_local_response(self):
        scenarios = list(self.ledgers(failures=True))
        self.assertEqual(len(scenarios), 5)
        for scenario, requests in scenarios:
            self.assertTrue(scenario["expected_rejection"])
            self.assertFalse(requests[-1]["checked"])
            self.assertIn("error", requests[-1])
            self.assertNotIn("local_response_sha256", requests[-1])

    def test_response_format_retries_keep_same_review_candidate(self):
        retries = [r for _, rs in self.ledgers() for r in rs if r.get("response_contract_retry")]
        self.assertEqual({r["role"] for r in retries}, {"validator", "vocabulary_matcher"})
        self.assertTrue(all(r.get("candidate_sha256") for r in retries))

    def test_no_live_calls_or_secret_loading_and_no_source_mutation(self):
        self.assertEqual(self.summary["api_calls"], 0)
        self.assertFalse(self.summary["environment_file_read"])
        self.assertTrue(self.summary["protected_inputs_unchanged"])


if __name__ == "__main__":
    unittest.main()
