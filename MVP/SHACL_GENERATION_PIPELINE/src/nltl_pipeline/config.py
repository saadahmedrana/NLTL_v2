from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError


PIPELINE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = PIPELINE_ROOT.parent
DEFAULT_CONFIG = PIPELINE_ROOT / "config" / "pipeline.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_pipeline_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (PIPELINE_ROOT / path).resolve()


@dataclass(slots=True)
class PipelineConfig:
    raw: dict[str, Any]
    config_path: Path

    @classmethod
    def load(cls, path: str | Path | None = None) -> "PipelineConfig":
        config_path = Path(path).resolve() if path else DEFAULT_CONFIG
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigurationError(f"Missing pipeline configuration: {config_path}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigurationError(f"Invalid pipeline JSON: {exc}") from exc
        required = {"pipeline_version", "environment_file", "paths", "models", "api", "generation", "reporting"}
        missing = sorted(required - set(raw))
        if missing:
            raise ConfigurationError(f"Pipeline configuration is missing: {', '.join(missing)}")
        return cls(raw=raw, config_path=config_path)

    def path(self, name: str) -> Path:
        try:
            return resolve_pipeline_path(str(self.raw["paths"][name]))
        except KeyError as exc:
            raise ConfigurationError(f"Unknown configured path: {name}") from exc

    @property
    def environment_file(self) -> Path:
        return Path(str(self.raw["environment_file"]))

    def model(self, role: str) -> str:
        try:
            return str(self.raw["models"][role])
        except KeyError as exc:
            raise ConfigurationError(f"No model configured for role: {role}") from exc

    def verify_locked_inputs(self) -> dict[str, Any]:
        lock_path = self.path("vocabulary_lock")
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Cannot read vocabulary lock: {lock_path}") from exc

        bound = lock.get("boundMachineReadableArtifacts", {})
        bound_index = lock.get("boundRequirementIndex", {})
        checks = {
            self.path("term_registry"): bound.get("registry/term_registry.json"),
            self.path("ontology"): bound.get("ontology/nltl_benchmark_vocabulary.ttl"),
            self.path("requirement_evidence"): bound.get("evidence/stage1_approved.json"),
            self.path("requirement_term_index"): next(iter(bound_index.values()), None),
        }
        failures: list[str] = []
        for source, expected in checks.items():
            if not source.exists():
                failures.append(f"missing {source}")
                continue
            actual = sha256_file(source)
            if not expected or actual != expected:
                failures.append(f"hash mismatch {source}: expected {expected}, actual {actual}")
        for name in ("few_shot_jsonl",):
            source = self.path(name)
            if not source.exists():
                failures.append(f"missing {source}")
        if failures:
            raise ConfigurationError("Locked input verification failed: " + "; ".join(failures))
        return {
            "lock_id": lock.get("lockId", ""),
            "workbook": lock.get("workbook", ""),
            "workbook_sha256": lock.get("workbookSha256", ""),
            "registry_sha256": checks[self.path("term_registry")],
            "ontology_sha256": checks[self.path("ontology")],
            "requirement_evidence_sha256": checks[self.path("requirement_evidence")],
            "requirement_term_index_sha256": checks[self.path("requirement_term_index")],
        }
