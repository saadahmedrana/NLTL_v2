from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from nltl_pipeline.telemetry.events import EventLogger


class ProgressLoggingTests(unittest.TestCase):
    def test_selected_events_are_printed_without_payload_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            stream = io.StringIO()
            logger = EventLogger(
                Path(temp_name) / "run",
                "SESSION-TEST",
                "RUN-TEST",
                "REQ-TEST",
                live_progress=True,
            )
            with contextlib.redirect_stderr(stream):
                logger.emit("run_started", requirement_category="Static")
                logger.emit(
                    "api_attempt_started",
                    role="generator",
                    model="test-model",
                    transport_attempt=1,
                    secret_payload="must-not-print",
                )
                logger.emit("artifact_written", artifact_path="hidden.txt")
                logger.emit("run_finished", status="GENERATION_ACCEPTED", accepted=True, attempts=1)
            output = stream.getvalue()
            self.assertIn("[REQ-TEST] START", output)
            self.assertIn("API START role=generator", output)
            self.assertIn("FINISH status=GENERATION_ACCEPTED", output)
            self.assertNotIn("must-not-print", output)
            self.assertNotIn("hidden.txt", output)


if __name__ == "__main__":
    unittest.main()
