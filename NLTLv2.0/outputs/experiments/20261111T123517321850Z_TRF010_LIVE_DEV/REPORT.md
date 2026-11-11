# TRF-010 live development pilot

Transport and response handling worked. NLTL accepted its first candidate after one review; repair was **not exercised**. No extra candidate was requested, and no six-requirement or 50-requirement run occurred.

## Recorded configuration

Git revision: `0677969701d42fa54d86c9d9a613bb1d78214ac0`; working tree was dirty and is recorded in git_status_before.txt and diff-stat artifacts. Exact implementation, prompts, configuration and source/schema inputs are preserved in snapshot/ with SHA-256 hashes. Current installed code matched source bytes. Schema hash: `ba247e3973b6afc36a9160ca170a31f863ceb3b0df497e07b7b3101dc7f347e4`.

Model: `gpt-5.6-luna-2026-07-09`; all three real provider responses report that model and completed status. Endpoint: `https://aalto-openai-apigw.azure-api.net/v1/openai/responses`. External credential location and presence were verified in preflight.json; no credential contents were copied or logged. Provider payloads omit authentication values. No separate model probe, transport retry or fresh regeneration occurred.

Selected examples: FS-BOOL-01 and FS-BOOL-02, both synthetic; TRF-010 was absent, with no substitution. Initial source/schema/example context and serialized generation requests were byte-equivalent across methods. The explicit live override changes network_enabled to true in this pilot only; base configurations are untouched. Single-shot made exactly one generation call and had no checker/reviewer/repair. NLTL had a six-candidate cap but stopped after generation 1 and its ACCEPT review.

## Code and findings

### Single-shot initial code

```turtle
@prefix nltl: <https://w3id.org/nltl/vocab#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .

nltl:TRF-010Shape
    a sh:NodeShape ;
    sh:targetClass nltl:ship ;
    sh:property [
        sh:path nltl:iceClass ;
        sh:class nltl:iceClassValue ;
        sh:minCount 1 ;
        sh:maxCount 1
    ] .
```

### NLTL initial code

```turtle
@prefix nltl: <https://w3id.org/nltl/vocab#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .

[
    a sh:NodeShape ;
    sh:targetClass nltl:ship ;
    sh:property [
        sh:path nltl:iceClass ;
        sh:minCount 1 ;
        sh:maxCount 1 ;
        sh:nodeKind sh:IRI
    ]
] .
```

NLTL emitted zero internal findings. Its reviewer returned exactly `{"decision":"ACCEPT","issues":[]}`; no suggested correction, repair packet, candidate edit or diff exists because no repair occurred. This confirms live operation, not repair effectiveness.

**Confirmed post-generation defect in both shapes:** neither enforces the six-value regulatory enumeration. Exact source/contract/line evidence, candidate excerpts and suggested correction are in finding_audit.json. NLTL uses IRI node-kind; Single-shot uses class membership. Under the recorded RDFS inference, any object of iceClass acquires the property's range type, so sh:class is not a closed list. Both accept polarClassPc6 in TRF-010-F01. A source-backed canonical six-IRI set and an actual set-membership constraint are required; that correction is recorded only, not applied.

**Context gap:** raw source text ends at 'as follows:'; normalized text and comparisonModel do state the six names. However controlledValueTerms is empty, and the supplied schema context lacks all six controlled-value IRIs. The reviewer still had evidence of an unimplemented six-value obligation and did not flag either its omission or missing canonical binding. This is a false internal acceptance.

Both shapes add sh:maxCount 1. Its support is not established by the supplied explicit contract or the represented core; this remains an unresolved possible overconstraint, not a confirmed defect or observed regression. No new test was manufactured. There was no unsupported repair feedback, repeated repair error, constraint weakening or repair regression to assess; none was exercised.

## Independent evaluation — same eight cases

Evaluation ran only after generation and acceptance had completed, with networking blocked and no feedback path to the runner. Every saved candidate was evaluated (one per method). Both used the same six positives, two intended negatives and two certified intended-only counterparts. No exclusions or shape/fixture transformations. All 20 validation executions and the independent source oracle evidence are preserved under evaluation/.

| Candidate | Positive acceptance | Strict intended detection | Missed defect | Unrelated rejection | No verdict | Ordinary agreement |
|---|---:|---:|---:|---:|---:|---:|
| Single-shot v1 | 6/6 | 1/2 | 1/2 | 0 | 0 | 7/8 |
| NLTL v1 | 6/6 | 1/2 | 1/2 | 0 | 0 | 7/8 |

Positive acceptance: 100% (6/6); strict intended detection: 50% (1/2); ordinary agreement: 87.5% (7/8), for each method. Both repaired counterparts pass each full shape (2/2). F01's unlisted value is missed. F02's missing assignment is rejected solely by minCount=1 on ship/iceClass, and its intended-only repair passes. That strict attribution was explicitly reviewed from constraint parameters, focus/path, source evidence and counterfactual reports; it does not depend on messages or blank-node IDs. The generic evaluator's conservative query-only attribution recognizer was not silently broadened.

Budgets 2, 3, 4, 5 and 6 all select the same first accepted NLTL candidate, v1, with the same 6/6 positive, 1/2 strict-negative and 7/8 ordinary results and zero no-verdicts. They use the identical saved two-call prefix, not new generations or evaluation-based candidate selection. These ties do not establish a useful iteration budget. Detailed per-budget records: evaluation/budget_results_2_to_6.json.

## Actual usage and time

| Method | Calls | Input tokens | Output tokens | Total tokens | Provider seconds | Runner seconds |
|---|---:|---:|---:|---:|---:|---:|
| Single-shot | 1 | 2679 | 642 | 3321 | 5.572 | 6.068 |
| NLTL | 2 | 5586 | 1149 | 6735 | 11.149 | 11.742 |

Total: 3 provider calls (two generations, one review), 10,056 tokens. No repair calls, auxiliary retries or additional generations. Provider wall time summed across calls: 16.721s; serial driver execution: 18.491s; independent evaluation: 17.361s. Provider-reported caching and reasoning details are retained in usage_summary.json and raw responses; these are observations, not a comparative latency or cost estimate.

## Recommendation before the six-requirement pilot

Do not dispatch the six-requirement batch unchanged. First resolve source/contract completeness for this observed missing obligation: include the complete source enumeration and its source-backed canonical value mapping, and require an explicit closed-set coverage check before internal acceptance. A range/type or IRI check must not satisfy that obligation. Test that gate with approved synthetic development inputs, keeping external evaluation fixtures and labels outside the loop. Do not add another LLM to perform a deterministic finite-set check. Then separately authorize the six-requirement operational pilot. This one-requirement result shows successful live integration and an acceptance failure, with no evidence of a performance advantage or real repair ability.
