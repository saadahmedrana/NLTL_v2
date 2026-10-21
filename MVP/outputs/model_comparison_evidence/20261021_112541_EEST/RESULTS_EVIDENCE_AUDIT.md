# Four-model behavioural accuracy and runtime evidence

Audit date: 21 October 2026 (Europe/Helsinki). Evidence recovery only: no generation, RDF evaluation, experiments, API requests, manuscript edits, workbook edits, or figure creation were performed. `build_evidence.py` reads saved files and recomputes arithmetic; it imports no pipeline, evaluator, or provider module.

## Verified final-stage results

All rows describe **SELF_REPAIR_FINAL**, the same 50 requirement IDs, and the same selected generation runs. Runtime includes all 50 completed runs, including unsuccessful runs. Accuracy is an equal-weight mean of per-requirement correct/assigned-case fractions.

| Model | Case version | Requirements | Assigned cases | Macro accuracy (%) | Correct cases | Executed cases | Mean runtime (s) | Sample SD (s) | Median runtime (s) | Timed runs | Accepted |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GPT-5.6 Luna | Retained | 50 | 373 | 72.032468 | 266 | 316 | 71.61006 | 55.45656 | 49.9350 | 50 | 43 |
| GPT-5.6 Sol | Retained | 50 | 373 | 82.193434 | 309 | 351 | 76.30978 | 115.24606 | 43.8980 | 50 | 47 |
| Gemini 3.5 Flash | Retained | 50 | 373 | 73.537013 | 278 | 348 | 114.50898 | 141.30442 | 64.5600 | 50 | 46 |
| GPT-OSS 120B | Retained | 50 | 373 | 47.041919 | 177 | 210 | 59.80680 | 38.39266 | 59.0075 | 50 | 28 |
| GPT-5.6 Luna | Legacy | 50 | 381 | 71.499134 | 270 | 322 | 71.61006 | 55.45656 | 49.9350 | 50 | 43 |
| GPT-5.6 Sol | Legacy | 50 | 381 | 81.374387 | 314 | 359 | 76.30978 | 115.24606 | 43.8980 | 50 | 47 |
| Gemini 3.5 Flash | Legacy | 50 | 381 | 72.717965 | 283 | 356 | 114.50898 | 141.30442 | 64.5600 | 50 | 46 |
| GPT-OSS 120B | Legacy | 50 | 381 | 46.891919 | 178 | 212 | 59.80680 | 38.39266 | 59.0075 | 50 | 28 |

Exact machine-readable values and source paths are in `model_comparison_summary.csv`. GPT-OSS's 59.0075 s rounds to 59.008 s at three decimals. Floating-point representation of Sol's median may appear as 43.897999999999996 in CSV; the exact millisecond-based median is 43.898 s.

## Sources and authority

Project root `P` = `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP`.

Experiment root `E` = `P/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50`.

Downloads root `D` = `/Users/sadisfaction570/Downloads`.

Every summary/per-requirement CSV expands its source paths; `source_sha256.csv` supplies exact filenames and hashes, including every assignment manifest, RDF fixture, generation event log, and accepted final shape used. `assigned_case_manifest.csv` records every case ID and original manifest path for both versions.

