from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CONFIGURATIONS = ("FULL", "NO_SEMANTIC", "SINGLESHOT")
EXPECTED_REQUIREMENTS = 268
EXPECTED_CASES = 2186
FAMILY_ORDER = {"I2": 0, "TRAFICOM": 1, "IMO": 2, "IMO26": 3}
SOURCE_IDS = {
    "IACS_UR_I2": "SRC-IACS-I2-R4",
    "TRAFICOM": "SRC-TRAFICOM-2021",
    "IMO_POLAR_CODE": "SRC-IMO-MSC385-94",
    "IMO_AMEND_2026": "SRC-IMO26-SUPPLEMENT",
}
FAMILY_SOURCES = {
    "I2": "SRC-IACS-I2-R4",
    "TRAFICOM": "SRC-TRAFICOM-2021",
    "IMO": "SRC-IMO-MSC385-94",
    "IMO26": "SRC-IMO26-SUPPLEMENT",
}
FAMILY_BATCHES = {
    "I2": ("i2", "abcdefghi"),
    "TRAFICOM": ("traficom", "abcdefghij"),
    "IMO": ("imo", "abcdefghijklmn"),
    "IMO26": ("imo26", "ab"),
}
EXPERIMENTS = {
    "FULL": {
        "directory": "FINAL_LUNA_MAIN",
        "queue": "luna_main_268_frozen.json",
        "config": "pipeline.final-luna-main-run01.json",
        "artifact_type": "final_accepted_shape",
        "usable_statuses": {"GENERATION_ACCEPTED"},
    },
    "NO_SEMANTIC": {
        "directory": "LUNA_NO_SEMANTIC_VALIDATOR",
        "queue": "luna_no_semantic_validator_268_frozen.json",
        "config": "pipeline.luna-no-semantic-validator-run01.json",
        "artifact_type": "no_semantic_validator_candidate_shape",
        "usable_statuses": {"NO_SEMANTIC_VALIDATOR_DETERMINISTIC_PASS"},
    },
    "SINGLESHOT": {
        "directory": "LUNA_CONTEXTUAL_SINGLESHOT",
        "queue": "luna_contextual_singleshot_268_frozen.json",
        "config": "pipeline.luna-contextual-singleshot-run01.json",
        "artifact_type": "single_shot_extracted_shape",
        "usable_statuses": {"SINGLESHOT_CAPTURED_DIAGNOSTIC_PASS"},
    },
}


class PreflightError(RuntimeError):
    """The experiment cannot execute without violating an integrity lock."""


