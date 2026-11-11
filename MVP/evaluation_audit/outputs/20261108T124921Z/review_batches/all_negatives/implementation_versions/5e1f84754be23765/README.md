# Offline evaluation audit

This evaluates retained outputs. It never imports an LLM client, runs generation, or calls an API.
`NO_SEMANTIC` is **NLTL_v2**; `SINGLESHOT` is **Single-shot**. Only RUN_01 artifacts referenced by the retained manuscript export are scored.

## All-retained-negative continuation

The latest continuation is **`outputs/20261108T124921Z/review_batches/all_negatives/`**. It processes every one of the 1,154 additional retained negative cases, preserves the previous 50 exactly, and finishes each case with a classification or explicit blocker. Read that directory's `SUMMARY.md` and `report.json` for current counts. `batch50/` remains the preserved earlier audit, rather than the latest report.

No new baseline or shapes are needed. From MVP, using the recorded environment below:

```bash
.venv/bin/python evaluation_audit/audit_all.py --phase report
.venv/bin/python -m unittest discover -s evaluation_audit -v
PYTHONPATH=SHACL_GENERATION_PIPELINE/src .venv/bin/python -m unittest discover \
  -s SHACL_GENERATION_PIPELINE/tests -p test_retrieval.py -v
```

Resume interrupted work with `.venv/bin/python evaluation_audit/audit_all.py --phase all --workers 6`. Preparation and evaluation save each case atomically; old records are archived under `record_history/` on subsequent changes. Unchanged negative reports are reused. Repaired validations are cached by exact graph/shape/environment hashes. To reconsider blockers **after providing concrete new evidence**, use `--phase all --retry-blocked --workers 6`; this does not fabricate specifications. To recheck schema and violation matching after changing audit code, use `--phase reclassify --workers 6`, then `--phase report`; eligible unchanged repaired executions are reused from cache.

The source/repair module reads only frozen source clauses, contracts, canonical schema, original source-authored builders and independent fixture oracles. It never reads generated SHACL to choose repairs. A builder replay must reproduce exact retained RDF terms (with explicitly documented same-value numeric lexical alignment), restore one explicit default or canonical unit, change one semantic field, preserve existing applicability selectors, and pass the independent oracle/schema. Unreconciled source equations, parent provisions, unrelated schema defects, coupled repairs and unreviewed violation meanings become case-specific blockers. These checks establish the represented requirement, not full-vessel compliance.

`strict_summary.csv` exposes two **common** denominators: all source-verified pairs (including unresolved semantic results without credit), and the fully classified common subset. Neither is full-benchmark strict accuracy. All valid blocked tests remain in the unchanged ordinary cohort; exclusions remain identical. `diagnostic_results.json` links the preserved separate shape-transformation arm and records no new transformations. Additional evidence/specifications, exact RDF changes, reports, no-verdicts, source reconciliation notes and per-case blockers are in `records/`, `cases/`, `reviewed_failure_specs_additional.json`, `unresolved_blockers.csv`, `requirements_coverage.csv` and `full_case_ledger.csv`.

## Authoritative run and the first 50-case review

The authoritative completed baseline is **`outputs/20261108T124921Z`**. `authoritative_run.json` points to its current report. The earlier `20261108T113918056821Z` has identical ordinary metrics, baseline verdicts and original 14-case strict classifications; its differing JSON hashes reflect evidence paths. `20261108T124705Z` is incomplete. Reconciliation is recorded in the authoritative run's `run_reconciliation.json`.

The preserved first review lives in **`outputs/20261108T124921Z/review_batches/batch50/`**: 50 negatives, 19 requirements, and the same source/repair specification for both workflows. The parent run's baseline and original 14-case artifacts are preserved. Its `LATEST_REVIEW.md` points to the extension. No full-baseline rerun is needed or performed for this extension.

Use these commands from MVP to regenerate the extension report and run checks:

