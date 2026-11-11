# Repository cleanup audit — review only

Audit date: 2026-10-28 (Europe/Helsinki). All project paths below are exact paths **relative to the Git root** `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2`. The audit directory is `MVP/cleanup_audit_2026-10-28/`.

**No pre-existing project file was deleted, moved, renamed, modified, restored, staged or unstaged. No commit, push, history rewrite, project pipeline execution, result regeneration, package installation or API call was performed.** Only audit artifacts were written. This report proposes actions for a separately authorized task; it is not authorization to execute them.

## Outcome and scope

The conservative proposal is **154 exact file paths**, totaling **70,172,910 bytes (70.17 MB / 66.92 MiB)** of logical working-tree content. Thirteen are tracked ZIP containers (68,657,023 bytes); the remaining 141 are already ignored metadata/caches. There are no proposed source, vocabulary, ontology, regulation, benchmark, result, generated-SHACL, response, log, assessment, timing or figure-data deletions. For ZIPs, deletion is proposed only for the redundant container: its substantive member bytes remain at the exact counterpart paths recorded in the archive inventory.

**The main generation default is still R5, not R13.** `config.py` sets `DEFAULT_CONFIG` to `config/pipeline.json`, whose lock is R5. The authoritative final R13 configuration is `config/pipeline.official-r13.json`; experiment configurations select their frozen variants explicitly. This audit did not change defaults. Both main READMEs describe older R1/R2-era inputs and should eventually be corrected in a separate authorized documentation task.

`file_inventory.csv.gz` is the complete per-file decision table, sorted into KEEP, PROPOSE DELETE and NEEDS REVIEW. It has one row for every present file/symlink and every pre-existing missing tracked path, including exact paths, byte sizes, Git tracking state, SHA-256, purpose, justification, replacement, dependencies, confidence and reproduction risk. `cleanup_candidates.csv.gz` is the complete filtered candidate list. `proposed_deletions.csv` and the final section of this report are the approval list. NEEDS REVIEW always means retain pending review.

| Decision | Records | Present logical bytes |
|---|---|---|
| KEEP | 368232 | 19,601,594,559 |
| PROPOSE DELETE | 154 | 70,172,910 |
| NEEDS REVIEW | 66 | 5,099,481 |
## Recorded repository state

- Actual Git root: `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2`; requested starting directory: `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP`.
- Branch: `main`. HEAD: `58fd9b39c193a31be440656319da6ae337452657`.
- Applicable `AGENTS.md`: none found in the repository, its traversed project subdirectories, or the ancestor locations `/`, `/Users`, the user's home, Desktop, `Journal 1`, and `NLTL_v2`. Git internals and external symlink targets were not traversed.
- Inventory: 368,422 present file/symlink records plus 30 pre-existing tracked deletions; 19,676,866,950 logical bytes. Symlink sizes/hashes refer to **link-target strings**, not external target contents. Seven tracked `node_modules` directory symlinks were explicitly recorded without following them.
- Present tracking states: 350,802 tracked, 45 untracked, 17,575 ignored. Hidden files and both local `.venv` trees are included. `.git` and this newly created audit directory are excluded from the project inventory.
- Existing user state: 30 tracked research files deleted, 45 untracked project files; no staged changes shown. Complete initial porcelain status is in `state.json`, not abbreviated here.
- `preservation_verification.json` records the final HEAD/status comparison and metadata check of every original present path, with any changed size/mtime rehashed. It excludes only new audit artifacts from status comparison.

The 30 missing tracked artifacts are the former `MVP/outputs/accuracy_runtime_figure_20261021_115034_600331/` and `MVP/outputs/model_comparison_evidence/20261021_112541_EEST/` files. Corresponding untracked files exist under `MVP/ocean_reporting/outputs/results_layout_variants_20261015_150529_094578/scaling outputs/`. Twenty match HEAD bytes exactly. Ten CSVs differ in newline representation; all 30 match after CRLF-to-LF normalization. This establishes content similarity, **not** authorization for their relocation or deletion. Exact original paths, HEAD sizes/hashes, counterpart paths and newline comparisons are in `missing_file_comparisons.csv`. All remain NEEDS REVIEW; all present counterparts remain protected.

## Active pipeline and authority map

The following paths are under `MVP/SHACL_GENERATION_PIPELINE/` unless prefixed otherwise.

