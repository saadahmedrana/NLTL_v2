from __future__ import annotations

import unittest

from nltl_pipeline.cli import validate_batch_queue


class BatchQueueValidationTests(unittest.TestCase):
    def test_matching_development_vocabulary_is_accepted(self) -> None:
        requirements, repetitions = validate_batch_queue(
            {
                "development_vocabulary_id": "VOCAB-R6",
                "requirements": ["TRF-011", "TRF-012"],
                "repetitions": 1,
            },
            "VOCAB-R6",
        )
        self.assertEqual(requirements, ["TRF-011", "TRF-012"])
        self.assertEqual(repetitions, 1)

    def test_mismatched_development_vocabulary_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_batch_queue(
                {
                    "development_vocabulary_id": "VOCAB-R5",
                    "requirements": ["TRF-011"],
                },
                "VOCAB-R6",
            )

    def test_duplicate_requirement_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_batch_queue(
                {"requirements": ["TRF-011", "TRF-011"]},
                "VOCAB-R6",
            )


if __name__ == "__main__":
    unittest.main()