```bash
AUDIT_RUN="evaluation_audit/outputs/20261108T124921Z"
.venv/bin/python evaluation_audit/audit.py --phase report --run-dir "$AUDIT_RUN" \
  --review-batch batch50 --specifications evaluation_audit/reviewed_failure_specs_batch50.json
.venv/bin/python -m unittest discover -s evaluation_audit -v
PYTHONPATH=SHACL_GENERATION_PIPELINE/src .venv/bin/python -m unittest discover \
  -s SHACL_GENERATION_PIPELINE/tests -p test_retrieval.py -v
```

To replay just the reviewed pairs with unchanged historical shapes and the separately logged diagnostic probes, use:

```bash
.venv/bin/python evaluation_audit/audit.py --phase reviewed --run-dir "$AUDIT_RUN" \
  --review-batch batch50 --specifications evaluation_audit/reviewed_failure_specs_batch50.json --workers 6
.venv/bin/python evaluation_audit/explain_batch50.py
```

The default `reviewed_failure_specs.json` remains the immutable original 14-case file, because historical input hashes refer to it. The expanded specifications are in `reviewed_failure_specs_batch50.json`. `build_batch50.py` defines the additional 36 exact mutations without reading shapes; `reviewed_oracles.py` independently checks all represented prerequisites and reports named defects. `bind_batch50_semantics.py` separately binds reviewed logical/SPARQL constraints without changing repairs. These authoring scripts are retained for audit, not part of routine report regeneration; rerunning them changes the batch specification snapshot and requires a fresh batch name if content changes.

`batch50/SUMMARY.md` is the short comparison report; `batch50/REPORT.md` contains detailed evidence notes. Supporting files include `strict_summary.csv`, `ordinary_reviewed50.csv`, `ordinary_corrected_reused.csv`, `strict_mismatch_causes.csv`, `failure_causes.csv` (all arms), `no_verdict_inventory.csv`, `diagnostic_results.csv`, `previous14_comparison.csv`, `review_blockers.csv`, and a complete updated `full_case_ledger.csv`. The 8 deferred candidates stay NOT_AUDITED in the ordinary cohort; no new test exclusions were made.

Exact exported RDF matters: negative/repaired files use N-Triples, which is also valid Turtle, to preserve decimal lexical forms. Unchanged evaluated shape snapshots retain original file bytes. `fixture_serialization_receipt.json` documents correction of the initial Turtle-shorthand exports; the validation graphs and scores were unchanged. `execution_provenance.json` documents the initial extension receipt's default-specification hash metadata error; the executed 50-case snapshot and command are preserved, and subsequent receipts record the selected specification hash.

## Environment and exact commands

Run from the MVP directory. The existing `.venv` has the historical **Python 3.13.5, rdflib 7.6.0 and pySHACL 0.31.0**. The CLI refuses other versions. If creating a separate environment:

```bash
python3.13 --version  # must be 3.13.5
python3.13 -m venv .venv-audit
.venv-audit/bin/python -m pip install -r evaluation_audit/requirements-lock.txt
```

The lock also captures the installed replay environment's transitive package versions. Only Python/rdflib/pySHACL versions were explicitly recorded in the historical run; historical transitive versions were not recorded. Installing dependencies downloads packages, but does not invoke any LLM API. All evaluation commands themselves are offline.

Use `.venv-audit/bin/python` below if you created the separate environment. The retained archive defaults to `$HOME/Downloads/NLTL_v2_manuscript_and_data.zip`; set `--archive /absolute/path/to/archive.zip` on the first command if needed. Original project artifacts must remain at their repository-relative locations.

```bash
.venv/bin/python evaluation_audit/audit.py --phase inventory
```

The following original phases are for a new full audit. Do not rerun the completed baseline for an unchanged review extension. For a fresh audit, copy the newly printed directory into `AUDIT_RUN`:

```bash
AUDIT_RUN="evaluation_audit/outputs/REPLACE_WITH_NEW_INVENTORY_TIMESTAMP"
.venv/bin/python evaluation_audit/audit.py --phase baseline --run-dir "$AUDIT_RUN" --workers 8
.venv/bin/python evaluation_audit/audit.py --phase pilot --run-dir "$AUDIT_RUN" --workers 4
.venv/bin/python evaluation_audit/audit.py --phase reviewed --run-dir "$AUDIT_RUN" --workers 4
.venv/bin/python evaluation_audit/audit.py --phase report --run-dir "$AUDIT_RUN"
.venv/bin/python -m unittest discover -s evaluation_audit -v
PYTHONPATH=SHACL_GENERATION_PIPELINE/src .venv/bin/python -m unittest discover -s SHACL_GENERATION_PIPELINE/tests -p test_retrieval.py -v
```

For a fresh independent evaluation, use the **new** timestamped directory printed by inventory, rather than the completed directory above. Supplying `--run-dir` intentionally continues that run and replaces that phase's derived outputs; no original benchmark, report or generated SHACL is modified. Without `--run-dir`, each invocation creates a new timestamped run. The baseline is the costly phase (thousands of local validations); it does not require or use API credentials.

`pilot` executes the 14 explicitly reviewed negatives in three arms and a small, explicitly selected I2-048 unit-predicate probe. `reviewed` executes **only specifications marked REVIEWED**, the explicitly selected specification snapshot (14 by default; 50 with the extension command above). It never invents specifications for other cases. Both phases save a negative/repaired pair and two full validation reports for each available output. Applicable-branch reports provide additional explanation for IMO-049; the full-shape verdict and full-shape repaired outcome always govern strict credit. Originally ineligible candidates run only in the diagnostic arm and retain `NO_VERDICT` in the scored status.

## Cohort, evidence and reproducibility

The exact retained membership comes from `NLTL_v2/case_outcomes.csv` inside the manuscript archive: 268 requirements, 2,160 unique case IDs, and 4,320 workflow/case rows. Membership, labels, RDF hashes, original verdicts, execution statuses and shape hashes are checked against independent local benchmark manifests, saved raw results and generation manifests. The older 2,186-case cohort supplies original evidence only. Its 26 omitted IDs are separately listed, with their unavailable adjudication reasons explicitly disclosed.

The ontology and recorded validation options come from the saved run manifest. XPath math extensions are the original project's implementation. Baseline runs each originally eligible shape on its original fixture; original no-verdict rows are preserved without execution. It also evaluates corrected fixtures using the **unchanged** original shapes. Identical corrected/original fixture bytes reuse the reproduced verdict and report. Any baseline difference blocks aggregate reporting and appears in `baseline_differences.json`; it must be investigated before reporting corrected accuracy.

Source hashes are checked again at reporting. `phase_receipts/` records commands, code/specification hashes and environment for each subsequent phase invocation. Inputs, hashes and original generation records remain in the full ledger. `source_review/` contains frozen contexts and full local PDF text; the rendered Table-8 page and a reviewed transcription support checking all 126 source cells independently of generated code. The pilot's exact mutation list was imported from the existing feasibility package and reviewed against source/schema. Its mixed fixture/shape-repair arm is **not** used as main accuracy.

## Fixture changes and exclusions

* **I2-048:** Move the existing thickness quantity link from plating to the steel-grade case. All quantity subgraphs, values, labels and expected labels are preserved. The ordinary link is `steelGradeRequirementCasePlating`. F002 deliberately lacks that link: its explicit case/plating construction in the original fixture builder supplies the documented ownership mapping, without restoring the missing link. F003 lacks thickness and remains missing. The zero-case fixture remains empty. All 152 labels are checked against the corrected owner model and all 126 frozen cells against source Table 8. This is the represented generic table model; Table-8 footnote 2's special single-strake allowance is not represented in these fixtures.
* **TRF-001:** Add the two canonical 2021 section-1.8/chapter-2 provision assertions to all five fixtures, PASS and FAIL alike. These are source-required prerequisites, separate from the intended edition/date defect.
* **TRF-002-F02:** Exclude this case identically for both workflows. Its 2018-06-01 contract with the 2017 edition is allowed by full-source section 1.2's earlier-date option. The frozen 2019-only negative oracle is unjustified. No label is flipped. Other TRF-002 cases are retained and remain unaudited for strict reasons.

