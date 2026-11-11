from __future__ import annotations

import json
import random
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable

import requests
from dotenv import dotenv_values

from ..config import PipelineConfig
from ..errors import ApiError, ConfigurationError
from ..models import ApiCallResult


TelemetryCallback = Callable[[str, dict[str, Any]], None]


class SlidingWindowRateLimiter:
    """Thread-safe shared request limiter with a small anti-burst interval."""

    def __init__(self, requests_per_minute: int, minimum_interval_seconds: float = 0.05) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        self.limit = requests_per_minute
        self.minimum_interval = max(0.0, minimum_interval_seconds)
        self._timestamps: deque[float] = deque()
        self._last_request = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> float:
        total_wait = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= 60.0:
                    self._timestamps.popleft()
                interval_wait = max(0.0, self.minimum_interval - (now - self._last_request))
                window_wait = 0.0
                if len(self._timestamps) >= self.limit:
                    window_wait = max(0.0, 60.0 - (now - self._timestamps[0]))
                wait_for = max(interval_wait, window_wait)
                if wait_for <= 0:
                    stamp = time.monotonic()
                    self._timestamps.append(stamp)
                    self._last_request = stamp
                    return total_wait
            time.sleep(min(wait_for, 1.0))
            total_wait += min(wait_for, 1.0)


