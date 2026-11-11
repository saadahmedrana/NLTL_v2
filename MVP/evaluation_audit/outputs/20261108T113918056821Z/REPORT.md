# Evaluation audit results

Ordinary verdict agreement and strict intended-failure credit are separate. Original no-verdict cases remain in accuracy denominators and receive zero credit.

original
- NLTL_v2: 1501/2160 ordinary agreement; requirement mean 76.1091% across 268 requirements; 202 no verdict.
- Single-shot: 1338/2160 ordinary agreement; requirement mean 68.4687% across 268 requirements; 401 no verdict.

corrected_before_exclusions
- NLTL_v2: 1634/2160 ordinary agreement; requirement mean 76.6521% across 268 requirements; 202 no verdict.
- Single-shot: 1429/2160 ordinary agreement; requirement mean 68.8364% across 268 requirements; 401 no verdict.

corrected_after_exclusions
- NLTL_v2: 1634/2159 ordinary agreement; requirement mean 76.6965% across 268 requirements; 202 no verdict.
- Single-shot: 1429/2159 ordinary agreement; requirement mean 68.8808% across 268 requirements; 401 no verdict.

- NLTL_v2 / original: strict 6/14 reviewed negatives (14 originally eligible). {'STRICT_INTENDED_MATCH': 6, 'MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE': 8}
- Single-shot / original: strict 6/14 reviewed negatives (8 originally eligible). {'STRICT_INTENDED_MATCH': 6, 'NO_VERDICT': 6, 'MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE': 2}
- NLTL_v2 / corrected_fixtures: strict 8/14 reviewed negatives (14 originally eligible). {'STRICT_INTENDED_MATCH': 8, 'MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE': 6}
- Single-shot / corrected_fixtures: strict 7/14 reviewed negatives (8 originally eligible). {'STRICT_INTENDED_MATCH': 7, 'NO_VERDICT': 6, 'MISSED_INTENDED_DEFECT': 1}
- NLTL_v2 / diagnostic_shape_repairs: strict 14/14 reviewed negatives (14 originally eligible). {'STRICT_INTENDED_MATCH': 14}
- Single-shot / diagnostic_shape_repairs: strict 7/14 reviewed negatives (8 originally eligible). {'STRICT_INTENDED_MATCH': 7, 'NO_VERDICT': 6, 'MISSED_INTENDED_DEFECT': 1}

One new exclusion per workflow: TRF-002-F02. No expected labels changed.
Unaudited cases remain NOT_AUDITED. Figure 6 CSVs retain expected PASS/FAIL strata and give cell counts, percentages and denominators.
Diagnostic shape transformations never enter the main accuracy results.
Missing evidence and source provenance: inventory.json and source_hashes.json.

I2-048 unit-predicate diagnostic:
- NLTL_v2 / I2-048-H-T001: expected PASS; unchanged conforms=True; diagnostic conforms=False; transformations=1.
- NLTL_v2 / I2-048-H-F011: expected FAIL; unchanged conforms=True; diagnostic conforms=True; transformations=1.
- NLTL_v2 / I2-048-H-F012: expected FAIL; unchanged conforms=True; diagnostic conforms=True; transformations=1.
- NLTL_v2 / I2-048-H-F013: expected FAIL; unchanged conforms=True; diagnostic conforms=False; transformations=1.
- NLTL_v2 / I2-048-H-F014: expected FAIL; unchanged conforms=True; diagnostic conforms=True; transformations=1.
- Single-shot / I2-048-H-T001: expected PASS; unchanged conforms=True; diagnostic conforms=True; transformations=0.
- Single-shot / I2-048-H-F011: expected FAIL; unchanged conforms=False; diagnostic conforms=False; transformations=0.
- Single-shot / I2-048-H-F012: expected FAIL; unchanged conforms=False; diagnostic conforms=False; transformations=0.
- Single-shot / I2-048-H-F013: expected FAIL; unchanged conforms=False; diagnostic conforms=False; transformations=0.
- Single-shot / I2-048-H-F014: expected FAIL; unchanged conforms=False; diagnostic conforms=False; transformations=0.
