from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from ..errors import ResponseContractError
from ..models import MatcherDecision, ValidatorDecision, ValidatorIssue


VALIDATOR_KEYS = {"accept", "activate_variable_matcher", "currentIssues"}


@dataclass(frozen=True, slots=True)
class ValidatorResponseNormalization:
    decision_text: str | None
    text_before_decision_block: str
    text_after_decision_block: str
    candidate_decision_block_count: int
    error: str | None = None

    @property
    def text_outside_decision_block(self) -> bool:
        return bool(self.text_before_decision_block.strip() or self.text_after_decision_block.strip())

    @property
    def multiple_candidate_decision_blocks(self) -> bool:
        return self.candidate_decision_block_count > 1

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("decision_text", None)
        before = value.pop("text_before_decision_block")
        after = value.pop("text_after_decision_block")
        value["text_outside_decision_block"] = {
            "before": before,
            "after": after,
        }
        value["has_text_outside_decision_block"] = self.text_outside_decision_block
        value["multiple_candidate_decision_blocks"] = self.multiple_candidate_decision_blocks
        return value


def _decision_signature(payload: dict[str, Any]) -> tuple[Any, ...]:
    """Return only explicit control semantics; never compare or reinterpret prose."""
    issues = payload.get("currentIssues")
    issue_controls: tuple[Any, ...]
    if isinstance(issues, list):
        issue_controls = tuple(
            (item.get("blocking"), item.get("needs_vocabulary_resolution"))
            if isinstance(item, dict) else ("INVALID_ISSUE", type(item).__name__)
            for item in issues
        )
    else:
        issue_controls = ("INVALID_CURRENT_ISSUES", type(issues).__name__)
    return payload.get("accept"), payload.get("activate_variable_matcher"), issue_controls


def normalize_validator_response(raw: str) -> ValidatorResponseNormalization:
    """Locate the final complete validator object without changing any byte inside it."""
    decoder = json.JSONDecoder()
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for start, character in enumerate(raw):
        if character != "{":
            continue
        try:
            payload, consumed = decoder.raw_decode(raw[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and set(payload) == VALIDATOR_KEYS:
            candidates.append((start, start + consumed, payload))

    if not candidates:
        return ValidatorResponseNormalization(None, raw, "", 0, "No complete validator decision object found")

    # A decision-shaped object nested inside another decision-shaped object has no
    # unambiguous final block boundary and is rejected.
    for index, (start, end, _) in enumerate(candidates):
        for other_start, other_end, _ in candidates[index + 1:]:
            if (start < other_start < end) or (other_start < start < other_end):
                return ValidatorResponseNormalization(
                    None, raw, "", len(candidates), "Ambiguous nested validator decision objects"
                )

    signatures = {_decision_signature(payload) for _, _, payload in candidates}
    final_start, final_end, _ = candidates[-1]
    before, after = raw[:final_start], raw[final_end:]
    if len(signatures) > 1:
        return ValidatorResponseNormalization(
            None, before, after, len(candidates), "Conflicting validator decision objects"
        )

    # Never fall back to an earlier object when a later response begins another
    # decision-shaped object but leaves it incomplete.
    trailing_open = after.find("{")
    if trailing_open >= 0:
        trailing = after[trailing_open:]
        key_mentions = sum(f'"{key}"' in trailing for key in VALIDATOR_KEYS)
        if key_mentions >= 1:
            return ValidatorResponseNormalization(
                None, before, after, len(candidates), "Incomplete trailing validator decision object"
            )

    return ValidatorResponseNormalization(raw[final_start:final_end], before, after, len(candidates))


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
    normalized = normalize_validator_response(raw)
    if normalized.error or normalized.decision_text is None:
        raise ResponseContractError(normalized.error or "No complete validator decision object found")
    try:
        payload = json.loads(normalized.decision_text)
    except json.JSONDecodeError as exc:  # defensive: the normalizer only returns decoded objects
        raise ResponseContractError(f"Invalid JSON: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != VALIDATOR_KEYS:
        raise ResponseContractError("Normalized validator response is not the required decision object")
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
        issues.append(ValidatorIssue(**{key: item[key] for key in issue_keys}))
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
        text_outside_decision_block=normalized.text_outside_decision_block,
        multiple_candidate_decision_blocks=normalized.multiple_candidate_decision_blocks,
        candidate_decision_block_count=normalized.candidate_decision_block_count,
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
