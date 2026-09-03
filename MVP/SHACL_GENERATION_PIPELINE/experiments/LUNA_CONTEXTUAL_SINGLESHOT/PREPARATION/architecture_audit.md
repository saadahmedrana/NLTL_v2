# LUNA_CONTEXTUAL_SINGLESHOT architecture audit

## Frozen full-pipeline reference

The reference condition is `experiments/FINAL_LUNA_MAIN/`. Its ten configurations use `VOCAB-LOCK-2026-08-22-R13`, the frozen 268-item queue, `gpt-5.6-luna-2026-07-09` for every LLM role, two few-shots, and four maximum semantic attempts. This directory was inspected read-only.

## Actual execution trace

1. `src/nltl_pipeline/cli.py::main` loads the JSON configuration with `PipelineConfig.load`, validates the batch queue with `validate_batch_queue`, instantiates `PipelineRunner` and `AaltoResponsesClient`, and invokes `PipelineRunner.run_requirement` for every queue item.
2. `src/nltl_pipeline/orchestration/runner.py::PipelineRunner.run_requirement` verifies generation eligibility and the COMPLETE dependency-contract gate.
3. `src/nltl_pipeline/retrieval/context.py::VocabularyRepository.build_context_pack` loads the frozen requirement, source/normalized text, category, verification/dependency contract, canonical terms, owner/path/node patterns, formulas/tables, applicability and usage policy.
4. `src/nltl_pipeline/retrieval/fewshot.py::FewShotSelector.select` selects the configured two examples from the locked R13 JSONL asset.
5. `src/nltl_pipeline/prompts.py::PromptFactory.generator_user` constructs the first generator user prompt. The developer prompt is the unchanged `generator.txt` loaded by `PromptFactory`. Before the first call, `repairFeedback` is `NONE`.
6. `src/nltl_pipeline/api/client.py::AaltoResponsesClient.call` builds the Responses API request. It supplies the developer and user text, selects the configured role model, and applies the role's `max_output_tokens`.
7. `src/nltl_pipeline/validation/shacl.py::extract_shacl` parses the exact `BEGIN_SHACL` / `END_SHACL` response contract. `ShaclStaticValidator.validate_raw` performs extraction and then `validate_turtle`.
8. `ShaclStaticValidator.validate_turtle` performs RDF/Turtle parsing, SHACL structure/meta-SHACL checks, embedded SPARQL parsing/runtime smoke checks, canonical-vocabulary scope checks, datatype/unit checks, target/path checks and deterministic contract policy checks.
9. If the failure is syntactic, `PipelineRunner.run_requirement` calls `PromptFactory.syntax_repair_user` and the `syntax_repair` LLM. The syntax-repair loop is bounded by `maximum_syntax_repairs_per_semantic_attempt` and does not consume a semantic attempt.
10. Once syntax parses, `PromptFactory.validator_user` constructs the semantic-validator request. `_call_and_parse` invokes the `validator` LLM and validates its one-line JSON response with `parse_validator_decision`.
11. When requested, `CandidateSearcher.search` supplies deterministic candidates and `_call_and_parse` invokes the `vocabulary_matcher` LLM; verified terms are appended to the next context/repair feedback.
12. The outer loop in `PipelineRunner.run_requirement` regenerates with accumulated feedback. `generation.maximum_semantic_attempts` bounds this loop.
13. `src/nltl_pipeline/telemetry/events.py::EventLogger` writes append-only `events.jsonl` and artifacts. `src/nltl_pipeline/reporting/tracker.py::TrackerExporter` derives CSV tables and the workbook. Batch session results are written by `src/nltl_pipeline/cli.py::main`.

## First-call information boundary

The first generator request contains the full generator developer instructions plus a sorted JSON user payload containing:

- frozen R13 requirement and source/normalized text;
- classification and verification/dependency contract;
- scoped allowed canonical vocabulary;
- node/owner/path patterns;
- formula, operand, result, table and applicability material present in the contract;
- selection and vocabulary-usage policies;
- the same two retrieved few-shot examples;
- the same generated-shape namespace;
- `repairFeedback: NONE`.

No validator output, matcher output, syntax-repair output or later expanded vocabulary is available before this first call.

## Isolated ablation path

`src/nltl_pipeline/orchestration/singleshot.py::ContextualSingleShotRunner` reuses `PipelineRunner` initialization, `VocabularyRepository`, `FewShotSelector`, `PromptFactory`, `ShaclStaticValidator`, `EventLogger` and `TrackerExporter. It renders the request through `render_first_generator_request`, calls only role `generator` once, saves the exact response, and runs diagnostics without feeding them to any model.

The CLI commands `contextual-single-shot` and `contextual-single-shot-batch` select this runner. Existing `generate`, `generate-batch`, `offline-smoke`, `evaluate` and `doctor` routes remain unchanged.
