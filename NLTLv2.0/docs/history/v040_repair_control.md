# v0.4.0 — witnessed failures, SPARQL scope and bounded repair

No model calls, new model generations, batch restart or historical score edits accompany this release. The stopped v0.3.1 batch remains a stopped batch with no accepted NLTL output. Replays and scripted responses are development diagnostics, never fresh workflow accuracy or evidence of automatic live repair quality.

## Reproduced root causes

The five input TTL files are byte-identical copies of saved I2-004 v1–v5. Their SHA-256 and origin paths are in `smoke_tests/regression_inputs/i2_004_v031/manifest.json`. The original source-authored witness contract and ontology remain byte-identical. An unchanged installed v0.3.1 replay was executed before implementation:

- v1: four counterexamples — below_max, near_miss, missing_result, missing_case_operand.
- v2–v4: the same five valid witnesses fail — one, max_last, max_first, tie, fraction.
- v5: all 13 behavioral witnesses unassessable because the nested SELECT omits the potentially pre-bound `this` projection.

The static checker inspected the outer SELECT but skipped complex binding analysis. In addition, RDFLib algebra translation consumes FILTER structure inside EXISTS, so analysis now also inspects the independent, unmodified parse tree. The UNION branches contain filters referring to a `resultValue` not guaranteed in their local scope. This is an uncertain static scope warning, corroborated by actual witness failures; it is not a claim that every UNION is invalid.

The old finding key used location, query excerpt and expected text. It both collapsed different witnesses and made query edits look like resolution. v0.4.0 behavioral identity uses contract, obligation, witness and check IDs; query hash, candidate hash/version and location are separate changing attributes.

## Implemented checks and limits

`src/nltlv2/sparql_analysis.py` parses SPARQL and inspects nested SELECT projections, subquery-visible variables, guaranteed UNION bindings and branch-local operand reads. `$this` and `?this` map to the same RDFLib variable. It calls the locked pySHACL 0.31.0 legality checker to retain the exact engine diagnostic. It checks parsed nested SELECT nodes as well, rather than relying only on the engine's first-match regex. SELECT * in a nested SELECT is not an acceptable substitute under the locked engine policy. Valid UNION, aggregate subquery, combined UNION/subquery and missingness-default controls are tested.

The guaranteed-binding analysis is conservative, not full SPARQL verification. OPTIONAL, correlation, aggregate semantics and unlisted expression forms are not proven. Binding observations are warnings, not confirmed runtime failures; actual source-authored witnesses provide behavioral evidence. This checker does not invent aliases, owner bindings, regulatory constants or closed-world assumptions.

`development_checks.py` keeps the exact validation log, original witness ID, source obligation, relevant operand record, expected/observed result and binding analysis. The operand record is the existing source-authored vector, not a globally minimized counterexample. Missing-input findings have an explicit target/path insertion context and no alleged offending token. The full latest candidate and independent version/hash checks remain in every normal repair request.

## Reconciliation, persistence and oscillation

`tracking.py` retains the catalog of all prior findings. Current observations can be NEW, PERSISTENT or REGRESSED; a previously failed witness is RESOLVED only when it actually executes with the expected result. Missing or failed execution makes it UNASSESSABLE, including earlier findings that had passed at an intermediate version. Thus v5 does not erase the five persistent positive failures (or the four earlier findings). Static warnings and behavioral findings remain distinct.

Exact SHA equality detects unchanged candidates. Isomorphic SHACL graph fingerprints normalize parsed EXISTS-local variable names to detect structural cycling such as v2 → v3 → v2. This is a bounded structural/alpha-renaming heuristic, not a proof of SPARQL equivalence; it preserves externally visible variable identities and does not normalize arbitrary arithmetic rewrites. Independent branches may rename local variables without creating progress. Persistent summaries are delivered in the next repair payload.

Stagnation detection always runs. Stopping is disabled by default, so the six-candidate cap and prefix policy remain unchanged. If explicitly enabled, repeated_failure_set_limit counts consecutive attempts with the same nonempty behavioral-failure set; unchanged_candidate_limit counts consecutive unchanged-code transitions; oscillation_limit counts structural returns to an earlier non-adjacent candidate. A triggered stop is STAGNATION_STOP, never acceptance or a silently smaller attempt budget.

The obligation-removal guard remains active. A diagnosed query replacement may change that exact query at its owning shape; unrelated SHACL signatures remain guarded, and the replacement is checked again. Previously removed obligations are carried forward until restored rather than disappearing from feedback on a later unrelated edit. Witness passes still do not prove all unrelated obligations preserved.

## Execution policy change

This is prospective v0.4.0 policy. It does not reinterpret the historical v0.3.1 stop or assign offline credit to that batch.

| Evidence | Handling |
|---|---|
| Known, bounded generated-query/SHACL legality error | Confirmed SPARQL_ERROR candidate finding; repair within remaining configured attempts. Behavioral observations remain unassessable. |
| Source-authored witness differs from independent source/contract expectation | Demonstrated behavioral finding; targeted repair. Passing finite witnesses is not proof. |
| Conservative operand/scope warning | Nonblocking SPARQL_STATIC_WARNING; retained in review/history and incomplete coverage. It does not independently justify regulatory edits. |
| Unknown engine/infrastructure error | Stop dispatch, no automatic retry or candidate blame. |
| Timeout, memory/recursion/resource exhaustion with uncertain attribution | RESOURCE_ATTRIBUTION_UNCERTAIN; stop dispatch without guessing code cause. |
| Request-integrity or checker/reviewer contradiction | Stop dispatch and preserve evidence. |

Error attribution is conservative and version-bound. Unknown messages remain unresolved. This release classifies observed resource failures; it does not introduce a new OS-enforced wall-clock limit for in-process pySHACL. Provider/network failures are not automatically retried. Reviewer format retries remain separately counted and bounded by the existing policy.

## Proposed single live diagnostic — not dispatched

`configs/i2_004_repair_diagnostic.json` labels TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC. Its seed is the exact historical v5 TTL (SHA-256 `d2c44f9c6243b3169e3d10d7ae32c81ed4a8342d6a4e6de9dd0e7f4a02e01184`). The seed is diagnostic candidate 1 with explicit historical-version metadata; no initial generation occurs. Three candidate attempts mean one seed plus at most two repair calls. Early acceptance, no fresh regeneration, source-authored witnesses enabled, stagnation stopping disabled. Existing bounded semantic review/format retries are auxiliary calls, not hidden candidate revisions. Maximum possible provider calls are two repairs plus up to four review/format calls; seed checking itself is offline. Credentials remain external; model calls remain disabled until separately authorized through the existing explicit live boundary.

Use only internal development witnesses in checking/repair. Any independent evaluation must run afterward in a separate phase; no evaluation fixtures, labels or repaired counterparts may enter the request. Seeded results are not a Single-shot comparison, a fresh pipeline result or part of the old batch.

## Offline commands

From this project root with declared dependencies installed:

```sh
python -m nltlv2 --project . check
python -m nltlv2 --project . smoke
python -m nltlv2 --project . replay --manifest smoke_tests/regression_inputs/i2_004_v031/manifest.json --requirement I2-004
```

Replay writes a fresh timestamped audit directory with complete rendered repair packets and integrity records. Offline smoke blocks network and does not load credentials. It runs independent 37-case reference controls after the unit suite, outside repair. Neither the five-requirement batch nor the 50-requirement study is run. The frozen six- and five-requirement manifests remain preserved and stale against the new implementation, not silently refreshed.
