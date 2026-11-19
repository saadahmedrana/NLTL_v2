# v0.4.0 repair-control verification

No model calls, new model generations, batch restart or study. The stopped v0.3.1 batch and its scores are preserved. New classifications below are diagnostic checker results only.

| Saved I2-004 candidate | Reproduced behavior on original internal witnesses | v0.4.0 reconciliation |
|---|---|---|
| v1 | Four failures: below_max, near_miss, missing_result, missing_case_operand | Four distinct stable witness findings |
| v2 | Five positive witnesses reject | Five observed regressions; four earlier failures rechecked as resolved |
| v3 | Same five positive failures | Five persistent failures despite query edit |
| v4 | Same five positive failures | Five persistent failures; structural return to v2 up to EXISTS-local variable renaming |
| v5 | Nested SELECT cannot execute on all 13 witnesses | Confirmed, repairable query error; all nine prior behavioral findings unassessable, zero claimed behavioral resolutions |

## Exact causes and fixes

1. The old checker checked the outer SELECT but skipped complex binding structure. Parsed nested SELECT inspection now checks required pre-bound focus projection with `$this`/`?this` equivalence and retains the locked engine diagnostic verbatim. Parsed UNION/subquery operand analysis supplies conservative warnings; actual witnesses establish the demonstrated behavior. RDFLib translation consumes some EXISTS FILTER structure, so an independent unmodified parse tree is inspected too. Valid UNION and aggregate/subquery controls are accepted.
2. Old finding keys depended on the mutable query/location/expected text and collapsed multiple witnesses. Stable contract/obligation/witness/check identities now preserve every witness, while location/query hash/candidate version remain separate. Reconciliation retains the whole prior catalog, recognizes regressions, and makes failed execution unassessable. Last-known locations are explicitly labelled with their original version/hash rather than presented as current.
3. Repairs repeated the same failed witness set and returned to a prior query structure. Exact unchanged-code, repeated-failure-set and structural/alpha-cycle detection now produce a persistent summary for the next repair. Optional stagnation stopping is explicit and disabled by default; the six-attempt cap is not silently changed.
4. v0.3.1 treated the generated nested-projection error as unresolved runtime context and stopped. v0.4.0 treats known bounded generated-query/SHACL errors as candidate findings repairable within budget. Infrastructure, integrity, contradictory feedback and uncertain time/resource failures stop dispatch. This prospective policy does not reinterpret the historical stop.

Feedback includes the full latest candidate/hash/version, source clause and original engine logs. Behavioral findings include original synthetic witness IDs, relevant operands and expected/observed results, plus binding evidence. Missing constraints have explicit insertion paths and no fabricated offending token. Exact diagnosed-query replacement is allowed while unrelated SHACL signatures and previously removed obligations remain guarded.

## Offline evidence

- Complete suite: **166 tests passed**; no failures/errors. Network blocked and no credentials loaded.
- Additional focused control: a correct source-authored UNION maximum implementation passed the actual checker/witness/runtime path and scripted acceptance. No new model response was generated.
- Independent reference controls: **37 cases (17 positive, 20 negative) and 20 intended-only counterparts passed**, separately from repair. These are development controls, not generated-output accuracy.
- Original installed v0.3.1 replay and environment are retained in `original_v031_replay/`; installed/source hashes matched before replay.
- Final identity checks confirm query line/hash changes do not change finding IDs, with AST location separate from identity.

## Complete rendered repair packets

- `candidate_01/repair_request.rendered.txt`: arithmetic and missing-input findings with insertion context.
- `candidate_02/repair_request.rendered.txt`: five separate positive failures and uncertain branch-binding evidence.
- `candidate_05/repair_request.rendered.txt`: exact nested-SELECT engine diagnostic and nine unassessable prior findings.

Each directory also contains the exact candidate, structured request, integrity result, complete witness logs, reconciliation and persistent-failure summary.

## Proposed one-requirement live diagnostic — not run

Use `configs/i2_004_repair_diagnostic.json`: TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC, historical v5 seed SHA-256 `d2c44f9c6243b3169e3d10d7ae32c81ed4a8342d6a4e6de9dd0e7f4a02e01184`, zero initial generation calls, at most two repair calls (one seed + two revisions), early acceptance, no regeneration, original internal witnesses, stagnation stopping disabled. Existing bounded review/format retries are auxiliary (at most four review/format calls); external evaluation may run only afterward. Model calls remain disabled pending separate authorization.

Remaining uncertainty: finite witnesses and conservative static warnings are not complete correctness proofs; arbitrary correlation/OPTIONAL/aggregate behavior, namespace environments, graph multiplicities and untested data remain outside proof. Unknown engine errors remain unresolved. Structural fingerprints are repeat heuristics, not equivalence proofs. No live automatic repair benefit has been established. See `docs/v040_repair_control.md` and `docs/v040_change_manifest.json` for policy, provenance, hashes and commands.
