# Luna without semantic feedback and refinement: 10-run analysis

## Integrity

Integrity status: **PASS**. RUN_01–RUN_10 each contain exactly 268 unique outcomes in frozen queue order, producing 2,680 trials. The queue SHA256 is `d6b540573dd7b6af5c59e369b2f37b86a864eefd81ea44ef49f137af07bd7331`. All normalized configs hash to `e7fab9b7b6564037655e4303aa1cdb41ecbe5720812a04b98a4bef2f70b1fb82`. Every one of the 268 first generator prompts was byte-identical across all ten runs. R13 hashes match the lock. Semantic-validator, vocabulary-matcher and semantic-regeneration calls were zero; syntax-only repair remained enabled.

## Headline deterministic validity

- Deterministic-valid outputs: **2485/2680 = 92.72%**.
- Mean run-level deterministic-valid rate: **92.72%**; median **93.28%**.
- Sample SD: **2.34 percentage points**.
- Minimum–maximum: **88.06%–95.52%**.
- Student-t 95% CI over n=10 run-level rates: **[91.05%, 94.39%]**, width **3.34 percentage points**.

The CI uses the ten repetition-level proportions. It does not treat all 2,680 repeated observations as independent.

## Cumulative stability

The mean/SD/95% CI progressed from 93.53%/1.88%/[88.87%, 98.20%] at three runs to 92.72%/2.34%/[91.05%, 94.39%] at ten. The detailed 3/5/7/10 trajectory is in `repetition_adequacy.csv`.

## Syntax-repair contribution

Syntax repair was invoked in **432/2680 = 16.12%** trials, using **622** repair calls. **361** triggered trials ended deterministic-valid, a recovery rate of **83.56%**. **55** exhausted repair and **16** parsed after repair but failed another deterministic check. The recovered count is observationally attributable to the repair path because initial syntax failure triggered repair and final validity followed; it is not a randomized causal estimate.

## Category results

- Static: 93.42% (1775/1900), syntax activation 16.11%.
- Static Calculation: 92.20% (378/410), syntax activation 15.37%.
- Complex: 89.73% (332/370), syntax activation 17.03%.

## Source results

- IACS_UR_I2: 90.67% (408/450), syntax activation 15.56%.
- IMO_AMEND_2026: 96.67% (145/150), syntax activation 18.00%.
- IMO_POLAR_CODE: 95.05% (1036/1090), syntax activation 13.30%.
- TRAFICOM: 90.51% (896/990), syntax activation 19.19%.

## Stability and failures

- Consistently deterministic-valid (10/10): 168.
- Highly reliable (8–9/10): 80.
- Stochastic/unstable (4–7/10): 15.
- Generally difficult (1–3/10): 4.
- Persistent deterministic failure (0/10): 1.
- Persistent cases: IMO-097.
- Stochastic examples: I2-018, I2-019, I2-030, I2-031, I2-034, I2-048, I2-055, IMO-102, TRF-006, TRF-028, TRF-042, TRF-049, TRF-053, TRF-085, TRF-130.

Across 195 deterministic failures, terminal statuses were `{"NO_SEMANTIC_VALIDATOR_DETERMINISTIC_FAIL": 140, "SYNTAX_REPAIR_EXHAUSTED": 55}`. A terminal `SYNTAX_REPAIR_EXHAUSTED` is distinct from a syntax-usable candidate that fails another deterministic check.

## API, tokens, cost and time

- Logical API calls: **3,302** (2,680 generator; 622 syntax repair; zero validator/matcher).
- Physical transport attempts: **3,302**; transport retries: **0**.
- Tokens: **31,205,108** (24,739,042 input; 6,466,066 output).
- Estimated cost: **$63.54**, using repository-configured Luna pricing of $1.0/million input and $6.0/million output tokens.
- Summed run wall-clock time: **20.11 hours**.

Pricing is an indicative repository estimate, not an Aalto invoice; it was not externally refreshed and may be stale.

## Operational comparison with FULL Luna

FULL Luna's mean internal semantic-validator acceptance was 74.78%; this experiment's 92.72% deterministic-valid rate is **not the same metric and must not be interpreted as superior performance**. Operational quantities such as calls, tokens, cost, wall time and run-level variability are compared in `full_vs_no_semantic_operational_comparison.csv`. The run-level SD was 2.34 points here versus 2.59 points for FULL, but each describes variability at a different terminal gate.

## Scientific caveat

Deterministic validity means extraction, syntax, vocabulary and configured structural checks passed. It is **not semantic correctness**. FULL's 74.78% internal semantic-validator acceptance and this condition's deterministic-valid percentage are **not directly comparable performance measures**. Hidden RDF evaluation against expected pass/fail behavior is required for semantic and behavioral comparison of the architectures.
