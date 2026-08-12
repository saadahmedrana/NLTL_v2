from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ApiCallResult:
    text: str
    response_id: str
    model: str
    usage: dict[str, Any]
    transport_attempts: int
    elapsed_ms: float


@dataclass(slots=True)
class ValidatorDecision:
    accept: bool
    activate_variable_matcher: bool
    feedback: str


@dataclass(slots=True)
class MatcherDecision:
    match_found: bool
    canonical_local_name: str
    canonical_iri: str
    feedback_appendix: str


@dataclass(slots=True)
class StaticValidationReport:
    valid: bool
    extraction_valid: bool
    turtle_valid: bool
    shacl_structure_valid: bool
    meta_shacl_valid: bool
    vocabulary_valid: bool
    datatype_unit_valid: bool
    target_path_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    used_canonical_iris: list[str] = field(default_factory=list)
    unknown_canonical_iris: list[str] = field(default_factory=list)
    out_of_scope_canonical_iris: list[str] = field(default_factory=list)
    suspicious_external_iris: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ContextPack:
    requirement: dict[str, Any]
    terms: list[dict[str, Any]]
    node_patterns: list[dict[str, Any]]
    source_lock: dict[str, Any]
    selection: dict[str, Any]
    usage_policy: dict[str, Any]

    @property
    def allowed_iris(self) -> set[str]:
        return {str(item["iri"]) for item in self.terms}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PipelineRunResult:
    run_id: str
    requirement_id: str
    status: str
    accepted: bool
    attempts: int
    run_directory: Path
    final_shape: Path | None
    final_feedback: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["run_directory"] = str(self.run_directory)
        payload["final_shape"] = str(self.final_shape) if self.final_shape else None
        return payload

