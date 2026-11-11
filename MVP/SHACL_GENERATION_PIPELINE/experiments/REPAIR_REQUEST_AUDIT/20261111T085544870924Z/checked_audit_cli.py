#!/usr/bin/env python3
"""Audit the selected FULL_REPAIR_V2 config offline; never create a live client."""
from __future__ import annotations

import argparse
import copy
import json
import socket
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nltl_pipeline.cli import offline_smoke_responses
from nltl_pipeline.config import PipelineConfig, sha256_file
from nltl_pipeline.orchestration.repair_request_audit import (
    AuditedScriptedClient, RepairRequestIntegrityError, require,
)
from nltl_pipeline.orchestration.runner import PipelineRunner

ACCEPT = '{"accept":true,"activate_variable_matcher":false,"currentIssues":[]}'


def rejection(version: int, vocabulary: bool = False) -> str:
    return json.dumps(dict(accept=False, activate_variable_matcher=vocabulary,
        currentIssues=[dict(category="CANONICAL_VOCABULARY" if vocabulary else "OFFLINE_CANARY",
            location=f"offline candidate version {version}",
            problem=f"Synthetic routing canary {version}; not a regulatory evaluation.",
            required_change="Use visualIceDetectionIlluminationMeansCount." if vocabulary else f"Apply local canary change {version}.",
            regression_guard=f"Preserve canary change {version}.", blocking=True,
            needs_vocabulary_resolution=vocabulary)]))


def scenarios() -> dict:
    original = offline_smoke_responses("IMO26-014")
    a = original["generator"][1]
    b = a.replace("gen:IMO26_014", "gen:IMO26_014_V2")
    c = a.replace("gen:IMO26_014", "gen:IMO26_014_V3")
    d = a.replace("gen:IMO26_014", "gen:IMO26_014_V4")
    wrong_type = a.replace("sh:datatype xsd:boolean", "sh:datatype xsd:integer")
    large = a.replace("gen:IMO26_014", "# HEAD_CANARY_α\n" + "# full previous code must survive rendering αβγ\n" * 4000 + "gen:IMO26_014")
    large = large.replace("<END_SHACL>", "# TAIL_CANARY_Ω\n<END_SHACL>")
    return {
        "semantic_latest_version": dict(generator=[a, b, c], validator=[rejection(1), rejection(2), ACCEPT]),
        "static_no_matcher": dict(generator=[wrong_type, b], validator=[ACCEPT]),
        "canonical_static_matcher": dict(generator=[original["generator"][0], b],
            vocabulary_matcher=original["vocabulary_matcher"], validator=[ACCEPT]),
        "canonical_semantic_matcher": dict(generator=[a, b],
            validator=[rejection(1, True), ACCEPT], vocabulary_matcher=original["vocabulary_matcher"]),
        "syntax_then_semantic": dict(generator=[a, "MALFORMED_CANDIDATE_VERSION_2", d],
            syntax_repair=["MALFORMED_CANDIDATE_VERSION_3", c],
            validator=[rejection(1), rejection(2), ACCEPT]),
        "fresh_escape_hatch": dict(generator=[a, b, a, d],
            validator=[rejection(1), rejection(1), rejection(1), ACCEPT]),
        "large_candidate": dict(generator=[large, b], validator=[rejection(1), ACCEPT]),
    }


