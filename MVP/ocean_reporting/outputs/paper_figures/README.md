# Ocean Engineering manuscript figures

This directory contains the three principal publication figures generated from the existing `report_02` reporting data. The program did not rerun generation or evaluation and did not modify the report, ontology, RDF graphs, labels, or source workbook.

## Rerun

```bash
cd "/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting"
python make_paper_figures.py --report-dir outputs/report_02 --output-dir outputs/paper_figures
```

`--report-dir` accepts either a report directory or a ZIP. ZIP members are validated against absolute paths, parent traversal, and symbolic links before extraction. A completed output created by this script is replaced atomically on rerun.

## Verified data

Internal behavioural policy: `PROPOSED_RDF_EDIT_SENSITIVITY`. This identifier is recorded in provenance and is omitted from figure labels.

- Manuscript dataset: 268 requirements / 2,160 configurations.
- Model sample: 50 requirements / 373 configurations.
- IACS I2: 45 requirements / 493 configurations
- Traficom: 99 requirements / 737 configurations
- Polar Code: 109 requirements / 803 configurations
- January 2026 supplement: 15 requirements / 127 configurations
- Verification modes: Direct static 190 requirements; Direct calculation 41; Complex readiness 37.
- Accuracy is the unweighted mean of requirement-level correct-case fractions. Cases without executable verdicts remain in each requirement denominator with zero credit.
- All expected evaluation rows were present and unique. Recorded unavailable outputs remain explicit and are distinct from missing evaluation records.
- Recomputed per-requirement, overall, and mode-level values matched the supplied report summaries. All 51 validation checks passed.

## Principal figures

- `pipeline.pdf`, `.svg`, `.png`: generation, validation, independent behavioural evaluation, and separate manual assessment.
- `workflow_comparison.pdf`, `.svg`, `.png`: principal workflow comparison with retrospective results visually separated.
- `model_comparison.pdf`, `.svg`, `.png`: paired first-generated and final-output accuracy for four models.

PDF and SVG retain vector graphics and editable text. PNG files are exported at 300 dpi. Figures contain no manuscript captions.

## Reusable data

- `pipeline_nodes.csv`, `pipeline_edges.csv`
- `workflow_overall_plot_data.csv`, `workflow_by_mode_plot_data.csv`
- `model_comparison_plot_data.csv`
- `per_requirement_behavioural_scores.csv`
- `coverage_error_table.csv`
- `source_mode_dataset_counts.csv`
- `manual_review_summary.csv`
- `referenced_files.csv`
- `validation_results.csv`
- `provenance_manifest.json`

The detailed heatmaps, confusion matrices, rubric heatmaps, and failure plots remain available in the existing report and are not part of this principal figure set. No maritime worked example is invented here.

## Paths

- Report source: `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/outputs/report_02` (directory)
- Output directory: `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/outputs/paper_figures`
- Shareable ZIP: `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/outputs/paper_figures.zip`

Exact consumed files:

- `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/outputs/report_02/summary_results.csv` (SHA-256 `eb51f20997331185780d02eaef7a3bc76c2836f5ec20891b50eec9bdeec21c59`)
- `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/outputs/report_02/breakdowns.csv` (SHA-256 `7534caa89480da50a723e9d1d5a40e7d820bc98b8d6eee558856f3fd3b9ed9fa`)
- `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/outputs/report_02/policy_case_outcomes.csv` (SHA-256 `655fb55f59137e931869332599d866026a7c1f1a96648b650e164438651154e8`)
- `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/outputs/report_02/requirement_scores.csv` (SHA-256 `142588d925cae74340c7572cb20eb9b476a9ecccd8b81347882bbd82903d4b71`)
- `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/outputs/report_02/manual_summary.csv` (SHA-256 `1a8d8bd415fe6575a19f17c5896fd22d1b096c9e2df6c4e0d6d75e4add82ab92`)
- `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/ocean_reporting/outputs/report_02/referenced_files.csv` (SHA-256 `d85500be6014430f26966b840fc76537ece95a078d85c6b2f8e8a5c6041e90aa`)
