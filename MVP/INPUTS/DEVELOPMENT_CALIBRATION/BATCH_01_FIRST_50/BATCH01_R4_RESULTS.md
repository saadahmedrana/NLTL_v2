# Batch 01 R4 results

Status: **R4 completed, but the first-50 calibration is not stable enough to scale to the remaining 190 yet.**

## Generation

- Requirements rerun: 38
- Generation accepted: 28
- Vocabulary-gap stops: 4
- Maximum-attempt stops: 6
- API calls: 153
  - Generator: 70; mean response time 49.72 s
  - Validator: 70; mean response time 16.29 s
  - Vocabulary matcher: 13; mean response time 2.85 s
- Total API tokens: 1,582,375
  - Input: 1,247,511
  - Output: 334,864

Every call retains requirement/run/attempt identifiers, timestamps, elapsed milliseconds, token counts, retries, model, role, prompt hash, and response hash in the run event logs and API-call tables.

## RDF evaluation

The latest accepted shape for each available requirement was executed against one PASS, one FAIL, and one BOUNDARY fixture.

- Requirements with an accepted latest shape: 40
- RDF cases: 120
- SHACL executions completed: 120
- Expected matches: 82
- Expected mismatches: 38
- R4-accepted requirements with all three expectations matching: 6 of 28
- R4-accepted requirements with at least one mismatch: 22 of 28

The evaluator made no LLM/API calls. Total deterministic execution time was 527.61 s. TRF-054 alone consumed 451.93 s across three fixtures, indicating a generated-query performance defect that must be addressed before large-scale bulk evaluation.

## Remaining generation failures

- Confirmed or likely vocabulary/index refinements:
  - TRF-020: controlled value for the non-conventional/electric Table 3-1 propulsion branch.
  - TRF-027: explicit existing-ship applicability/status representation, subject to source-scope verification.
  - TRF-043: framing-component target/discriminator.
  - TRF-051: exact tank-bottom structural class.
  - TRF-055: abreast-of-hatch relation and separate actual/required formula quantities/evidence.
- Generator/validator repair failures rather than missing vocabulary:
  - TRF-014, TRF-022, TRF-034, TRF-044, and TRF-059.

## Decision

Do not run the remaining 190 yet. R4 proved that the runtime gate works—every accepted R4 shape executed—but 22 accepted requirements still disagree with authored RDF expectations, and one query is too slow for safe scaling. The next step is a consolidated R5 repair of these demonstrated issues, followed by one targeted rerun. Once the first 50 are stable, the remaining 190 can be run as one discovery batch.
