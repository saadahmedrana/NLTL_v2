# Ocean Engineering manuscript: completion checklist

Updated: 15 October 2026
Status: evidence collection and initial manuscript/source-code audit. No manuscript text changed in this step.
Working order: collect and reconcile results -> settle definitions and evidence -> revise Methods -> revise Results -> revise Introduction/Related Work -> revise Discussion/Conclusions -> final audit.
Tick an item only when its evidence and manuscript change have both been checked. A topic appearing in the draft does not by itself mean it is complete.

## Current reference values

- Main experiment: 268 requirements; 2,160 RDF test configurations.
- NLTL_v2: requirement-level macro accuracy 76.11%; executable coverage 91.79%.
- Single-shot: requirement-level macro accuracy 68.47%; executable coverage 82.46%.
- Updated manual review, 70 requirements per workflow:
  - Single-shot: correct 22, minor defect 8, major defect 40.
  - NLTL_v2: correct 42, minor defect 15, major defect 13.
- These are reported aggregate values, not a fresh recomputation.
- Confirm whether the updated review uses the same previously sampled requirement IDs.
- Prior semantic-fidelity and implementation-quality averages are not automatically valid after the revised review.

## 1. Results data first

- [ ] D01 — Freeze the current manuscript, figure-generator version, benchmark release and result files used for this revision. Record filenames, version/commit IDs and the mapping between requirements and RDF cases.
- [ ] D02 — Reconcile every main result with the authoritative tables/logs, including per-source and per-verification-mode denominators. Keep requirement counts, case counts and generated-artifact counts distinct.
- [ ] D03 — Obtain the updated review sheet: requirement ID, workflow, final category, defect explanation and applicable criterion scores. Reconcile the 70-per-workflow totals and confirm how previously unassessable outputs became assessable.
- [ ] D04 — Record how Saad and Haitham performed the review: jointly, independently then reconciled, or initial review followed by adjudication. Record the actual roles and any blinding. Do not invent independent reviewer agreement.
- [ ] D05 — Recalculate semantic-fidelity and implementation-quality averages and criterion-level summaries from the revised item-level scores, or remove/mark old summaries pending revision.
- [ ] D06 — Collect generation/authoring logs: requirement ID, model/version, workflow, repetition, output status, stage timings, repair iterations, token use and costs if available. Identify the exact start/end of each timer.
- [ ] D07 — Collect validation timings separately: parsing/checks, pySHACL execution, and total behavioural evaluation; record whether graph loading and process startup are included.
- [ ] D08 — Collect model-comparison results: exact model IDs and dates, prompts/settings, subset IDs, requirement and case counts, output counts, executable coverage, accuracy, runtime, repetitions and failure categories.
- [ ] D09 — Collect actual dataset-scaling runs, if available: multiple workload sizes, exact requirement IDs, RDF case counts, graph sizes/triple counts, wall time and repeats. A comparison between models at one size is not by itself a scalability experiment.
- [ ] D10 — Document hardware/software, local versus API execution, concurrency, caching, timeout policy, warm/cold runs and rate limits. Use consistent conditions or state the differences.
- [ ] D11 — Assemble one clean results table with explicit units, denominators, missing values and uncertainty summaries supported by the available repetitions. Never fabricate repeated-run variability.

### Planned placeholder: runtime and engineering effort

- [ ] R01 — Add a Results subsection on runtime and authoring effort, supported by an experimental-protocol subsection in Methods.
- [ ] R02 — Insert an explicitly pending table using this structure; keep authoring and verification activities separate.

| Activity | Workflow/comparator | Requirements / RDF cases | Timing boundary | Total elapsed time | Per-requirement time | Human effort | Evidence type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SHACL generation and repair | NLTL_v2 | Pending | Define | Pending | Pending | Pending | Measured logs |
| SHACL generation | Single-shot | Pending | Define | Pending | Pending | Pending | Measured logs |
| SHACL authoring | Human expert, if measured | Pending | Define | Pending | Pending | Pending | Matched timed study, if available |
| Behavioural validation | Generated constraints | Pending | Define | Pending | Pending | Not the same as elapsed runtime | Measured logs |

