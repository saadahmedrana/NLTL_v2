# Arm A — TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC

A byte-identical copy of the historical defective NLTL TRF-010 candidate (SHA-256 `080007c68965287e5b8a344ba8d94c89c789a709a61a1a859d2edd46f1af0e8b`) was rechecked with frozen v0.2.0. The actual MISSING_ENUMERATION finding was submitted through the production repair renderer, Runner.dispatch and live request-boundary integrity checks, with full latest code, version/SHA, complete source clause and canonical schema bindings. No initial generation occurred. The experiment-specific seed adapter only supplies the historical starting candidate; it calls the frozen production checks, renderer, dispatch, reviewer and acceptance rules.

One repair call added exactly the six-value sh:in list at ship/iceClass. The diff is in diff_01_02.patch; all other RDF constraint structure is isomorphic to the seed after removing this sole addition. The checker finding resolved, with zero persistent/new findings; production review returned ACCEPT and candidate v2 was accepted. At most two repair calls were authorized, but the second was not needed or made. No auxiliary retry, runtime failure, stale/truncated code, contradictory feedback, weakening or regeneration occurred. Request integrity evidence: request_001_integrity.json. Complete feedback: request_001.rendered.txt.

Independent evaluation ran after the arm finished, with networking blocked and no feedback to repair. Same six positives, two intended negatives and two certified intended-only repairs per candidate; no exclusions.

| Candidate | Positive acceptance | Strict intended detection | Ordinary agreement | Unrelated rejection | No verdict | Repaired acceptance |
|---|---:|---:|---:|---:|---:|---:|
| Historical seed v1 (diagnostic copy) | 6/6 | 1/2 | 7/8 | 0 | 0 | 2/2 |
| Live repaired v2 | 6/6 | 2/2 | 8/8 | 0 | 0 | 2/2 |

The repaired shape detects the unlisted value and the missing assignment for the intended reasons; each intended-only repair passes the full shape. Constraint semantics, exact path/focus, parameter values and reports are saved under evaluation/. This is evidence of one successful targeted development repair, not fresh pipeline accuracy and not a Single-shot comparison. No new defects were observed on the reviewed cases; general absence of defects is not established.

The historical maxCount 1 was retained, not added or newly justified. Source/representation support for a maximum remains unresolved, and the core does not test multiplicity.

Actual usage: 2 provider calls (one repair, one review), 25,576 input + 567 output = 26,143 tokens. Provider time: 6.225s; repair/review runner: 6.910s. Independent evaluation: 17.724s. No code was manually repaired.
