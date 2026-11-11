from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class EventLogger:
    def __init__(
        self,
        run_directory: Path,
        session_id: str,
        run_id: str,
        requirement_id: str,
        *,
        live_progress: bool = False,
    ) -> None:
        self.run_directory = run_directory.resolve()
        self.run_directory.mkdir(parents=True, exist_ok=False)
        self.events_path = self.run_directory / "events.jsonl"
        self.session_id = session_id
        self.run_id = run_id
        self.requirement_id = requirement_id
        self.live_progress = live_progress
        self._sequence = 0
        self._lock = Lock()

    @staticmethod
    def _progress_message(event: dict[str, Any]) -> str | None:
        event_type = event["event_type"]
        requirement = event["requirement_id"]
        prefix = f"[{event['timestamp_utc']}] [{requirement}]"
        if event_type == "run_started":
            return f"{prefix} START run={event['run_id']} category={event.get('requirement_category', '')}"
        if event_type == "api_attempt_started":
            return (
                f"{prefix} API START role={event.get('role')} model={event.get('model')} "
                f"transport_attempt={event.get('transport_attempt')}"
            )
        if event_type == "api_attempt_finished":
            return (
                f"{prefix} API END role={event.get('role')} status={event.get('status')} "
                f"elapsed_ms={event.get('elapsed_ms')} retrying={event.get('retrying')}"
            )
        if event_type == "api_call_completed":
            return (
                f"{prefix} API USAGE role={event.get('role')} elapsed_ms={event.get('elapsed_ms')} "
                f"input_tokens={event.get('input_tokens', '')} output_tokens={event.get('output_tokens', '')}"
            )
        if event_type == "api_retry_wait":
            return (
                f"{prefix} RETRY role={event.get('role')} cycle={event.get('retry_cycle')} "
                f"wait_seconds={event.get('delay_seconds')}"
            )
        if event_type == "api_operator_intervention":
            return f"{prefix} ATTENTION {event.get('message', '')}"
        if event_type == "validation_completed":
            error_count = len(event.get("errors") or [])
            warning_count = len(event.get("warnings") or [])
            return (
                f"{prefix} STATIC VALIDATION iteration={event.get('iteration')} valid={event.get('valid')} "
                f"errors={error_count} warnings={warning_count}"
            )
        if event_type == "response_contract_error":
            return (
                f"{prefix} CONTRACT RETRY role={event.get('role')} "
                f"attempt={event.get('contract_attempt')} retrying={event.get('retrying')}"
            )
        if event_type == "matcher_search":
            return (
                f"{prefix} MATCHER SEARCH iteration={event.get('iteration')} "
                f"candidates={event.get('candidate_count')}"
            )
        if event_type == "matcher_decision":
            return (
                f"{prefix} MATCHER DECISION iteration={event.get('iteration')} "
                f"found={event.get('match_found')} term={event.get('canonical_local_name', '')}"
            )
        if event_type == "iteration_completed":
            return (
                f"{prefix} ITERATION {event.get('iteration')} decision={event.get('decision')} "
                f"static_valid={event.get('static_valid')} matcher={event.get('matcher_activated')}"
            )
        if event_type == "unresolved_issue":
            return (
                f"{prefix} UNRESOLVED iteration={event.get('iteration')} "
                f"type={event.get('issue_type')}"
            )
        if event_type == "run_finished":
            return (
                f"{prefix} FINISH status={event.get('status')} accepted={event.get('accepted')} "
                f"attempts={event.get('attempts')}"
            )
        if event_type == "reporting_completed":
            return f"{prefix} TRACKER READY file={event.get('workbook')}"
        if event_type == "reporting_warning":
            return f"{prefix} TRACKER WARNING {event.get('warning', '')}"
        return None

    def emit(self, event_type: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        body = dict(payload or {})
        body.update(kwargs)
        with self._lock:
            self._sequence += 1
            event = {
                "event_id": f"EVT-{self._sequence:06d}",
                "timestamp_utc": utc_now(),
                "session_id": self.session_id,
                "run_id": self.run_id,
                "requirement_id": self.requirement_id,
                "event_type": event_type,
                **body,
            }
            line = json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n"
            with self.events_path.open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
            if self.live_progress:
                message = self._progress_message(event)
                if message:
                    print(message, file=sys.stderr, flush=True)
        return event

    def write_artifact(
        self,
        relative_path: str | Path,
        content: str | bytes,
        *,
        artifact_type: str,
        iteration: int | None = None,
    ) -> Path:
        target = (self.run_directory / relative_path).resolve()
        if self.run_directory not in target.parents:
            raise ValueError("Artifact path escapes the run directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode("utf-8") if isinstance(content, str) else content
        target.write_bytes(data)
        self.emit(
            "artifact_written",
            artifact_type=artifact_type,
            artifact_path=str(target.relative_to(self.run_directory)),
            sha256=sha256_bytes(data),
            bytes=len(data),
            iteration=iteration,
        )
        return target

    def read_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        return [json.loads(line) for line in self.events_path.read_text(encoding="utf-8").splitlines() if line]
