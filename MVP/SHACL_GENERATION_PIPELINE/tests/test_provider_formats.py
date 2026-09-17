from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.errors import ApiError

SCRIPTS = Path(__file__).resolve().parents[1] / "experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts"
sys.path.insert(0, str(SCRIPTS))
from provider_clients import AaltoProviderClient  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.status_code = 200
        self._payload = payload
        self.text = ""
        self.headers: dict[str, str] = {}

    def json(self) -> dict:
        return self._payload


class CapturingSession:
    def __init__(self, payload: dict) -> None:
        self.response = FakeResponse(payload)
        self.calls: list[dict] = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


class ProviderFormatTests(unittest.TestCase):
    def make_config(self, root: Path, endpoint_type: str) -> PipelineConfig:
        env = root / "test.env"
        env.write_text(
            "AALTO_AI_API_KEY=test-only-key\n"
            "AALTO_AI_RESPONSES_URL=https://example.invalid/v1/responses\n"
            "AALTO_AI_CHAT_COMPLETIONS_URL=https://example.invalid/v1/chat/completions\n",
            encoding="utf-8",
        )
        base = PipelineConfig.load()
        raw = copy.deepcopy(base.raw)
        raw["environment_file"] = str(env)
        raw["models"] = {key: "exact-test-model" for key in raw["models"]}
        raw["api"].update({
            "endpoint_type": endpoint_type,
            "api_key_env": "AALTO_AI_API_KEY",
            "endpoint_env": (
                "AALTO_AI_RESPONSES_URL" if endpoint_type == "responses"
                else "AALTO_AI_CHAT_COMPLETIONS_URL"
            ),
            "auth_scheme": "bearer",
            "requests_per_minute": 10000,
            "minimum_interval_seconds": 0,
            "persistent_transient_retries": False,
        })
        return PipelineConfig(raw=raw, config_path=base.config_path)

    def test_responses_format_and_usage(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            session = CapturingSession({
                "id": "resp-1",
                "model": "exact-test-model",
                "output": [{"content": [{"type": "output_text", "text": "response text"}]}],
                "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            })
            client = AaltoProviderClient(
                self.make_config(Path(name), "responses"), session=session, sleep=lambda _seconds: None
            )
            result = client.call("generator", "developer", "user")
            self.assertEqual(result.text, "response text")
            self.assertEqual(client.endpoint_type, "responses")
            self.assertEqual(result.usage["input_tokens"], 11)
            call = session.calls[0]
            self.assertEqual(call["headers"]["Authorization"], "Bearer test-only-key")
            self.assertEqual(call["json"]["input"][0]["role"], "developer")
            self.assertNotIn("messages", call["json"])

    def test_chat_completions_format_and_usage(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            session = CapturingSession({
                "id": "chat-1",
                "model": "exact-test-model",
                "choices": [{"message": {"role": "assistant", "content": "chat text"}}],
                "usage": {"prompt_tokens": 13, "completion_tokens": 5, "total_tokens": 18},
            })
            client = AaltoProviderClient(
                self.make_config(Path(name), "chat_completions"), session=session, sleep=lambda _seconds: None
            )
            result = client.call("validator", "system", "user")
            self.assertEqual(result.text, "chat text")
            self.assertEqual(client.endpoint_type, "chat_completions")
            self.assertEqual(result.usage["input_tokens"], 13)
            self.assertEqual(result.usage["output_tokens"], 5)
            call = session.calls[0]
            self.assertEqual(call["headers"]["Authorization"], "Bearer test-only-key")
            self.assertEqual(call["json"]["messages"][0], {"role": "system", "content": "system"})
            self.assertNotIn("input", call["json"])

    def test_chat_completions_array_parts_and_compatible_text_fields(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            session = CapturingSession({
                "id": "chat-parts-1",
                "model": "exact-test-model",
                "choices": [{
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": {"value": "first"}},
                            {"type": "output_text", "output_text": "second"},
                            {"type": "text", "content": "third"},
                        ],
                    },
                }],
            })
            client = AaltoProviderClient(
                self.make_config(Path(name), "chat_completions"), session=session, sleep=lambda _seconds: None
            )
            result = client.call("generator", "system", "user")
            self.assertEqual(result.text, "first\nsecond\nthird")

    def test_chat_completions_empty_content_has_safe_diagnostics(self) -> None:
        payload = {
            "id": "chat-empty-1",
            "model": "exact-test-model",
            "choices": [{
                "index": 0,
                "finish_reason": "length",
                "message": {"role": "assistant", "content": []},
            }],
            "usage": {"prompt_tokens": 9, "completion_tokens": 0},
            "secret_material": "must-not-appear",
        }
        with self.assertRaises(ApiError) as caught:
            AaltoProviderClient._chat_text(payload, http_status=200)
        diagnostic = str(caught.exception)
        self.assertIn("'http_status': 200", diagnostic)
        self.assertIn("'finish_reason': 'length'", diagnostic)
        self.assertIn("'content_type': 'list'", diagnostic)
        self.assertIn("'secret_material'", diagnostic)  # key name only
        self.assertNotIn("must-not-appear", diagnostic)

    def test_chat_connectivity_limit_has_safe_minimum_without_changing_responses(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            chat_config = self.make_config(Path(name), "chat_completions")
            chat_config.raw["api"].setdefault("max_output_tokens", {})["generator"] = 16
            chat = AaltoProviderClient(chat_config, session=CapturingSession({}), sleep=lambda _seconds: None)
            self.assertEqual(chat._payload("generator", "system", "user")["max_tokens"], 128)

            responses_config = self.make_config(Path(name), "responses")
            responses_config.raw["api"].setdefault("max_output_tokens", {})["generator"] = 16
            responses = AaltoProviderClient(responses_config, session=CapturingSession({}), sleep=lambda _seconds: None)
            self.assertEqual(responses._payload("generator", "developer", "user")["max_output_tokens"], 16)


if __name__ == "__main__":
    unittest.main()
