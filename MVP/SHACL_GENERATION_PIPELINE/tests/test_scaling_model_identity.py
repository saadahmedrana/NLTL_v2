from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts"
sys.path.insert(0, str(SCRIPTS))
from experiment import verify_gateway_model_identity  # noqa: E402


class ScalingModelIdentityTests(unittest.TestCase):
    def test_approved_gemini_identities_are_canonical_aliases(self) -> None:
        requested = "gemini-3.5-flash"
        self.assertEqual(requested, verify_gateway_model_identity("gemini", requested, requested))
        self.assertEqual(
            requested,
            verify_gateway_model_identity("gemini", requested, "google/gemini-3.5-flash"),
        )

    def test_other_gemini_identities_are_rejected(self) -> None:
        for returned in ("google/gemini-3.0-flash", "other/gemini-3.5-flash"):
            with self.subTest(returned=returned), self.assertRaises(RuntimeError):
                verify_gateway_model_identity("gemini", "gemini-3.5-flash", returned)

    def test_sol_remains_exact_match_only(self) -> None:
        requested = "gpt-5.6-sol-2026-07-09"
        self.assertEqual(requested, verify_gateway_model_identity("sol", requested, requested))
        with self.assertRaises(RuntimeError):
            verify_gateway_model_identity("sol", requested, f"openai/{requested}")

    def test_gpt_oss_remains_exact_match_only(self) -> None:
        requested = "gpt-oss-120b"
        self.assertEqual(requested, verify_gateway_model_identity("gpt_oss", requested, requested))
        with self.assertRaises(RuntimeError):
            verify_gateway_model_identity("gpt_oss", requested, f"openai/{requested}")

    def test_requested_identity_must_remain_locked(self) -> None:
        with self.assertRaises(RuntimeError):
            verify_gateway_model_identity("gemini", "google/gemini-3.5-flash", "google/gemini-3.5-flash")


if __name__ == "__main__":
    unittest.main()
