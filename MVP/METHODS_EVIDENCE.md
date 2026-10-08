# Methods evidence for NLTL_v2 maritime-regulation-to-SHACL experiments

Prepared 2026-09-30 from repository `saadahmedrana/NLTL_v2`, local checkout commit `d07197135dc75fe2b80ef36f1cf1f4ef37bae893`. This is a read-only reconstruction: no generation, evaluation, model API, relabelling, or experiment rerun was performed.

## Evidence convention

- **[A] Saved-run evidence**: directly supported by a frozen configuration, manifest, log, result, lock, or workbook record.
- **[B] Current implementation only**: present in the checkout, but the saved records do not prove that this exact revision governed the selected run.
- **[C] Unavailable**: absent or insufficiently recorded; author confirmation is required.

Repository paths below are relative to `MVP/`. Bundle copies are indexed in `FILE_INDEX.md`.

## 1. Experiment identity and status

### Main ablation

**[A] Selected evidence chain**

| Paper label | Selected generation evidence | Behavioural evaluation record | Status |
|---|---|---|---|
| `V2_FALLBACK25` | `SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/RUN_01/` plus the 25 preserved rejected attempt-4 candidates identified by `SHACL_GENERATION_PIPELINE/evaluation/generated_rule_manifests/RUN_01/full_repair_v2_rejected_attempt4_diagnostic.jsonl` | `BEHAVIORAL-R13-FULL-REPAIR-V2-RUN01-20260915T144116505813Z`; diagnostic supplement `BEHAVIORAL-R13-FULL-REPAIR-V2-REJECTED-A4-RUN01-20260915T155743340362Z` | Final reporting policy, but not a native pipeline configuration. It combines the official revised V2 output with a retrospective diagnostic fallback over 25 rejected candidates. |
| `NO_SEMANTIC` | `SHACL_GENERATION_PIPELINE/experiments/LUNA_NO_SEMANTIC_VALIDATOR/RUN_01/`; manifest `SHACL_GENERATION_PIPELINE/evaluation/generated_rule_manifests/RUN_01/no_semantic_generated_rules.jsonl` | Condition `NO_SEMANTIC` in `BEHAVIORAL-R13-20260911T080233539977Z` | Final eligible run pool is RUN_01. |
| `SINGLESHOT` | `SHACL_GENERATION_PIPELINE/experiments/LUNA_CONTEXTUAL_SINGLESHOT/RUN_01/`; manifest `SHACL_GENERATION_PIPELINE/evaluation/generated_rule_manifests/RUN_01/singleshot_generated_rules.jsonl` | Condition `SINGLESHOT` in `BEHAVIORAL-R13-20260911T080233539977Z` | Only RUN_01 is a formal complete run; RUN_02--RUN_10 are placeholders/non-formal. |

The selected records are established by `SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/README.txt`, `CODEX_PREPARE_AUDIT.txt`, `audit_selection.json`, and the three evaluation manifests/summaries above. They specify the eligible run pools and show no later compatible complete 268-requirement/2,186-case evaluation.

**[A] Preliminary/superseded evidence.** Condition `FULL` in `BEHAVIORAL-R13-20260911T080233539977Z` evaluates the earlier `FINAL_LUNA_MAIN/RUN_01` output. It is not the revised `FULL_REPAIR_V2` result and must not be reported as `V2_FALLBACK25`. The ten `FINAL_LUNA_MAIN` and ten `NO_SEMANTIC` operational runs are useful generation/reliability summaries, but the behavioural comparison and audit use RUN_01 only. `FULL_REPAIR_V2` has one complete revised run.

