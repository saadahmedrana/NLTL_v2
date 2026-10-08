# Ocean Engineering offline reporting

This package reads the saved experiments and the copied latest workbook. It never calls model APIs, reruns generation or SHACL evaluation, or modifies source workbooks/RDF. **The reporting program has not been executed.** Syntax and source-schema inspection cannot establish runtime or figure correctness.

Use Python 3.10 or newer. From Terminal:

```bash
cd "/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python report.py --repo-root "/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP" --workbook "inputs/NLTL_Manual_Audit_with_Model_Scaling_FINAL (1) (4).xlsx" --output-dir "outputs/report_01"
```

Open `outputs/report_01/report.html` in your browser. The shareable ZIP will be `outputs/report_01.zip`. `RESULTS_REPORT.md`, `MISSING_DATA.md`, figure formats, CSV/JSON exports and provenance manifests are created by this command. None are presented as calculated results before execution.

Output directories must be new. For another run, use `--output-dir outputs/report_02`. This avoids stale figures or overwriting previous reports. If the command fails, inspect `RUN_FAILED.md` and `MISSING_DATA.md` in that run's output folder; partial exports are diagnostic only.

Optional scoring checks, authored but not run here:

```bash
python -m unittest discover -s tests -v
```

An explicit confirmed exclusion list can be UTF-8 text with one case ID per line, or CSV with a `case_id` column:

```bash
python report.py --exclude-ids confirmed_exclusions.txt --output-dir outputs/report_confirmed
```

This adds an EXPLICIT_EXCLUSIONS scenario alongside the original and 26-case proposed-edit sensitivity. The script reports the actual overlap with the model sample and new case/requirement totals; it does not assume 381 model cases after exclusions.

Use `--no-figures` for data-only reports. Use `--allow-incomplete` only to request an explicitly incomplete diagnostic analysis: expected missing rows are retained as no verdict and every incomplete combination is marked. Missing evaluation rows do not establish missing generation artifacts. Conflicting identities/labels/duplicate rows are errors even with this flag.

The exact default run selection is documented in [ANALYSIS_PLAN.md](ANALYSIS_PLAN.md). If relocating or resolving a different selected run, pass `--input-config selection.json` with explicit absolute paths:

```json
{
  "official": "/absolute/path/to/official/evaluation-directory",
  "historical": "/absolute/path/to/ablation/evaluation-directory",
  "rejected": "/absolute/path/to/rejected-diagnostic/evaluation-directory",
  "scaling_root": "/absolute/path/to/MODEL_SCALING_FULL_REPAIR_V2_50"
}
```

The workflow evaluation directory name must equal its recorded run/diagnostic ID. Model evaluation identities must be the frozen FINAL model/stage IDs. Alternatives are never chosen by reported performance.

Main reusable outputs:

- `workbook_sheets/`: original cached sheet grids, including notes; formulas and cached coordinates are exported separately.
- `workflow_case_outcomes`, `model_case_outcomes`, `policy_case_outcomes`, `requirement_scores`, `summary_results`, `outcome_matrices`, `breakdowns`, `paired_differences`.
- `proposed_exclusions`, `explicit_exclusions`, `exclusion_policy_summary`, `model_sample`, `retrospective_contribution`.
- `manual_scores`, `manual_criteria`, `manual_summary`, manual/behavioural cache discrepancies and `summary_cache_checks`.
- `failure_diagnostics_cases`, `failure_diagnostics_requirements`, `failure_reason_counts`, generation manifests.
- `sources_used.csv`: absolute input paths, roles, experiment identities, SHA-256 hashes.
- `referenced_files.csv`: recorded/resolved SHACL, RDF, traceback and other evidence paths and current existence. Missing current files do not invalidate a saved verdict by themselves.
- `verification.csv`, `figure_verification.csv`, `execution_config.json`, reports and figures.

Accuracy is equal-weight per requirement; pooled accuracy is supplementary. Manual score distributions are exploratory, cover selected subsets, and never override categorical major defects. Expected labels stay original; proposed RDF edits are sensitivity exclusions, not automatic label changes. Some existing paper-summary formulas omit unassessable workflow outputs from their categorical denominator; the recalculated report uses every selected slot and exports the discrepancy.

The HTML gallery, SVGs and PDFs should be visually checked after your run. Constrained layout and tight exports help avoid clipping; automated bounds checks cannot establish that all labels are overlap-free. A 100% implementation score does not establish semantic correctness. Results are single selected runs and do not imply significance, universal correctness or general scaling laws.

To share runnable code, include this folder's Python source, requirements, plan and README plus the source data/experiment directories separately as authorised. The generated results ZIP contains reports/data/figures only, not credentials, environment files or unrelated repository material.
