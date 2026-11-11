"""Offline request-boundary checks. This module never constructs a live client.

Candidate references come from the immediately preceding local response and
runner artifacts, independently of the candidate embedded by the prompt renderer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..api.client import ScriptedResponsesClient
from ..validation.shacl import extract_shacl
from ..validation.contracts import parse_matcher_decision, parse_validator_decision
from .repair import packet_sha256, static_issues


class RepairRequestIntegrityError(RuntimeError):
    pass


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require(condition: bool, explanation: str) -> None:
    if not condition:
        raise RepairRequestIntegrityError(explanation)


def check_previous_code(payload: dict[str, Any], field: str, expected: str,
                        expected_sha256: str) -> dict[str, Any]:
    """Fail closed on absence, staleness, whitespace changes or truncation."""
    actual = payload.get(field)
    require(isinstance(actual, str) and bool(actual.strip()), f"{field}: previous code absent")
    require(text_hash(expected) == expected_sha256, "Independent candidate reference hash is stale")
    require(actual == expected, f"{field}: previous code stale, changed or truncated")
    require(text_hash(actual) == expected_sha256, f"{field}: previous candidate hash mismatch")
    return dict(previous_candidate_present=True, previous_candidate_complete=True,
                previous_candidate_sha256=expected_sha256,
                embedded_candidate_sha256=text_hash(actual),
                previous_candidate_utf8_bytes=len(expected.encode("utf-8")))


class AuditedScriptedClient(ScriptedResponsesClient):
    """Run the real runner, audit complete requests, then return local canaries."""

    def __init__(self, responses: dict[str, list[str]], output: Path) -> None:
        super().__init__(responses)
        self.output = output
        self.requests: list[dict[str, Any]] = []
        self.latest_raw: str | None = None
        self.latest_response_version: int | None = None
        self.latest_validation: dict[str, Any] | None = None
        self.latest_syntax_diagnostics: dict[str, Any] | None = None

    def observe_validation(self, raw: str, turtle: str, report: Any) -> None:
        require(raw == self.latest_raw, "Validation is not for the immediately preceding response")
        self.latest_validation = dict(raw_sha256=text_hash(raw),
            candidate_sha256=text_hash(turtle) if turtle else None,
            response_version=self.latest_response_version, report=report.to_dict())

    def observe_syntax_diagnostics(self, raw: str, report: Any, diagnostics: dict[str, Any]) -> None:
        require(self.latest_validation is not None, "Syntax feedback has no validation source")
        require(text_hash(raw) == self.latest_validation["raw_sha256"], "Syntax feedback source is stale")
        require(report.to_dict() == self.latest_validation["report"], "Syntax feedback report is stale")
        self.latest_syntax_diagnostics = json.loads(json.dumps(diagnostics))

    def _run_directory(self) -> Path:
        runs = list((self.output / "runs").glob("RUN-*"))
        require(len(runs) == 1, "Audit scenario must have exactly one isolated runner directory")
        return runs[0]

    def _prompt_artifact(self, developer: str, user: str) -> Path:
        rendered = developer + "\n\n--- USER INPUT ---\n" + user
        matches = [p for p in self._run_directory().glob("artifacts/attempt_*/*prompt*.txt")
                   if p.read_text() == rendered]
        require(bool(matches), "Complete rendered request does not match a saved runner prompt")
        return max(matches, key=lambda p: (p.parent.name, p.name))

    def _previous_state(self, prompt: Path, expected_turtle: str) -> dict[str, Any]:
        iteration = int(prompt.parent.name.removeprefix("attempt_"))
        require(iteration > 1, "Normal candidate repair cannot be attempt one")
        previous = prompt.parent.parent / f"attempt_{iteration - 1:02d}"
        candidate = previous / "candidate_shape.ttl"
        require(candidate.is_file(), "Immediately preceding candidate artifact is absent")
        require(candidate.read_text() == expected_turtle, "Saved preceding candidate is stale")
        metadata = json.loads((previous / "attempt_metadata.json").read_text())
        require(metadata["candidate_sha256"] == text_hash(expected_turtle), "Preceding candidate metadata hash is stale")
        issues = json.loads((previous / "structured_current_issues.json").read_text())
        require(metadata["current_issue_packet_sha256"] == packet_sha256(issues), "Saved feedback packet hash mismatch")
        require(self.latest_validation is not None and self.latest_validation["candidate_sha256"] == text_hash(expected_turtle),
                "Feedback validation belongs to an older candidate")
        saved_validation = json.loads((previous / "deterministic_validation.json").read_text())
        require(saved_validation == self.latest_validation["report"], "Saved error report belongs to another candidate/version")
        # A validator request, when present, must itself have reviewed this code.
        if metadata["decision"] in {"REVISE", "REVISE_WITH_MATCH"}:
            reviewed = [r for r in self.requests if r.get("role") == "validator"
                        and r.get("candidate_sha256") == text_hash(expected_turtle)
                        and Path(r["runner_prompt_artifact"]).parent == previous]
            require(bool(reviewed), "Semantic feedback has no review of this candidate")
            decision = parse_validator_decision(reviewed[-1]["local_response_text"])
            expected_issues = [i.to_dict() for i in decision.current_issues]
            feedback_origin = "SEMANTIC_REVIEW_OF_SAME_CANDIDATE"
        else:
            expected_issues = [i.to_dict() for i in static_issues(saved_validation["errors"])]
            feedback_origin = "DETERMINISTIC_REPORT_FOR_SAME_CANDIDATE"
        if metadata["decision"] in {"REVISE_STATIC_WITH_MATCH", "REVISE_WITH_MATCH"}:
            resolutions = [r for r in self.requests if r["role"] == "vocabulary_matcher"
                           and Path(r["runner_prompt_artifact"]).parent == previous
                           and r.get("candidate_sha256") == text_hash(expected_turtle)]
            require(bool(resolutions), "Matcher feedback has no resolution for this candidate")
            match = parse_matcher_decision(resolutions[-1]["local_response_text"])
            require(match.match_found, "Matcher-assisted repair lacks a verified match")
            for issue in expected_issues:
                if issue["needs_vocabulary_resolution"]:
                    issue["required_change"] += f" Locked resolution: use exactly {match.canonical_iri}."
        # ValidatorIssue.to_dict intentionally omits internal source attribution.
        # All seven substantive fields must still match exactly.
        rendered_issues = [{k: v for k, v in issue.items() if k != "source"} for issue in issues]
        require(rendered_issues == expected_issues, "Error feedback did not originate from this candidate/version")
        return dict(candidate_path=str(candidate), candidate_attempt=iteration - 1,
                    candidate_sha256=text_hash(expected_turtle), issues=rendered_issues,
                    saved_feedback_packet_sha256=packet_sha256(issues),
                    feedback_origin=feedback_origin,
                    metadata=metadata, issues_path=str(previous / "structured_current_issues.json"))

    def call(self, role: str, developer_prompt: str, user_prompt: str):
        capture = self.output / "complete_requests"
        capture.mkdir(parents=True, exist_ok=True)
        request = dict(sequence=len(self.requests) + 1, role=role,
            developer=developer_prompt, user=user_prompt,
            developer_sha256=text_hash(developer_prompt), user_sha256=text_hash(user_prompt),
            checked=False, offline_only=True)
        path = capture / f"request_{request['sequence']:03d}_{role}.json"
        self.requests.append(request)
        try:
            payload, consumed = json.JSONDecoder().raw_decode(user_prompt)
            correction = user_prompt[consumed:].strip()
            if correction:
                require(role in {"validator", "vocabulary_matcher"}
                        and correction.startswith("Your previous response violated the required one-line JSON contract:"),
                        "Unexpected text appended to the complete request")
            request["response_contract_retry"] = bool(correction)
            prompt = self._prompt_artifact(developer_prompt, user_prompt)
            request["runner_prompt_artifact"] = str(prompt)
            task = str(payload.get("task", ""))
            if role == "generator" and prompt.name == "semantic_repair_prompt.txt":
                require(task == "Repair the supplied current SHACL candidate", "Repair disguised as fresh regeneration")
                require(self.latest_raw is not None, "Normal repair has no preceding response")
                expected = extract_shacl(self.latest_raw)
                request.update(check_previous_code(payload, "previousCandidateShacl", expected, text_hash(expected)))
                previous = self._previous_state(prompt, expected)
                require(payload.get("currentIssues") == previous["issues"], "Repair error feedback is stale or changed")
                require(bool(previous["issues"]), "Normal repair has no concrete current feedback")
                mode = {"REVISE_STATIC_GATE": "STATIC_REPAIR",
                        "REVISE_STATIC_WITH_MATCH": "MATCHER_ASSISTED_REPAIR",
                        "REVISE_WITH_MATCH": "MATCHER_ASSISTED_REPAIR",
                        "REVISE": "SEMANTIC_CANDIDATE_REPAIR"}.get(previous["metadata"]["decision"])
                require(mode is not None, "Feedback decision has no appropriate repair route")
                request.update(mode=mode, fresh_regeneration=False,
                    candidate_attempt=previous["candidate_attempt"],
                    feedback_candidate_sha256=previous["candidate_sha256"],
                    feedback_packet_sha256=packet_sha256(previous["issues"]),
                    saved_feedback_packet_sha256=previous["saved_feedback_packet_sha256"],
                    feedback_source=previous["issues_path"],
                    feedback_origin=previous["feedback_origin"],
                    candidate_source=previous["candidate_path"], feedback_version_matches=True)
                request["canonical_findings"] = [i for i in previous["issues"]
                    if i["needs_vocabulary_resolution"] or i["category"] == "CANONICAL_VOCABULARY"]
                if request["canonical_findings"]:
                    require(mode in {"STATIC_REPAIR", "MATCHER_ASSISTED_REPAIR", "SEMANTIC_CANDIDATE_REPAIR"},
                            "Canonical finding entered an inappropriate repair route")
                    require(all(i in payload["currentIssues"] for i in request["canonical_findings"]),
                            "Canonical findings were dropped from feedback")
            elif role == "generator" and prompt.name == "escape_hatch_prompt.txt":
                require(task == "Fresh regeneration escape hatch after targeted repair became stuck", "Fresh regeneration mislabeled as repair")
                require("previousCandidateShacl" not in payload, "Fresh regeneration must be explicitly distinct from code repair")
                require("FRESH" in developer_prompt.upper() and "ESCAPE HATCH" in developer_prompt,
                        "Fresh regeneration lacks explicit developer instructions")
                require(self.latest_raw is not None, "Fresh escape hatch has no prior candidate")
                previous = self._previous_state(prompt, extract_shacl(self.latest_raw))
                require(payload.get("currentIssues") == previous["issues"], "Fresh regeneration feedback is stale")
                request.update(mode="FRESH_REGENERATION_ESCAPE_HATCH", fresh_regeneration=True,
                    previous_candidate_required=False, feedback_version_matches=True,
                    feedback_candidate_sha256=previous["candidate_sha256"],
                    feedback_source=previous["issues_path"],
                    feedback_packet_sha256=packet_sha256(previous["issues"]))
            elif role == "generator":
                require(prompt.name == "generator_prompt.txt", "Unknown generator/repair route")
                require(self.latest_raw is None, "Fresh generation silently substituted for normal repair")
                require("previousCandidateShacl" not in payload, "Initial generation unexpectedly contains previous code")
                request.update(mode="INITIAL_GENERATION", fresh_regeneration=False)
            elif role == "syntax_repair":
                require(self.latest_raw is not None, "Syntax repair has no previous response")
                request.update(check_previous_code(payload, "candidateResponse", self.latest_raw, text_hash(self.latest_raw)))
                require(self.latest_validation is not None and self.latest_validation["raw_sha256"] == text_hash(self.latest_raw),
                        "Syntax error feedback refers to a different candidate")
                require(payload.get("syntaxDiagnostics") == self.latest_syntax_diagnostics,
                        "Syntax error feedback is stale or truncated")
                request.update(mode="SYNTAX_REPAIR", fresh_regeneration=False,
                    feedback_candidate_sha256=text_hash(self.latest_raw),
                    response_version=self.latest_response_version, feedback_version_matches=True,
                    feedback_packet_sha256=packet_sha256(self.latest_syntax_diagnostics))
            elif role == "validator":
                require(self.latest_raw is not None, "Validator has no candidate")
                expected = extract_shacl(self.latest_raw)
                check_previous_code(payload, "candidateShacl", expected, text_hash(expected))
                require(self.latest_validation is not None and self.latest_validation["candidate_sha256"] == text_hash(expected),
                        "Validator deterministic report has a stale candidate")
                require(payload.get("deterministicValidation") == self.latest_validation["report"],
                        "Validator received feedback for a different version")
                request.update(mode="CANDIDATE_REVIEW", candidate_sha256=text_hash(expected), feedback_version_matches=True)
            elif role == "vocabulary_matcher":
                require(self.latest_validation is not None, "Matcher has no candidate validation")
                if not self.latest_validation["report"]["valid"]:
                    relevant = static_issues(self.latest_validation["report"]["errors"])
                else:
                    reviews = [r for r in self.requests if r["role"] == "validator"
                               and Path(r["runner_prompt_artifact"]).parent == prompt.parent
                               and r.get("candidate_sha256") == self.latest_validation["candidate_sha256"]]
                    require(bool(reviews), "Matcher has no semantic feedback for this candidate")
                    relevant = parse_validator_decision(reviews[-1]["local_response_text"]).current_issues
                relevant = [i.to_dict() for i in relevant if i.needs_vocabulary_resolution]
                require(payload.get("currentVocabularyIssues") == relevant,
                        "Canonical matcher feedback belongs to another candidate/version")
                request.update(mode="VOCABULARY_RESOLUTION", candidate_sha256=self.latest_validation["candidate_sha256"])
            request["checked"] = True
            response = super().call(role, developer_prompt, user_prompt)
            request["local_response_sha256"] = text_hash(response.text)
            if role not in {"generator", "syntax_repair"}:
                request["local_response_text"] = response.text
            if role in {"generator", "syntax_repair"}:
                self.latest_raw = response.text
                self.latest_response_version = request["sequence"]
                raw_path = capture / f"candidate_response_{request['sequence']:03d}.txt"
                raw_path.write_text(response.text)
                request["response_artifact"] = str(raw_path)
            return response
        except Exception as exc:
            request["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            path.write_text(json.dumps(request, indent=2, ensure_ascii=False) + "\n")
            (capture / f"request_{request['sequence']:03d}_{role}.txt").write_text(
                developer_prompt + "\n\n--- USER INPUT ---\n" + user_prompt)
