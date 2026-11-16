# Arm B — Fresh paired TRF-010 development pilot

One fresh run per workflow used identical corrected source/schema/example context and generation settings from the pre-dispatch snapshot. Full rendered initial requests and actual provider payload hashes match. Single-shot made exactly one generation call with no checker feedback or revision. NLTL was capped at six candidates, but its first generation implemented the enumeration and passed deterministic checking and production review, so it stopped at candidate v1. No repair, fresh-regeneration escape, format retry or preferred-outcome rerun occurred in this arm.

Both original candidates contain the exact canonical six-value sh:in at ship/iceClass and minCount 1. The NLTL candidate additionally checks iceClassValue typing, which does not substitute for its explicit enumeration. Neither fresh shape imposes maxCount 1. Source support for maximum cardinality remains unresolved; its absence was not treated as an error. No runtime, integrity or contradictory-feedback problem appeared.

Independent evaluation was performed only after both workflows finished, with networking blocked and no results supplied to repair. Every candidate was evaluated (one per method). Same eight reviewed cases and two repaired counterparts, no exclusions or shape transformations:

| Method | Positive acceptance | Strict intended detection | Ordinary agreement | Unrelated rejection | No verdict | Repaired acceptance |
|---|---:|---:|---:|---:|---:|---:|
| Single-shot original v1 | 6/6 | 2/2 | 8/8 | 0 | 0 | 2/2 |
| NLTL accepted v1 | 6/6 | 2/2 | 8/8 | 0 | 0 | 2/2 |

This fresh arm did not exercise NLTL repair; Arm A provides a separate targeted repair diagnostic, not an interchangeable performance result. One requirement provides no evidence of a general advantage or best iteration budget.

| Method | Real calls | Input tokens | Output tokens | Total tokens | Provider time | Runner time |
|---|---:|---:|---:|---:|---:|---:|
| Single-shot | 1 generation | 11,826 | 271 | 12,097 | 2.631s | 2.767s |
| NLTL | 1 generation + 1 review | 23,967 | 558 | 24,525 | 5.690s | 6.254s |

Independent evaluation: 19.093s. Cache/reasoning details and raw provider responses are retained; cache warming and one short run prevent general cost/latency claims. Verification is category assignment only, not ship engineering qualification.
