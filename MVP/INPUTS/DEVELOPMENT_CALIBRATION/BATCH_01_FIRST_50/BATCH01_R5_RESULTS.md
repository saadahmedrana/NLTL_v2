# Batch 01 R5 results

Status: **R5 completed successfully as an experiment, but the first-50 development gate is not yet clean. Do not scale to the remaining 190 requirements yet.**

## Generation and API usage

- Targeted requirements: 32 of 32 completed.
- Accepted generations: 15.
- Maximum semantic attempts reached: 11.
- Vocabulary-gap stops: 6.
- Semantic attempts: 77.
- API calls: 170: 77 generator, 77 validator, and 16 vocabulary matcher.
- Tokens: 1,551,883 input; 400,464 output; 1,952,347 total.
- Mean response times: generator 46.83 s; validator 20.47 s; matcher 3.35 s.

Every call remains traceable by session, run, requirement, iteration, timestamp, model, elapsed time, prompt/response hashes, tokens, and transport attempts in the existing event logs.

## Deterministic RDF evaluation

Only the 15 R5-accepted shapes were bound to the current R5 fixtures. No older R3/R4 shape was used.

- RDF cases: 45.
- SHACL executions completed: 45 of 45.
- Expected matches: 19.
- Expected mismatches: 26.
- Requirements matching all PASS/FAIL/BOUNDARY expectations: 0 of 15.
- Slowest requirement across its three cases: approximately 6.6 s.

The R4 performance defect is therefore fixed: no query took several minutes and every accepted shape executed normally.

## Engineering classification

- 12 accepted requirements expose canonical-domain versus fixture-placement misalignment: TRF-007, TRF-009, TRF-013, TRF-024, TRF-032, TRF-034, TRF-036, TRF-037, TRF-048, TRF-053, TRF-054, and TRF-059. These are not credible model-accuracy failures until the canonical node ownership is fixed and the fixtures are rebuilt from it.
- TRF-011 is a genuine semantic acceptance defect: the accepted shape checks only that an upper ice waterline exists and omits the required upper-envelope semantics.
- TRF-041 is a bounded-query portability/behavior defect despite passing static acceptance.
- TRF-016 requires one explicit node-model decision for whether the propeller-submergence fact belongs to the ship or to a propeller component.
- The 11 maximum-attempt outcomes are generator/validator repair problems, with TRF-043 also exposing a possible qualitative-evidence vocabulary gap.
- The six vocabulary stops are TRF-015, TRF-030, TRF-044, TRF-047, TRF-049, and TRF-055. TRF-015 is specifically an index/scope defect because the salinity unit exists in R5 but was not supplied to that requirement; the other five need verified class/property/path additions or index refinement.

## Decision

R6 should first make subject ownership authoritative for every Batch 01 property and use that ownership to build fixtures deterministically. It should then close the six verified index/vocabulary gaps, add semantic-validator checks for completeness rather than presence-only approximations, and rerun only the still-affected requirements. The remaining 190 should be held until the first-50 gate passes.

