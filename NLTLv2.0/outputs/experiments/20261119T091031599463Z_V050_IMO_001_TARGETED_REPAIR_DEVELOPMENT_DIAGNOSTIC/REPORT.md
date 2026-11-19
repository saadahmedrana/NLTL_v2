# IMO-001: frozen v0.5.0 targeted repair diagnostic

TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC — seeded development evidence only; no fresh workflow comparison.

Removed only the excessive selector sh:in as a functional change. Selector minCount 1, IRI/class checks, ship target and exact conditional query remain unchanged. The message was updated under the frozen cosmetic-annotation policy.

## External reviewed results

Counts below are diagnostic shape behavior. Rejected seed results do not receive workflow credit. Ordinary agreement is separate from strict intended detection.

| Candidate | Positives accepted | Strict intended negatives | Unrelated/additional | Missed | Unresolved | No verdict | Repaired counterparts pass | Ordinary agreement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Rejected historical seed | 1/2 | 3/3 | 0 | 0 | 0 | 0 | 3/3 | 4/5 |
| Accepted repair 1 (candidate 2) | 2/2 | 3/3 | 0 | 0 | 0 | 0 | 3/3 | 5/5 |

## Feedback and preservation

Actual production feedback contained one independently validated exact-constraint permission and two source-authored behavioral counterexamples, bound to full seed/version 1/SHA `d343219b4548a6c5fe6fe524421158c7e54f9eb41aa2a170e5c5870e5ab499da`. All **3 resolved**; persistent/new/regressed/unassessable **0**. All **7 internal controls passed**. The live request-integrity guard and the preservation guard passed. No unsupported feedback, repeated error, unauthorized functional edit or observed regression remained.

See `diagnostic/request_001.rendered.txt`, `diagnostic/provider_request_001.json`, complete provider responses, `diagnostic/diff_01_02.patch`, `diagnostic/reconciliation_02.json` and source evidence in the original findings. Additional cosmetic edits: [{"kind": "COSMETIC_MESSAGE_UPDATE", "authorized_regulatory_change": false, "allowed_by": "Frozen v0.5.0 COSMETIC annotation policy; not a functional constraint", "old": "Selector message required the sole medium-ice value.", "new": "Selector message requires only the evidenced IRI/type readiness."}].

## Calls and time

Zero initial generations; **1 repair + 1 review = 2 provider calls**, **0 auxiliary retries**. Tokens: 25,543 input + 805 output = **26,348 total**. Provider time **7.32s**; runner **17.49s**; total diagnostic **17.87s**; separate external evaluation **14.65s**.

## Integrity and limits

Installed/source v0.5.0, all snapshot/config/seed hashes and **5,719 prior output hashes** verified unchanged after completion. Fresh experiment ID; no pipeline/base-config edits. Snapshot excludes evaluation data. Runtime audit denied evaluation/history/MVP reads during repair. External evaluation ran only after diagnostic completion, with original cases and certified counterparts. No labels, exclusions, fixtures or historical scores changed.

Strict attribution used the actual leaf constraints, complete contracted paths, applicable query branches, nested reports and passing source-certified intended-only counterparts. Multiple wrapper reports of one failure were not counted as unrelated failures. See `evaluation/semantic_adjudications.json` and `evaluation/final_adjudicated_results.json`.

These two candidate shapes and small reviewed requirement subset do not establish general accuracy, an iteration budget or superiority. No further model calls or experiment expansion were performed.
