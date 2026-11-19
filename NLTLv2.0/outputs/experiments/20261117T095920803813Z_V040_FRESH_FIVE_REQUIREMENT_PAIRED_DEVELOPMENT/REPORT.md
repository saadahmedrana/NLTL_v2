# Fresh v0.4.0 paired development pilot

Only this fresh batch is included. All five requirements completed; I2-042 deferred. No seeded shapes or diagnostic solutions were supplied. No implementation/configuration changes, reruns, exclusions or shape transformations.

## Selected workflow results

P = positives accepted; S = strict intended detections; M = missed defects; U = unrelated/additional rejection; A = unresolved attribution; NV = no-verdict cases (positive + negative). P and S have separate denominators.

| Requirement | Workflow | P | S | M | U | A | NV | Ordinary agreement / executable | NLTL acceptance |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| I2-004 | Single-shot | 3/3 | 2/3 | 1 | 0 | 0 | 0 | 5/6 | original |
| I2-004 | NLTL | 3/3 | 3/3 | 0 | 0 | 0 | 0 | 6/6 | 1 |
| I2-005 | Single-shot | 0/1 | 1/4 | 0 | 3 | 0 | 0 | 4/5 | original |
| I2-005 | NLTL | 0/1 | 1/4 | 0 | 3 | 0 | 0 | 4/5 | 2 |
| IMO-001 | Single-shot | 1/2 | 3/3 | 0 | 0 | 0 | 0 | 4/5 | original |
| IMO-001 | NLTL | 0/2 | 0/3 | 0 | 0 | 0 | 5 | 0/0 | exhausted at 6 |
| TRF-010 | Single-shot | 6/6 | 2/2 | 0 | 0 | 0 | 0 | 8/8 | original |
| TRF-010 | NLTL | 6/6 | 2/2 | 0 | 0 | 0 | 0 | 8/8 | 1 |
| TRF-035 | Single-shot | 2/2 | 4/4 | 0 | 0 | 0 | 0 | 6/6 | original |
| TRF-035 | NLTL | 2/2 | 4/4 | 0 | 0 | 0 | 0 | 6/6 | 1 |
| TOTAL | Single-shot | 12/14 | 12/16 | 1 | 3 | 0 | 0 | 27/30 | |
| TOTAL | NLTL | 11/14 | 10/16 | 0 | 3 | 0 | 5 | 24/25 | |

All 30 case IDs and 16 negative IDs remain in both workflow denominators. NLTL has one executable positive rejection and five NO_VERDICT cases (IMO-001: 2P/3N), not six ordinary disagreements. Single-shot has three ordinary disagreements. Ordinary executable agreement is 90% Single-shot and 96% NLTL, with coverage 100% and 83.33% respectively; these conditional percentages must not hide the missing NLTL outcomes. Correct/executable/retained counts are 27/30/30 and 24/25/30.

The secondary common executable subset has 25 cases (12P/13N): Single-shot ordinary 23/25, strict 9/13; NLTL ordinary 24/25, strict 10/13. This subset omits the five valid IMO cases ONLY for a labelled coverage comparison; they remain in the primary results. No claim of superiority follows.

## What repairs did

- I2-004, TRF-010 and TRF-035 accepted candidate 1. I2-004 Single-shot misses the below-maximum defect because two NOT EXISTS filters are conjunctive; NLTL initially produced the correct disjunctive condition. This difference did not result from repair.
- I2-005 accepted candidate 2 after correcting `qudt:DEG` (wrong namespace) to canonical `unit:DEG` and adding query prefixes. Values/threshold were preserved. This is a safe identifier correction, not numeric conversion.
- I2-005 is nevertheless a false internal acceptance: both workflows use `sh:hasValue "7"^^xsd:decimal`. The reviewed positive and three valid repairs contain `"7.0"^^xsd:decimal`; their numeric value is 7 but RDF terms differ. Source and approved serialization require numeric equality and decimal datatype, not one lexical spelling. The internal positive witnesses use the matching `"7"` spelling. Keep all these valid tests. F01 alone receives strict credit because its certified repair uses the matching spelling and the full shape passes.
- IMO-001 exhausted six candidates. Initial/odd candidates wrongly close the selector to only the applicable medium-ice value. Even candidates remove that unsupported closure and pass all internal witnesses and all five external cases, but the preservation guard blocks the deleted `sh:in`. Later feedback restores the bad restriction, producing oscillation. Three unsupported preservation blockers occur at v2/v4/v6. No conflict status was raised; no operational failure occurred. These rejected candidates are diagnostic, never promoted to workflow success.

