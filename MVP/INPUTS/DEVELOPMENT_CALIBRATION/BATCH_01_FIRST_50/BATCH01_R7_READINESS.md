# Batch 01 R7 readiness

Date: 2026-08-13  
Status: ready for one final 12-requirement calibration run  
Development vocabulary: `VOCAB-DEV-2026-08-13-BATCH01-R7`

## Scope

R7 is the final planned first-50 calibration revision. Its live queue contains the 12 requirements that were not accepted and RDF-clean in R6:

`TRF-011`, `TRF-014`, `TRF-020`, `TRF-022`, `TRF-025`, `TRF-026`, `TRF-027`, `TRF-030`, `TRF-037`, `TRF-042`, `TRF-046`, and `TRF-049`.

R7 remains development evidence, not an evaluation lock. No R7 API calls were made during preparation or verification.

## Engineering changes

- Added one verified vocabulary gap: `upperIceWaterlineBreadth`, an ASCII-safe lowerCamelCase quantity property on `iceWaterline`, because clause 3.2.2 explicitly uses breadth at UIWL and no verified existing term expressed that operand.
- Added existing-but-unscoped terms to the affected requirement profiles: UIWL/LIWL relationships and dimensions for TRF-020, the required compound unit for TRF-025, and the strengthened-part relationship for TRF-046.
- Corrected requirement-scoped owners for waterline profile points, direct-analysis cases, frame-end/support structures, and frame attachments.
- Added bounded semantic obligations for the 12 remaining cases, including applicability prerequisites, paired direct-analysis inputs, tolerance rules, formula caps, and evidence placement.
- Registered deterministic XPath math functions `sin`, `cos`, `tan`, and `atan` under `http://www.w3.org/2005/xpath-functions/math#` in the local rdflib/pySHACL evaluation profile. Bare non-standard function names remain rejected.
- Rebuilt all 150 first-50 RDF fixtures and their hashes under the R7 development binding.

## Verification evidence

- Pipeline doctor: PASS.
- Automated regression tests: 34/34 PASS.
- RDF fixture construction and syntax validation: 150/150 PASS.
- Workbook formula scan: 0 formula errors.
- Workbook visual review: all 10 sheets reviewed.
- Migration evaluation: 60/60 expected matches for 20 previously RDF-clean R5/R6 shapes against the R7 fixtures (20 requirements x pass/fail/boundary; zero API calls).

Migration output:

`SHACL_GENERATION_PIPELINE/outputs/development_batch01/evaluations/EVAL-BATCH01-R7-MIGRATION-CLEAN-SHAPES-20260812T230457111270Z/evaluation_summary.json`

## Decision gate after the live run

Evaluate every R7-accepted shape against its three hash-bound RDF fixtures. Record remaining generation or semantic failures as pipeline/model findings. Do not create another first-50 vocabulary revision solely to force acceptance. Unless the live run exposes a genuine missing vocabulary operand, close first-50 calibration and proceed to the remaining generation-eligible requirements as the broader vocabulary-discovery batch.