| Stage | Entry/module/config | Inputs and behavior |
|---|---|---|
| Entry points | run_pipeline.py; src/nltl_pipeline/__main__.py; pyproject.toml console script nltl-pipeline | Both delegate to nltl_pipeline.cli.main; local source path is inserted by run_pipeline.py. |
| Configuration and input gate | src/nltl_pipeline/config.py; config/pipeline.official-r13.json | Paths resolve relative to pipeline root, including configs stored under experiments. Four core input hashes are verified; few-shot existence is checked. Config metadata does not cause every lock field to be checked. |
| Retrieval | src/nltl_pipeline/retrieval/context.py; retrieval/fewshot.py | VocabularyRepository loads lock, registry, ontology, evidence and requirement/dependency index; deterministic requirement scoping and few-shot selection. |
| Generation and feedback | src/nltl_pipeline/orchestration/runner.py; orchestration/repair.py; api/client.py | PipelineRunner, static validation, syntax-only repair, semantic review and repair memory/escape hatch; optional vocabulary matcher. Live API/environment access only through explicitly live execution. |
| Deterministic gates | src/nltl_pipeline/validation/shacl.py; validation/contracts.py; validation/sparql_extensions.py | Turtle/SHACL checks, canonical vocabulary, datatypes, units, dependency contracts, runtime/meta validation and recovery diagnostics. |
| Prompts | src/nltl_pipeline/prompts.py; prompts/r11/; prompts/validator.txt; prompts/semantic_repair.txt; prompts/syntax_repair.txt; prompts/vocabulary_matcher.txt | Current PromptFactory centrally reads validator and semantic_repair from prompts/, even with an old prompt_directory; generation/syntax/matcher use selected-directory files with root fallback. Preserve all prompts and snapshots. |
| Ablations/baselines | src/nltl_pipeline/orchestration/no_semantic_validator.py; orchestration/singleshot.py; experiments/LUNA_NO_SEMANTIC_VALIDATOR/; experiments/LUNA_CONTEXTUAL_SINGLESHOT/ | CLI no-semantic-validator[-batch] and contextual-single-shot[-batch] preserve independent experiment definitions; syntax checking/repair differs by baseline. |
| Historical baseline | MVP/OLD FILES/src/pipeline/; MVP/OLD FILES/src/api/; MVP/OLD FILES/src/processing/; MVP/OLD FILES/src/prompts/ | run_pipeline.py and run_pipeline_experiment* / run_experiments* variants, input/ship graph/few-shot data and historical analysis remain protected. OLD FILES is not a deletion recommendation. |
| Bulk RDF evaluation | evaluation/run_behavioral_evaluation.py; evaluation/experiment_runner/core.py, execution.py, analysis.py; evaluation/run_full_candidate_diagnostics.py; evaluation/run_rejected_attempt4_diagnostic.py | Separate from generation; frozen generated-rule identities and 268-requirement/2,186-case benchmark; explicit family manifests and lock globs, not a blanket vocabulary filename search. |
| RDF fixtures and integrity | evaluation/BEHAVIORAL_RDF_R13/; evaluation/behavioral_benchmark/; repository-root verify_full_benchmark_integrity_final.py | Frozen cases, specifications, manifests, locks, source clauses, Pilot 02 and collision-repair evidence. Preserve creator/validator scripts, all historical fixtures and reports. |
| Model scaling | experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/experiment.py; run_rdf_evaluation.py; rdf_evaluation_common.py; CONFIGS/; MANIFESTS/ | Frozen 50-requirement sample, provider clients, first-generation/final modes, extracted Luna reference, final vs smoke separation, manual audit packets and all outputs. |
| Reporting and result discovery | src/nltl_pipeline/reporting/costs.py; reporting/; MVP/make_*fig*.py; MVP/ocean_reporting/runtime_evidence/ | Costs and runtime discovery recursively consume events.jsonl; analyses glob run/session/artifact directories. No individual text reference is required for these files to matter. |
| Tests | tests/ (26 test_*.py files); model-scaling tests/ | API/provider mocks, full repair, recovery, ablations, evaluator, benchmark identity, lock R6–R13, logging and reporting. Earlier versions are explicit regression inputs. |
| Environment | pyproject.toml; requirements.txt; MVP/.venv/; MVP/ocean_reporting/.venv/; tracked node_modules symlinks | Python >=3.11; requests, python-dotenv, rdflib and pyshacl ranges. Reporting uses external Node and @oai/artifact-tool paths. No complete environment lock found. No notebooks (.ipynb) found. |
### Exact authoritative R13 input paths