Every correction has evidence, original/corrected paths and hashes, and exact added/removed RDF triples. No generated regulatory logic is manually repaired for main scoring.

## Metrics and strict decision rule

Ordinary agreement is `observed == expected`, with no verdict receiving zero accuracy credit. Requirement-averaged accuracy is the mean, across requirements with at least one retained case, of each requirement's `correct / retained cases`. Cases are removed identically across workflows. Here one new exclusion gives **2,159 cases / 268 requirements**, with **955 expected PASS / 1,204 expected FAIL** per workflow; TRF-002's own denominator decreases by one. The original 2,160-case figures and corrected figures both before and after exclusion are preserved.

Strict credit requires rejection, reviewed intended violation evidence, no unrelated/additional violation, and a full-shape PASS after exactly the reviewed repair. The fixture must first satisfy the independent source-backed negative/repaired oracle. Matching uses property/path, focus, constraint family and reviewed logical/SPARQL structure. It ignores message strings and blank-node identifiers. `sh:node` wrappers are treated as wrappers only when nested details are present on reviewed traversal paths; applicable IMO-049 branches are chosen from category and ice-strengthening assertions, never from whichever branch passes.

Statuses are `STRICT_INTENDED_MATCH`, `MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE`, `MISSED_INTENDED_DEFECT`, `UNRESOLVED_REASON`, `INVALID_TEST_EXCLUDED`, and `NO_VERDICT`. Remaining cases retain `NOT_AUDITED`. Strict percentages refer to the explicitly selected reviewed negative fixtures per workflow (14 in the preserved pilot, 50 in batch50), including original no-verdict cases; an eligible denominator is shown separately. This purposive subset is not an estimate for all 1,205 original negatives. Losing strict credit never relabels a negative fixture as PASS.

## Output map

* `REPORT.md`, `report.json`: results and limitations.
* `full_case_ledger.csv`, `retained_rows.json`, `retained_case_outcomes.csv`: full case inventory, requirement texts, paths, original eligibility and review status.
* `inventory.json`, `source_hashes.json`, `environment.json`, `phase_receipts/`: provenance, missing information, execution settings.
* `fixture_corrections.{json,csv}`, `corrected_benchmark/`: new benchmark copy and exact changes.
* `table8_source_cell_checks.csv`, `table8_expectation_checks.csv`: source/schema checks, independent of generated SHACL.
* `exclusions.csv`, `exclusions_by_requirement.csv`, `prior_cohort_exclusions.csv`: new fair exclusions and older membership differences.
* `reviewed_failure_specs.json`: applicability, source, owner/path, admissible violation semantics, exact repairs and expected repaired PASS.
* `baseline_results.{json,csv}`, `baseline_differences.json`, `baseline/`: reproduction and unchanged-shape corrected validation reports.
* `original_*`, `corrected_before_exclusions_*`, `corrected_after_exclusions_*`: ordinary counts, per-requirement scores, and Figure-6 expected/observed cells with explicit denominators and percentages.
* `strict_results.{json,csv}`, `strict_summary.csv`, `reviewed/`: negative/repaired fixtures, full and applicable-branch reports, and strict classifications.
* `diagnostic_shape_repair_results.csv`, `unit_diagnostic_results.{json,csv}`, `unit_diagnostics/`: separate diagnostic arms and every transformation. IMO-049 probes change the owner path and plain string constants; the I2-048 probe changes only an erroneous unit predicate used for the table reference. Remaining shape logic and cardinalities are retained, so residual bugs remain visible.
* `unresolved_cases.csv`: unaudited, excluded and unresolved/no-verdict cases.

The context-builder change is for future context construction only: explicit ownership takes precedence, unique canonical domains may resolve ownership, and unknown ownership remains `None` with `UNRESOLVED` and candidate information. `ownershipReadyForGeneration` is separate from the existing regulatory category eligibility. Historical context packs and generated outputs are unchanged.
