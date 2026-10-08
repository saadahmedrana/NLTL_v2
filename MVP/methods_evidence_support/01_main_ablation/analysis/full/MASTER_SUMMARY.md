# Final Luna Main: aggregated 10-run analysis

## Integrity conclusion

All ten formal run directories exist. Each contains one completed 268-item batch result with every frozen requirement exactly once and in the same order. The normalized configurations are identical; only pipeline version/run naming and output directory differ. Every doctor log identifies `VOCAB-LOCK-2026-08-22-R13`, 268 eligible requirements and `gpt-5.6-luna-2026-07-09` for generator, validator, syntax repair and vocabulary matcher. R13 hashes match the lock and all ten doctor logs. Two completed terminal `BATCH_ITEM_ERROR` outcomes occurred (RUN_03/I2-035 and RUN_06/TRF-059); neither represents a missing queue item.

## Headline Luna performance

- Pooled acceptance: **2004/2680 = 74.78%**.
- Mean run-level acceptance (n=10): **74.78%**.
- Median: **75.75%**; sample SD: **2.59%**.
- Minimum–maximum: **70.52%–77.24%**.
- 95% Student-t CI for the run-level mean: **[72.93%, 76.63%]**.

The CI uses ten repetition-level proportions. The 2,680 repeated requirement observations are not assumed mutually independent.

## Repair-loop contribution

- Estimated single-shot performance: **40.37%**.
- Full-loop performance through four attempts: **74.78%**.
- Absolute repair gain: **34.40 percentage points**.
- Relative improvement over single-shot: **85.21%**.
- Eventual successes requiring repair: **46.01%**.
- Eventual successes first accepted at attempts 3–4: **16.92%**.
- Attempt 4 added **110** accepted trials (**4.10 percentage points**); this is non-zero incremental value, to be weighed against its API cost.

## Category differences

- Static: 76.53% (1454/1900)
- Static Calculation: 75.37% (309/410)
- Complex: 65.14% (241/370)

## Source differences

- IACS_UR_I2: 64.89% (292/450)
- IMO_AMEND_2026: 78.00% (117/150)
- IMO_POLAR_CODE: 82.11% (895/1090)
- TRAFICOM: 70.71% (700/990)

## Stability and hard requirements

- Consistently successful (10/10): 104.
- Highly reliable (8–9/10): 67.
- Stochastic/unstable (4–7/10): 57.
- Generally difficult (1–3/10): 29.
- Persistent systematic failure (0/10): 11.
- Persistent cases dominated by `MAX_ATTEMPTS_REACHED`: I2-048, IMO-097, TRF-016, TRF-130.
- Persistent cases dominated by `TERM_RESOLUTION_UNRESOLVED`: I2-032, IMO-043, IMO-052, IMO-064, IMO-111, TRF-108, TRF-120.
- Stochastic middle examples: I2-001, I2-011, I2-014, I2-022, I2-024, I2-035, I2-047, I2-051, I2-054, I2-061, I2-065, IMO-001, IMO-021, IMO-022, IMO-030, IMO-031, IMO-032, IMO-047, IMO-065, IMO-075.
- 10/10-success cases with the largest attempt ranges: I2-026, IMO-066, IMO-108, IMO-114, IMO26-001, TRF-006, TRF-024, TRF-037, TRF-057, TRF-058.

`TERM_RESOLUTION_UNRESOLVED` is reported only as an observed pipeline status; it is not interpreted as proof of a genuine vocabulary gap.

## Failure taxonomy

Terminal status counts across all trials: `{"BATCH_ITEM_ERROR": 2, "GENERATION_ACCEPTED": 2004, "MAX_ATTEMPTS_REACHED": 255, "SYNTAX_REPAIR_EXHAUSTED": 113, "TERM_RESOLUTION_UNRESOLVED": 306}`. Failure mechanisms vary for some requirements across repetitions; `failure_by_case.csv` records the exact ten-status sequence and whether the mechanism changes.

## API calls, tokens, timing and estimated cost

The analysis counts `api_call_completed` once per logical API response and does not double-count paired transport-finished events. Transport attempts and non-200 events are reported separately. End-to-end requirement time is the first-to-last event span, including pipeline handling and tracker emission.

- Completed logical API calls: 12264.
- Input tokens: 105,020,215.
- Output tokens: 19,509,465.
- Estimated 10-run cost: **$222.08**.
- Pricing used: repository config, Luna input $1.0/million and output $6.0/million tokens.

This is an indicative configured estimate, not an Aalto invoice. The repository pricing may be stale and was not silently replaced with external pricing.

## Were ten repetitions adequate?

The first three runs were unusually similar and therefore produced a deceptively narrow interval; adding later runs revealed more run-to-run variability rather than monotonically narrowing the CI. The run-level 95% CI width changed from 0.0185 after 3 runs to 0.0370 after 10, while the 7-run and 10-run widths were 0.0356 and 0.0370. The cumulative mean changed by 0.0097 between 7 and 10 runs. The chronological least-squares slope was -0.561 percentage points per run, with RUN_09 and RUN_10 below the early runs; this indicates that chronological stability is imperfect, but it is descriptive and does not establish drift or a cause. Ten repetitions are adequate for a useful aggregate variability estimate and identifying persistent versus unstable cases, but more repetitions would be needed for narrow per-case probabilities in the stochastic middle.

## Scientific interpretation and caveats

These ten runs characterize stochastic SHACL generation under the frozen R13 pipeline and Luna model configuration. Generation acceptance means that deterministic gates and the semantic validator accepted the candidate; it is **not equivalent to hidden RDF semantic accuracy**. No generated shapes were re-evaluated against newly created RDF cases in this aggregation, and no failed case was repaired or regenerated.