| Role | Exact repository-relative path |
|---|---|
| Selected official config | MVP/SHACL_GENERATION_PIPELINE/config/pipeline.official-r13.json |
| Active R13 lock | MVP/benchmark_vocabulary_stage2_LOCK-2026-08-22-R13.lock.json |
| Registry | MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/registry/term_registry.json |
| Ontology loaded by generation | MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/ontology/nltl_benchmark_vocabulary.ttl |
| Requirement evidence | MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/evidence/stage1_approved.json |
| Requirement mappings/contracts | MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/requirement_term_index.json |
| Few-shot examples | MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/few_shots/few_shot_pairs.jsonl |
| Locked root workbook | MVP/benchmark_vocabulary_stage2_LOCK-2026-08-22-R13.xlsx |
| Checksums | MVP/benchmark_vocabulary_stage2_LOCK-2026-08-22-R13.sha256 |
| Other protected bound exports | MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/context/; ontology/*.rdf; registry/*.csv; evidence/; few_shots/; validation/; provenance/r12_immutable_source_hashes.json |
The lock identifies `VOCAB-LOCK-2026-08-22-R13`, `2.23.0-stage2-final-r13`, 313 requirements and 268 generation-eligible/complete contracts. All 19 `boundMachineReadableArtifacts` match current bytes. All 177 paths in R13's R12 immutable-source manifest match. The root R13 workbook matches locked SHA-256 `a5c458d3375ef84097f46f498525fcd50c072397d630a7f050064cced341a4b0`. These are fresh static hash checks; recorded unit-test/RDF PASS statements inside the lock are historical results, not checks rerun by this audit.

The workbook **inside** `FINAL_LOCK_R13/` hashes to `7ae079a564c59e43143c4a3c0436de239c235c6f7b978afb71ae8434dd232259`. The root and bundle files have identical resolved nonempty cell values and formula strings across all 11 sheets (28,815 cells); ZIP XML, shared-string vs inline-string storage, styles, relationships and document metadata differ. Cell equality is not byte identity, nor proof of all display/print equivalence. Preserve both; see both workbook comparison JSON files.

Three current pipeline files differ from the generation-source hashes recorded in the R13 lock: `orchestration/runner.py`, `prompts.py`, `validation/shacl.py`. Their current code includes later FULL_REPAIR_V2 and prompt behavior; the lock is a historical source fingerprint, not a proof of today's source equivalence. Other four recorded source hashes and all four recorded prompt hashes match. Do not revert these files or remove implementation snapshots to make old hashes match. `r13_hash_verification.csv` includes every exact expected/current hash and result.

### Documented commands — recorded, not executed

From `MVP/SHACL_GENERATION_PIPELINE/`, README documents `../.venv/bin/python -m unittest discover -s tests -t . -v`, `run_pipeline.py doctor`, `offline-smoke --requirement IMO26-014`, `generate`, `generate-batch`, `evaluate --manifest ../INPUTS/RDF_SHIP_GRAPH_PILOT/pilot_manifest.json`, and `cost-report`. Unqualified generation/doctor/smoke selects the historical R5 default. Future final-vocabulary validation must explicitly select `--config config/pipeline.official-r13.json`.

`evaluation/EXPERIMENT_RUNNER_README.md` documents repository-root behavioral manifest building, `--all`, `--all-generation-runs`, smoke filters, resume and analysis commands. These write manifests/results and were not run. The scaling README documents connectivity, generation, extraction and evaluation; connectivity and generation call paid/provider APIs and were not run. `code_entrypoint_inventory.csv` preserves 377 source/shell files' functions/imports; `dynamic_and_command_references.csv` captures 362 dynamic-loading/CLI lines. All exact configuration path bindings (689 path records) are in `configuration_path_map.csv`; all mapped non-output inputs exist locally.

## Investigation and retention decisions

### ZIPs

All 17 project ZIPs were opened without extraction. Every file member was read, SHA-256 hashed and compared to present file contents. `archive_members.csv` includes the complete member list, compressed/uncompressed sizes, hashes, comparison and up to three exact retained counterpart paths per member; full cross-file equivalence groups are in `duplicates.json` / `duplicate_groups.csv.gz`. Member index disambiguates repeated member names. AppleDouble (`__MACOSX`) and Finder metadata are identified separately; no code/result byte was dismissed as metadata. Runtime-package `.tar.gz`/`.gz` files under `.venv` remain dependencies, not cleanup candidates.

Thirteen archives have no unique substantive members and are proposed as redundant delivery containers. Each exact counterpart needed by the proposal remains retained: notably 30 otherwise recompilable bytecode files in `src/` remain KEEP because they are exact counterparts of `src.zip` members. The ZIP proposal therefore does not silently remove the last copy of any member. No active generation/evaluation ZIP reader was identified. Analysis references to their exported ZIPs are writers; external consumers cannot be ruled out, so container-distribution risk is disclosed in each row.

| Archive path | Decision | Member comparison |
|---|---|---|
| BEHAVIORAL_R13_RUN01_RESULTS.zip | PROPOSE DELETE | 10554 members; byte-identical retained file: 10554 |
| FULL_CANDIDATE_SUMMARIES.zip | PROPOSE DELETE | 9 members; byte-identical retained file: 9 |
| GENERATED_RULE_MANIFESTS_RUN01.zip | KEEP | 3 members; unique or different bytes: 3 |
| MODEL_SCALING_SMOKE_RESULTS.zip | KEEP | 214 members; byte-identical retained file: 213; unique or different bytes: 1 |
| MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13.zip | NEEDS REVIEW | 406 members; metadata only: 225; byte-identical retained file: 181 |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results/HARNESS-SMOKE-I2-021.zip | PROPOSE DELETE | 97 members; metadata only: 53; byte-identical retained file: 44 |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/NLTL_AUTOMATIC_EVIDENCE_RESULTS.zip | PROPOSE DELETE | 4 members; byte-identical retained file: 4 |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/NLTL_AUTOMATIC_EVIDENCE_RESULTS_R2.zip | PROPOSE DELETE | 4 members; byte-identical retained file: 4 |
| MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/FINAL_LUNA_CONTEXTUAL_SINGLESHOT_RUN01_ANALYSIS.zip | PROPOSE DELETE | 21 members; byte-identical retained file: 21 |
| MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_NO_SEMANTIC_VALIDATOR/FINAL_LUNA_NO_SEMANTIC_FEEDBACK_10RUN_ANALYSIS.zip | PROPOSE DELETE | 21 members; byte-identical retained file: 21 |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/MANUAL_AUDIT_SCALING_10/BATCH_01.zip | KEEP | 256 members; byte-identical retained file: 256 |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/MODEL_SCALING_RDF_EVALUATION_RESULTS.zip | PROPOSE DELETE | 5392 members; byte-identical retained file: 5392 |
| MVP/SHACL_GENERATION_PIPELINE/outputs/development_r10_sol_full269_max7_01/r10_sol_full269_analysis.zip | PROPOSE DELETE | 7832 members; byte-identical retained file: 7832 |
| MVP/SHACL_GENERATION_PIPELINE/src.zip | PROPOSE DELETE | 153 members; metadata only: 86; byte-identical retained file: 67 |
| MVP/methods_evidence.zip | PROPOSE DELETE | 110 members; byte-identical retained file: 110 |
| NLTL_RUN01_FOUR_ARCHITECTURES_20260915T182442.zip | PROPOSE DELETE | 22 members; byte-identical retained file: 22 |
| NLTL_V2_REJECTED_ATTEMPT4_DIAGNOSTIC_RUN01_20260915T190414.zip | PROPOSE DELETE | 420 members; byte-identical retained file: 420 |
`GENERATED_RULE_MANIFESTS_RUN01.zip` is KEEP: all three archived JSONL manifests are unique historical variants. Each has 268 rows; current variants add `generation_run: RUN_01` and alter `manifest_id` from `RUN01-...` to `RUN_01-...`. The archive preserves prior identity evidence. `MODEL_SCALING_SMOKE_RESULTS.zip` is KEEP: its `manifests/configuration_lock.json` has a different `implementation_file_sha256` record from the current configuration lock. Neither is safely replaced by today's manifest. Comparisons are in `unique_archive_comparisons.json`.

`.../MANUAL_AUDIT_SCALING_10/BATCH_01.zip` is KEEP even though 256 members match retained files: its container SHA-256 is bound twice in `selection_manifest.json` and its copied evidence manifest. This is package-identity evidence. `MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13.zip` is NEEDS REVIEW: its members match the retained bundle, but final export authority and the bundle/root workbook checksum discrepancy make retention prudent.

### Patch, promotion and repair scripts

No patch/promotion/repair script is proposed for deletion. They hold unique transformation logic and research provenance; matching one fix is insufficient to prove every operation is dispensable. `needs_review.csv` lists every uncertain script separately, and `code_entrypoint_inventory.csv` lists their functions/imports. The substantive findings are:

| Exact path or related script set | Evidence checked | Decision / remaining uncertainty |
|---|---|---|
| repair_pilot02_batch_ef_collision.py | Statically parsed embedded PILOT_ORIGINALS_B64 without importing the script. All 20 embedded RDF/specification files match current restored bytes. Script migrates Batch E/F identifiers, snapshots old manifests/locks and recomputes hashes. | NEEDS REVIEW; unique recovery recipe and original embedded bytes remain protected. Existing fix does not replace recovery/provenance purpose. |
| MVP/BENCHMARK_VOCABULARY/STAGE2/promote_r5_imo057_fix.py | Current R13 ontology maintainedTemperature has domain compartment; IMO-057 relationship model and verify_r5_imo057_fix.py cover ship -> hasComponent -> shipComponent -> hasContainingCompartment -> compartment. | NEEDS REVIEW; primary intended fix exists. Complete workbook/export/evidence side effects have not been shown equivalent to a maintained replacement. |
| MVP/BENCHMARK_VOCABULARY/STAGE2/promote_r6_global_audit.py; promote_r7_source_grounded.py | Retained R6/R7 registries, mappings, deltas and regression tests directly depend on earlier versions; scripts implement ontology/context/contract/provenance transformations. | NEEDS REVIEW; no equivalent single maintained script; do not delete unique transformation history. |
| MVP/BENCHMARK_VOCABULARY/STAGE2/promote_r8_verification_policy.py; promote_r9_classification_and_fewshots.py | R8/R9 policy/classification/few-shot changes have corresponding tests/configs/artifacts. | NEEDS REVIEW; these are historical promotions, not duplicate runtime modules; all operations not independently replayed. |
| MVP/BENCHMARK_VOCABULARY/STAGE2/promote_r10_mechanical_corrections.py; promote_r11_source_grounded_corrections.py; promote_r12_direct_calculation_metadata.py | Matching test modules compare R9–R12; R13 binds all 177 R12 source files; current R13 completeness and table-reference report hashes match. | NEEDS REVIEW; replacement not established for full historical transformation and evidence generation. |
| MVP/BENCHMARK_VOCABULARY/STAGE2/promote_r13_narrow_source_corrections.py | Actual final R13 narrow-correction promotion, not the earlier development R13 promotion. Source decisions, final registry/index, lock-bound reports and R13 tests retained. | NEEDS REVIEW; intended narrow corrections represented by current bound artifacts; source-grounding/provenance recipe is unique. |
| MVP/BENCHMARK_VOCABULARY/STAGE2/promote_r13_to_final_lock.py | Despite its name, SOURCE is DEV_R13_APPLICABILITY_MATRIX_CLOSURE and TARGET is FINAL_LOCK_R3, dated August 14. | NEEDS REVIEW; development R13 is not authoritative final R13. Do not infer supersession from this filename. |
| MVP/BENCHMARK_VOCABULARY/STAGE2/promote_r14_to_final_lock.py | SOURCE DEV_R14_FINAL_STRESS_GAP_CLOSURE promotes FINAL_LOCK_R4. | NEEDS REVIEW; does not establish any final R14 superseding locked R13. |
| MVP/BENCHMARK_VOCABULARY/ARCHIVE/PRE_NAMESPACE_R4_WITHDRAWN_2026-08-14/migrate_r4_namespace.py | Archived namespace migration traverses vocab/input manifests and writes transformed artifacts; withdrawn snapshot is retained. | NEEDS REVIEW; historical migration and withdrawn evidence are unique. |
| MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_NO_SEMANTIC_VALIDATOR/PREPARATION/implementation.patch | Text implementation record, not an executable patch. no_semantic_validator.py, CLI commands and deterministic test module exist in current source. | KEEP experimental implementation evidence; observed incorporation does not erase provenance need. |
| MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/PREPARATION/implementation.patch | Diff names SingleShotRunResult, ContextualSingleShotRunner, render_first_generator_request, CLI/config/queue/tests and preparation scripts; corresponding maintained modules exist. | KEEP source snapshot; complete hunk equivalence was not asserted. |
| MVP/SHACL_GENERATION_PIPELINE/experiments/FINAL_LUNA_MAIN/MANIFESTS/uncommitted_diff_before.patch | Zero-byte recorded pre-run patch snapshot, paired with Git-state evidence. | KEEP; empty provenance record is meaningful, not disposable simply because size is zero. |
### Earlier versions, duplicates, large files and scratch-looking files

R1–R12 standalone workbooks, locks and checksums remain KEEP. Historical configurations resolve root lock paths, tests compare successive locked registries/ontologies, and provenance chains bind earlier files. Byte-identical copies do exist, but a root-file path and a bundle-file path are not automatically interchangeable to a configuration, checksum or external consumer. Exact groups are included in the duplicate inventory. No filename-only supersession decision was made.

All raw responses, generated shapes, run/session outputs, logs (including ignored `.log` files), candidate diagnostics, ablation/model-control results, partial/failed run evidence, human/AI manual assessments, timing/cost evidence, and figure data remain protected, even when duplicated or reproducible in principle. Copied `methods_evidence_support/` materials remain intact; deleting the duplicate `methods_evidence.zip` container does not remove this publication evidence tree or its three root documents. `MVP/figures/` and `MVP/ocean_reporting/figure5_accuracy_layouts/` are retained; untracked copies must not be treated as throwaway.

`MVP/tmp/pdfs/r3_stress_review/` contains eight tracked regulation-page PNGs; keep as source-grounding review evidence. Large `.xlsx.inspect.ndjson` files can contain validation/figure/workbook evidence. Their disposability was not established; keep. Both virtual environments remain intact apart from unbound Finder metadata proposals: declared dependency ranges are not an exact installed-environment lock.

| Largest retained/candidate path | Bytes | Decision |
|---|---|---|
| MVP/SHACL_GENERATION_PIPELINE/evaluation/candidate_diagnostics/FULL-CANDIDATES-RUN01-RUN10/full_candidate_case_results.jsonl | 256,970,742 | KEEP |
| MVP/SHACL_GENERATION_PIPELINE/outputs/cost_reporting/pipeline_cost_ledger.xlsx.inspect.ndjson | 60,118,428 | KEEP |
| MVP/SHACL_GENERATION_PIPELINE/outputs/development_r10_sol_full269_max7_01/r10_sol_full269_analysis.zip | 37,759,096 | PROPOSE DELETE |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results/BEHAVIORAL-R13-20260911T080233539977Z/raw_case_results.jsonl | 24,955,622 | KEEP |
| NLTL_RUN01_FOUR_ARCHITECTURES_20260915T182442/historical_three/raw_case_results.jsonl | 24,955,622 | KEEP |
| MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R5/benchmark_vocabulary_stage2_LOCK-2026-08-19-R5.xlsx.inspect.ndjson | 18,966,268 | KEEP |
| MVP/BENCHMARK_VOCABULARY/ARCHIVE/PRE_NAMESPACE_R4_WITHDRAWN_2026-08-14/FINAL_LOCK_R4_PRE_NAMESPACE_SNAPSHOT/benchmark_vocabulary_stage2_LOCK-2026-08-14-R4.xlsx.inspect.ndjson | 18,731,239 | KEEP |
| MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R4/benchmark_vocabulary_stage2_LOCK-2026-08-14-R4.xlsx.inspect.ndjson | 18,707,361 | KEEP |
| MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R3/benchmark_vocabulary_stage2_LOCK-2026-08-14-R3.xlsx.inspect.ndjson | 18,704,247 | KEEP |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results/BEHAVIORAL-R13-20260911T080233539977Z/raw_case_results.csv | 18,606,680 | KEEP |
| NLTL_RUN01_FOUR_ARCHITECTURES_20260915T182442/historical_three/raw_case_results.csv | 18,606,680 | KEEP |
| MVP/BENCHMARK_VOCABULARY/STAGE2_R2/benchmark_vocabulary_stage2_R2.xlsx.inspect.ndjson | 18,549,048 | KEEP |
The complete >=5,000,000-byte list is `large_files.csv`. Largest example: `full_candidate_case_results.jsonl` is a 256,970,742-byte protected evaluation ledger, not a cache. The 60,118,428-byte cost-ledger inspection export is retained as reporting evidence. The 37,759,096-byte R10 analysis ZIP is proposed only because all 7,832 file members have retained exact counterparts.

There are **19,619 byte-identical regular-file groups**, totaling **1,519,609,921 bytes across all copies**. The logical excess after retaining one copy per group is **1,184,188,978 bytes**. That is an upper bound on duplicate content, **not** proposed space recovery: most copies are protected, path-sensitive research artifacts. It excludes redundancy inside archive containers. No approximate semantic duplicates were counted as byte duplicates.

### Caches and metadata

All 69 Finder files have the expected `0000000142756431` header. Sixty-seven are proposed. Two remain KEEP because exact paths appear in frozen provenance: `MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R6/validation/.DS_Store` and `MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R7/validation/.DS_Store`. R7 matches its bound hash; R6 already differs from the historical expected hash. This pre-existing discrepancy is not repaired here. A blanket Finder cleanup would break additional history checks.

Of 126 project `.pyc` files outside `.venv`, 104 match their retained source code when compiled in memory under the matching interpreter. Recursive code-object equality ignores only `co_filename`; flags, bytecode, constants, nested functions, names and line metadata are compared. Of these, 30 are explicitly kept as exact `src.zip` counterparts, leaving 74 cache proposals. Eleven compiled files differ from today's source and eleven have another interpreter's magic number: all 22 remain NEEDS REVIEW. This method does not execute or import the cached modules. Source-present alone was not considered sufficient proof.

## Space, Git tracking and history

Proposed logical working-tree reduction: **70,172,910 bytes**. Sum of reported allocated blocks for proposed files: **70,520,832 bytes**. These are different measures; APFS compression, clones, snapshots and filesystem allocation mean actual freed volume space cannot be promised from logical sizes or `st_blocks` alone. No duplicate-group total is presented as actual freed disk space. All proposals have individually retained replacements or disposable unbound metadata status.

Only 13 ZIP containers are tracked, totaling **68,657,023 logical bytes**; the other 141 proposals are already ignored and would not change a GitHub checkout. Removing the tracked files in a later commit reduces current-tree clutter. Their blobs remain in earlier Git commits, so historical repository/clone storage generally does not shrink. A separate explicit history-rewrite decision would be needed for that; none is proposed or performed here. Git internals/object storage were excluded, so these totals do not estimate packed-history or remote storage size.

## Unresolved evidence and dependencies

1. The R5 default and R1/R2 README claims conflict with final R13 intent. Review how users invoke generation; preserve older configs and inputs until any authorized default/documentation migration is separately validated.
2. Final R13 workbook container bytes disagree with the root lock even though resolved cell/formula content matches. Both remain; provenance/formatting expectations need review before deduplicating them.
3. Three current pipeline modules differ from source hashes frozen in the R13 lock. This is evidence of later maintained changes, not proof of corruption. Clean generation-time source snapshots remain relevant; preserve patches/configuration locks and the unique archives. Existing `MISSING_EVIDENCE.md` also documents reproduction gaps.
4. Thirty tracked deletions and their untracked counterparts need the user's relocation review. Newline-normalized equivalence is not a tracking-state decision.
5. Historical R6 Finder provenance already has a byte mismatch. Removing the currently matching R7 metadata, or removing either bound path, would compound the problem.
6. No complete dependency/environment lock was found. Python version, installed package snapshots, external Node executable and @oai/artifact-tool availability remain portability concerns. Seven tracked absolute `node_modules` links point outside the repository. Environment-file location is external; credentials were not read, printed or hashed.
7. Differing/mismatched-interpreter bytecode may preserve revisions. Complete intended-effect equivalence for all promotion/migration scripts has not been established. These are NEEDS REVIEW and retained.
8. Static text search covered 160,331 project text files under 2 MB, with declared suffixes and exclusions in `reference_scan_scope.json`; binaries, large files, external shell history, other machines and downstream upload consumers can retain references. All project files were inventoried/hashed; archive members were all hashed. Basename hits can include non-functional mentions and same-name files. Absence of a text reference was never used alone to establish safety.
9. Dynamic discovery exists: event-log recursion, run/session/artifact globs, historical few-shot/input directory recursion, fixture locks and whole-tree provenance hashing. Preserve those trees and exact path bindings. This is why duplicate scientific files are not mass-proposed.
10. No test or pipeline was executed, so this report does not assert current end-to-end runtime success. Hash verification and source inspection are the completed validation. Future behavior verification must run in a disposable isolated copy.

## Proposed validation plan for the separate cleanup task

1. Re-read applicable instructions; record new root/branch/HEAD/status. Recheck **every approved exact path's SHA-256** against `proposed_deletions.csv`; reject any changed/new/untracked unique content. Recheck archive members and retained counterpart hashes, including the 30 cache counterparts this proposal keeps.
2. Preserve all current user changes, the 45 untracked project files, ignored scientific logs/data, and all 30 existing deletions as their current state. Use an isolated `codex/` cleanup branch/worktree with an explicit safe snapshot strategy; do not run a blind stash/reset or accidentally omit untracked research from the reproduction copy. Approval is path-specific; no directory/glob expansion or new candidate substitution.
3. Before deletion, rerun reference and hash-binding checks against all approved candidates and complete configuration/provenance closure, including directory-based loaders and external scripts. Retain all KEEP and NEEDS REVIEW files and every substantive artifact byte; confirm selected approvals do not delete both an archive and its last exact counterpart.
4. Establish a before-cleanup offline baseline in a disposable copy with network disabled and mocked/scripted clients, isolated output roots, and cache writes redirected outside protected trees. Explicitly select official R13; do not rely on default R5. Do not run paid connectivity/generation commands.
5. Perform proposed removals only after that separate approval; then run the same isolated offline checks: read-only lock hashes, Turtle/RDF/XML isomorphism, 313 contexts/268 eligibility, contract completeness/table references, deterministic retrieval and few shots, syntax-recovery/semantic-feedback mocked cases, ablation tests, evaluator harness and model-scaling manifest identity tests. Use the documented unit-test discovery command **only in the copied project** after checking its writes. Compare failures with the before baseline.
6. Exercise scripted `doctor` / `offline-smoke --requirement IMO26-014` with explicit `--config config/pipeline.official-r13.json` and redirected scratch outputs. Evaluate only copied benchmark/accepted SHACL fixtures into a new scratch directory; never overwrite stored reports or rebuild frozen manifests in place. Verify all 2,186 frozen fixture identities/hashes, generated-rule manifests and protected source/result hashes stay unchanged.
7. Do not invoke `tools/verify_r13_lock.py` on the original tree: despite its name, its `main()` writes `FINAL_LOCK_R13/validation/r13_namespace_policy_and_integrity_report.json`, which is itself bound. Other promotion/validation/reporting scripts also write artifacts. If needed, execute only copied/redirected variants and compare independently without copying outputs back.
8. Present the isolated diff, approved-path-only deletions, validation baseline/comparison and preserved artifacts for review. Do not commit/push/rewrite history unless separately authorized. A later history-storage audit is a distinct task.

## Suggested ignore-policy review — not applied

Existing root and MVP rules already ignore `.venv/`, `__pycache__/`, `*.py[cod]`, test/type/lint caches, `.DS_Store`, `.env` variants and editor files. More cache/environment rules are not needed for today's proposals. Existing blanket `*.log` rules can hide protected scientific run logs; do not infer that ignored means disposable. Any future log-rule change should use narrowly scoped runtime-only locations and explicit retention for scientific logs.

Possible additions, only after confirming these files are not evidence:

```gitignore
# Transient Jupyter/IPython state (none found in this audit)
.ipynb_checkpoints/
.ipython/
# Transient Office lock files, never the real workbook
~$*.xlsx
~$*.docx
~$*.pptx
# Packaging/tool caches
.pyre/
.tox/
.nox/
```

Do not add blanket `*.zip`, `*.log`, `outputs/`, `tmp/`, `*.ttl`, `*.jsonl`, `*.xlsx`, `*.inspect.ndjson` or earlier-vocabulary patterns as cleanup substitutes. They would mask unique archives, scientific outputs, source-review images or environment/evidence files. Do not add `node_modules/` here until the tracked external-link dependencies have a portable replacement. Ignore rules do **not** remove already tracked files or historical Git blobs. The new audit directory is untracked and was not added to ignore rules or Git; its detailed backing inventories should not be casually committed to the research repository.

## Inventory/evidence index

- `file_inventory.csv.gz`: complete grouped per-file decisions; decompression yields CSV, not executable instructions.
- `cleanup_candidates.csv.gz`, `proposed_deletions.csv`, `needs_review.csv`, `large_files.csv`: exact filtered path lists with the same required decision fields.
- `inventory.raw.json`: initial per-file sizes, allocated blocks, tracking state, hash, timestamp and symlink-target evidence; corrected to include directory symlinks. Missing paths include HEAD hash and size separately.
- `state.json`, `preservation_verification.json`, `audit_summary.json`: initial Git state, preservation check and totals.
- `duplicates.json`, `duplicate_groups.csv.gz`: complete SHA-256 groups, copy paths, total grouped bytes and excess after one copy.
- `archive_members.csv`, `archive_summary.json`, `unique_archive_comparisons.json`: complete archive-member lists, retained counterparts and meaningful differences. Counterpart arrays are representative exact paths; full matching groups are keyed by SHA-256 in duplicate inventories.
- `candidate_references.csv`, `reference_scan_scope.json`, `candidate_hash_references.txt`, `candidate_hash_dependencies.json`: text reference evidence, scope limits and explicit cryptographic dependencies. The hash-reference file excludes this audit's own self-references.
- `code_entrypoint_inventory.csv`, `dynamic_and_command_references.csv`, `configuration_path_map.csv`, `directory_symlinks.json`: source entry points/imports, commands/dynamic discovery and config/dependency resolution.
- `r13_hash_verification.csv`, `r13_workbook_container_comparison.json`, `r13_workbook_cell_comparison.json`, `pilot_recovery_verification.json`, `bytecode_verification.json`, `missing_file_comparisons.csv`: reproducibility and candidate-specific comparisons.

The report and inventory deliberately retain complete path lists instead of substituting directory-wide deletion recommendations. These audit artifacts are new local files; no broad deletion command is included.

## Exact proposed deletion list — for separate approval only

The following is the complete approval list, identical to `proposed_deletions.csv`. Sizes are logical bytes. The CSV also contains each full SHA-256, retained replacement/counterpart inventory, justification, dependency evidence, confidence and risk. **Any path not listed here remains unapproved.**

| Exact repository-relative path | Bytes | Git status |
|---|---|---|
| .DS_Store | 18,436 | ignored |
| BEHAVIORAL_R13_RUN01_RESULTS.zip | 11,987,599 | tracked |
| FULL_CANDIDATE_SUMMARIES.zip | 1,048,513 | tracked |
| MVP/.DS_Store | 14,340 | ignored |
| MVP/.venv/.DS_Store | 6,148 | ignored |
| MVP/.venv/lib/.DS_Store | 6,148 | ignored |
| MVP/.venv/lib/python3.13/.DS_Store | 6,148 | ignored |
| MVP/.venv/lib/python3.13/site-packages/.DS_Store | 6,148 | ignored |
| MVP/BENCHMARK_VOCABULARY/.DS_Store | 10,244 | ignored |
| MVP/BENCHMARK_VOCABULARY/ARCHIVE/.DS_Store | 6,148 | ignored |
| MVP/BENCHMARK_VOCABULARY/ARCHIVE/STAGE1_2026-08-11/.DS_Store | 6,148 | ignored |
| MVP/BENCHMARK_VOCABULARY/DEVELOPMENT/.DS_Store | 10,244 | ignored |
| MVP/BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R10_GRAPH_COMPLETION/.DS_Store | 6,148 | ignored |
| MVP/BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R11_FAILURE_CLOSURE/.DS_Store | 6,148 | ignored |
| MVP/BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R12_FINAL_GAP_CLOSURE/.DS_Store | 6,148 | ignored |
| MVP/BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R13_APPLICABILITY_MATRIX_CLOSURE/.DS_Store | 6,148 | ignored |
| MVP/BENCHMARK_VOCABULARY/DEVELOPMENT/DEV_R9_FOUNDATION/.DS_Store | 6,148 | ignored |
| MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R13/.DS_Store | 8,196 | ignored |
| MVP/BENCHMARK_VOCABULARY/FINAL_LOCK_R8/.DS_Store | 6,148 | ignored |
| MVP/BENCHMARK_VOCABULARY/PIPELINE_CONTEXT/.DS_Store | 8,196 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/.DS_Store | 10,244 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/bind_r12_prelock.cpython-313.pyc | 3,221 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/build_batch01_dev_r6.cpython-313.pyc | 8,539 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/build_batch01_dev_r7.cpython-313.pyc | 9,705 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/build_batch01_dev_r8_stabilization.cpython-313.pyc | 5,133 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/build_dev_r11_failure_closure.cpython-313.pyc | 28,617 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/build_dev_r12_final_gap_closure.cpython-313.pyc | 29,486 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/build_dev_r13_applicability_matrix_closure.cpython-313.pyc | 23,183 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/create_r2_lock.cpython-313.pyc | 6,589 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/finalize_r11_lock.cpython-313.pyc | 8,662 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/finalize_r12_lock.cpython-313.pyc | 8,658 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/promote_r12_direct_calculation_metadata.cpython-313.pyc | 16,360 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/promote_r13_narrow_source_corrections.cpython-313.pyc | 31,916 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/validate_r11_offline.cpython-313.pyc | 7,790 | ignored |
| MVP/BENCHMARK_VOCABULARY/STAGE2/__pycache__/validate_r12_offline.cpython-313.pyc | 8,179 | ignored |
| MVP/INPUTS/.DS_Store | 8,196 | ignored |
| MVP/OLD FILES/.DS_Store | 10,244 | ignored |
| MVP/OLD FILES/2025_07_22_dfd3e559900bbd5d8782g/.DS_Store | 6,148 | ignored |
| MVP/OLD FILES/data/.DS_Store | 10,244 | ignored |
| MVP/OLD FILES/data/Mappings Excel/.DS_Store | 6,148 | ignored |
| MVP/OLD FILES/data/input/.DS_Store | 6,148 | ignored |
| MVP/OLD FILES/data/shipdesigns/.DS_Store | 6,148 | ignored |
| MVP/OLD FILES/src/.DS_Store | 6,148 | ignored |
| MVP/OLD FILES/src/pipeline/__pycache__/run_experiments_no_validator_noctx.cpython-313.pyc | 19,987 | ignored |
| MVP/OLD FILES/src/pipeline/__pycache__/run_pipeline_experiment_no_validator_noctx.cpython-313.pyc | 17,649 | ignored |
| MVP/OLD FILES/src/processing/__pycache__/shacl_extractor.cpython-313.pyc | 838 | ignored |
| MVP/OLD FILES/src/utils/__pycache__/io.cpython-313.pyc | 1,614 | ignored |
| MVP/OLD FILES/src/utils/__pycache__/logger.cpython-313.pyc | 573 | ignored |
| MVP/RELEVANT FILES/.DS_Store | 8,196 | ignored |
| MVP/RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/.DS_Store | 6,148 | ignored |
| MVP/RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/__pycache__/validate_examples.cpython-313.pyc | 13,780 | ignored |
| MVP/RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/cases/.DS_Store | 10,244 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/.DS_Store | 12,292 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/__pycache__/run_pipeline.cpython-313.pyc | 577 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/.DS_Store | 12,292 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/PILOT_02_FILES/.DS_Store | 8,196 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/__pycache__/analyze_behavioral_results.cpython-313.pyc | 1,338 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/__pycache__/run_behavioral_evaluation.cpython-313.pyc | 715 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/__pycache__/run_full_candidate_diagnostics.cpython-313.pyc | 745 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/__pycache__/run_rejected_attempt4_diagnostic.cpython-313.pyc | 754 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/candidate_diagnostics/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/candidate_diagnostics/FULL-CANDIDATES-RUN01-RUN10/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/candidate_diagnostics/FULL-CANDIDATES-RUN01-RUN10/reports/.DS_Store | 8,196 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results/.DS_Store | 8,196 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results/BEHAVIORAL-R13-20260911T080233539977Z/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results/BEHAVIORAL-R13-20260911T080233539977Z/reports/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results/HARNESS-SMOKE-I2-021.zip | 83,643 | tracked |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results/HARNESS-SMOKE-I2-021/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/__pycache__/__init__.cpython-313.pyc | 335 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/__pycache__/analysis.cpython-313.pyc | 21,068 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/__pycache__/candidate_diagnostics.cpython-313.pyc | 59,906 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/__pycache__/cli.cpython-313.pyc | 8,289 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/__pycache__/core.cpython-313.pyc | 31,221 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/__pycache__/execution.cpython-313.pyc | 30,832 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/__pycache__/rejected_attempt4_diagnostic.cpython-313.pyc | 13,873 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/.DS_Store | 10,244 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/NLTL_AUTOMATIC_EVIDENCE_RESULTS.zip | 1,887,227 | tracked |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/NLTL_AUTOMATIC_EVIDENCE_RESULTS_R2.zip | 1,888,243 | tracked |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/scripts/__pycache__/enrich_automatic_evidence.cpython-313.pyc | 94,095 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/scripts/__pycache__/test_enrich_automatic_evidence.cpython-313.pyc | 31,439 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/.DS_Store | 10,244 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/FINAL_LUNA_MAIN/.DS_Store | 10,244 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/RUN_01/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/.DS_Store | 10,244 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/FINAL_LUNA_CONTEXTUAL_SINGLESHOT_RUN01_ANALYSIS.zip | 40,573 | tracked |
| MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_NO_SEMANTIC_VALIDATOR/.DS_Store | 8,196 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_NO_SEMANTIC_VALIDATOR/FINAL_LUNA_NO_SEMANTIC_FEEDBACK_10RUN_ANALYSIS.zip | 29,387 | tracked |
| MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_NO_SEMANTIC_VALIDATOR/PREPARATION/__pycache__/preflight.cpython-313.pyc | 8,827 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/LUNA_NO_SEMANTIC_VALIDATOR/PREPARATION/__pycache__/preflight_06_to_10.cpython-313.pyc | 12,012 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/MODEL_SCALING_RDF_EVALUATION_RESULTS.zip | 8,032,705 | tracked |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/OUTPUTS/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/OUTPUTS/FINAL/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/OUTPUTS/RDF_EVALUATION/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/__pycache__/build_blinded_manual_audit_10.cpython-313.pyc | 34,039 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/__pycache__/experiment.cpython-313.pyc | 22,347 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/__pycache__/provider_clients.cpython-313.pyc | 15,916 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/__pycache__/rdf_evaluation_common.cpython-313.pyc | 10,739 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/__pycache__/run_rdf_evaluation.cpython-313.pyc | 22,209 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/__pycache__/summarize_rdf_evaluations.cpython-313.pyc | 6,362 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/tests/__pycache__/test_blinded_manual_audit_10.cpython-313.pyc | 5,651 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/outputs/.DS_Store | 22,532 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/outputs/development_r10_sol_full269_max7_01/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/outputs/development_r10_sol_full269_max7_01/r10_sol_full269_analysis.zip | 37,759,096 | tracked |
| MVP/SHACL_GENERATION_PIPELINE/outputs/development_r12_sol_targeted28_max4_01/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/outputs/runs/.DS_Store | 10,244 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/outputs/runs/RUN-IMO26-014-20260812T095941776147Z/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/prompts/.DS_Store | 6,148 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/src.zip | 274,400 | tracked |
| MVP/SHACL_GENERATION_PIPELINE/tests/.DS_Store | 10,244 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/__init__.cpython-313.pyc | 491 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_api_client.cpython-313.pyc | 8,298 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_behavioral_experiment_runner.cpython-313.pyc | 16,646 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_cli.cpython-313.pyc | 2,144 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_contextual_singleshot.cpython-313.pyc | 8,284 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_contracts.cpython-313.pyc | 10,573 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_cost_reporting.cpython-313.pyc | 4,463 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_evaluator.cpython-313.pyc | 5,282 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_full_candidate_diagnostics.cpython-313.pyc | 10,210 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_full_repair_v2.cpython-313.pyc | 7,943 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_no_semantic_validator.cpython-313.pyc | 9,458 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_pipeline_offline.cpython-313.pyc | 12,477 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_progress_logging.cpython-313.pyc | 2,492 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_provider_formats.cpython-313.pyc | 11,080 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_r10_mechanical_corrections.cpython-313.pyc | 12,557 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_r11_source_grounded_corrections.cpython-313.pyc | 14,984 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_r12_direct_calculation_metadata.cpython-313.pyc | 10,125 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_r13_narrow_source_corrections.cpython-313.pyc | 14,500 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_r6_lock.cpython-313.pyc | 4,706 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_r7_lock.cpython-313.pyc | 8,800 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_r8_verification_policy.cpython-313.pyc | 13,798 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_r9_classification_and_fewshots.cpython-313.pyc | 13,122 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_retrieval.cpython-313.pyc | 13,906 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_scaling_model_identity.cpython-313.pyc | 3,594 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_scaling_rdf_evaluation.cpython-313.pyc | 9,775 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_shacl_validation.cpython-313.pyc | 22,960 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tests/__pycache__/test_shacl_wrapper_normalizer.cpython-313.pyc | 6,574 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tools/__pycache__/validate_direct_calculation_completeness.cpython-313.pyc | 3,132 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tools/__pycache__/verify_r11_lock.cpython-313.pyc | 15,452 | ignored |
| MVP/SHACL_GENERATION_PIPELINE/tools/__pycache__/verify_r12_lock.cpython-313.pyc | 14,957 | ignored |
| MVP/WEBSITE STUFF/.DS_Store | 6,148 | ignored |
| MVP/__pycache__/make_accuracy_runtime_figure.cpython-313.pyc | 8,636 | ignored |
| MVP/methods_evidence.zip | 786,195 | tracked |
| MVP/ocean_reporting/.DS_Store | 6,148 | ignored |
| MVP/ocean_reporting/outputs/.DS_Store | 6,148 | ignored |
| MVP/ocean_reporting/outputs/results_layout_variants_20261015_150529_094578/.DS_Store | 8,196 | ignored |
| MVP/ocean_reporting/outputs/results_layout_variants_20261015_150529_094578/scaling outputs/.DS_Store | 8,196 | ignored |
| MVP/ocean_reporting/outputs/results_layout_variants_20261015_150529_094578/scaling outputs/accuracy_runtime_figure_20261021_115034_600331/.DS_Store | 6,148 | ignored |
| MVP/tmp/.DS_Store | 6,148 | ignored |
| MVP/tmp/pdfs/.DS_Store | 6,148 | ignored |
| NLTL_RUN01_FOUR_ARCHITECTURES_20260915T182442.zip | 4,196,580 | tracked |
| NLTL_V2_REJECTED_ATTEMPT4_DIAGNOSTIC_RUN01_20260915T190414.zip | 642,862 | tracked |