**[A] Main results and completeness.** The common benchmark contains 268 requirements and 2,186 cases. Historical `FULL`: 1,232/2,186 correct, 1,514 executable, 672 infrastructure/no-verdict rows, 102 exactly correct requirements. Revised official V2: 1,472/2,186 correct, 1,780 executable, 406 infrastructure/no-verdict rows, 115 exactly correct requirements. The rejected-attempt-4 diagnostic adds 25 requirements/199 executable cases, 140 correct and 3 exactly correct requirements. The saved audit workbook's retrospective `V2_FALLBACK25` totals are 1,612/2,186 (0.7374199451 end-to-end), requirement-equal-weight accuracy 0.8021100753, and 118 exactly correct requirements. `NO_SEMANTIC`: 1,513/2,186, 1,980 executable, 115 exact. `SINGLESHOT`: 1,349/2,186, 1,779 executable, 98 exact.

### Four-model comparison

**[A] Final experiment.** `SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/` contains a frozen 50-requirement sample with 381 RDF cases, four models, and two artifact modes: `FIRST_GENERATION` and `SELF_REPAIR_FINAL`. All eight final cells have 381 evaluation rows. Smoke runs are explicitly separate and excluded. There is one generation/evaluation run per model, not repeated trials.

The eight complete run identifiers are `RDF-SCALING50-FINAL-FIRST_GENERATION-{LUNA,SOL,GEMINI,GPT_OSS}` and `RDF-SCALING50-FINAL-SELF_REPAIR_FINAL-{LUNA,SOL,GEMINI,GPT_OSS}` in `OUTPUTS/RDF_EVALUATION/.../run_manifest.json`. Luna artifacts were extracted from revised `FULL_REPAIR_V2/RUN_01`; Sol, Gemini, and GPT-OSS came from their final control runs. `REFERENCE/LUNA/extraction_manifest.json` records that extraction performed no generation or evaluation.

| Model key / exact saved model ID | First generation: correct/all; executable | Self-repair final: correct/all; executable |
|---|---:|---:|
| Luna / `gpt-5.6-luna-2026-07-09` | 275/381; 324 | 270/381; 322 |
| Sol / `gpt-5.6-sol-2026-07-09` | 336/381; 381 | 314/381; 359 |
| Gemini / `gemini-3.5-flash` | 278/381; 351 | 283/381; 356 |
| GPT-OSS / `gpt-oss-120b` | 193/381; 257 | 178/381; 212 |

This is a same-model validation/repair comparison: each control configuration assigns its listed model to generator, syntax repair, semantic validator, and vocabulary matcher. It is not evidence that repair always improves behavioural accuracy; Luna, Sol, and GPT-OSS are lower in the final mode on the saved end-to-end metric.

## 2. Repository and configuration provenance

