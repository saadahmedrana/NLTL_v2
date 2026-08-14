from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .api.client import AaltoResponsesClient, ScriptedResponsesClient
from .config import PIPELINE_ROOT, PipelineConfig
from .errors import PipelineError
from .evaluator.bulk import BulkRdfEvaluator, EvaluationManifest
from .orchestration.runner import PipelineRunner, identifier
from .reporting.costs import terminal_cost_summary, write_cost_ledger
from .retrieval.context import VocabularyRepository
from .retrieval.fewshot import FewShotSelector


def offline_smoke_responses(requirement_id: str) -> dict[str, list[str]]:
    if requirement_id != "IMO26-014":
        raise ValueError("The auditable offline smoke fixture is currently defined for IMO26-014 only")
    wrong_shape = '''<BEGIN_SHACL>
@prefix gen: <urn:nltl:generated-shape:> .
@prefix nltl: <https://w3id.org/nltl-benchmark/vocab#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

gen:IMO26_014 a sh:NodeShape ;
    sh:targetClass nltl:ship ;
    sh:property [
        sh:path nltl:operatesOnlyInContinuousDaylight ;
        sh:datatype xsd:boolean ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] ;
    sh:sparql [
        sh:message "Two means of illumination are required unless operation is only in continuous daylight." ;
        sh:select """
            PREFIX nltl: <https://w3id.org/nltl-benchmark/vocab#>
            SELECT $this WHERE {
                $this nltl:operatesOnlyInContinuousDaylight ?daylight .
                FILTER (?daylight = false)
                FILTER NOT EXISTS {
                    $this nltl:visualIceDetectionLightCount ?count .
                    FILTER (?count >= 2)
                }
            }
        """
    ] .
<END_SHACL>'''
    correct_shape = wrong_shape.replace("visualIceDetectionLightCount", "visualIceDetectionIlluminationMeansCount")
    return {
        "generator": [wrong_shape, correct_shape],
        "validator": [
            '{"accept":false,"activate_variable_matcher":true,"feedback":"Replace visualIceDetectionLightCount with the verified canonical property for the number of illumination means used for visual ice detection."}',
            '{"accept":true,"activate_variable_matcher":false,"feedback":"The conditional minimum-count logic, target, datatype, and canonical vocabulary are suitable for later RDF evaluation."}',
        ],
        "vocabulary_matcher": [
            '{"match_found":true,"canonical_local_name":"visualIceDetectionIlluminationMeansCount","canonical_iri":"https://w3id.org/nltl-benchmark/vocab#visualIceDetectionIlluminationMeansCount","feedback_appendix":"This indexed integer property exactly represents the number of illumination means for visual ice detection."}'
        ],
    }


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NLTL vocabulary-grounded SHACL generation pipeline")
    parser.add_argument("--config", type=Path, help="Optional pipeline configuration JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Verify code inputs and dependencies without reading the environment file")

    smoke = sub.add_parser("offline-smoke", help="Run the complete repair route using scripted local responses")
    smoke.add_argument("--requirement", default="IMO26-014")

    generate = sub.add_parser("generate", help="Run one live API generation")
    generate.add_argument("--requirement", required=True)
    generate.add_argument("--allow-deferred", action="store_true")

    batch = sub.add_parser("generate-batch", help="Run a live requirement queue sequentially")
    batch.add_argument("--queue", type=Path, required=True)
    batch.add_argument("--allow-deferred", action="store_true")

    evaluate = sub.add_parser("evaluate", help="Run frozen SHACL shapes against RDF graphs without an LLM")
    evaluate.add_argument("--manifest", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, help="Evaluation output root")
    sub.add_parser("cost-report", help="Rebuild the all-runs token and estimated-cost ledger without an API call")
    return parser


def report_project_cost(config: PipelineConfig) -> None:
    summary = write_cost_ledger(config)
    print(terminal_cost_summary(summary), file=sys.stderr, flush=True)
    if summary.workbook:
        print(f"[COST] LEDGER READY file={summary.workbook}", file=sys.stderr, flush=True)


def doctor(config: PipelineConfig) -> dict[str, Any]:
    vocabulary = VocabularyRepository(config)
    few_shots = FewShotSelector(config.path("few_shot_jsonl"))
    eligible = sum(1 for item in vocabulary.requirements.values() if vocabulary.is_generation_eligible(item))
    dependency_contracts = vocabulary.dependency_contracts
    complete_contracts = sum(
        item.get("status") == "COMPLETE" for item in dependency_contracts.values()
    )
    draft_contracts = len(dependency_contracts) - complete_contracts
    return {
        "status": "PASS",
        "pipeline_version": config.raw["pipeline_version"],
        "environment_file_accessed": False,
        "vocabulary_lock": vocabulary.lock_info,
        "requirements": len(vocabulary.requirements),
        "generation_eligible_requirements": eligible,
        "registry_terms": len(vocabulary.registry),
        "canonical_terms_including_infrastructure": len(vocabulary.all_terms),
        "few_shot_examples": len(few_shots.examples),
        "dependency_contracts": {
            "total": len(dependency_contracts),
            "complete": complete_contracts,
            "draft_or_review": draft_contracts,
        },
        "models": config.raw["models"],
        "requests_per_minute": config.raw["api"]["requests_per_minute"],
    }


