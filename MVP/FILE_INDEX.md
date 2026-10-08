# File index

The ZIP root contains `METHODS_EVIDENCE.md`, this index, `MISSING_EVIDENCE.md`, and `methods_evidence_support/`. Paths below are bundle-relative. Original paths are relative to `MVP/`. No `.env`, credential, API key, private blinding key, full output tree, model weight, virtual environment, cache, `.git`, regulatory PDF, or complete fixture corpus is included.

## 01_main_ablation

### Configurations

Each file is the saved RUN_01 configuration used to identify models, role assignments, limits, retries, and ablation switches. Originals are respectively in `SHACL_GENERATION_PIPELINE/experiments/FINAL_LUNA_MAIN/CONFIGS/`, `.../FULL_REPAIR_V2/CONFIGS/`, `.../LUNA_NO_SEMANTIC_VALIDATOR/CONFIGS/`, and `.../LUNA_CONTEXTUAL_SINGLESHOT/CONFIGS/`:

- `configs/pipeline.final-luna-main-run01.json`
- `configs/pipeline.full-repair-v2-run01.json`
- `configs/pipeline.luna-no-semantic-validator-run01.json`
- `configs/pipeline.luna-contextual-singleshot-run01.json`

### Behavioural evaluation identity/results

- `evaluations/historical/run_manifest.json` and `behavioral_summary.json` — originals: `SHACL_GENERATION_PIPELINE/evaluation/experiment_results/BEHAVIORAL-R13-20260911T080233539977Z/`; establishes the historical FULL/NO_SEMANTIC/SINGLESHOT evaluation, commit, hashes, options, totals, and results.
- `evaluations/revised_v2/run_manifest.json` and `behavioral_summary.json` — originals: `.../BEHAVIORAL-R13-FULL-REPAIR-V2-RUN01-20260915T144116505813Z/`; establishes revised official V2.
- `evaluations/rejected_attempt4/run_manifest.json` and `behavioral_summary.json` — originals: `.../BEHAVIORAL-R13-FULL-REPAIR-V2-REJECTED-A4-RUN01-20260915T155743340362Z/`; establishes the 25-candidate diagnostic supplement.

### Generation and operational manifests

- `manifests/full_repair_v2_generated_rules.jsonl` — original `SHACL_GENERATION_PIPELINE/evaluation/generated_rule_manifests/RUN_01/full_repair_v2_generated_rules.jsonl`; official revised artifact map.
- `manifests/full_repair_v2_rejected_attempt4_diagnostic.jsonl` — original `.../RUN_01/full_repair_v2_rejected_attempt4_diagnostic.jsonl`; the 25 fallback-policy candidates.
- `manifests/no_semantic_generated_rules.jsonl` — original `.../RUN_01/no_semantic_generated_rules.jsonl`; selected ablation artifact map.
- `manifests/singleshot_generated_rules.jsonl` — original `.../RUN_01/singleshot_generated_rules.jsonl`; selected single-shot artifact map.
- `manifests/full_repair_v2_batch_result.json` — original `SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/RUN_01/sessions/SESSION-BATCH-20260915T092108806520Z/batch_result.json`; 268-item revised-batch completion summary.
- `manifests/final_luna_main_git_commit.txt` and `final_luna_main_git_status_before.txt` — originals in `SHACL_GENERATION_PIPELINE/experiments/FINAL_LUNA_MAIN/MANIFESTS/`; generation commit/status provenance.

### Aggregate generation summaries

- `analysis/full/MASTER_SUMMARY.md`, `analysis_manifest.json`, `api_timing_cost_summary.csv`, `experiment_integrity.json` — originals in `SHACL_GENERATION_PIPELINE/experiments/FINAL_LUNA_MAIN/ANALYSIS_10RUN/`; ten-run operational completeness, normalized configuration/queue/R13 hashes, timing, tokens, and configured cost.
- `analysis/no_semantic/MASTER_SUMMARY.md`, `analysis_manifest.json`, `api_timing_cost_summary.csv`, `experiment_integrity.json`, `full_vs_no_semantic_operational_comparison.csv` — originals in `SHACL_GENERATION_PIPELINE/experiments/LUNA_NO_SEMANTIC_VALIDATOR/ANALYSIS_10RUN/`; corresponding ablation aggregates and comparison.
- `analysis/singleshot/MASTER_SUMMARY.md`, `analysis_manifest.json`, `overall_statistics.json` — originals in `SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/ANALYSIS_RUN01/`; establishes formal RUN_01 versus placeholder directories and single-shot output statistics.