- **[A]** Current checkout: `d07197135dc75fe2b80ef36f1cf1f4ef37bae893`; origin is `https://github.com/saadahmedrana/NLTL_v2`.
- **[A]** Historical main-ablation evaluation commit: `1a3da0e96f59bfbec894f4e5028f08087417a4a0`, clean. Generated-manifest hashes: FULL `421b591ce39d68a577e1cebe4d2a756ad5843f1f140869d1c812a9f89258d76c`, NO_SEMANTIC `1ac7d16274ec9f0ee98de4a5af1b2e2fc73c8efcc08fc8d34d4fa56ba1177679`, SINGLESHOT `2b2ef5f9f619b2345aae2df6294a3faa18428e45303d6da3e5bf821b15de1dc4`.
- **[A]** Revised V2 evaluation commit: `5a51f512b312000ff43aa81a55ab0fe44f1f08d2`, dirty; generated-manifest SHA-256 `67e51e09d2c39aa66446e4e478f6dcace488e6410437434855018127bdb12a49`.
- **[A]** Model-comparison RDF evaluation commit: `8887d83d4f6d6ec8491389a33040929997fb3b67`, dirty. Its lock records reference-config SHA-256 `a04cb8f6fc01f740106f6b8edf5ecf9b006706541b5785d7d944ab367e9d0442`, common-config hash `77982c2f6d9b3eb9698cbf9e4190caebc112133d7627f5a5b2b115aa2db2a49d`, prompt-directory hash `ba75b584d5e0dbc2a92eae64413e2bd0f08769659c2cbe4398b1ecb5df352080`, generator-prompt hash `46fa9b711ec9800c699d7340c965a2bd92c0286b0dc4f90405c11575fdb186e2`, and validator-prompt hash `767978430a40b9e671f6ffbf6b00f73c10b0eca5bb4d7e01c0c7a11e5a5c4a8c`.
- **[A]** Saved run-config SHA-256 values: historical FULL `5bb85e9f5248e674c51af27fac57f669316c8aeb3e36b7ff712b46789a150be2`, NO_SEMANTIC `0d276f13dd1810d0d4237d856d1b0f3d40eb8fad7a846bb167d79c57f00247da`, SINGLESHOT `d1243a7d3d7bfe2ad85004fa12898bbef8dfee56409455975048dd1754e57148`, revised V2 `a04cb8f6fc01f740106f6b8edf5ecf9b006706541b5785d7d944ab367e9d0442`; model-control config hashes are Gemini `90b0e2fff8019fbd8fb44fad9eb1b6a7cf2edaf197029fa0a56d29c22ed89a82`, GPT-OSS `fb1429391c21087e55aa1356a8e09d4bbe51e47cbb1ff23d37450c8d76e1a057`, and Sol `3c29e2fbb1da4095be12619428f7d37bffecd8c285761ba80e9b60e4d9345237`. `FINAL_LUNA_MAIN/MANIFESTS/git_commit.txt` records generation commit `0298217f6ebc95fbdcf6a2abfcf328e86a1d4005`, with an ahead/untracked status snapshot.
- **[A]** Ten-run integrity summaries record normalized FULL config hash `74b667cb958db0d5f39dbd71dad6bba1810197f085350ed5d30d8dd426ec7c76`, normalized NO_SEMANTIC config hash `e7fab9b7b6564037655e4303aa1cdb41ecbe5720812a04b98a4bef2f70b1fb82`, and common queue hash `d6b540573dd7b6af5c59e369b2f37b86a864eefd81ea44ef49f137af07bd7331`.
- **[A]** The model-comparison lock records per-file implementation hashes, including full runner `0fe47afa996c88749898b2e7b61ba59536908a146e2a3ecf2e463ffab20b1b4c`, SHACL validator `0857529505be41f1b444581a655843e663d60702e3ddde1282841160482cafbe`, behavioural execution `2576262d33e0adcac3075407d82e334da09b870de27710005947a185fc435f7e`, and analysis `f352c5bd01e636302fa71f96a624f7b3bdfabd348b89e8b1ec66dba0e559e647`; all other recorded code hashes remain verbatim in `configuration_lock.json`.
- **[C]** A single clean generation commit is not recorded for every selected condition/control. Dirty evaluation checkouts prevent treating the evaluation commits as complete source snapshots.

## 3. Regulatory requirements and benchmark construction

**[A] Frozen benchmark state.** Repository-root `verify_full_benchmark_integrity_final.py` (path `../verify_full_benchmark_integrity_final.py` from `MVP/`) checks the manifest/lock hashes, unique requirement and case identifiers, unique RDF paths, source-family mappings, unchanged pilots, exact totals, and equality of coverage with COMPLETE R13 contracts. The final direct benchmark is:

| Source family | Requirements | RDF cases |
|---|---:|---:|
| Inland Waterways (`I2`) | 45 | 499 |
| TRAFICOM | 99 | 755 |
| IMO SOLAS chapter II-1 (`IMO`) | 109 | 805 |
| IMO SOLAS chapter II-2 (`IMO26`) | 15 | 127 |
| **Total** | **268** | **2,186** |

Verification modes are 190 direct static, 41 direct calculation, and 37 complex readiness requirements. The full R13 lock also records categories outside the executable direct benchmark: 191 static, 43 static calculation, 45 complex, 19 dynamic, and 15 physical. Contract status totals are COMPLETE 268, legacy 34, engineering review 5, insufficient 2, dynamic 2, scope 1, and blocked 1.