Do not turn a published estimate of manual compliance checking into a measured manual SHACL-authoring baseline. If no matched human-authoring measurement exists, use a clearly labelled literature/context comparison and limit the efficiency claim.

### Planned placeholder: model comparison and scalability

- [ ] R03 — Add a Results subsection provisionally titled “Runtime, model comparison, and scalability”; split it if the evidence supports distinct experiments.
- [ ] R04 — Add a pending cross-model table with the following fields.

| Model/version | Workflow | Subset/version | Requirements | RDF cases | Output rate (%) | Executable coverage (%) | Macro accuracy (%) | Total generation time | Median per-requirement time | Validation time | Repetitions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending |

- [ ] R05 — Reserve a model-comparison figure for runtime, accuracy and executable coverage. Show output rate separately if it adds information; define it before plotting. Choose the final chart after data arrive.
- [ ] R06 — Reserve a true scaling figure of runtime against measured workload size, if multiple sizes exist. Report which size varies: requirements, configurations, RDF triples, or another defined quantity. Do not assert a complexity law from one workload.
- [ ] R07 — Mark all missing entries as pending during drafting. Remove or complete placeholders before submission.

## 2. Prior-work narrative and contribution

- [x] P01 — The supplied current Introduction connects Al-Shami et al.'s manual framework and proposed LLM-assisted extraction/translation to the present authoring problem, including verification. Citation key: alshami2026regulatory. Final bibliography verification remains A02.
- [x] P02 — The supplied Introduction and structured-data background explain AnchorMap as complementary canonical-variable alignment rather than SHACL generation. Citation key: rana2026anchormap. No integration claim is made.
- [x] P03 — The supplied Introduction identifies the thesis as the precursor and describes the broader benchmark, workflow comparison and manual review as extensions. Citation key: rana2026thesis. Exact reuse and novelty audit remains P05.
- [ ] P04 — Confirm the thesis's public repository record/citation metadata. The supplied thesis PDF is available; a matching public Aaltodoc record was not located in the initial web search. Do not invent a URL.
- [ ] P05 — State precisely what is reused, extended and new relative to the thesis and the two papers. Describe the present method as constraint authoring with checking, within the stated scope.
- [ ] P06 — Align research questions, contributions and results sections so every claimed contribution has evidence.

Suggested narrative relationship: semantic engineering data and manually encoded checks (Al-Shami et al.); complementary variable alignment (AnchorMap); preliminary LLM-to-SHACL work (thesis); broader generation-and-repair evaluation with independent behavioural tests (present paper). This is a conceptual relationship, not an assumed publication chronology.

## 3. Alternatives and justification of the method

- [ ] M01 — Build a cited comparison of the main approach families: manual expert authoring; templates/patterns and deterministic extraction; supervised semantic parsing/fine-tuning or training; ontology/data-derived shape induction; existing-LLM prompting with context/retrieval and iterative checking; hybrids. Treat these as a practical taxonomy, not proof that only a fixed number of methods exists.
- [ ] M02 — Compare the same target task across approaches. Distinguish extracting a clause, aligning a variable, inducing a descriptive data schema, and encoding a normative regulatory obligation.
- [ ] M03 — Find primary research on manual SHACL/rule-authoring effort, prioritising timed studies with numerical measurements. Record task, expertise, sample size, measured versus estimated time and whether review/rework is included.
- [ ] M04 — Extract relevant prior-work timing numbers with their original scope. Follow primary references where needed. Do not use numbers merely because they support the desired story.
- [ ] M05 — Explain why this study uses an existing model rather than training/fine-tuning: labelled paired-data requirements, regulatory/ontology variation, maintainability, compute and study scope, supported by literature and actual project constraints. Do not claim training is inherently inferior without a controlled comparison.
- [ ] M06 — Explain why expert authoring remains valuable and why repeated patterns may favour templates. Present hybrid approaches as alternatives and acknowledge what was not tested.
- [ ] M07 — Tie the selected method to ontology grounding, deterministic executability checks, semantic feedback and human review; separate motivation from experimentally demonstrated benefits.

