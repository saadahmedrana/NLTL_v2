# Batch 01 R3 post-run engineering report

Status: **development calibration completed; R4 repair revision ready for rerun**.

This report is not final benchmark accuracy. The RDF fixtures were visible development material used to expose vocabulary, retrieval, generator, parser, and graph-model defects before a future fixed-lock evaluation.

## R3 outcome

- Requirements executed: 50
- Generation accepted: 31
- Reported vocabulary gaps: 12
- Maximum-attempt failures: 7
- Accepted shapes evaluated: 31
- RDF cases executed: 93
- Requirement classifications:
  - R3 clean calibration: 12
  - Confirmed schema gaps: 14
  - Existing-vocabulary or pipeline/model repair: 5
  - Runtime-invalid acceptance: 10
  - Executable RDF-expectation mismatch: 9

The classification is requirement-level. A reported `VOCABULARY_GAP` was not automatically accepted as a real gap; exact registry terms, requirement indexes, source wording, validator feedback, and RDF execution were checked first.

## Scalable repairs made in R4

- Added clause-backed applicability and targeting terms such as `navigatingInIce`, `iceStringer`, `mainFrame`, `intermediateIceFrame`, `longitudinalFrame`, `weatherdeckHatch`, and `hasWeatherdeckHatch`.
- Added explicit cross-component connection paths for frame ends, supporting structures, horizontal members, adjacent main frames, connection brackets, and frame-boundary evidence.
- Added repeatable direct-analysis position types and capacity-minimization evidence instead of relying on one free-text location.
- Added draught-specific brash-ice resistance operands and an explicit ice-class draught-mark value for comparisons.
- Added source-unit individuals for coefficient units that had no verified external QUDT IRI; no external equivalence was invented.
- Corrected requirement retrieval indexes where valid terms existed but were not supplied to the generator.
- Removed misleading terms from selected contexts, including additional propulsion power from TRF-017 and maximum-continuous-rating power from the TRF-037 `k` calculation context.
- Added a real embedded-SPARQL parser and a target-activated SHACL runtime smoke check. This blocks forbidden `VALUES` clauses, malformed queries, and similar candidates before semantic acceptance.
- Corrected the angle-IRI scanner so a comparison operator such as `<=` is not misread as an external IRI.
- Reworked structured RDF fixtures so waterlines, frame attachments, frame ends, direct-analysis cases, and weatherdeck-hatch evidence are attached to the correct nodes without generic duplicate paths.

## R4 state

- Development vocabulary: `VOCAB-DEV-2026-08-12-BATCH01-R4`
- Registry terms: 1,053
- Canonical terms including ontology infrastructure: 1,106
- Batch 01 RDF fixtures: 150; parser and vocabulary validation PASS
- Pipeline tests: 27 PASS
- Pipeline doctor: PASS
- Affected requirements queued for R4 rerun: 38

The 12 R3-clean requirements are retained as development evidence. All 50 will still be regenerated from scratch after the vocabulary, prompts, validator, model settings, and hidden evaluation fixtures are finally frozen.

## Next command

From the MVP root:

```bash
.venv/bin/python SHACL_GENERATION_PIPELINE/run_pipeline.py \
  --config SHACL_GENERATION_PIPELINE/config/pipeline.dev-batch01.json \
  generate-batch \
  --queue INPUTS/DEVELOPMENT_CALIBRATION/BATCH_01_FIRST_50/generation_queue_r4_affected_38.json
```

After that run, build a latest-accepted manifest, execute each affected shape against its R4 PASS/FAIL/BOUNDARY fixtures, classify remaining mismatches, and repeat only when a concrete engineering or pipeline defect is demonstrated.
