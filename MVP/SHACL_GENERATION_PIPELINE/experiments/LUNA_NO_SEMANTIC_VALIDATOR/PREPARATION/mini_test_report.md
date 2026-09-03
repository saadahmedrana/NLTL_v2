# Three-case development mini-test

## Intended sample

| Requirement | Category | Verification mode | Reason selected |
|---|---|---|---|
| IMO-088 | Static | DIRECT_STATIC | Conditional applicability and alternative-compliance evidence |
| TRF-081 | Static Calculation | DIRECT_CALCULATION | Multiple arithmetic inputs and outputs |
| TRF-012 | Complex | COMPLEX_READINESS | Structured input/result paths without formula reconstruction |

The three entries were copied from the frozen 268-item queue without changing the requirement IDs or objects.

## Execution outcome

The batch began with IMO-088 but the Aalto gateway rejected both configured authentication-header alternatives. The single logical generator call made ten physical transport attempts: five returned HTTP 403 and five returned HTTP 401. Because `persistent_transient_retries` is intentionally enabled, the call would retry indefinitely. It was interrupted safely after five retry cycles.

No model response completed. Therefore this is a transport/authentication-blocked preparation attempt, not a requirement failure and not experimental evidence.

| Requirement | Logical generator calls | Physical attempts | Validator | Matcher | Syntax repair | Regeneration | Extraction / parse / deterministic status | Tokens | Model cost |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| IMO-088 | 1 (not completed) | 10 (5×403, 5×401) | 0 | 0 | 0 | 0 | Not reached | 0 | $0.00 |
| TRF-081 | 0 | 0 | 0 | 0 | 0 | 0 | Not started | 0 | $0.00 |
| TRF-012 | 0 | 0 | 0 | 0 | 0 | 0 | Not started | 0 | $0.00 |

Transport request elapsed time recorded in the events totals 588.336 ms; retry waiting dominated wall-clock time. No `api_call` completion/usage event, batch result, terminal requirement status, tokens, or cost was recorded.

Preserved artifacts:

- `MINI_TEST/runs/RUN-IMO-088-20260901T085218939802Z/events.jsonl`
- the initial context pack
- selected few-shots
- the rendered first generator prompt

The event ledger confirms semantic-validator calls = 0, vocabulary-matcher calls = 0, syntax-repair calls = 0, and regeneration calls = 0. A completed three-case mini-test remains required after the API credential/gateway issue is resolved.