## 4. Test design and metric definitions

- [ ] E01 — Define each checking stage and its role: syntax parsing, deterministic shape/query checks, pySHACL execution, LLM semantic checking during generation, and independent post-generation behavioural evaluation.
- [ ] E02 — Audit data separation: expected outcomes and behavioural test graphs must not reach generation or repair. Identify any permitted synthetic prompt examples and establish their separation from held-out evaluation cases.
- [ ] E03 — Document how expected PASS/FAIL labels were derived from regulatory interpretations, who reviewed them, and how those labels remain independent of generated outputs.
- [ ] E04 — Justify both PASS and FAIL cases: they expose false rejections and false acceptances and prevent always-PASS/always-FAIL rules from appearing successful. Explain applicability, boundary, missing-data, exception and alternative-route cases where present.
- [ ] E05 — Explain why one RDF configuration is insufficient for a requirement with multiple behaviours. Map cases to obligations, branches and boundaries. Document how the number and diversity of cases per requirement were chosen.
- [ ] E06 — Define output availability/output rate, syntax validity, executable artifact and completed executable verdict separately. Distinguish an expected FAIL verdict from an execution failure, missing output or timeout.
- [ ] E07 — Formalise executable coverage using the manuscript's current strict definition: a requirement is covered only when every assigned configuration receives a completed PASS/FAIL verdict, regardless of correctness. Keep case-level verdict availability separate if also reported.
- [x] E08 — The supplied Methods defines per-case agreement, per-requirement accuracy and macro accuracy, assigns zero credit to no-verdict cases and explains equal requirement weighting. Check consistency of new experiments separately under D02/S04.
- [ ] E09 — Define all-correct requirement rate, false acceptance and false rejection; give denominators for every displayed rate. Do not silently substitute conditional accuracy among executable cases for the main accuracy metric.
- [ ] E10 — Audit every mathematical symbol and index: requirements, cases, expected/observed outputs, missing outcomes, indicators, sets, sample sizes, weights and normalisation. Include a compact notation table if useful.
- [x] E11 — The supplied Methods and Limitations explicitly bound conclusions to tested configurations and distinguish behavioural agreement from semantic equivalence or full ship compliance.
- [x] E12 — The supplied Background, Discussion and Conclusions distinguish readiness/evidence availability from correctness of external engineering assessments.

## 5. Manual assessment and its relationship to behavioural testing

- [ ] H01 — Cite methodological precedents for manual semantic review of generated formal rules/code and for testing with known positive/negative cases. Use task-relevant primary sources.
- [ ] H02 — Document the 70-requirement sampling frame, randomisation procedure, seed if retained, replacement policy and shared IDs across workflows. Establish whether sampling occurred before reviewing outputs.
- [ ] H03 — Assess sample composition by regulatory source, verification mode and other relevant difficulty features. Random sampling does not guarantee the observed sample mirrors every subgroup; report the actual distribution.
- [ ] H04 — Specify the independent review evidence: source clause, ontology context, generated artifact, and supporting cases. State whether reviewers saw workflow identity or automated scores.
- [ ] H05 — Map Q1-Q7 and CQ1-CQ3 to source evidence and study-specific reasoning. Distinguish borrowed criteria from adapted/new criteria; literature motivation does not validate every chosen scoring anchor.
- [ ] H06 — Define 0/1/2 anchors, N/A, unclear/unassessable handling and score denominators. Explain equal weighting and what numerical normalisation does; arithmetic alone does not establish rubric validity.
- [ ] H07 — Finalise correct/minor/major definitions and check them against the revised review records. Recommended principle: severity follows effect on regulatory meaning/applicability/conformance decisions, not repair time or number of edited lines. A wrong target is normally major if it changes what is checked.
- [ ] H08 — Specify the aggregation rule: any major defect gives an overall major verdict; minor applies only in the absence of a major defect; correct means no identified defect within scope. Keep category verdicts separate from average criterion scores.
- [ ] H09 — Record concrete borderline examples and the agreed rationale, especially wrong targets, missing conditions, unit/threshold errors, redundant logic, diagnostic errors and source-reference problems. Do not rewrite definitions to force a preferred result.
- [ ] H10 — Cross-tabulate manual categories against behavioural outcomes for the same reviewed requirements. Identify outputs that pass all tests yet contain a reviewed major defect, and inspect the reason for each disagreement.
- [ ] H11 — Explain the manual review as complementary evidence about semantic fidelity and possible gaps in the test suite/reference labels. It does not prove that the automated evaluator is universally correct. Review benchmark cases if discrepancies indicate oracle/test-design issues.
- [ ] H12 — Report reviewer agreement only if independent initial ratings exist. For a joint review, describe consensus and adjudication rather than inventing kappa or an agreement percentage.
- [ ] H13 — Update the abstract, Methods review procedure, Results narrative, Figure 7 caption, review-score tables, representative defects, Discussion and Conclusions consistently. Reconfirm zero unassessable/unclear counts rather than relying on the old caption.

