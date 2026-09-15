from __future__ import annotations

import json
from typing import Any

from ..errors import ResponseContractError
from ..models import MatcherDecision, ValidatorDecision, ValidatorIssue


def _one_line_object(raw: str, expected_keys: set[str]) -> dict[str, Any]:
    text = raw.strip()
    if "\n" in text or "\r" in text:
        raise ResponseContractError("Response must be exactly one physical line of JSON")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResponseContractError(f"Invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ResponseContractError("Response must be a JSON object")
    if set(payload) != expected_keys:
        raise ResponseContractError(
            f"Response keys must be exactly {sorted(expected_keys)}; received {sorted(payload)}"
        )
    return payload


def parse_validator_decision(raw: str) -> ValidatorDecision:
    payload = _one_line_object(raw, {"accept", "activate_variable_matcher", "currentIssues"})
    if type(payload["accept"]) is not bool or type(payload["activate_variable_matcher"]) is not bool:
        raise ResponseContractError("accept and activate_variable_matcher must be JSON booleans")
    if not isinstance(payload["currentIssues"], list):
        raise ResponseContractError("currentIssues must be an array")
    issue_keys = {
        "category", "location", "problem", "required_change", "regression_guard",
        "blocking", "needs_vocabulary_resolution",
    }
    issues: list[ValidatorIssue] = []
    vague = ("could be improved", "might be more robust", "consider clarifying")
    for index, item in enumerate(payload["currentIssues"]):
        if not isinstance(item, dict) or set(item) != issue_keys:
            received = sorted(item) if isinstance(item, dict) else type(item).__name__
            raise ResponseContractError(
                f"currentIssues[{index}] keys must be exactly {sorted(issue_keys)}; received {received}"
            )
        for key in ("category", "location", "problem", "required_change", "regression_guard"):
            if not isinstance(item[key], str) or not item[key].strip():
                raise ResponseContractError(f"currentIssues[{index}].{key} must be a non-empty string")
        for key in ("blocking", "needs_vocabulary_resolution"):
            if type(item[key]) is not bool:
                raise ResponseContractError(f"currentIssues[{index}].{key} must be a JSON boolean")
        if item["blocking"]:
            combined = f'{item["problem"]} {item["required_change"]}'.lower()
            if any(phrase in combined for phrase in vague):
                raise ResponseContractError(
                    f"currentIssues[{index}] uses vague prose as blocking feedback"
                )
        issues.append(ValidatorIssue(**{key: item[key].strip() if isinstance(item[key], str) else item[key] for key in issue_keys}))
    if payload["accept"] and payload["activate_variable_matcher"]:
        raise ResponseContractError("An accepted response cannot activate the vocabulary matcher")
    if payload["activate_variable_matcher"] and not any(issue.needs_vocabulary_resolution for issue in issues):
        raise ResponseContractError("Matcher activation requires a current vocabulary-resolution issue")
    blocking = [issue for issue in issues if issue.blocking]
    if payload["accept"] and blocking:
        raise ResponseContractError("An accepted response cannot contain blocking currentIssues")
    if not payload["accept"] and not blocking:
        raise ResponseContractError("A rejected response requires at least one concrete blocking currentIssue")
    return ValidatorDecision(
        accept=payload["accept"],
        activate_variable_matcher=payload["activate_variable_matcher"],
        current_issues=issues,
    )


def parse_matcher_decision(raw: str) -> MatcherDecision:
    payload = _one_line_object(
        raw,
        {"match_found", "canonical_local_name", "canonical_iri", "feedback_appendix"},
    )
    if type(payload["match_found"]) is not bool:
        raise ResponseContractError("match_found must be a JSON boolean")
    for key in ("canonical_local_name", "canonical_iri", "feedback_appendix"):
        if not isinstance(payload[key], str):
            raise ResponseContractError(f"{key} must be a string")
    if payload["match_found"]:
        if not payload["canonical_local_name"].strip() or not payload["canonical_iri"].strip():
            raise ResponseContractError("A positive match requires a canonical local name and IRI")
    elif payload["canonical_local_name"].strip() or payload["canonical_iri"].strip():
        raise ResponseContractError("A negative match must leave the canonical local name and IRI empty")
    return MatcherDecision(
        match_found=payload["match_found"],
        canonical_local_name=payload["canonical_local_name"].strip(),
        canonical_iri=payload["canonical_iri"].strip(),
        feedback_appendix=payload["feedback_appendix"].strip(),
    )
