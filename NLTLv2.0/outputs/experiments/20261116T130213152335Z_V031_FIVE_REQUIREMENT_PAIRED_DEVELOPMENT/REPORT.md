# v0.3.1 paired development pilot — stopped by safety policy

Only I2-004 was attempted. NLTL candidate 5 produced a SHACL-SPARQL execution failure: nested SELECT does not project the potentially pre-bound `$this`. Generation stopped without candidate 6 or any calls for the remaining four requirements. No frozen pipeline changes or reruns.

## Selected workflow results on attempted I2-004 cases

| Workflow | Positive accepted / 3 | Strict detected / 3 | Missed | Unrelated | Unresolved attribution | Negative no verdict | Ordinary agreement / executable |
|---|---:|---:|---:|---:|---:|---:|---:|
| Single-shot | 3 | 2 | 1 | 0 | 0 | 0 | 5 / 6 |
| NLTL | 0 | 0 | 0 | 0 | 0 | 3 | 0 / 0 |

NLTL has no internally accepted candidate: all six I2-004 case outputs are NO_VERDICT. Its rejected candidates are diagnostic only. I2-005 (1P/4N), IMO-001 (2P/3N), TRF-010 (6P/2N), TRF-035 (2P/4N) are NOT_RUN for both workflows. Their combined 24 cases and 13 counterparts were not validated against nonexistent outputs. Planned denominators remain 30 cases/16 negatives, but results are not full-pilot accuracy. Common selected executable negative denominator: 0. I2-042 remains deferred.

## All saved candidate diagnostics

| I2-004 output | Positive accepted / 3 | Strict / 3 | Missed | Unrelated/additional | Negative no verdict | Ordinary / 6 |
|---|---:|---:|---:|---:|---:|---:|
| Single-shot v1 | 3 | 2 | 1 | 0 | 0 | 5 |
| NLTL v1 | 3 | 1 | 2 | 0 | 0 | 4 |
| NLTL v2 | 0 | 0 | 0 | 3 | 0 | 3 |
| NLTL v3 | 0 | 0 | 0 | 3 | 0 | 3 |
| NLTL v4 | 0 | 0 | 0 | 3 | 0 | 3 |
| NLTL v5 | 0 | 0 | 0 | 0 | 3 | 0 |

Single-shot misses F02 (missing selected displacement). F01 is correctly detected by the source-backed maximum query; F03 is detected by the canonical-unit constraint. Nested `sh:detail` reports were inspected: quantity wrappers and their unit leaf describe the same intended defect, not unrelated failures. Both certified intended-only repairs pass.

NLTL v1 misses F01/F02 and correctly detects F03. Repair v2 adds missing-input minCounts but introduces a UNION/outer-variable scope failure; v2–v4 reject every reviewed positive and every repaired counterpart. V4 restores V2’s query. V5 switches to an aggregate subquery that fails the SHACL pre-bound-variable projection restriction.

From v1 to v2–v4, ordinary verdict gains are F01/F02 (2 unique cases), while all three positives regress; strict gains are zero and F03 loses strict credit (valid repair fails). Deduplicated regression union: 4 cases. These ordinary gains are not intended-detection recoveries. From v1 to final v5, gains are zero and executable coverage is lost on all 6 cases; 4 previously correct cases lose correctness/coverage. No repair earns workflow credit.

## Feedback, checks and limits

Source-authored behavioral witnesses triggered 4 confirmed findings at v1 and 5 positive-control counterexamples at each of v2–v4. V5 records one query-level runtime defect on 13 witnesses, explicitly unconfirmed as regulatory findings. Parser/canonical/path checks did not identify the nested SELECT projection or UNION operand-scope defect. No semantic reviewer calls occurred; zero false internal acceptances and no unsupported conformance findings were established. Missing-input feedback cites the unique query although the absent minCount has no offending code token; localization is incomplete.

Frozen transition keys collapse several same-location witness findings and treat query-text edits as resolved/new; stable-witness review shows the same five positive failures persist across v2–v4. Original records remain intact. This bookkeeping limitation must not be mistaken for successful repair. No witness pass constitutes complete correctness proof.

## Budgets 2–6

No saved prefix contains an accepted NLTL candidate. Budgets 2–4 therefore produce NO_VERDICT; budget 5 stops on runtime failure. Budget 6 is censored at candidate 5 under the safety policy, not an observed completed six-attempt run. Four requirements are unrun for every budget. No optimal-budget or superiority inference is possible.

## Calls and time

- Single-shot: 1 calls, 5,692 input + 2,635 output = 8,327 tokens; 19.52s workflow time.
- NLTL: 5 calls, 112,406 input + 9,815 output = 122,221 tokens; 102.38s workflow time.
- Total: 6 successful provider calls (2 initial generations, 4 repairs), 130,548 tokens, no reviews or auxiliary retries. Generation batch 122.60s; provider request time 84.29s; independent validation 51.46s.

Preservation check: 2666 prior output artifacts unchanged; active implementation and frozen snapshot hashes unchanged. All initial requests/settings match; external fixture IDs/instance namespaces absent from requests. Full provider requests/responses, findings, execution logs, hashes, diffs, acceptance decisions, semantic adjudications and prefix accounts are saved alongside this report.

Recommendation: **fix the demonstrated SPARQL analysis and transition-bookkeeping defects before another live pilot.** Extend the existing checker to nested SELECT pre-bound-variable projection and UNION operand scope, and retain exact execution diagnostics for actionable repair. Use stable contract/witness IDs for semantic transitions. Make those changes offline in a new version; do not patch this batch or proceed to the 50-requirement study.
