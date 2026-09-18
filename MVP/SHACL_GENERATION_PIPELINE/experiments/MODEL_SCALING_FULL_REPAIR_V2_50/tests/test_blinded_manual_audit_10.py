from __future__ import annotations

import importlib.util
import json
import unittest
from collections import Counter
from pathlib import Path


EXPERIMENT = Path(__file__).resolve().parents[1]
SCRIPT = EXPERIMENT / "scripts/build_blinded_manual_audit_10.py"
SPEC = importlib.util.spec_from_file_location("build_blinded_manual_audit_10", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class BlindedAuditPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sample = json.loads((EXPERIMENT / "MANIFESTS/sample_50.json").read_text(encoding="utf-8"))
        cls.selected = MODULE.select_requirements(cls.sample["records"])

    def test_selection_is_deterministic_and_metadata_only(self) -> None:
        again = MODULE.select_requirements(list(reversed(self.sample["records"])))
        self.assertEqual([r["requirement_id"] for r in self.selected], [r["requirement_id"] for r in again])
        self.assertEqual(
            [r["requirement_id"] for r in self.selected],
            ["I2-031", "TRF-006", "IMO-112", "IMO26-014", "I2-051", "TRF-059", "IMO-079", "I2-043", "TRF-123", "TRF-025"],
        )

    def test_required_splits(self) -> None:
        self.assertEqual(Counter(r["verification_mode"] for r in self.selected), Counter({"DIRECT_STATIC": 4, "DIRECT_CALCULATION": 3, "COMPLEX_READINESS": 3}))
        self.assertEqual(Counter(r["source_family"] for r in self.selected), Counter({"TRAFICOM": 4, "I2": 3, "IMO": 2, "IMO26": 1}))

    def test_selected_list_hash_is_locked(self) -> None:
        ids = [r["requirement_id"] for r in self.selected]
        self.assertEqual(MODULE.selected_list_hash(ids), "cd52efebf4a2237e04f6e147561e76d910524a0be391a265629915bb3ef63f14")

    def test_blinding_is_per_requirement_and_complete(self) -> None:
        first = MODULE.blind_assignments("I2-031")
        second = MODULE.blind_assignments("TRF-006")
        self.assertEqual({r["opaque_id"] for r in first}, {f"A{i:02d}" for i in range(1, 9)})
        self.assertEqual(len({(r["model_key"], r["evaluation_mode"]) for r in first}), 8)
        self.assertNotEqual([(r["model_key"], r["evaluation_mode"]) for r in first], [(r["model_key"], r["evaluation_mode"]) for r in second])


if __name__ == "__main__":
    unittest.main()