## 6. Representativeness and reproducibility of additional experiments

- [ ] S01 — Define whether additional model experiments use all 268 requirements or a subset, and give exact selection/version IDs.
- [ ] S02 — Compare subset and full-dataset composition: regulatory source, verification mode, clause/constraint complexity, case counts, and available prompt-length or calculation/branch indicators.
- [ ] S03 — Explain selection logic and any stratification. Include difficult and unsuccessful cases; avoid selecting only requirements already known to work.
- [ ] S04 — Use the same requirements, RDF cases and evaluator across models when claiming a direct comparison; document any changes in prompts, context limits, parameters or retry budgets.
- [ ] S05 — Use paired requirement-level comparisons where supported by the records. Keep exploratory subset findings distinct from full-benchmark conclusions.
- [ ] S06 — Separate latency, throughput, cost, coverage and correctness. Define output rate's numerator/denominator explicitly; it need not equal executable coverage.
- [ ] S07 — Explain whether increasing workload changes composition as well as size. Repeat timings where feasible and report variability supported by real measurements.
- [ ] S08 — Document reproducibility: model/version dates, API/local runtime, prompts, dependency versions, benchmark hashes, random seeds, timeout/failure handling and scripts.

## 7. Literature and final manuscript audit

- [ ] A01 — Build a claim-to-source table with the claim, primary citation, relevant passage/page, evidence type, limitation and intended manuscript location.
- [ ] A02 — Resolve all placeholders and missing citations. Distinguish measured findings, published estimates, assumptions, design choices and proposed future work.
- [ ] A03 — Reconcile every number across abstract, text, tables, figures and conclusion. Check rounding using the underlying values.
- [ ] A04 — Keep Results tables/figures in Results; retain the agreed figure palette and final print-size label checks.
- [ ] A05 — Reassess limitations: finite synthetic cases, ontology dependence, interpretation uncertainty, reviewer dependence, model/version sensitivity, subset coverage and absence of a matched human-effort study if applicable.
- [ ] A06 — Read and edit the paper section by section with Saad after the results data and definitions are settled.

## Verified source leads and cautions

### Haitham Al-Shami et al., Ocean Engineering (2026)

Title: Regulatory requirement classification and semantic verification for model-based ship design.
DOI: https://doi.org/10.1016/j.oceaneng.2026.126356
Supplied source: HAITHAMSOCEANENGINEERINGJOURNAL.pdf.
Checked: Section 6 discussion of computational profile and manual effort; discussion around printed pages 12-13.

- Reports automated SHACL validation of the case study in 2.54 seconds.
- Estimates 10-20 minutes per requirement for manual checking, described as roughly 30-70 engineering hours for 201 requirements.
- These are an estimated manual-checking baseline and a reported automated-validation runtime, not a timed experiment in manual SHACL authoring.
- Explicitly motivates LLM-assisted extraction/translation while requiring checking and human review.
- Use as a direct research-continuity link; do not claim the present paper automates extraction unless it actually does.