**[A] Inclusion/exclusion rule.** `SHACL_GENERATION_PIPELINE/src/nltl_pipeline/retrieval/context.py:176-194` implements eligibility as not figure-dependent and either an exact eligible category/mode pair with COMPLETE status, or a legacy active-status fallback. The locked benchmark covers COMPLETE direct static, direct calculation, and complex-readiness contracts; deferred dynamic and physical checks are excluded from behavioural execution.

**[A] RDF fixtures and labels.** Per-family manifests bind requirement ID, case ID, expected PASS/FAIL, RDF path, rationale, source/clause, and pattern. Locks hash the fixture files and state `generated_without_inspecting_generated_shacl=true`. `SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13/README.md` and its I2 Batch A README state that fixtures were authored from the regulation and frozen R13 contracts, use small requirement-level graphs, and fix PASS/FAIL oracles without inspecting generated SHACL; pilots remained unchanged. The global run manifests verify fixture hashes before and after evaluation.

**[C] Upstream corpus preparation.** The repository does not fully reconstruct who extracted the requirement text from the regulatory PDFs, how borderline clauses were adjudicated, reviewer identities/counts, or every exclusion decision before the FINAL_LOCK_R13 tables. These should not be inferred from the final lock.

## 4. Corrections and exclusions

**[A]** Read-only inspection of `SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/NLTL_Manual_Audit_with_Model_Scaling_FINAL.xlsx` found 2,186 CaseReview rows: 140 marked reviewed, 2,046 not reviewed; 26 proposed `RDF_EDIT` items; no agreed decisions; and zero applied label changes. The original expected labels therefore remained in force for all three systems. The workbook protocol says an AGREED label-only change would update the expected label across all systems, while an RDF edit or execution fix requires a new offline rerun and cannot reuse an old verdict. Missing values are retained rather than zero-filled.

**[A]** No generated-output exclusions were silently applied in the frozen summaries: missing shapes, parse failures, and execution errors stay in the all-case denominator. The model-comparison smoke subsets are separate and excluded from final results.

**[C]** The 26 proposed RDF edits remain unresolved. Any paper statement that labels were “corrected” needs author evidence not present here.

## 5. Information boundaries and few-shot selection

**[A/B] Generation inputs.** Saved prompts/examples and `SHACL_GENERATION_PIPELINE/src/nltl_pipeline/prompts.py:40-58` show the generator receives the requirement, source metadata, R13 context pack, allowed vocabulary guidance, and selected few-shot examples. Repair receives the previous candidate plus deterministic/semantic issues (`prompts.py:89-104`); the optional escape generator receives the requirement, context, prior candidate and unresolved issues (`:106-116`). Syntax repair receives the invalid candidate and parser/static errors (`:118-130`). Vocabulary matching receives issue terms and candidate vocabulary options (`:132-147`).

**[A/B] Semantic-validation boundary.** `SHACL_GENERATION_PIPELINE/src/nltl_pipeline/prompts.py:60-87` explicitly instructs the validator to judge the requirement against the candidate and context and states that no ship graph or expected RDF outcome is supplied. Evaluation fixtures and PASS/FAIL labels live under `SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13` and are loaded by the separate evaluation runner after generation. Saved representative run records contain no fixture labels in model inputs. The code and artifacts support the intended separation, but **[C]** there is no external-service attestation beyond the saved payload/log evidence.

**[A] Few shots.** The frozen library has 22 `FS-*` synthetic examples marked “synthetic-not-benchmark-ground-truth.” `SHACL_GENERATION_PIPELINE/src/nltl_pipeline/retrieval/fewshot.py:64-96` ranks by token-set Jaccard similarity between requirements, adds a +2 readiness bonus for complex-readiness examples, sorts deterministically by score then example ID, and selects two. No few-shot identifier overlaps an evaluation requirement or RDF case identifier. Vocabulary terms can overlap because both use the same locked vocabulary; this is not requirement overlap.

## 6. Pipeline, acceptance, and ablations