def find_repo_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    candidates = [here, *here.parents, Path(__file__).resolve(), *Path(__file__).resolve().parents]
    for candidate in candidates:
        if candidate.is_file():
            candidate = candidate.parent
        if (candidate / "verify_full_benchmark_integrity_final.py").exists() and (
            candidate / "MVP/SHACL_GENERATION_PIPELINE"
        ).exists():
            return candidate
    raise PreflightError("Could not locate repository root")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def composite_hash(paths: Iterable[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted({p.resolve() for p in paths}, key=lambda p: str(p)):
        digest.update(str(path.relative_to(root.resolve())).encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def source_family(requirement_id: str) -> str:
    if requirement_id.startswith("I2-"):
        return "I2"
    if requirement_id.startswith("TRF-"):
        return "TRAFICOM"
    if requirement_id.startswith("IMO26-"):
        return "IMO26"
    if requirement_id.startswith("IMO-"):
        return "IMO"
    raise PreflightError(f"Unknown requirement family: {requirement_id}")


@dataclass(frozen=True)
class BenchmarkCase:
    source_family: str
    source_id: str
    source_clause: str
    requirement_id: str
    verification_mode: str
    verification_mode_source: str
    case_id: str
    rdf_path: str
    rdf_sha256: str
    expected_outcome: str
    source_oracle_rationale: str
    test_pattern: str

    def key(self, configuration: str) -> tuple[str, str, str]:
        return configuration, self.requirement_id, self.case_id


@dataclass
class Benchmark:
    root: Path
    cases: list[BenchmarkCase]
    manifest_paths: list[Path]
    locked_paths: list[Path]
    integrity_hash: str

    @property
    def requirement_ids(self) -> list[str]:
        return sorted({c.requirement_id for c in self.cases}, key=requirement_sort_key)

    def by_requirement(self) -> dict[str, list[BenchmarkCase]]:
        grouped: dict[str, list[BenchmarkCase]] = defaultdict(list)
        for case in self.cases:
            grouped[case.requirement_id].append(case)
        return {key: sorted(value, key=lambda c: c.case_id) for key, value in grouped.items()}


def requirement_sort_key(requirement_id: str) -> tuple[int, str]:
    family = source_family(requirement_id)
    return FAMILY_ORDER[family], requirement_id


def systematic_manifest_paths(benchmark_root: Path) -> list[Path]:
    paths: list[Path] = []
    for family in ("I2", "TRAFICOM", "IMO", "IMO26"):
        prefix, batches = FAMILY_BATCHES[family]
        paths.extend(benchmark_root / "manifests" / f"{prefix}_batch_{b}_manifest.jsonl" for b in batches)
    return paths


def load_benchmark(repo: Path, strict_counts: bool = True) -> Benchmark:
    root = repo / "MVP/SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13"
    r13_index_path = repo / "MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/requirement_term_index.json"
    index = json.loads(r13_index_path.read_text(encoding="utf-8"))["dependencyContracts"]
    manifests = systematic_manifest_paths(root)
    rows: list[BenchmarkCase] = []
    for manifest in manifests:
        if not manifest.exists():
            raise PreflightError(f"Missing systematic manifest: {manifest}")
        for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            required = {"requirement_id", "case_id", "rdf_path", "expected", "source_id", "source_clause"}
            missing = required - raw.keys()
            if missing:
                raise PreflightError(f"{manifest}:{line_number}: missing {sorted(missing)}")
            requirement_id = str(raw["requirement_id"])
            family = source_family(requirement_id)
            expected = str(raw["expected"]).upper()
            if expected not in {"PASS", "FAIL"}:
                raise PreflightError(f"{manifest}:{line_number}: invalid expected outcome {expected!r}")
            rdf_rel = str(raw["rdf_path"])
            rdf_path = root / rdf_rel
            if not rdf_path.is_file():
                raise PreflightError(f"Missing RDF fixture: {rdf_path}")
            verification_mode = raw.get("verification_mode")
            mode_source = "benchmark_manifest"
            if not verification_mode:
                # Six early I2 manifests predate the field. Their frozen R13 dependency
                # contracts are the authoritative, locked requirement-level fallback.
                verification_mode = index.get(requirement_id, {}).get("verificationMode")
                mode_source = "r13_dependency_contract_fallback"
            if verification_mode not in {"DIRECT_STATIC", "DIRECT_CALCULATION", "COMPLEX_READINESS"}:
                raise PreflightError(f"No valid verification mode for {requirement_id}")
            rows.append(BenchmarkCase(
                source_family=family,
                source_id=str(raw["source_id"]),
                source_clause=str(raw["source_clause"]),
                requirement_id=requirement_id,
                verification_mode=str(verification_mode),
                verification_mode_source=mode_source,
                case_id=str(raw["case_id"]),
                rdf_path=rdf_rel,
                rdf_sha256=sha256(rdf_path),
                expected_outcome=expected,
                source_oracle_rationale=str(raw.get("source_oracle_rationale", raw.get("rationale", ""))),
                test_pattern=str(raw.get("test_pattern", "")),
            ))
    reqs = [c.requirement_id for c in rows]
    case_ids = [c.case_id for c in rows]
    rdf_paths = [c.rdf_path for c in rows]
    duplicate_cases = [key for key, count in Counter(case_ids).items() if count != 1]
    duplicate_paths = [key for key, count in Counter(rdf_paths).items() if count != 1]
    if duplicate_cases:
        raise PreflightError(f"Duplicate case IDs: {duplicate_cases[:10]}")
    if duplicate_paths:
        raise PreflightError(f"Duplicate RDF paths: {duplicate_paths[:10]}")
    for case in rows:
        if case.source_id != FAMILY_SOURCES[case.source_family]:
            raise PreflightError(f"Benchmark source mismatch for {case.case_id}: {case.source_id}")
        if not case.case_id.startswith(case.requirement_id + "-"):
            raise PreflightError(f"Case/requirement identity mismatch: {case.case_id}")
    if strict_counts and (len(set(reqs)), len(rows)) != (EXPECTED_REQUIREMENTS, EXPECTED_CASES):
        raise PreflightError(
            f"Frozen benchmark count mismatch: {len(set(reqs))} requirements / {len(rows)} cases"
        )
    locks = sorted((root / "locks").glob("*_batch_*_fixture_lock.json"))
    locked_paths = [*manifests, *[root / c.rdf_path for c in rows], *locks, r13_index_path]
    return Benchmark(root, sorted(rows, key=lambda c: (*requirement_sort_key(c.requirement_id), c.case_id)), manifests, locked_paths, composite_hash(locked_paths, repo))


def run_integrity_check(repo: Path) -> dict[str, Any]:
    command = [sys.executable, str(repo / "verify_full_benchmark_integrity_final.py")]
    completed = subprocess.run(command, cwd=repo, text=True, capture_output=True, check=False)
    output = completed.stdout + completed.stderr
    required = (
        "R13 COMPLETE systematic coverage: PASS (268/268)",
        "Systematic RDF cases represented: 2186",
        "Pilot 02 frozen hashes: PASS",
        "OVERALL FINAL BENCHMARK INTEGRITY: PASS",
    )
    ok = completed.returncode == 0 and all(token in output for token in required)
    if not ok:
        raise PreflightError(f"Final benchmark integrity check failed:\n{output}")
    return {"status": "PASS", "command": command, "output": output, "returncode": completed.returncode}


def _one_csv_row(path: Path) -> dict[str, str]:
    if not path.exists():
        raise PreflightError(f"Missing metadata table: {path}")
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    if len(rows) != 1:
        raise PreflightError(f"Expected exactly one row in {path}, found {len(rows)}")
    return rows[0]


def _artifact_rows(path: Path, artifact_type: str, run_id: str, requirement_id: str) -> list[dict[str, str]]:
    if not path.exists():
        raise PreflightError(f"Missing artifact table: {path}")
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    for row in rows:
        if row.get("RUN_ID") != run_id or row.get("REQUIREMENT_ID") != requirement_id:
            raise PreflightError(f"Artifact identity mismatch in {path}: {row}")
    return [row for row in rows if row["ARTIFACT_TYPE"] == artifact_type]


def build_generated_manifest(repo: Path, configuration: str, output_path: Path) -> list[dict[str, Any]]:
    if configuration not in CONFIGURATIONS:
        raise PreflightError(f"Unknown configuration: {configuration}")
    policy = EXPERIMENTS[configuration]
    experiment_root = repo / "MVP/SHACL_GENERATION_PIPELINE/experiments" / policy["directory"]
    queue_path = experiment_root / "QUEUES" / policy["queue"]
    config_path = experiment_root / "CONFIGS" / policy["config"]
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected_requirements = list(queue["requirements"])
    if len(expected_requirements) != EXPECTED_REQUIREMENTS or len(set(expected_requirements)) != EXPECTED_REQUIREMENTS:
        raise PreflightError(f"{configuration} queue is not a unique 268-requirement queue")

    run_records: dict[str, list[tuple[Path, dict[str, str]]]] = defaultdict(list)
    runs_root = experiment_root / "RUN_01/runs"
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        row = _one_csv_row(run_dir / "tables/runs.csv")
        if row["RUN_ID"] != run_dir.name:
            raise PreflightError(f"Run directory/table ID mismatch: {run_dir}")
        run_records[row["REQUIREMENT_ID"]].append((run_dir, row))

    records: list[dict[str, Any]] = []
    for requirement_id in expected_requirements:
        candidates = run_records.get(requirement_id, [])
        if len(candidates) > 1:
            raise PreflightError(f"Duplicate generated rules/runs for {configuration} {requirement_id}")
        if not candidates:
            records.append({
                "manifest_id": f"RUN01-{configuration}-{requirement_id}",
                "configuration": configuration,
                "requirement_id": requirement_id,
                "source_id": FAMILY_SOURCES[source_family(requirement_id)],
                "source_identity_locator": None,
                "source_clause": None,
                "generated_shacl_path": None,
                "generated_shacl_sha256": None,
                "generation_status": "NOT_GENERATED",
                "failure_stage": "RUN_DISCOVERY",
                "failure_detail": "No RUN01 metadata record exists",
                "run_id": None,
                "generation_timestamp": None,
                "model_identifier": config["models"]["generator"],
                "generation_config_identifier": config["pipeline_version"],
                "prompt_config_identifier": config["paths"]["prompt_directory"],
                "r13_contract_identifier": queue["development_vocabulary_id"],
                "queue_identifier": queue["queue_id"],
            })
            continue
        run_dir, run = candidates[0]
        context_path = run_dir / "artifacts/context_pack_initial.json"
        context = json.loads(context_path.read_text(encoding="utf-8"))
        context_req = context.get("requirement", {})
        if context_req.get("id") != requirement_id:
            raise PreflightError(f"Context-pack identity mismatch in {run_dir}")
        source_locator = context_req.get("sourceSheet")
        generated_source_id = SOURCE_IDS.get(str(source_locator))
        if not generated_source_id:
            raise PreflightError(f"Unknown generated source locator {source_locator!r} in {run_dir}")
        artifact_matches = _artifact_rows(
            run_dir / "tables/artifacts.csv", str(policy["artifact_type"]), run["RUN_ID"], requirement_id
        )
        if len(artifact_matches) > 1:
            raise PreflightError(f"Duplicate selected artifacts for {configuration} {requirement_id}")
        usable_status = run["FINAL_STATUS"] in policy["usable_statuses"]
        generation_status = "GENERATED" if usable_status else "GENERATION_ERROR"
        failure_stage = None if usable_status else run["FINAL_STATUS"]
        failure_detail = None if usable_status else run.get("FINAL_FEEDBACK", "")
        shape_path: Path | None = None
        shape_hash: str | None = None
        recorded_hash: str | None = None
        if artifact_matches:
            artifact = artifact_matches[0]
            shape_path = run_dir / artifact["ARTIFACT_PATH"]
            recorded_hash = artifact["SHA256"]
            if shape_path.exists():
                shape_hash = sha256(shape_path)
                if shape_hash != recorded_hash:
                    generation_status = "GENERATION_ERROR"
                    failure_stage = "ARTIFACT_HASH_MISMATCH"
                    failure_detail = f"Recorded {recorded_hash}; actual {shape_hash}"
            else:
                generation_status = "GENERATION_ERROR"
                failure_stage = "SHAPE_MISSING"
                failure_detail = f"Recorded artifact does not exist: {shape_path}"
        elif usable_status:
            generation_status = "GENERATION_ERROR"
            failure_stage = "SHAPE_MISSING"
            failure_detail = f"No {policy['artifact_type']} artifact record"
        if configuration == "FULL" and usable_status:
            final_ref = run.get("FINAL_SHAPE", "")
            if not final_ref or shape_path is None or (run_dir / final_ref).resolve() != shape_path.resolve():
                raise PreflightError(f"FULL final-shape records disagree for {requirement_id}")
        records.append({
            "manifest_id": f"RUN01-{configuration}-{requirement_id}",
            "configuration": configuration,
            "requirement_id": requirement_id,
            "source_id": generated_source_id,
            "source_identity_locator": source_locator,
            "source_clause": context_req.get("clause"),
            "generated_shacl_path": str(shape_path.relative_to(repo)) if shape_path else None,
            "generated_shacl_sha256": shape_hash,
            "recorded_generated_shacl_sha256": recorded_hash,
            "generation_status": generation_status,
            "pipeline_final_status": run["FINAL_STATUS"],
            "failure_stage": failure_stage,
            "failure_detail": failure_detail,
            "run_id": run["RUN_ID"],
            "generation_timestamp": run.get("FINISHED_UTC") or run.get("STARTED_UTC"),
            "model_identifier": config["models"]["generator"],
            "generation_config_identifier": config["pipeline_version"],
            "prompt_config_identifier": config["paths"]["prompt_directory"],
            "r13_contract_identifier": run.get("VOCABULARY_LOCK_ID") or queue["development_vocabulary_id"],
            "queue_identifier": queue["queue_id"],
            "run_metadata_path": str((run_dir / "tables/runs.csv").relative_to(repo)),
            "artifact_metadata_path": str((run_dir / "tables/artifacts.csv").relative_to(repo)),
            "context_pack_path": str(context_path.relative_to(repo)),
        })
    extra = sorted(set(run_records) - set(expected_requirements))
    if extra:
        raise PreflightError(f"Unexpected RUN01 requirements for {configuration}: {extra}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(output_path)
    return records


def load_generated_manifest(path: Path, configuration: str) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    keys = [row["requirement_id"] for row in rows]
    if len(keys) != len(set(keys)):
        raise PreflightError(f"Duplicate requirement IDs in generated manifest: {path}")
    if any(row.get("configuration") != configuration for row in rows):
        raise PreflightError(f"Configuration mismatch in generated manifest: {path}")
    return rows


def validate_generated_manifest(
    repo: Path, benchmark: Benchmark, configuration: str, rows: list[dict[str, Any]], strict_counts: bool = True
) -> dict[str, dict[str, Any]]:
    benchmark_sources = {c.requirement_id: c.source_id for c in benchmark.cases}
    by_requirement = {row["requirement_id"]: row for row in rows}
    if strict_counts and set(by_requirement) != set(benchmark.requirement_ids):
        missing = sorted(set(benchmark.requirement_ids) - set(by_requirement))
        extra = sorted(set(by_requirement) - set(benchmark.requirement_ids))
        raise PreflightError(f"Generated manifest coverage mismatch for {configuration}; missing={missing}, extra={extra}")
    for requirement_id, row in by_requirement.items():
        if row.get("source_id") != benchmark_sources.get(requirement_id):
            raise PreflightError(
                f"Generated/benchmark source identity mismatch for {configuration} {requirement_id}: "
                f"{row.get('source_id')} != {benchmark_sources.get(requirement_id)}"
            )
        path_value = row.get("generated_shacl_path")
        if path_value:
            path = repo / path_value
            if source_family(requirement_id) not in FAMILY_SOURCES:
                raise PreflightError(f"Unknown generated requirement identity: {requirement_id}")
            if path.exists() and row.get("generated_shacl_sha256") != sha256(path):
                raise PreflightError(f"Generated shape changed after manifest creation: {path}")
    return by_requirement


def select_cases(
    benchmark: Benchmark,
    requirement: str | None = None,
    family: str | None = None,
    case_id: str | None = None,
    smoke: bool = False,
) -> list[BenchmarkCase]:
    cases = benchmark.cases
    if requirement:
        cases = [item for item in cases if item.requirement_id == requirement]
    if family:
        normalized = "TRAFICOM" if family.upper() in {"TRF", "TRAFICOM"} else family.upper()
        cases = [item for item in cases if item.source_family == normalized]
    if case_id:
        cases = [item for item in cases if item.case_id == case_id]
    if smoke and not (requirement or family or case_id):
        first = cases[0].requirement_id if cases else None
        cases = [item for item in cases if item.requirement_id == first]
    if not cases:
        raise PreflightError("Development filter selected no benchmark cases")
    return cases