### AnchorMap, 40th ECMS (2026)

Title: AnchorMap: A Multi-Agent Pipeline for Variable Standardisation in Maritime Engineering.
DOI: https://doi.org/10.7148/2026-0389
Official proceedings record: https://www.scs-europe.net/dlib/2026/2026-0389.html
Supplied source: AnchorMap__A_Multi_Agent_Pipeline_for_Variable_Standardisation_in_Maritime_Engineering (1).pdf.
Checked: abstract and task framing.
- Relevant to canonical variable alignment, grounding and controlled automation with human review.
- It addresses variable standardisation, not regulatory-clause-to-SHACL generation.

### Saad Ahmed Rana, master's thesis (2026)

Title: Translating Natural-Language Maritime Regulations into Machine-Readable Rules Using Large Language Models.
Supplied source: THESIS_RANA.pdf.
Checked: abstract and future-work discussion around printed pages 50-51.
- Evaluates 90 regulatory cases and discusses ontology/ship-context grounding, repair and manual semantic assessment.
- Calls for broader regulatory/ship-graph evaluation and discusses hybrid template/LLM authoring.
- Public repository citation remains to be resolved; the initial web search did not identify the exact Aaltodoc item.

## 15 October audit: current manuscript and supplied source code

Reviewed inputs: Pasted text(20261015-121731).txt (manuscript), Pasted text (2)(10).txt (figure generator), and src(3).zip (pipeline source). The ZIP contains no events.jsonl, evaluation_results.csv/JSONL, batch_result.json or pipeline configuration files. No model mean runtimes can be calculated from this upload alone.

### Timing locations established from the code

Let OUTPUTS be the resolved value of paths.outputs in the configuration used for the experiment. In this source layout the default configuration is MVP/config/pipeline.json, and relative paths resolve against MVP, not necessarily the shell working directory. Overrides must be checked too.

| File under OUTPUTS or the chosen evaluation output root | Useful fields | Interpretation |
| --- | --- | --- |
| runs/<run_id>/events.jsonl | run_started/run_finished: timestamp_utc, session_id, run_id, requirement_id | Difference gives recorded requirement-run elapsed time. Context/few-shot preparation happens before run_started; tracker export happens after run_finished in both inspected workflows. |
| runs/<run_id>/tables/runs.csv | STARTED_UTC, FINISHED_UTC, FINAL_STATUS, ATTEMPTS | Derived per-requirement view of the same run event timestamps. |
| runs/<run_id>/tables/api_calls.csv | ROLE, MODEL, STATUS, ELAPSED_MS | Contains BOTH transport-attempt rows and completed-call totals. Never sum every row. |
| runs/<run_id>/events.jsonl | api_call_completed: role, model, elapsed_ms | One completed logical API call, including its internal rate-limit waits/retries/backoff in the inspected live client. It excludes time outside that call and cannot represent calls that never completed. |
| runs/<run_id>/tables/iterations.csv | GENERATOR_ELAPSED_MS, VALIDATOR_ELAPSED_MS | Selected iteration-call timings, not necessarily all formatting retries, syntax corrections, matcher calls, or local processing. Not the complete pipeline total. |
| sessions/<session_id>/batch_result.json | results, repetition, queue, execution_mode where present | Links runs to a batch/repetition. Single-shot result.elapsed_ms is the generator-call duration, not requirement-run wall time. |
| EVAL-<evaluation_id>-<timestamp>/evaluation_results.csv or .jsonl | elapsed_ms, execution_ok, expected_match, requirement_ids, shape_file | Per-case evaluation time including hashes, shape/data loading, pySHACL and report construction. Not pure pySHACL time. Evaluation output root is passed to the evaluator. |

Source evidence: reporting/tracker.py, telemetry/events.py, api/client.py, orchestration/runner.py, orchestration/singleshot.py, cli.py and evaluator/bulk.py under src/nltl_pipeline.

### Additional tasks from this audit

