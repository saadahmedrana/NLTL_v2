# Reporting plan and source selection

The latest user-supplied workbook has been copied byte-for-byte into `inputs/`.
No source workbook, SHACL, RDF, experimental output or configuration is modified.
The reporting program has not been run; inspection and static code checks are separate from executing the analysis.

1. Read the workbook twice, for cached values and original formulas. Export every sheet, including notes/evidence, as CSV and JSON; export all formula cells with coordinates and caches separately.
2. Build the expected case universe from the frozen `BEHAVIORAL_RDF_R13/manifests/*_batch_*_manifest.jsonl` files. Exclude the pilot manifest. Check 268 requirements, 2,186 unique case IDs, and original labels against CaseReview. Use the workbook requirement metadata for regulatory source and verification mode, checking the scaling sample against its frozen manifest.
3. Use the following exact saved evaluation directories under `SHACL_GENERATION_PIPELINE/evaluation/experiment_results/`:

| Purpose | Directory | Selected configuration |
|---|---|---|
| Official revised workflow | `BEHAVIORAL-R13-FULL-REPAIR-V2-RUN01-20260915T144116505813Z` | FULL_REPAIR_V2 |
| Ablations | `BEHAVIORAL-R13-20260911T080233539977Z` | NO_SEMANTIC and SINGLESHOT only |
| Rejected-candidate diagnostic | `BEHAVIORAL-R13-FULL-REPAIR-V2-REJECTED-A4-RUN01-20260915T155743340362Z` | 25 rejected fourth-attempt candidates |

Read `raw_case_results.csv` and each run manifest. Read the corresponding generation manifests in `evaluation/generated_rule_manifests/RUN_01/`. Historical FULL/OLD_FULL, smoke runs and RUN_02 onwards are excluded. Directory selection is fixed by identity rather than performance.

4. Create a separate retrospective condition, `RETROSPECTIVE_V2_PLUS_REJECTED25`. Replace only official no-verdict cases for the 25 rejected requirements. Preserve ledger provenance and mark every substituted case. Never substitute into the official condition.
5. For `experiments/MODEL_SCALING_FULL_REPAIR_V2_50/`, read `MANIFESTS/sample_50.json`, final generation control/extraction manifests, `RDF_INPUTS/FINAL/{stage}/{model}/generated_rules.jsonl`, and all eight `OUTPUTS/RDF_EVALUATION/{stage}/{model}/raw_case_results.csv` ledgers with their manifests. Models: luna, sol, gemini, gpt_oss. Stages: FIRST_GENERATION and SELF_REPAIR_FINAL. Check common frozen IDs, expected case counts, sample hashes, final scope and matching underlying generation run IDs across stages.
6. Left join each ledger onto its expected case universe. Missing evaluation rows remain explicit and receive no credit in diagnostic mode; do not infer missing generated artifacts from missing rows. By default incomplete evaluation coverage stops the report before final summaries, figures or ZIP packaging. Duplicate/conflicting IDs, labels, manifests or runs always stop execution.
7. Calculate requirement accuracy as correct included cases / all included cases for that requirement. Average these fractions with equal requirement weights. Export pooled case accuracy under a distinct supplementary name. Export PASS/FAIL × PASS/FAIL/no-verdict counts and row-normalised fractions.
8. Apply three possible policies: ORIGINAL, PROPOSED_RDF_EDIT_SENSITIVITY (26 proposed RDF_EDIT cases), and optional EXPLICIT_EXCLUSIONS. The explicit policy is separate, not unioned automatically with proposed edits. Apply each policy to all workflow and model conditions, recalculate denominators, export overlap IDs/sample sizes and any requirements with no cases.
9. Preserve each original manual-review record. Select the 70 non-NOT_REVIEWED rows per workflow sheet and all 80 scaling slots. V2 manual review describes the retrospective selection. Recalculate Q1–Q7 and CQ1–CQ3 independently; N/A is excluded, blank/UNCLEAR makes an assessment incomplete, and unassessable outputs have no numeric mean contribution. Retain categorical verdicts including major defects. Export contribution counts and discrepancies with cached scores and paper summaries.
10. Compare paired per-requirement workflow scores and model stages. Export retrospective contribution, source/mode breakdowns and diagnostics at case and requirement levels. Use exact recorded failure stages/exception labels, not speculative ontology or infrastructure diagnoses. A NOT_PARSED marker alone is insufficient to diagnose Turtle syntax.
11. Generate overall and detailed scientific figures in PDF/SVG/300-dpi PNG. Keep retrospective results in a separate panel. Use categorical stages, consistent colours, exploratory labels in the report for manual subsets, and an HTML gallery. Perform automated renderer bounds checks; final human figure inspection remains necessary.
12. Hash all consumed sources, inventory referenced evidence paths and existence, verify unchanged workbook bytes, reconcile counts and independent macro averages, write Markdown/HTML reports and MISSING_DATA.md, and ZIP only generated results.

All inspection findings are source metadata, not freshly calculated manuscript results. No significance or broad scaling-law claims are made.