| Source | Role, metric and scope |
|---|---|
| `E/MANIFESTS/sample_50.json`, `manifest_lock.json` | Authoritative frozen 50-requirement cohort, seed, strata and original case counts; sample hash verified against lock. |
| `P/SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13/manifests/*_batch_*_manifest.jsonl` | Independent original assigned-case list: 2,186 globally, 381 in the sample. All file hashes match saved evaluation manifest hashes. |
| `E/OUTPUTS/RDF_EVALUATION/SELF_REPAIR_FINAL/{luna,sol,gemini,gpt_oss}/raw_case_results.jsonl` | Authoritative saved verdicts for the original 381 cases. Complete, unique case coverage for each model. |
| `E/RDF_INPUTS/FINAL/SELF_REPAIR_FINAL/<model>/generated_rules.jsonl` | Final artifact selection, generating run IDs, status, hashes and paths; hashes verified against saved summaries. |
| `E/OUTPUTS/RDF_EVALUATION/FIRST_GENERATION/<model>/raw_case_results.jsonl` | Separate iteration-1 results on the same 50 requirements and original 381 cases. Never used as final-stage accuracy. |
| `P/SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/RUN_01/runs/*/events.jsonl` | Luna runtime source, restricted to the manifest's 50 requirements. The other 218 Luna requirements are excluded. |
| `E/OUTPUTS/FINAL/{sol,gemini,gpt_oss}/runs/*/events.jsonl` | Other models' full-repair runtime sources. Event IDs and requirement identities paired with evaluated outputs. |
| `P/ocean_reporting/NLTL_Runtime_and_Iterations.xlsx`, `Requirement_Runs` | Existing runtime workbook; all 200 selected times independently matched to event timestamps and run IDs. |
| `P/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/NLTL_Manual_Audit_with_Model_Scaling_FINAL.xlsx`, `Paper stats 2!A3:H10` | Legacy final-stage **pooled case accuracy**, 50 requirements / 381 cases; `F7:F10` correct counts and `H7:H10` correct/381. This is not requirement-macro accuracy. Downloaded FINAL variants preserve these behavioural values. |
| Same audit workbook, `Paper stats 3!A3:H10` | Legacy **FIRST_GENERATION** pooled case accuracy on 50 / 381. |
| Same audit workbook, `MethodV2!A16:F16` | Explicit definition of requirement-macro accuracy as equal-weight per-requirement case accuracy. |
| `D/NLTL_v2_manuscript_and_data.zip!NLTL_v2/case_outcomes.csv` | Retained assignment membership: 2,160 unique cases in each of NO_SEMANTIC and SINGLESHOT. Restriction to the independent 50-requirement cohort gives exactly 373 cases. This export is used only for case membership, never as another model's verdict source. |
| `D/Ocean_Eng_Journal.pdf`, duplicate `(1).pdf`, pp. 9–14, especially Sections 3.5.1–3.5.2, 3.7.3 and 4.3 | Model-inclusive manuscript specifies removal of 26 benchmark cases/eight sample cases; Eq. 2 defines macro accuracy; final 373-case results are 72.03%, 82.19%, 73.54%, 47.04%. All four independently reproduced. |
| `D/NLTL_v2_manuscript_and_data.zip!NLTL_v2/main.tex`, `README.md`, `data_provenance.json`; `D/NLTL_v2_Paper_LaTeX.zip!main.tex`, `README.md`; `D/NLTL_v2_Paper_Handover.md` | Subsequent main-study-only package, using 268 / 2,160. Its README and handover explicitly distinguish the prior model comparison, and its Results omits it. This establishes a substantive revision relationship, not just file dates. |
| `P/ocean_reporting/inputs/NLTL_v2_Paper_Tables.xlsx`; `D/NLTL_v2_Paper_Tables.xlsx` and `(1).xlsx` | Clean main-study tables: 16 main-study sheets; runtime-enhanced copies add a Runtime summary. No behavioural four-model table. Cannot supply model accuracy by substitution. |
| `D/R13_Behavioral_Evaluation_Mapping_v3.xlsx` and `(1).xlsx` | Requirement test-design plans and provenance library, not an executed 373-case identity manifest. Not used to invent excluded case IDs. |

`manuscript_version_inventory.csv` groups PDFs by extracted-text hash and records whether model results occur. The base PDF and `(1)` contain the model comparison. PDFs `(2)` through `(13)` omit it. The handover explicitly says the latest supplied manuscript omits model results. Therefore **373 matches the recovered model-inclusive manuscript and retained main-study case membership; the later main-study manuscript contains no four-model result to verify**. There is no need to assume that the numerically largest PDF suffix alone identifies authority.

The local `METHODS_EVIDENCE.md` and its copied `methods_evidence_support/03_model_comparison` document the original 381-case experiment. They are useful provenance summaries; original manifests and ledgers govern the independent recalculation. Copied summaries, smoke runs, and ZIP duplicates are not additional trials.

## Metric implementation and disagreements

For requirement r, accuracy is correct expected PASS/FAIL verdicts divided by **all independently assigned cases** for that requirement. Headline accuracy = 100 × sum of these 50 fractions / 50. An execution failure, missing output, or missing verdict earns zero. Requirements are not dropped because they have no executable output.

Inspected implementations:

- `E/scripts/rdf_evaluation_common.py`, `summarize_cases` and `requirement_results`: select execution_status=EXECUTED; count expected PASS/actual true and expected FAIL/actual false; divide correct by all rows for per-requirement end-to-end accuracy. Its overall summary is pooled, not macro.
- `P/SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/analysis.py`, `summarize_rows` and requirement aggregation: distinguish correct/all cases from correct/executed cases.
- `P/SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/execution.py`, `semantic_outcome` and `infrastructure_row`: FAIL with nonconformance is correct, while infrastructure failure has actual_conforms=None and no credit.
- The audit workbook's MethodV2 macro definition and manuscript Eq. 2 specify taking the equal-weight arithmetic mean of these per-requirement fractions. The new arithmetic implements this documented aggregation, with denominators independently established from manifests.

All emitted behavioral_match flags were checked against an independent expected/actual comparison. Saved summaries' correct and executed totals match the raw ledgers for all eight model/stage combinations. There are no absent emitted cases or duplicate (requirement, case) pairs in those ledgers. Explicit infrastructure rows remain counted. All retained expected labels, requirement IDs, RDF paths, and RDF SHA256s match the independent assignment sources and original ledgers. No labels or fixtures were changed for this recovery.

