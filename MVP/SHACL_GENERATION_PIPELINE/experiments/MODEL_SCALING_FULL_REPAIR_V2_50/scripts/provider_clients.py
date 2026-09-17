"""Experiment-local Aalto clients for Responses and Chat Completions.

Kept local because the repository's R11/R13 API client is hash-locked.
"""
from __future__ import annotations

import os
import random
import time
from typing import Any, Callable

import requests
from dotenv import dotenv_values

from nltl_pipeline.api.client import SlidingWindowRateLimiter
from nltl_pipeline.config import PipelineConfig
from nltl_pipeline.errors import ApiError, ConfigurationError
from nltl_pipeline.models import ApiCallResult

TelemetryCallback = Callable[[str, dict[str, Any]], None]


class AaltoProviderClient:
    RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        config: PipelineConfig,
        *,
        telemetry: TelemetryCallback | None = None,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.telemetry = telemetry or (lambda _event, _payload: None)
        self.session = session or requests.Session()
        self.sleep = sleep
        api = config.raw["api"]
        self.endpoint_type = str(api["endpoint_type"])
        if self.endpoint_type not in {"responses", "chat_completions"}:
            raise ConfigurationError(f"Unsupported Aalto endpoint type: {self.endpoint_type}")
        values = dotenv_values(config.environment_file) if config.environment_file.is_file() else {}
        key_name = str(api["api_key_env"])
        endpoint_name = str(api["endpoint_env"])
        self.api_key = str(os.environ.get(key_name) or values.get(key_name) or "").strip().strip('"').strip("'")
        self.base_url = str(os.environ.get(endpoint_name) or values.get(endpoint_name) or "").strip().strip('"').strip("'")
        timeout_raw = os.environ.get("AALTO_TIMEOUT") or values.get("AALTO_TIMEOUT") or "180"
        try:
            self.timeout = int(str(timeout_raw).strip())
        except ValueError as exc:
            raise ConfigurationError("AALTO_TIMEOUT must be an integer number of seconds") from exc
        if not self.api_key:
            raise ConfigurationError(f"{key_name} is empty; export it or define it in {config.environment_file}")
        if not self.base_url:
            raise ConfigurationError(f"{endpoint_name} is empty; export it or define it in {config.environment_file}")
        self.initial_backoff = float(api["initial_backoff_seconds"])
        self.maximum_backoff = float(api["maximum_backoff_seconds"])
        self.auth_retry_seconds = float(api["auth_retry_seconds"])
        self.persistent = bool(api["persistent_transient_retries"])
        self.max_retry_cycles = int(api.get("max_retry_cycles", 8))
        self.rate_limiter = SlidingWindowRateLimiter(
            int(api["requests_per_minute"]), float(api.get("minimum_interval_seconds", 0.05))
        )

    @staticmethod
    def _responses_text(data: dict[str, Any]) -> str:
        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"]
        texts = [
            content["text"]
            for item in data.get("output", []) if isinstance(item, dict)
            for content in item.get("content", []) if isinstance(content, dict)
            if isinstance(content.get("text"), str) and content["text"].strip()
        ]
        if not texts:
            raise ApiError("Responses API returned no extractable output text")
        return "\n".join(texts)

    @staticmethod
    def _chat_text(data: dict[str, Any], *, http_status: int | None = None) -> str:
        choices = data.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None

        def text_values(value: Any) -> list[str]:
            if isinstance(value, str):
                return [value] if value.strip() else []
            if isinstance(value, list):
                return [text for item in value for text in text_values(item)]
            if isinstance(value, dict):
                texts: list[str] = []
                # OpenAI-compatible gateways use several equivalent text-part
                # spellings. Only traverse known text-bearing fields so metadata
                # such as part type or IDs can never become response content.
                for key in ("text", "output_text", "content", "value", "parts"):
                    if key in value:
                        texts.extend(text_values(value[key]))
                return texts
            return []

        texts = text_values(content)
        if texts:
            return "\n".join(texts)
        diagnostic = {
            "http_status": http_status,
            "top_level_response_keys": sorted(str(key) for key in data),
            "choice_keys": sorted(str(key) for key in choice) if isinstance(choice, dict) else [],
            "message_keys": sorted(str(key) for key in message) if isinstance(message, dict) else [],
            "content_type": type(content).__name__,
            "finish_reason": choice.get("finish_reason") if isinstance(choice, dict) else None,
        }
        raise ApiError(f"Chat Completions API returned no extractable message content; diagnostic={diagnostic}")

    def _payload(self, role: str, developer_prompt: str, user_prompt: str) -> dict[str, Any]:
        model = self.config.model(role)
        if self.endpoint_type == "responses":
            payload: dict[str, Any] = {
                "model": model,
                "input": [
                    {"role": "developer", "content": [{"type": "input_text", "text": developer_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
                ],
            }
        else:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": developer_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        limits = self.config.raw["api"].get("max_output_tokens", {})
        if role in limits:
            parameter = "max_output_tokens" if self.endpoint_type == "responses" else str(
                self.config.raw["api"].get("chat_max_tokens_parameter", "max_tokens")
            )
            configured_limit = int(limits[role])
            # The connectivity config requests only "OK" but Gemini-compatible
            # gateways may consume a small allowance before emitting visible
            # content. Production limits are already much larger and unchanged.
            payload[parameter] = max(configured_limit, 128) if self.endpoint_type == "chat_completions" else configured_limit
        return payload

    def call(self, role: str, developer_prompt: str, user_prompt: str) -> ApiCallResult:
        model = self.config.model(role)
        payload = self._payload(role, developer_prompt, user_prompt)
        call_started = time.monotonic()
        transport_attempt = 0
        retry_cycle = 0
        while True:
            retry_cycle += 1
            transport_attempt += 1
            wait_ms = self.rate_limiter.acquire() * 1000
            started = time.monotonic()
            self.telemetry("api_attempt_started", {
                "role": role, "model": model, "transport_attempt": transport_attempt,
                "auth_header_name": "Authorization", "endpoint_type": self.endpoint_type,
                "rate_limit_wait_ms": round(wait_ms, 3),
            })
            try:
                response = self.session.post(
                    self.base_url,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                    timeout=self.timeout,
                )
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as exc:
                self.telemetry("api_attempt_finished", {
                    "role": role, "model": model, "transport_attempt": transport_attempt,
                    "status": "NETWORK_ERROR", "error_type": type(exc).__name__,
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
                    "auth_header_name": "Authorization", "endpoint_type": self.endpoint_type,
                    "rate_limit_wait_ms": round(wait_ms, 3), "retrying": True,
                })
                response = None
            if response is not None:
                self.telemetry("api_attempt_finished", {
                    "role": role, "model": model, "transport_attempt": transport_attempt,
                    "status": response.status_code,
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
                    "auth_header_name": "Authorization", "endpoint_type": self.endpoint_type,
                    "rate_limit_wait_ms": round(wait_ms, 3), "retrying": response.status_code != 200,
                })
                if response.status_code == 200:
                    try:
                        data = response.json()
                    except ValueError as exc:
                        raise ApiError("Aalto API returned HTTP 200 with invalid JSON") from exc
                    usage = dict(data.get("usage") or {})
                    if self.endpoint_type == "chat_completions":
                        if usage.get("prompt_tokens") is not None:
                            usage.setdefault("input_tokens", usage["prompt_tokens"])
                        if usage.get("completion_tokens") is not None:
                            usage.setdefault("output_tokens", usage["completion_tokens"])
                    text = (
                        self._responses_text(data)
                        if self.endpoint_type == "responses"
                        else self._chat_text(data, http_status=response.status_code)
                    )
                    return ApiCallResult(
                        text=text, response_id=str(data.get("id") or ""), model=str(data.get("model") or model),
                        usage=usage, transport_attempts=transport_attempt,
                        elapsed_ms=round((time.monotonic() - call_started) * 1000, 3),
                    )
                if response.status_code not in self.RETRYABLE_STATUS | {401, 403}:
                    raise ApiError(f"Non-retryable Aalto API error {response.status_code}: {(response.text or '')[:1000]}")
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else (
                    self.auth_retry_seconds if response.status_code in {401, 403} else
                    min(self.maximum_backoff, self.initial_backoff * (2 ** max(0, retry_cycle - 1)))
                )
            else:
                delay = min(self.maximum_backoff, self.initial_backoff * (2 ** max(0, retry_cycle - 1)))
            delay = max(0.0, delay) + random.uniform(0.0, min(1.0, max(0.0, delay) * 0.1))
            self.telemetry("api_retry_wait", {
                "role": role, "retry_cycle": retry_cycle, "delay_seconds": round(delay, 3),
                "persistent": self.persistent, "endpoint_type": self.endpoint_type,
            })
            if not self.persistent and retry_cycle >= self.max_retry_cycles:
                raise ApiError(f"Transient Aalto API failure after {retry_cycle} retry cycles")
            self.sleep(delay)


def client_for_config(config: PipelineConfig, **kwargs: Any) -> AaltoProviderClient:
    return AaltoProviderClient(config, **kwargs)