**[B] Current full implementation.** In `SHACL_GENERATION_PIPELINE/src/nltl_pipeline/orchestration/runner.py`, eligibility is checked at `:133-141`, context/few-shots loaded at `:149-160`, and attempts bounded at `:162-164`. Initial generation is `:196-198`; later attempts use escape or semantic repair (`:199-207`). Each candidate may receive syntax repair (`:212-225`), then deterministic checks (`:228-286`), semantic validation (`:292-308`), vocabulary matching after rejection (`:309-340`), and optionally a fresh escape candidate on stall/oscillation/repeated issues (`:342-356`). Acceptance requires deterministic validity and a semantic validator `accept`; the loop breaks at `:388-391`. Only an accepted artifact is published as official final output; unsuccessful last candidates are preserved as diagnostics (`:399+`).

**[A] Saved limits/settings.** Full/revised configs set four semantic attempts, up to three syntax repairs per attempt, two few shots, matcher limit 12 and threshold 0.24, validator contract retries 2, and other structured-call contract retries 2. The revised V2 README describes four candidates and at most one fresh escape hatch. Contract “retries=2” means at most three calls for that logical structured response (`runner.py:55-93`) and does not consume an additional semantic attempt. Transport retry statuses are 408, 429, 500, 502, 503, and 504, with 5--60 s backoff; persistent transient retry is enabled. Current `SHACL_GENERATION_PIPELINE/src/nltl_pipeline/api/client.py` stops non-persistent retries after eight cycles but permits persistent retry until a non-transient outcome.

**[A] Failure/candidate policy.** Syntax-repair exhaustion, deterministic invalidity at attempt exhaustion, validator contract failure, or four unsuccessful semantic candidates produces no official final shape. The last candidate remains diagnostic. `V2_FALLBACK25` is a later reporting rule that substitutes the 25 preserved rejected attempt-4 candidates for behavioural evaluation; it did not alter the generation run or acceptance decision.

| Component | Revised V2/full | NO_SEMANTIC | SINGLESHOT |
|---|---:|---:|---:|
| Context + 2 few shots | yes | yes | yes |
| Generator | yes | yes | one call only |
| Turtle/static/meta/runtime checks | gating | gating | diagnostic/read-only |
| Syntax repair | yes | yes | no |
| Semantic validator | yes | no | no |
| Vocabulary matcher | after relevant rejection | no | no |
| Semantic regeneration/repair | up to 4 candidates | no | no |
| Escape generation | conditional | no | no |
| Official acceptance flag | deterministic + semantic | not used (`accepted=false`) | not used (`accepted=false`) |

`SHACL_GENERATION_PIPELINE/src/nltl_pipeline/orchestration/no_semantic_validator.py:145-320` and `singleshot.py:179-280` implement the ablations. Their saved configurations/manifests are [A]; exact current line implementations are [B].

## 7. Models, endpoints, and generation settings

**[A]** Main ablation uses `gpt-5.6-luna-2026-07-09` for generator, syntax repair, semantic validator, and vocabulary matcher where those roles are enabled. Saved limits are 70 requests/min, 0.05 min interval, output caps 16,000 tokens for generation/syntax, 3,000 for validator, and 700 for matcher.

**[A]** Model comparison uses the exact IDs in Section 1. Sol/Gemini/GPT-OSS config files record the expected Aalto gateway endpoints: Responses at `https://ai-api-v2.aalto.fi/v1/responses` for Sol/GPT-OSS and Chat Completions at `https://ai-api-v2.aalto.fi/v1/chat/completions` for Gemini. Luna also uses a Responses client. `scripts/provider_clients.py:115-143` constructs the saved comparison payloads.

**[A/C]** Runtime endpoint URLs are loaded from environment variables, and the historical Luna records do not preserve the actual value. The expected endpoint is not proof of the live endpoint. Underlying cloud provider/deployment revision beyond the exposed model ID is unrecorded. Payload code sends model, input/messages, and output-token limit; it does not send temperature, top-p, or a sampling seed. Server defaults and backend determinism are therefore [C]. No environment or credential file was inspected or copied.

## 8. Model-comparison sampling and artifact selection

