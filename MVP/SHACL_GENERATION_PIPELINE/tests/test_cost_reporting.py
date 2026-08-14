from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.reporting.costs import build_cost_payload


class CostReportingTests(unittest.TestCase):
    def test_counts_completed_calls_once_and_prices_exact_recorded_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            run = root / "runs" / "RUN-TEST"
            run.mkdir(parents=True)
            events = [
                {"event_type": "run_started", "timestamp_utc": "2026-01-01T00:00:00Z", "session_id": "S", "run_id": "RUN-TEST", "requirement_id": "REQ", "pipeline_version": "test"},
                {"event_type": "api_attempt_finished", "timestamp_utc": "2026-01-01T00:00:01Z", "session_id": "S", "run_id": "RUN-TEST", "requirement_id": "REQ", "model": "gpt-5.6-sol-2026-07-09"},
                {"event_type": "api_call_completed", "timestamp_utc": "2026-01-01T00:00:02Z", "session_id": "S", "run_id": "RUN-TEST", "requirement_id": "REQ", "role": "generator", "model": "gpt-5.6-sol-2026-07-09", "input_tokens": 1_000_000, "output_tokens": 100_000, "total_tokens": 1_100_000, "response_id": "resp"},
                {"event_type": "run_finished", "timestamp_utc": "2026-01-01T00:00:03Z", "session_id": "S", "run_id": "RUN-TEST", "requirement_id": "REQ", "status": "GENERATION_ACCEPTED", "accepted": True},
            ]
            (run / "events.jsonl").write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")
            payload, summary = build_cost_payload(PipelineConfig.load(), root)
            self.assertEqual(summary.calls, 1)
            self.assertEqual(summary.total_tokens, 1_100_000)
            self.assertAlmostEqual(summary.estimated_usd, 8.0)
            self.assertEqual(payload["run_rows"][0][14], 8.0)

    def test_unknown_model_is_flagged_and_not_silently_priced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            run = root / "runs" / "RUN-UNKNOWN"
            run.mkdir(parents=True)
            event = {"event_type": "api_call_completed", "timestamp_utc": "2026-01-01T00:00:00Z", "session_id": "S", "run_id": "RUN-UNKNOWN", "requirement_id": "REQ", "role": "validator", "model": "unknown-model", "input_tokens": 5, "output_tokens": 2, "total_tokens": 7}
            (run / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
            _payload, summary = build_cost_payload(PipelineConfig.load(), root)
            self.assertEqual(summary.unknown_pricing_calls, 1)
            self.assertEqual(summary.estimated_usd, 0.0)


if __name__ == "__main__":
    unittest.main()