def run_scenario(config: PipelineConfig, folder: Path, name: str,
                 responses: dict, fault: str | None = None) -> dict:
    raw = copy.deepcopy(config.raw)
    # No generation budget, model, prompt or locked input override is allowed.
    raw["paths"]["outputs"] = str(folder / "runner_output")
    raw["reporting"]["excel_enabled"] = False
    effective = PipelineConfig(raw=raw, config_path=config.config_path)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "effective_config.json").write_text(json.dumps(raw, indent=2) + "\n")
    runner = PipelineRunner(effective)
    client = AuditedScriptedClient(responses, effective.path("outputs"))
    validate_raw = runner.static_validator.validate_raw
    syntax_diagnostics = runner.static_validator.syntax_repair_diagnostics
    render_repair = runner.prompts.semantic_repair_user
    rendered_count = 0
    first_candidate = None
    first_issues = None

    def observed_validation(raw_text, context):
        turtle, report = validate_raw(raw_text, context)
        client.observe_validation(raw_text, turtle, report)
        return turtle, report

    def observed_syntax(raw_text, turtle, report):
        diagnostics = syntax_diagnostics(raw_text, turtle, report)
        client.observe_syntax_diagnostics(raw_text, report, diagnostics)
        return diagnostics

    def rendered(*args, **kwargs):
        nonlocal rendered_count, first_candidate, first_issues
        user = render_repair(*args, **kwargs)
        payload = json.loads(user)
        rendered_count += 1
        if first_candidate is None:
            first_candidate = payload["previousCandidateShacl"]
            first_issues = payload["currentIssues"]
        if fault == "absent":
            payload.pop("previousCandidateShacl")
        elif fault == "truncated":
            payload["previousCandidateShacl"] = payload["previousCandidateShacl"][:128]
        elif fault == "stale" and rendered_count == 2:
            payload["previousCandidateShacl"] = first_candidate
        elif fault == "stale_feedback" and rendered_count == 2:
            payload["currentIssues"] = first_issues
        elif fault == "repair_disguised_as_fresh":
            payload["task"] = "Fresh regeneration escape hatch after targeted repair became stuck"
            payload.pop("previousCandidateShacl")
        return json.dumps(payload, indent=2, ensure_ascii=True)

    caught = None
    result = None
    try:
        with patch.object(runner.static_validator, "validate_raw", side_effect=observed_validation), \
             patch.object(runner.static_validator, "syntax_repair_diagnostics", side_effect=observed_syntax), \
             patch.object(runner.prompts, "semantic_repair_user", side_effect=rendered):
            result = runner.run_requirement("IMO26-014", client)
    except RepairRequestIntegrityError as exc:
        caught = str(exc)
        if fault is None:
            raise
    finally:
        (folder / "request_ledger.json").write_text(json.dumps(client.requests, indent=2, ensure_ascii=False) + "\n")
    if fault:
        require(caught is not None, f"Negative control {fault} was not rejected")
    else:
        require(result is not None and result.accepted, f"Offline scenario {name} did not finish")
        require(all(r["checked"] for r in client.requests), "Unaudited request")
        for request in client.requests:
            if request.get("mode") in {"STATIC_REPAIR", "MATCHER_ASSISTED_REPAIR", "SEMANTIC_CANDIDATE_REPAIR", "FRESH_REGENERATION_ESCAPE_HATCH"}:
                parent = Path(request["runner_prompt_artifact"]).parent
                metadata = json.loads((parent / "attempt_metadata.json").read_text())
                require(metadata["mode"] == request["mode"], "Actual runner mode differs from audited repair route")
    return dict(scenario=name, fault=fault, passed=True, expected_rejection=caught,
        requests=len(client.requests), modes=dict(Counter(r.get("mode", "REJECTED") for r in client.requests)),
        run_directory=str(result.run_directory) if result else None,
        request_ledger=str(folder / "request_ledger.json"))