**[A]** `scripts/freeze_samples.py:21-24` fixes seed `NLTL-FULL-REPAIR-V2-MODEL-SCALING-50-20260917-v1` and mode targets 20 direct-static, 15 direct-calculation, 15 complex-readiness. Within mode, `:28-69` allocates at least one requirement per source family and distributes remainders by Hamilton allocation, then ranks candidates using SHA-256 of the seed/stratum/ID; selection uses metadata only (`:87-99`). Sample-manifest SHA-256 is `abad236af40fbe22985957457fe1f7a8149a10aa83e280204f9d547bff16a2cf`. There are no repeated samples/runs.

**[A]** `scripts/run_rdf_evaluation.py:73-97` extracts first generation only through an unambiguous response-wrapper or code-fence normalization; it performs no Turtle repair, semantic rewrite, or retry. At `:211-270`, final mode selects the official accepted final artifact while first-generation selects iteration-1 output. `:291-342` checks exactly 381 cases. Luna is extracted from the revised reference run; each other model has one final control generation manifest.

## 9. Deterministic and behavioural evaluation

**[B] Generation-time validation.** `SHACL_GENERATION_PIPELINE/src/nltl_pipeline/validation/shacl.py:336-705` parses Turtle; checks SHACL shapes, targets and constraints; runs pySHACL Meta-SHACL against an empty graph; executes a synthetic target-activation/runtime smoke test; parses SPARQL constraints; and enforces vocabulary/scope/external-term, ownership, datatype/unit, numeric `sh:hasValue`, dependency, readiness, selector, and cardinality rules. `meta_shacl_valid` is composite: it is false for either a Meta-SHACL failure or a synthetic runtime-smoke execution/no-report-graph failure. SPARQL parser failures are appended to `errors` and make overall `valid=false`, but do not independently flip the meta field.

**[A] Behavioural execution.** `SHACL_GENERATION_PIPELINE/evaluation/experiment_runner/execution.py:33-43` records pySHACL settings: RDFS inference, advanced and meta-SHACL enabled, ontology graph supplied, imports disabled, abort-on-first false, and infos/warnings not treated as conformance. At `:228-325`, each RDF graph is parsed and executed with the generated shape; missing artifacts, RDF/Turtle parsing failures, pySHACL exceptions, and missing report graphs become infrastructure/no-verdict rows.

**[A] Confusion matrix and denominators.** PASS is the positive class: TP = expected PASS/conforms; TN = expected FAIL/nonconforms; FP = expected FAIL/conforms (false accept); FN = expected PASS/nonconforms (false reject), `execution.py:150-186`. End-to-end accuracy is correct/all cases, so missing/error rows count as not correct. Usable accuracy is correct/executed only. Requirement-level exact correctness requires every case for that requirement to execute and be correct (`analysis.py:88-137`). The workbook's “macro”/equal-weight measure is the arithmetic mean of per-requirement correct/total-case accuracy, not macro-F1. No saved script reports a hypothesis test or confidence interval.

## 10. Manual audit evidence

**[A] Main audit selection.** Seed `NLTL-MANUAL-AUDIT-20260915-v1` provides deterministic SHA-256 order, 27 batches (26 x 10 requirements plus 8), and one expected PASS plus one expected FAIL case per requirement (536 case IDs). The same cases are presented for V2, NO_SEMANTIC, and SINGLESHOT. Packaging instructions explicitly prohibit grading during packaging.

**[A] Main audit status.** Each system sheet has 268 requirements. V2 has 70 `REVIEWED` and 198 not reviewed; NO_SEMANTIC has 67 reviewed, 3 not assessable, 198 not reviewed; SINGLESHOT has 60 reviewed, 10 not assessable, 198 not reviewed. Seventy rows per sheet identify the reviewer/status source as `AI-assisted draft`; the remainder is blank. This is not evidence of a completed independent human audit.