## 02_benchmark

- `verify_full_benchmark_integrity_final.py` — original repository-root `verify_full_benchmark_integrity_final.py` (`../verify_full_benchmark_integrity_final.py` from `MVP/`); executable integrity/totals/coverage checks.
- `behavioral_benchmark_README.md` — original `SHACL_GENERATION_PIPELINE/evaluation/behavioral_benchmark/README.md`; fixture-construction and lock protocol.
- `README_I2_BATCH_A.md`, `i2_batch_a_manifest.jsonl`, `i2_batch_a_fixture_lock.json` — originals under `SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13/`; one representative fixture-family protocol, manifest schema, and cryptographic lock. The RDF files themselves are intentionally omitted.
- `VERIFICATION_POLICY_R13.md` and `benchmark_vocabulary_stage2_LOCK-2026-08-22-R13.lock.json` — originals `BENCHMARK_VOCABULARY/FINAL_LOCK_R13/evidence/VERIFICATION_POLICY_R13.md` and `BENCHMARK_VOCABULARY/FINAL_LOCK_R13/benchmark_vocabulary_stage2_LOCK-2026-08-22-R13.lock.json`; eligibility/category policy and frozen vocabulary/context hash manifest.
- `r13_direct_calculation_completeness.json` — original `BENCHMARK_VOCABULARY/FINAL_LOCK_R13/validation/r13_direct_calculation_completeness.json`; direct-calculation coverage evidence.
- `few_shots_README.md` and `VALIDATION_REPORT.md` — originals under `BENCHMARK_VOCABULARY/FINAL_LOCK_R13/few_shots/`; synthetic library status, validation, and non-benchmark-ground-truth provenance.

## 03_model_comparison

- `README.md` — original `SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/README.md`; experiment scope, final/smoke distinction, modes, and workflow.
- `configs/sol.json`, `gemini.json`, `gpt_oss.json` — originals in that experiment's `CONFIGS/`; exact models, expected endpoints, and same-model role assignments. Luna is governed by the revised V2 config in `01_main_ablation`.
- `manifests/sample_50.json`, `manual_audit_20.json`, `smoke_2.json`, `manifest_lock.json`, `configuration_lock.json` — originals in `.../MANIFESTS/`; deterministic samples/seeds, sample/config/code/prompt hashes, and integrity locks.
- `manifests/extraction_manifest.json` — original `.../REFERENCE/LUNA/extraction_manifest.json`; Luna reference extraction provenance and no-generation/no-evaluation statement.
- `generation_manifests/sol_run_manifest.json`, `gemini_run_manifest.json`, `gpt_oss_run_manifest.json` — originals `.../OUTPUTS/FINAL/<model>/scaling_control/run_manifest.json`; final non-Luna generation-control identity/completeness.
- `results/combined_summary.json` — original `.../OUTPUTS/RDF_EVALUATION/combined_summary.json`; aggregate results for all eight final cells.
- `results/FIRST_GENERATION/{luna,sol,gemini,gpt_oss}_run_manifest.json` — originals `.../OUTPUTS/RDF_EVALUATION/FIRST_GENERATION/<model>/run_manifest.json`; per-cell evaluation identity, versions, totals, and confusion matrices.
- `results/SELF_REPAIR_FINAL/{luna,sol,gemini,gpt_oss}_run_manifest.json` — originals in the corresponding `SELF_REPAIR_FINAL/<model>/` directories; same purpose for final repaired artifacts.

### Model-comparison scripts

All are copied from `SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/`:

- `freeze_samples.py` — deterministic stratification, Hamilton allocation, and seed hashing.
- `freeze_configuration.py` — configuration/prompt/code locking.
- `experiment.py` — control-run orchestration.
- `provider_clients.py` — Responses/Chat Completions payload and retry behaviour.
- `extract_luna_subset.py` — Luna artifact extraction.
- `run_rdf_evaluation.py`, `rdf_evaluation_common.py`, `run_all_rdf_evaluations.sh` — artifact selection, first-response normalization, and final RDF evaluation dispatch.
- `summarize.py`, `summarize_rdf_evaluations.py` — generation/evaluation aggregation.
- `build_manual_audit_packets.py`, `build_blinded_manual_audit_10.py`, `build_blinded_manual_audit_workbook.mjs` — manual-audit selection, blinding, packet, and workbook construction.