class AaltoResponsesClient:
    """Minimal Responses API client for the Aalto gateway.

    The environment file is read only when this class is instantiated for a
    live call. It is never written or logged.
    """

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

        env_path = config.environment_file
        if not env_path.is_file():
            raise ConfigurationError(
                f"Environment file is not ready: {env_path}. The pipeline did not create or modify it."
            )
        values = dotenv_values(env_path)
        self.api_key = str(values.get("AALTO_API_KEY") or "").strip().strip('"').strip("'")
        self.base_url = str(values.get("AALTO_RESPONSES_BASE_URL") or "").strip().strip('"').strip("'")
        try:
            self.timeout = int(str(values.get("AALTO_TIMEOUT") or "180").strip())
        except ValueError as exc:
            raise ConfigurationError("AALTO_TIMEOUT must be an integer number of seconds") from exc
        if not self.api_key:
            raise ConfigurationError(f"AALTO_API_KEY is empty in {env_path}")
        if not self.base_url:
            raise ConfigurationError(f"AALTO_RESPONSES_BASE_URL is empty in {env_path}")

        api = config.raw["api"]
        self.header_order = [str(item) for item in api["auth_header_order"]]
        self.initial_backoff = float(api["initial_backoff_seconds"])
        self.maximum_backoff = float(api["maximum_backoff_seconds"])
        self.auth_retry_seconds = float(api["auth_retry_seconds"])
        self.persistent = bool(api["persistent_transient_retries"])
        self.rate_limiter = SlidingWindowRateLimiter(
            int(api["requests_per_minute"]),
            float(api.get("minimum_interval_seconds", 0.05)),
        )

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        direct = data.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        texts: list[str] = []
        for item in data.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text)
        if not texts:
            raise ApiError("Responses API returned no extractable output text")
        return "\n".join(texts)

    @staticmethod
    def _retry_after(response: requests.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    @staticmethod
    def _looks_like_gateway_or_vpn_failure(response: requests.Response) -> bool:
        text = (response.text or "").lower()
        markers = ("vpn", "gateway", "apim", "subscription", "forbidden", "access denied")
        return response.status_code in {401, 403} and any(marker in text for marker in markers)

    def call(self, role: str, developer_prompt: str, user_prompt: str) -> ApiCallResult:
        model = self.config.model(role)
        payload = {
            "model": model,
            "input": [
                {"role": "developer", "content": [{"type": "input_text", "text": developer_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
        }
        output_limits = self.config.raw.get("api", {}).get("max_output_tokens", {})
        configured_limit = output_limits.get(role) if isinstance(output_limits, dict) else None
        if configured_limit is not None:
            payload["max_output_tokens"] = int(configured_limit)
        call_started = time.monotonic()
        transport_attempt = 0
        retry_cycle = 0

        while True:
            retry_cycle += 1
            backoff = min(self.maximum_backoff, self.initial_backoff * (2 ** max(0, retry_cycle - 1)))
            last_auth_response: requests.Response | None = None

            for header_name in self.header_order:
                transport_attempt += 1
                rate_wait = self.rate_limiter.acquire()
                started = time.monotonic()
                self.telemetry("api_attempt_started", {
                    "role": role,
                    "model": model,
                    "transport_attempt": transport_attempt,
                    "auth_header_name": header_name,
                    "rate_limit_wait_ms": round(rate_wait * 1000, 3),
                })
                try:
                    response = self.session.post(
                        self.base_url,
                        headers={"Content-Type": "application/json", header_name: self.api_key},
                        json=payload,
                        timeout=self.timeout,
                    )
                except (
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.ChunkedEncodingError,
                ) as exc:
                    elapsed = (time.monotonic() - started) * 1000
                    self.telemetry("api_attempt_finished", {
                        "role": role,
                        "model": model,
                        "transport_attempt": transport_attempt,
                        "status": "NETWORK_ERROR",
                        "elapsed_ms": round(elapsed, 3),
                        "error_type": type(exc).__name__,
                        "auth_header_name": header_name,
                        "rate_limit_wait_ms": round(rate_wait * 1000, 3),
                        "retrying": True,
                    })
                    break

                elapsed = (time.monotonic() - started) * 1000
                self.telemetry("api_attempt_finished", {
                    "role": role,
                    "model": model,
                    "transport_attempt": transport_attempt,
                    "status": response.status_code,
                    "elapsed_ms": round(elapsed, 3),
                    "auth_header_name": header_name,
                    "rate_limit_wait_ms": round(rate_wait * 1000, 3),
                    "retrying": response.status_code != 200,
                })

                if response.status_code == 200:
                    try:
                        data = response.json()
                    except ValueError as exc:
                        raise ApiError("Responses API returned HTTP 200 with invalid JSON") from exc
                    text = self._extract_text(data)
                    return ApiCallResult(
                        text=text,
                        response_id=str(data.get("id") or ""),
                        model=str(data.get("model") or model),
                        usage=dict(data.get("usage") or {}),
                        transport_attempts=transport_attempt,
                        elapsed_ms=round((time.monotonic() - call_started) * 1000, 3),
                    )

                if response.status_code in {401, 403}:
                    last_auth_response = response
                    continue
                if response.status_code in self.RETRYABLE_STATUS:
                    retry_after = self._retry_after(response)
                    backoff = retry_after if retry_after is not None else backoff
                    break
                body = (response.text or "")[:1000]
                raise ApiError(f"Non-retryable Aalto API error {response.status_code}: {body}")
            else:
                # Every configured header returned an authentication response.
                if last_auth_response is not None and not self._looks_like_gateway_or_vpn_failure(last_auth_response):
                    # Aalto authentication can still depend on VPN. Keep the run alive as requested,
                    # but record that operator action is likely required.
                    self.telemetry("api_operator_intervention", {
                        "role": role,
                        "status": last_auth_response.status_code,
                        "message": "Authentication/gateway response persisted; check key and Aalto VPN.",
                    })
                backoff = self.auth_retry_seconds

            delay = max(0.0, backoff) + random.uniform(0.0, min(1.0, max(0.0, backoff) * 0.1))
            self.telemetry("api_retry_wait", {
                "role": role,
                "retry_cycle": retry_cycle,
                "delay_seconds": round(delay, 3),
                "persistent": self.persistent,
            })
            if not self.persistent and retry_cycle >= 8:
                raise ApiError(f"Transient Aalto API failure after {retry_cycle} retry cycles")
            self.sleep(delay)


class ScriptedResponsesClient:
    """Offline test client. It never reads the environment file or uses HTTP."""

    def __init__(
        self,
        responses: dict[str, list[str]],
        telemetry: TelemetryCallback | None = None,
    ) -> None:
        self.responses = {key: list(values) for key, values in responses.items()}
        self.telemetry = telemetry or (lambda _event, _payload: None)
        self.calls: list[dict[str, str]] = []

    def call(self, role: str, developer_prompt: str, user_prompt: str) -> ApiCallResult:
        started = time.monotonic()
        queue = self.responses.get(role, [])
        if not queue:
            raise ApiError(f"Offline scripted client has no remaining {role} response")
        text = queue.pop(0)
        self.calls.append({"role": role, "developer": developer_prompt, "user": user_prompt})
        elapsed = (time.monotonic() - started) * 1000
        self.telemetry("api_attempt_started", {
            "role": role,
            "model": "offline-scripted",
            "transport_attempt": 1,
            "auth_header_name": "NONE",
            "rate_limit_wait_ms": 0.0,
        })
        self.telemetry("api_attempt_finished", {
            "role": role,
            "model": "offline-scripted",
            "transport_attempt": 1,
            "status": "OFFLINE",
            "elapsed_ms": round(elapsed, 3),
            "retrying": False,
        })
        return ApiCallResult(
            text=text,
            response_id=f"offline-{role}-{len(self.calls)}",
            model="offline-scripted",
            usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            transport_attempts=1,
            elapsed_ms=round(elapsed, 3),
        )