| Model | Audit workbook final pooled accuracy, 381 (%) | Recomputed final macro, 381 (%) | Model-inclusive manuscript final macro, 373 (%) | Recomputed final macro, 373 (%) |
|---|---:|---:|---:|---:|
| Luna | 70.866142 | 71.499134 | 72.03 | 72.032468 |
| Sol | 82.414698 | 81.374387 | 82.19 | 82.193434 |
| Gemini | 74.278215 | 72.717965 | 73.54 | 73.537013 |
| GPT-OSS | 46.719160 | 46.891919 | 47.04 | 47.041919 |

These differences have two distinct causes: equal requirement weighting versus pooled case weighting, and exclusion of eight identified cases. They are not rounding discrepancies or acceptance percentages. `report_reconciliation.csv` preserves both metrics for both stages and both versions.

FIRST_GENERATION macro results are kept separately in `first_generation_separate_summary.csv`. For retained 373 they are Luna 72.422150%, Sol 88.757071%, Gemini 71.137013%, GPT-OSS 52.057648%; for legacy 381 they are 71.603102%, 87.938023%, 70.451299%, 51.971934%. The retained numbers reproduce the model-inclusive manuscript's initial-stage values at displayed precision. Full-repair runtimes are deliberately NA for this stage in that separate CSV; they must not be interpreted as initial-response latency.

Acceptance = accepted final generated artifacts / 50 (43, 47, 46, 28). Strict executable requirement coverage = requirements with a completed verdict on every assigned case / 50, regardless of correctness. On these final-stage records it happens to equal acceptance for all four models; the concepts remain distinct. Case-level executed coverage is executed_case_count / assigned_case_count; neither coverage measure is accuracy. Conditional accuracy among executed cases is also distinct and is not used for the headline result.

## The 381-versus-373 reconciliation

The manuscript states that 26 benchmark configurations flagged during review were excluded across conditions. The manuscript archive contains the full retained 2,160-case set for each of two main-study conditions. Their case identities agree exactly. Original assignment manifests contain 2,186 cases; the set difference contains exactly 26 IDs. Restricting those identities to the independently locked model sample identifies these eight exclusions:

| Requirement | Excluded case IDs |
|---|---|
| I2-008 | I2-008-F02; I2-008-P01 |
| TRF-060 | TRF-060-F04; TRF-060-P01 |
| TRF-101 | TRF-101-F02; TRF-101-P01 |
| TRF-123 | TRF-123-F04; TRF-123-P01 |

This is an explicit retained-ID reconstruction from independent manuscript data, not a choice of eight cases to fit a target metric. The resulting 373 IDs and labels are common across all four models and both stages. Original 381-case ledgers remain the verdict evidence, with the recovered retained assignment set applied as a reporting filter. No standalone saved 373-case four-model raw ledger was found. Both versions are recoverable by arithmetic, and both are reported without relabeling one as the other.

Remaining limit: case-specific benchmark-review decisions and the original `report_02(1).zip` referenced by the archive's data_provenance.json were not found in the searched project/Downloads files. We can verify exactly which IDs were excluded and reproduce the manuscript; we cannot independently adjudicate the scientific reason for each exclusion from a saved review log. The mapping workbook is a test-plan document and does not fill that gap.

## Runtime pairing and timing boundaries

All supplied mean, sample SD and median values were independently recovered from each run's first/only run_started and last/only run_finished timestamps, then matched to the existing runtime workbook by run ID. All selected 200 runs have one start and one finish; no zero duration was fabricated. Per-model counts are 50, including 7/3/4/22 unsuccessful runs for Luna/Sol/Gemini/GPT-OSS. Sample SD describes differences between requirements, not repeated-generation uncertainty.

For accepted outputs, generated-manifest hashes match saved evaluation summaries, every ledger points to the corresponding generation identity and artifact hash, and every final file's current SHA256 matches. Initial and final manifest run IDs agree. Luna comes only from the 50 selected `FULL_REPAIR_V2/RUN_01` requirements; the other models come from `OUTPUTS/FINAL`, excluding all smoke and rerun folders.

Two GPT-OSS control rows, IMO-112 and TRF-059, record RUNNER_EXCEPTION/BATCH_ITEM_ERROR and missing run IDs. Both evaluation stages carry unavailable-output rows with missing generation_run_id. For each, exactly one run directory exists in the final GPT-OSS scope, its events identify the same requirement and model session, and its PIPELINE_ERROR feedback matches the control/evaluation failure text. These completed unsuccessful timings are retained. `output_runtime_pairing.csv` records the actual event run ID, **NA** evaluation run ID, and this recovery method. There is no accepted artifact to hash for those failures; this limitation is not concealed by inventing an evaluation ID.