### Scaling audit protocol

- `audit/selection_manifest.json` — original `.../MANUAL_AUDIT_SCALING_10/selection_manifest.json`; 10-requirement strata, seeds, artifact statuses, and opaque ordering.
- `audit/README.md` — original in the same directory; scoring/blinding protocol.
- `audit/batch_manifest.json` and `audit/scoring_template.xlsx` — originals in `.../MANUAL_AUDIT_SCALING_10/BATCH_01/`; blinded slot manifest and rubric/anchors. The private identity key and scored master workbook are omitted.

## 04_evaluator

- `experiment_runner/core.py`, `execution.py`, `analysis.py` — originals in `SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/`; manifest loading, pySHACL execution/options, outcome conventions, denominators, and requirement aggregation.
- `scripts/run_behavioral_evaluation.py` — original `SHACL_GENERATION_PIPELINE/evaluation/run_behavioral_evaluation.py`; main behavioural-evaluation entry point.
- `scripts/run_full_candidate_diagnostics.py` — original beside the above; diagnostic candidate evaluation.
- `scripts/run_rejected_attempt4_diagnostic.py` — original beside the above; exact 25-candidate fallback diagnostic construction.

## 05_manual_audit

- `CODEX_PREPARE_AUDIT.txt`, `README.txt`, `README_AUTOMATIC_EVIDENCE.txt` — originals in `SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/`; audit selection, eligible run pools, blinding/packaging, label-change rules, and status caveats.
- `audit_selection.json` — original in the same directory; full deterministic 268-requirement/536-case main-audit selection. It is the largest supporting file but compresses well and establishes per-case provenance.
- `automatic_summary_r2.json` — original in the same directory; compact automatic triage/status summary.
- `packet_manifest.json` — original in the same directory; batch packaging identity and hashes.
- `scripts/package_audit.py`, `enrich_automatic_evidence.py`, `update_workbook.mjs`, `verify_audit.py`, `verify_workbook.mjs` — originals in `.../AUDIT_20260915/scripts/`; selection/packaging, evidence enrichment, workbook updates, and consistency checks. The large audit workbook is intentionally omitted because the receiving chat already has it.

## 06_example_logs

These are representative schema examples only, not a sample for quantitative analysis. Each was scanned for common credential/key patterns before copying.

- `accepted/events.jsonl`, `accepted/runs.csv` — originals under `SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/RUN_01/runs/RUN-I2-001-20260915T092108806675Z/`; accepted first-candidate run event and run-table schema.
- `repaired/events.jsonl`, `repaired/runs.csv`, `repaired/attempt_02_metadata.json`, `repaired/attempt_02_repair_diff.json` — originals under `.../RUN-I2-006-20260915T092305368296Z/`; successful semantic-repair example and provenance.
- `unsuccessful_fallback/events.jsonl`, `unsuccessful_fallback/runs.csv`, `unsuccessful_fallback/attempt_04_metadata.json`, `unsuccessful_fallback/last_candidate_metadata.json` — originals under `.../RUN-I2-008-20260915T092418840618Z/`; four-attempt unsuccessful run whose last diagnostic candidate participates in the fallback policy.

## 07_dependencies

- `pyproject.toml` and `requirements.txt` — originals in `SHACL_GENERATION_PIPELINE/`; declared package metadata and dependency ranges. These are not a complete installed-environment lock.

## Deliberate omissions

Full generation/evaluation output directories, all 2,186 RDF fixtures, all requirement contracts, the already-held R13 context package, regulatory PDFs, large workbooks, full prompts/responses, model weights, caches, virtual environments, `.git`, `.DS_Store`, temporary Office files, `.env` files, API keys, and `MANUAL_AUDIT_SCALING_10/PRIVATE/BLINDING_KEY.csv` are excluded. Nothing essential was silently truncated: omitted evidence is either already held by the receiving chat, redundant/large, private, or explicitly called out in `MISSING_EVIDENCE.md`.
