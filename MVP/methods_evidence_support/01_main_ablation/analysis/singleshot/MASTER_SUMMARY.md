# LUNA_CONTEXTUAL_SINGLESHOT RUN_01 analysis

## Integrity

Integrity passed. RUN_01 contains 268 finalized, unique results in the exact frozen-queue order. Every requirement has one retained raw response and exactly one generator call. Validator, matcher, syntax-repair and regeneration calls are all zero. All 268 rendered generator prompts are byte-identical to the corresponding first generator prompts in `FINAL_LUNA_MAIN/RUN_01`.

## Headline result

- Deterministic diagnostic pass: **221/268 (82.46%)**
- Deterministic diagnostic fail: **47/268 (17.54%)**
- Raw responses retained: **268/268**
- Extracted shapes retained: **254/268**

This is not semantic-validator acceptance and not hidden-RDF semantic accuracy. It reports whether the unmodified single generator output passed the read-only extraction and deterministic harness.

## Failure stages

- DATATYPE_UNIT_FAILURE: 2 (4.26% of failures)
- EXTRACTION_FAILURE: 14 (29.79% of failures)
- META_SHACL_FAILURE: 5 (10.64% of failures)
- OTHER_DETERMINISTIC_FAILURE: 4 (8.51% of failures)
- TURTLE_PARSE_FAILURE: 17 (36.17% of failures)
- VOCABULARY_DIAGNOSTIC_FAILURE: 5 (10.64% of failures)

Observed diagnostic statuses must not be interpreted automatically as ontology gaps. They describe where the unmodified output failed the deterministic harness.

## Category

- Complex: 31/37 (83.78%)
- Static: 159/190 (83.68%)
- Static Calculation: 31/41 (75.61%)

## Source

- Ice Class Regulations and the Application Thereof: 75/99 (75.76%)
- International Code for Ships Operating in Polar Waters (Polar Code): 99/109 (90.83%)
- Polar Code January 2026 Supplement - Resolution MSC.538(107): 9/15 (60.00%)
- UR I2 Structural Requirements for Polar Class Ships: 38/45 (84.44%)

## API, tokens, timing and cost

- Logical API calls: **268**, all generator
- Physical transport attempts: **269**
- Non-200 transport attempts: **1**
- Input tokens: **2,374,468**
- Output tokens: **553,179**
- Total tokens: **2,927,647**
- Estimated cost: **USD 5.693542**
- Mean cost per requirement: **USD 0.021245**
- Mean API latency: **30.17 s**
- Median API latency: **26.99 s**
- P95 API latency: **54.05 s**
- Run wall clock: **2.31 h**

Cost uses the repository's indicative Luna prices of USD 1/M input and USD 6/M output tokens. It is not an Aalto invoice and may be stale.

## Statistical limitation

This package analyzes one repetition. Run-level SD, a t-based 95% confidence interval, requirement stability and adequacy of repetitions are not estimable at n=1. The 268 heterogeneous requirements are not treated as mutually exchangeable independent Bernoulli trials, so no misleading binomial CI is reported.

## Scientific interpretation

The condition successfully isolates the removal of all LLM-mediated verification and repair while preserving the same first-call context. Its diagnostic-pass rate measures syntactic, structural and controlled-vocabulary viability of unmodified contextual Luna outputs under frozen R13. Later repetitions are required to measure stochasticity, and hidden RDF evaluation is required before making semantic-accuracy claims.