**[A] Scaling audit.** Ten requirements were selected with seed `NLTL-MANUAL-AUDIT-SCALING-10-20260918-v1`: 4 static, 3 calculation, 3 complex; family allocation I2 3, TRAFICOM 4, IMO 2, IMO26 1. Blinding seed `NLTL-MANUAL-AUDIT-BLINDING-20260918-v1` assigns each requirement's eight artifacts (4 models x 2 modes) opaque IDs A01--A08 by SHA-256 order. Identity keys were withheld until scoring. The 80 slots include 59 AVAILABLE, 16 MISSING, and 5 UNPARSEABLE artifacts. The final workbook records reviewer `ChatGPT blind audit` for all 80 on 2026-09-17, then unblinding on 2026-09-18: 30 CORRECT, 8 MINOR_ERROR, 26 MAJOR_ERROR, and 16 NOT_ASSESSABLE; no suspected benchmark fault or adjudication flag was recorded.

**[A] Rubric.** Semantic items Q1--Q7 and implementation items CQ1--CQ3 use 0--2 anchors, with semantic maximum 14 and implementation maximum 6. Primary verdicts are CORRECT, MINOR_ERROR, MAJOR_ERROR, NOT_ASSESSABLE, or UNCLEAR; critical-error rules can override numerical means. Missing/unavailable items remain explicit and are not zero-filled. The five unparseable slots are separately recorded at packaging; the final workbook verdict totals should be used rather than assuming every unparseable slot became NOT_ASSESSABLE.

**[C]** No independent human reviewer count, credentials, inter-rater agreement, reconciliation transcript, or completed human adjudication is recorded. Do not describe either audit as a human expert audit without further evidence.

## 11. Time, tokens, costs, software, and environment

**[A] Historical FULL RUN_01:** 10,177,448 input, 1,896,019 output, 12,073,467 total tokens; 1,192 logical/physical calls; 21,380,723 ms summed wall time; configured estimate USD 21.553562. Ten-run pool: 105,020,215 input, 19,509,465 output, 124,529,680 total; 12,264 logical and 12,638 physical calls; 260,788,602 ms; USD 222.077005.

**[A] NO_SEMANTIC RUN_01:** 2,473,426 input, 649,751 output, 3,123,177 total; 328 logical/physical calls; 7,383,910 ms; USD 6.371932. Ten-run pool: 31,205,108 tokens; 72,379,197 ms; USD 63.535438. **SINGLESHOT RUN_01:** 2,374,468 input, 553,179 output, 2,927,647 total; 268 logical/269 physical calls; 8,329.882 s; USD 5.693542.

**[A/C]** Luna cost assumptions are USD 1 per million input tokens and USD 6 per million output tokens, described as an indicative configured/Azure list estimate, not an Aalto invoice. A revised-V2 aggregate cost and comparable model-comparison costs/prices were not found. Per-call revised-V2 token/elapsed records exist, but should not be promoted to a rigorously measured end-to-end runtime without an explicit aggregation protocol.

**[A]** Behavioural evaluation manifests record Python 3.13.5, RDFLib 7.6.0, and pySHACL 0.31.0. The model-comparison evaluator records the same versions and runner version 1.1.0. `pyproject.toml` and `requirements.txt` supply declared ranges/dependencies.

**[C]** No complete environment lock/freeze, operating-system version, CPU/GPU model, RAM, container image, gateway build, or model-weight revision is recorded. Generation happened through a remote API; no local model weights are included.

## 12. Safe wording for a Methods section

The strongest supportable description is: the study evaluated 268 frozen COMPLETE direct-verification requirements (2,186 independently locked RDF cases) across three pipeline conditions; reported “V2_FALLBACK25” is a retrospective combination of the revised full pipeline's official accepted outputs with 25 preserved fourth-attempt diagnostic candidates, not a generation-time fallback setting. A separate deterministic stratified 50-requirement/381-case comparison ran four exact model IDs once each and contrasted normalized first responses with official same-model validated/repaired outputs. Missing, parsing, and execution failures remained in end-to-end denominators. Saved audit evidence is AI-assisted/ChatGPT-based and proposed fixture edits were not applied.

See `MISSING_EVIDENCE.md` before making stronger claims about human review, reproducibility, providers, timing, or statistical inference.