Negative attribution inspected the actual property paths, source queries and nested details, with the intended-only repaired reports. The I2-005 lexical failures are unrelated/additional failures where valid repairs still reject. Other wrappers describe the same underlying intended missing/unit/value defects; no message-text or blank-node-ID matching was used. See `evaluation/semantic_adjudications.json` and `demonstrated_defects.json`.

## Recoveries and regressions

Initial → selected NLTL outputs: **one unique strict recovery**, I2-005-G-F01; no positive or ordinary recovery. Four previously correct IMO outcomes lose credit/coverage because no candidate was accepted (P01 and F01–F03); all five IMO outcomes become NO_VERDICT. These are coverage losses, not newly measured logical rejections.

Initial → last generated diagnostics (unaccepted IMO v6 kept separate): two unique recoveries, I2-005-G-F01 strict and IMO-001-P02 positive/ordinary; no final logical regression. Across all repair transitions, IMO-001-P02 repeatedly recovers/regresses; count it once in each relevant union, not once per oscillation. No rejected IMO recovery contributes to selected-workflow scores.

## Budgets 2–6

Same saved histories, first acceptance within each prefix; no external-score selection and no new calls. All budgets select I2-004 v1, I2-005 v2, TRF-010 v1, TRF-035 v1; IMO has no acceptance. Performance is identical across budgets: NLTL P=11/14, strict=10/16, unrelated=3, no verdict=5. Higher budgets spend more on the unresolved preservation loop, not better selected outputs. This does not establish an optimal general budget.

| Budget | Paired calls (Single-shot + NLTL) | NLTL calls | Paired provider tokens |
|---|---:|---:|---:|
| 2 | 16 | 11 | 145,754 |
| 3 | 17 | 12 | 152,742 |
| 4 | 18 | 13 | 165,883 |
| 5 | 19 | 14 | 173,355 |
| 6 | 20 | 15 | 186,380 |

## Calls and runtime

| Workflow | Calls | Initial generations | Repairs | Reviews | Format retries | Input tokens | Output tokens | Total tokens | Workflow seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Single-shot | 5 | 5 | 0 | 0 | 0 | 31,600 | 6,301 | 37,901 | 50.48 |
| NLTL | 15 | 5 | 6 | 4 | 0 | 135,266 | 13,213 | 148,479 | 159.93 |

Total: 20 successful calls, 186,380 tokens (166,866 input / 19,514 output). Generation batch 214.35s; included provider time 158.29s; separate independent validation 130.95s. Raw provider cache/reasoning usage preserved. No auxiliary retries.

## Recommendation

Fix the demonstrated deterministic numeric-literal coverage/operand gap and the preservation guard’s authorization of source-backed excess-constraint removal before another live expansion. Do not disable the guard broadly, normalize fixtures to satisfy code, or drop valid cases. Keep earlier pilots and seeded diagnostics separate. These five development requirements cannot establish general superiority or an optimal iteration budget. The 50-requirement study remains pending review.


Preservation/integrity verification passed: 3956 prior output artifacts unchanged; installed/source/snapshot identity unchanged; all 10 actual initial requests paired identically; no evaluation IDs/instance namespaces in model requests; original example corpus unchanged. All 16 saved candidates, 90 candidate-case outcomes and 51 negative/repaired pairs are retained.
