from __future__ import annotations

import json
from typing import Any

from ..errors import ResponseContractError
from ..models import MatcherDecision, ValidatorDecision


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
    payload = _one_line_object(raw, {"accept", "activate_variable_matcher", "feedback"})
    if type(payload["accept"]) is not bool or type(payload["activate_variable_matcher"]) is not bool:
        raise ResponseContractError("accept and activate_variable_matcher must be JSON booleans")
    if not isinstance(payload["feedback"], str):
        raise ResponseContractError("feedback must be a string")
    if payload["accept"] and payload["activate_variable_matcher"]:
        raise ResponseContractError("An accepted response cannot activate the vocabulary matcher")
    if not payload["accept"] and not payload["feedback"].strip():
        raise ResponseContractError("A rejected response must contain concrete feedback")
    return ValidatorDecision(
        accept=payload["accept"],
        activate_variable_matcher=payload["activate_variable_matcher"],
        feedback=payload["feedback"].strip(),
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