Current inspected `src/nltl_pipeline/orchestration/runner.py` places context-pack construction and few-shot selection before run_started; initial context/artifact logging, initial generation, validation, any syntax/semantic repair, vocabulary matching, and final diagnostics occur inside the interval. run_finished precedes tracker workbook export/reporting_completed. The recorded interval therefore includes enabled repairs, checks and intervening logged waits; it excludes earlier preparation and later tracker export. It is a wall-clock timestamp difference, not a monotonic pure-compute timer, and is not batch makespan or throughput.

Post-generation RDF evaluation is a separate process/ledger and is excluded from these generation runtime values. In `evaluation/experiment_runner/execution.py`, per-case runtime_ms starts immediately before RDF parsing and includes pySHACL validation, result extraction and report serialization. It excludes earlier generated-shape/ontology loading and identity checks; pre-execution infrastructure rows can contain the sentinel 0.0. Those are not measured zero-cost evaluations. These per-case intervals must not be labeled pure pySHACL engine time or added to the generation-runtime medians.

The main Single-shot/NLTL_v2 268-requirement experiment is separate. Historical NO_SEMANTIC identifiers retain their original provenance and use **NLTL_v2** in publication-facing labels. The full-repair model sample cannot be relabeled as that main-study condition.

## Selection and representativeness

The locked seed is `NLTL-FULL-REPAIR-V2-MODEL-SCALING-50-20260917-v1`. Manifest algorithm: metadata-only selection, minimum-one Hamilton proportional allocation by source family within verification mode, followed by SHA256(seed|purpose|mode|family|requirement_id) ranking and requirement-ID tie-breaking. Generation results, acceptance and RDF scores are not selection inputs.

| Verification mode | Sample n / 50 | Sample (%) | Benchmark n / 268 | Benchmark (%) |
|---|---:|---:|---:|---:|
| Direct static | 20 | 40.00 | 190 | 70.90 |
| Direct calculation | 15 | 30.00 | 41 | 15.30 |
| Complex readiness | 15 | 30.00 | 37 | 13.81 |

Sample sources are I2 13 (26%), IMO 14 (28%), IMO26 2 (4%), TRAFICOM 21 (42%); population counts are 45, 109, 15, 99, respectively. The sample deliberately overrepresents calculation/readiness requirements. The requested accuracy gives each sampled requirement equal weight; it is not a post-stratified population estimate. The earlier experiment summary's post-stratified estimates are not silently substituted. One run per model and selected requirement supports a paired descriptive comparison, not a general model-size scaling law, reliability across repeats, or a representative population performance claim. Prompt-length and finer difficulty balance have not been established here.

## Search scope, checklist, and unresolved evidence

Searched the workspace, its parent NLTL_v2, Desktop for relevant manuscript/checklist/workbook filenames, and Downloads/Documents for manuscript, checklist, mapping, evaluation and result archives. Inspected existing paper tables, audit-workbook versions, METHODS_EVIDENCE/FILE_INDEX/MISSING_EVIDENCE, scaling reports/scripts/manifests, raw ledgers, runtime workbook and generation event logs. Inspected manuscript ZIP contents and all Ocean_Eng_Journal PDF versions without executing their scripts. An initial skill-path version was stale; the installed PDF skill was found at `pdf/26.1020.11127/skills/pdf/SKILL.md` and used for read-only extraction.

Verified findings: both denominator versions, shared cohort/case identities, macro metrics, manuscript rounding agreement, all runtime summaries, final-artifact provenance and the two exception timing links. Nothing numerical required for a correctly labeled final-stage comparison remains missing.

Unresolved items are the per-case exclusion adjudication/source report, and which manuscript branch the authors intend to reinstate the model comparison into. The later main-study-only source does not itself contain those results. The 373 reconstruction and two missing GPT-OSS evaluation run IDs remain explicitly qualified above.

The authoritative checklist is `D/Ocean_Engineering_Completion_Checklist (1).md`: compared with the unsuffixed version, its contents preserve the original task list, add the source/timing audit and update supported existing statuses. Selection was based on these substantive additions. Only a dated results-evidence section is appended; unrelated tasks retain their original contents and statuses. A complete updated review copy and the original checklist snapshot are saved beside this audit. Broader manuscript tasks remain open because no manuscript edits were authorized here.

`source_sha256.csv` and `verification_checks.json` record input integrity at recovery time. The checklist's subsequent authorized append is recorded separately in `checklist_update_receipt.json`; its original input hash is intentionally retained in the source inventory. All original workbooks, raw results and manuscript files remain unchanged. The figure remains pending and was neither generated nor modified.
