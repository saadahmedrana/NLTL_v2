# I2-005: frozen v0.5.0 targeted repair diagnostic

TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC — seeded development evidence only; no fresh workflow comparison.

Replaced numeric sh:hasValue with minInclusive=maxInclusive=7. Decimal datatype, units, minCount, target and full query remain unchanged.

## External reviewed results

Counts below are diagnostic shape behavior. Rejected seed results do not receive workflow credit. Ordinary agreement is separate from strict intended detection.

| Candidate | Positives accepted | Strict intended negatives | Unrelated/additional | Missed | Unresolved | No verdict | Repaired counterparts pass | Ordinary agreement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Rejected historical seed | 0/1 | 1/4 | 3 | 0 | 0 | 0 | 1/4 | 4/5 |
| Accepted repair 1 (candidate 2) | 1/1 | 4/4 | 0 | 0 | 0 | 0 | 4/4 | 5/5 |

## Feedback and preservation

Actual production feedback contained one independently validated exact-constraint permission and two source-authored behavioral counterexamples, bound to full seed/version 1/SHA `59c60a39431268aed7d5de381bc1283d14cb7d079bd93ec2118b81a2c36c4a9c`. All **3 resolved**; persistent/new/regressed/unassessable **0**. All **14 internal controls passed**. The live request-integrity guard and the preservation guard passed. No unsupported feedback, repeated error, unauthorized functional edit or observed regression remained.

See `diagnostic/request_001.rendered.txt`, `diagnostic/provider_request_001.json`, complete provider responses, `diagnostic/diff_01_02.patch`, `diagnostic/reconciliation_02.json` and source evidence in the original findings. Additional cosmetic edits: [].

## Calls and time

Zero initial generations; **1 repair + 1 review = 2 provider calls**, **0 auxiliary retries**. Tokens: 38,937 input + 1,369 output = **40,306 total**. Provider time **11.69s**; runner **28.91s**; total diagnostic **29.28s**; separate external evaluation **17.63s**.

## Integrity and limits

Installed/source v0.5.0, all snapshot/config/seed hashes and **5,557 prior output hashes** verified unchanged after completion. Fresh experiment ID; no pipeline/base-config edits. Snapshot excludes evaluation data. Runtime audit denied evaluation/history/MVP reads during repair. External evaluation ran only after diagnostic completion, with original cases and certified counterparts. No labels, exclusions, fixtures or historical scores changed.

Strict attribution used the actual leaf constraints, complete contracted paths, applicable query branches, nested reports and passing source-certified intended-only counterparts. Multiple wrapper reports of one failure were not counted as unrelated failures. See `evaluation/semantic_adjudications.json` and `evaluation/final_adjudicated_results.json`.

These two candidate shapes and small reviewed requirement subset do not establish general accuracy, an iteration budget or superiority. No further model calls or experiment expansion were performed.