def validate_batch_queue(queue: dict[str, Any], vocabulary_lock_id: str) -> tuple[list[str], int]:
    requirements = [str(item) for item in queue.get("requirements", [])]
    repetitions = int(queue.get("repetitions", 1))
    if not requirements or repetitions <= 0:
        raise ValueError("Batch queue needs non-empty requirements and positive repetitions")
    if len(requirements) != len(set(requirements)):
        raise ValueError("Batch queue contains duplicate requirement IDs")
    expected_vocabulary = str(queue.get("development_vocabulary_id", "")).strip()
    if expected_vocabulary and expected_vocabulary != vocabulary_lock_id:
        raise ValueError(
            "Batch queue vocabulary does not match the active configuration: "
            f"queue={expected_vocabulary}, active={vocabulary_lock_id}"
        )
    return requirements, repetitions


def main(argv: list[str] | None = None) -> None:
    args = make_parser().parse_args(argv)
    try:
        config = PipelineConfig.load(args.config)
        if args.command == "doctor":
            print(json.dumps(doctor(config), indent=2, ensure_ascii=True))
            return
        if args.command == "cost-report":
            summary = write_cost_ledger(config)
            print(terminal_cost_summary(summary), file=sys.stderr, flush=True)
            print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=True))
            return
        if args.command == "evaluate":
            manifest = EvaluationManifest.load(args.manifest)
            output = args.output or config.path("outputs") / "evaluations"
            result = BulkRdfEvaluator(config).evaluate(manifest, output)
            print(json.dumps({"status": "PASS", "output": str(result)}, indent=2))
            return

        runner = PipelineRunner(config, live_progress=True)
        if args.command == "offline-smoke":
            client = ScriptedResponsesClient(offline_smoke_responses(args.requirement))
            result = runner.run_requirement(args.requirement, client)
            report_project_cost(config)
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=True))
            return

        client = AaltoResponsesClient(config)
        if args.command == "generate":
            result = runner.run_requirement(
                args.requirement,
                client,
                allow_deferred=args.allow_deferred,
            )
            report_project_cost(config)
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=True))
            return

        queue_path = args.queue.resolve()
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        requirements, repetitions = validate_batch_queue(
            queue,
            str(runner.vocabulary.lock_info.get("lock_id", "")),
        )
        session_id = identifier("SESSION-BATCH")
        results = []
        total_items = repetitions * len(requirements)
        print(
            f"[BATCH] START session={session_id} requirements={len(requirements)} "
            f"repetitions={repetitions} total_items={total_items}",
            file=sys.stderr,
            flush=True,
        )
        item_number = 0
        for repetition in range(1, repetitions + 1):
            for requirement_id in requirements:
                item_number += 1
                print(
                    f"[BATCH] ITEM {item_number}/{total_items} requirement={requirement_id} "
                    f"repetition={repetition}",
                    file=sys.stderr,
                    flush=True,
                )
                try:
                    result = runner.run_requirement(
                        str(requirement_id),
                        client,
                        allow_deferred=args.allow_deferred,
                        session_id=session_id,
                    )
                    payload = result.to_dict()
                    payload["repetition"] = repetition
                    results.append(payload)
                    print(
                        f"[BATCH] ITEM DONE {item_number}/{total_items} requirement={requirement_id} "
                        f"status={result.status} attempts={result.attempts}",
                        file=sys.stderr,
                        flush=True,
                    )
                except Exception as exc:
                    results.append({
                        "requirement_id": requirement_id,
                        "repetition": repetition,
                        "status": "BATCH_ITEM_ERROR",
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    print(
                        f"[BATCH] ITEM ERROR {item_number}/{total_items} requirement={requirement_id} "
                        f"error_type={type(exc).__name__}",
                        file=sys.stderr,
                        flush=True,
                    )
        accepted_count = sum(1 for item in results if item.get("accepted") is True)
        print(
            f"[BATCH] FINISH session={session_id} accepted={accepted_count}/{total_items}",
            file=sys.stderr,
            flush=True,
        )
        report_project_cost(config)
        print(json.dumps({"session_id": session_id, "results": results}, indent=2, ensure_ascii=True))
    except KeyboardInterrupt:
        try:
            report_project_cost(config)
        except Exception as cost_exc:
            print(f"[COST] WARNING could not refresh ledger: {type(cost_exc).__name__}: {cost_exc}", file=sys.stderr)
        print("Run interrupted safely; completed JSONL events remain in the run folder.", file=sys.stderr)
        raise SystemExit(130)
    except (PipelineError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