def audit_config(path: Path, output: Path, *, include_negative_controls: bool = True) -> dict:
    config = PipelineConfig.load(path)
    require(config.raw.get("architecture") == "FULL_REPAIR_V2", "Select an explicit FULL_REPAIR_V2 config; no implicit default config")
    require(config.raw["generation"]["maximum_semantic_attempts"] >= 4,
            "Configured budget cannot exercise all four candidate/escape routes")
    require(config.raw["generation"].get("maximum_syntax_repairs_per_semantic_attempt", 0) >= 2,
            "Configured syntax budget cannot exercise chained syntax repair")
    output.mkdir(parents=True, exist_ok=False)
    (output / "DO_NOT_EVALUATE_SYNTHETIC.txt").write_text(
        "Scripted local canaries only. Not generated regulatory outputs or measured experiment results.\n")
    lock = config.verify_locked_inputs()
    protected = [config.config_path] + [config.path(n) for n in
        ["vocabulary_lock", "term_registry", "ontology", "requirement_evidence", "requirement_term_index", "few_shot_jsonl"]]
    protected += sorted((ROOT / "src/nltl_pipeline").rglob("*.py"))
    protected += sorted((ROOT / "prompts").rglob("*.txt"))
    hashes = {str(p): sha256_file(p) for p in protected}
    (output / "config_original.json").write_text(config.config_path.read_text())
    manifest = dict(config_path=str(config.config_path), config_sha256=sha256_file(config.config_path),
        architecture=config.raw["architecture"], generation_run=config.raw["generation_run"],
        runner="nltl_pipeline.orchestration.runner.PipelineRunner", locked_inputs=lock,
        generation=config.raw["generation"], models=config.raw["models"],
        prompt_directory=str(config.path("prompt_directory")),
        effective_prompt_sha256={name: sha256_file(ROOT / "prompts" / relative) for name, relative in
            [("generator", "r11/generator.txt"), ("syntax_repair", "syntax_repair.txt"),
             ("semantic_repair", "semantic_repair.txt"), ("validator", "validator.txt"),
             ("matcher", "r11/vocabulary_matcher.txt" if (ROOT / "prompts/r11/vocabulary_matcher.txt").exists() else "vocabulary_matcher.txt")]},
        overrides={"paths.outputs": "isolated per-scenario dry-run directory", "reporting.excel_enabled": False},
        api_calls=0, environment_file_read=False, source_sha256=hashes)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    runs = []
    # Defense in depth: even an accidental live-client addition cannot contact HTTP.
    with patch("requests.sessions.Session.request", side_effect=AssertionError("Network forbidden in repair audit")), \
         patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden in repair audit")):
        for name, responses in scenarios().items():
            runs.append(run_scenario(config, output / name, name, responses))
            (output / "progress.json").write_text(json.dumps(runs, indent=2) + "\n")
        if include_negative_controls:
            for fault in ["absent", "stale", "truncated", "stale_feedback", "repair_disguised_as_fresh"]:
                runs.append(run_scenario(config, output / ("reject_" + fault), "negative_control",
                    scenarios()["semantic_latest_version"], fault=fault))
                (output / "progress.json").write_text(json.dumps(runs, indent=2) + "\n")
    for p, expected in hashes.items():
        require(sha256_file(Path(p)) == expected, f"Audit changed protected input {p}")
    summary = dict(manifest, passed=True, scenarios=runs,
        negative_controls=sum(r["fault"] is not None for r in runs),
        normal_routes_passed=True, protected_inputs_unchanged=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "README.md").write_text(
        "# Repair request dry run\n\nOffline scripted responses; no environment secrets or API calls. "
        "The selected config, budgets, prompt sources and all source hashes are in manifest.json. "
        "Only output paths and Excel export differ from the selected config.\n\n"
        "Each scenario/request_ledger.json binds candidate SHA/version, saved feedback and route. "
        "Complete developer/user text is saved for every request under runner_output/complete_requests/ "
        "and by the real runner under artifacts/. Failed negative-control requests are retained too. "
        "Fresh escape-hatch generation is distinct and does not promise inclusion of previous code.\n\n"
        "This audits renderer/runner requests at the offline client boundary, not live provider delivery "
        "or automated repair quality. It does not install a live transport guard or change generation logic.\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "experiments/REPAIR_REQUEST_AUDIT" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    summary = audit_config(args.config.resolve(), output.resolve())
    print(json.dumps(dict(passed=summary["passed"], config=summary["config_path"],
        output=str(output.resolve()), scenarios=len(summary["scenarios"]), api_calls=0), indent=2))


if __name__ == "__main__":
    main()