- [ ] C01 — Upload/logically identify the actual completed experiment output folders and configurations. Link each session to the benchmark release, generation run, model-role settings, requirement subset and repetition.
- [ ] C02 — Add a read-only timing-summary utility (reporting/timings.py or an ocean_reporting helper). Existing experiments do not require rerunning merely to recover the recorded event interval.
- [ ] C03 — For each unique run_id, use its actual run_started/run_finished pair; calculate seconds from timestamps. Preserve completed unsuccessful generations in attempted-run summaries. Report incomplete, interrupted, malformed and missing-timestamp runs separately; never assign zero duration to missing data.
- [ ] C04 — Group summaries by experiment/session, workflow, generator/validator/syntax-repair/matcher model-role mapping, benchmark/subset and repetition. Do not pool development runs, different models, different cohorts or repeated copies of the same logs. Flag unknown metadata for reconciliation.
- [ ] C05 — Export one row per requirement-run and a grouped summary: recorded run count, unique requirements, completed unsuccessful count, incomplete/interrupted count, arithmetic mean, sample SD when n >= 2, median, total elapsed requirement-run time, attempts and model-role signature. Runtime SD across requirements is not repeated-generation accuracy uncertainty.
- [ ] C06 — Add a separate API breakdown using only api_call_completed for logical completed-call totals, grouped by role/model. Analyse transport attempts and retry waits separately; do not add them to completed-call totals. Document unfinished calls that these totals omit.
- [ ] C07 — Link evaluator outputs to the generating run/model using the manifest and shape-file provenance. Summarise all attempted-case elapsed times and successful-case elapsed times separately. A completed FAIL verdict is an executed case, not an engine failure.
- [ ] C08 — For paper timing comparisons use the same timed scope and cohort. Distinguish arithmetic mean of per-requirement times from batch elapsed time / throughput, and report concurrency if used. Do not equate summed overlapping durations with batch wall time.
- [ ] C09 — For future runs add a monotonic recorded_run_wall_ms interval with the SAME boundaries as run_started/run_finished; record all paths including exceptions/interruption, using try/finally. Add actual configured model-role mapping to run metadata. Optionally add separate preparation and tracker-export times without silently changing the definition used for historical runs.
- [ ] C10 — If pure validation-engine timing is required, add a separate pyshacl_elapsed_ms timer immediately around pyshacl.validate, alongside the existing inclusive per-case elapsed_ms. Export both fields consistently to CSV/JSON/Excel; historical inclusive times cannot be relabelled as pure engine times.
- [ ] C11 — Do not use accepted as a generic output or executability flag: the inspected single-shot runner intentionally records accepted=False even when deterministic diagnostics pass. Define output rate from the chosen artifact-availability rule and executable coverage from completed benchmark verdicts.
- [ ] C12 — Reconcile paper and source VERSION before describing repair behaviour. Inspected runner.py identifies FULL_REPAIR_V2, uses maximum_syntax_repairs_per_semantic_attempt with a default of 2, and can expand context and retain structured repair memory. The manuscript describes three syntax corrections. Only the configuration and code used for the reported run establish the actual settings.
- [ ] C13 — Replace outdated manual-review prose: abstract still says NLTL_v2 correct 30 and major defects 29 versus 33; Results still says assessable 67 versus 60, correct 30 versus 22, minor 8 versus 5, major 29 versus 33 and unassessable 3 versus 10. The figure generator already uses the new totals (42/15/13 and 22/8/40), so the paper and figure currently disagree.
- [ ] C14 — Update the one-author review descriptions in Methods and Limitations to reflect the actual review with Haitham. Recompute or withhold stale SF/IQ and criterion-score tables; do not infer new score means from categorical counts. Recheck representative defects against final review decisions.
- [ ] C15 — Add runtime/model-comparison Methods and Results sections. The current Results contains neither. Retain full-dataset single-model findings separately; qualify the one-model limitation once the supplementary model subset and results are established.
- [ ] C16 — Resolve the reported direct-calculation accuracy improvement: displayed values 79.83 - 62.64 give 17.19 percentage points, whereas the current text says 17.20. Check underlying unrounded values and apply one consistent rounding policy before changing the claim.
- [ ] C17 — End matter still has placeholder CRediT, Data Availability and Acknowledgements. Complete them using confirmed contributions, repository/release identifiers and funding details.

