# TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC — I2-004, frozen v0.4.0

The first live repair was internally accepted; the diagnostic stopped immediately. Zero initial generations; no second repair, regeneration, manual edit, batch restart or study.

| Question | Result |
|---|---|
| Nested SELECT projection corrected? | Yes. The model added `?this` to the nested SELECT and GROUP BY; these are the only two changed lines. |
| Repaired query executed? | Yes, on all 13 original internal witnesses and all reviewed external cases/counterparts. |
| Internal transitions | Two corroborating findings for one query-level projection defect resolved. No persistent, regressed or unassessable findings remain. The seed's 13 behavioral checks were unassessable; the repair produces 13 assessed matches, not 13 prior behavioral defects resolved. |
| Internal acceptance | Diagnostic candidate 2 (one repair of the historical v5 seed), after deterministic checks, runtime probe and reviewer ACCEPT. No format retry. |

## Independent evaluation — after repair finished

| Diagnostic candidate | Positives accepted / 3 | Strict intended detections / 3 | Missed | Unrelated | Unresolved attribution | No-verdict cases / 6 | Repaired counterparts passing / 3 | Ordinary agreement / executable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Seed (historical v5; diagnostic v1) | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 / 0 |
| Repaired, accepted v2 | 3 | 3 | 0 | 0 | 0 | 0 | 3 | 6 / 6 |

F01 reports the source-backed MAX comparison at the applicable ship. F02 reports missing selected displacement via minCount 1 on the exact owner/path. F03 reports the canonical-unit mutation through a node wrapper and its nested unit-membership detail: these describe the same intended defect. Every intended-only repair makes the full unchanged candidate pass; no unrelated leaves remain. Attribution uses constraint/query/path semantics and the counterfactual reports, not messages or blank-node spelling. See `evaluation/semantic_adjudications.json`.

## Actual calls, tokens and time

- **2 calls:** one targeted repair and one review. **0 initial generations, 0 format retries.**
- **15,564 input + 3,442 output = 19,006 provider-reported tokens.** Raw provider usage, including cache/reasoning details, is preserved.
- Diagnostic elapsed **40.72s**; provider request time **24.71s**; separate external validation **18.43s**.

## Evidence and preservation

The seed SHA-256 is `d2c44f9c6243b3169e3d10d7ae32c81ed4a8342d6a4e6de9dd0e7f4a02e01184`. Installed/source identity, bundle hashes and frozen resources were checked before dispatch. The base config remains unchanged; live authorization was a saved runtime overlay through the existing explicit opt-in. Credentials stayed external and were not copied or exposed.

Complete rendered requests, actual provider payloads/raw responses, candidate hashes, original diagnostics, diff, stable reconciliation, persistent summaries and acceptance records are in `diagnostic/`. Independent reports/oracles and semantic adjudications are in `evaluation/`. The snapshot contains no evaluation directory; the repair process denied reads of original evaluation, old outputs and old MVP. External fixture IDs/instance namespaces were absent from sent requests.

**3812 historical output artifacts verified unchanged.** This demonstrates one successful live targeted repair and response path. It does not establish fresh workflow accuracy, general superiority, complete correctness or an optimal attempt budget. Historical stopped-run scores remain unchanged. Stopped after this diagnostic.
