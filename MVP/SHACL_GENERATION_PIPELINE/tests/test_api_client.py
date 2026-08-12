from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import requests

from nltl_pipeline.api.client import AaltoResponsesClient
from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.errors import ApiError


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "", headers: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = headers or {}

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, outcomes: list[FakeResponse | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def post(self, *_args, **_kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class ApiClientTests(unittest.TestCase):
    def make_client(self, root: Path, outcomes: list[FakeResponse | Exception]):
        env_file = root / "test.env"
        env_file.write_text(
            "AALTO_API_KEY=test-only-key\n"
            "AALTO_RESPONSES_BASE_URL=https://example.invalid/responses\n"
            "AALTO_MODEL=test-model\n"
            "AALTO_TIMEOUT=1\n",
            encoding="utf-8",
        )
        base = PipelineConfig.load()
        raw = copy.deepcopy(base.raw)
        raw["environment_file"] = str(env_file)
        raw["models"] = {key: "test-model" for key in raw["models"]}
        raw["api"].update({
            "requests_per_minute": 10000,
            "minimum_interval_seconds": 0,
            "initial_backoff_seconds": 0,
            "maximum_backoff_seconds": 0,
            "auth_retry_seconds": 0,
            "persistent_transient_retries": False,
        })
        events = []
        config = PipelineConfig(raw=raw, config_path=base.config_path)
        client = AaltoResponsesClient(
            config,
            telemetry=lambda event, payload: events.append((event, payload)),
            session=FakeSession(outcomes),
            sleep=lambda _seconds: None,
        )
        return client, events

    @staticmethod
    def ok_response(text: str = "done") -> FakeResponse:
        return FakeResponse(200, {
            "id": "resp-test",
            "model": "test-model",
            "output": [{"content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
        })

    def test_retries_429_inside_same_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            client, events = self.make_client(
                Path(temp_name),
                [FakeResponse(429, text="rate", headers={"Retry-After": "0"}), self.ok_response()],
            )
            result = client.call("generator", "system", "user")
            self.assertEqual(result.text, "done")
            self.assertEqual(result.transport_attempts, 2)
            self.assertTrue(any(event == "api_retry_wait" for event, _payload in events))

    def test_retries_network_failure_inside_same_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            client, _events = self.make_client(
                Path(temp_name),
                [requests.exceptions.ConnectionError("vpn unavailable"), self.ok_response("recovered")],
            )
            result = client.call("validator", "system", "user")
            self.assertEqual(result.text, "recovered")
            self.assertEqual(result.transport_attempts, 2)

    def test_tries_second_aalto_auth_header(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            client, _events = self.make_client(
                Path(temp_name),
                [FakeResponse(403, text="forbidden"), self.ok_response("second-header")],
            )
            result = client.call("vocabulary_matcher", "system", "user")
            self.assertEqual(result.text, "second-header")
            self.assertEqual(result.transport_attempts, 2)

    def test_non_retryable_contract_error_stops(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            client, _events = self.make_client(Path(temp_name), [FakeResponse(400, text="invalid payload")])
            with self.assertRaises(ApiError):
                client.call("generator", "system", "user")


if __name__ == "__main__":
    unittest.main()

