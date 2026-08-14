# Final benchmark vocabulary lock R3

Lock ID: `VOCAB-LOCK-2026-08-14-R3`

This directory is the immutable vocabulary input for the final NL-to-SHACL experiment. It contains 1,620 registry terms, 1,673 canonical terms including infrastructure terms, all 313 requirement records, and 238 complete generation-eligible dependency contracts.

Use `benchmark_vocabulary_stage2_LOCK-2026-08-14-R3.lock.json` and its SHA-256 bindings to verify content identity. The root-level locked workbook and manifest are distribution copies of the same lock.

The final pipeline configuration is `SHACL_GENERATION_PIPELINE/config/pipeline.final-r3.json`. Its output directory is separate from every development run.

## Experimental boundary

- If a canonical term exists in this lock but a model misses, invents, or misuses it, record that as a model/pipeline outcome. Do not edit the vocabulary.
- If a required concept is genuinely absent from this lock, record a benchmark-infrastructure defect and exclude or invalidate the affected scored case. Any repair requires a new lock ID and a fresh experiment.
- Development outputs R1-R13 remain historical calibration evidence and must not be mixed with the final experiment outputs.

## Non-blocking publication items

- The provisional `w3id.org` namespace is not yet registered. This does not affect private execution, but it should be registered or replaced before public publication.
- ISO 19848 normative text was unavailable, so this lock makes no unverified ISO-specific normative claim.

No API call was made while creating this final lock.