### Precise scope of planned code additions

Keep the working figure generator intact. Add timing ingestion and a new chart only after actual timing/model-summary data are reconciled; it currently contains only reported aggregate metric snapshots and cannot recover execution times. Prefer a separate read-only summariser that imports no generation client and makes no API calls. Require explicit selection of paper sessions; print a metadata/incomplete-run audit before producing publication summaries. Do not automatically mix every historical run found in the repository.

## First data handoff

For the next working step, provide whichever of these already exist; raw logs are preferable to manually transcribed summaries:
1. Revised manual-review sheet with requirement IDs and criterion scores.
2. Generation/runtime logs for NLTL_v2 and single-shot.
3. Cross-model result files plus exact subset IDs and settings.
4. Dataset-size scaling runs, if performed.
5. Any measured human-authoring times, with the timed task and protocol.

We will reconcile available evidence first, identify genuine missing measurements, and then fill the placeholder tables before drafting new claims.



## 21 October 2026: four-model results-evidence verification

Evidence-only update; no manuscript or figure changes. This section records evidence completion independently of the broader manuscript-revision tasks above, whose statuses are preserved.

Evidence package: /Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/outputs/model_comparison_evidence/20261021_112541_EEST/
Audit: RESULTS_EVIDENCE_AUDIT.md. Summary: model_comparison_summary.csv. Requirement detail: model_comparison_per_requirement.csv.

- [x] Four-model behavioural accuracy verified against raw evidence. SELF_REPAIR_FINAL requirement-macro accuracy on retained 373 cases: Luna 72.032468%, Sol 82.193434%, Gemini 73.537013%, GPT-OSS 47.041919%. Independently reproduced the model-inclusive manuscript's displayed values; legacy 381-case results saved separately.
- [x] Shared 50-requirement cohort and case identities verified. Locked sample membership and independent assignment manifests match all four models and both stages. Luna is restricted to the selected 50 FULL_REPAIR_V2 requirements.
- [x] Legacy/current case-count discrepancy resolved or disclosed. Recovered exact eight excluded sample case IDs using the manuscript archive's retained 2,160-case exports, yielding 373 sample cases; expected labels and RDF hashes match. Case-specific exclusion adjudication and original report_02(1).zip remain unavailable. The later main-study-only manuscript omits model results.
- [x] Runtime and accuracy paired to corresponding outputs. All 200 generation event intervals match the runtime workbook. Accepted artifact hashes match evaluations. GPT-OSS IMO-112/TRF-059 evaluation run IDs are missing; unique final-scope requirement runs and identical exception messages establish their failed-run timing links. Missing evaluation IDs remain NA.
- [x] Timing boundaries documented. run_started to run_finished includes enabled generation/checks/repairs; excludes earlier context/few-shot preparation, later tracker export and separate post-generation RDF evaluation. Completed unsuccessful runs remain included.
- [x] Model sample selection and representativeness documented. Metadata-only deterministic stratified selection, seed and allocations retained. Sample modes 20/15/15 overrepresent calculation/readiness relative to 190/41/37 in the full benchmark. Reported macro values describe the sample; no population or repeated-run uncertainty claim.
- [x] Acceptance, executable coverage, and accuracy distinguished. Acceptance 43/47/46/28 out of 50 is separate from expected-verdict agreement; pooled and requirement-macro accuracy are distinguished in the audit.
- [ ] Accuracy-versus-median-runtime figure pending verified evidence. Required numeric evidence is now verified with the stated provenance qualifications; figure creation remains pending by instruction.

Remaining provenance questions: recover the per-case benchmark-exclusion review decisions if needed for submission, and identify the manuscript branch into which the model comparison should be reinstated. Do not substitute FIRST_GENERATION accuracy for final-stage accuracy or pair it with full-repair runtime as initial-response latency.
