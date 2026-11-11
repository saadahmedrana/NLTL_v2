# Confirmed code defects and existing-loop investigation

Authoritative inputs: latest ownership reconciliation 20261110T231036768724Z and its current_case_records snapshot, under baseline 20261108T124921Z. Main classifications, ordinary scores, exclusions, fixtures and shapes are unchanged. This is a separate development diagnostic investigation.

**Recommendation: add a deterministic canonical operand/term-kind check inside the existing static-validation → structured-issue → repair path.** It addresses **29 confirmed faulty generated shape files across 24 requirements** (17 NLTL_v2, 12 Single-shot). All 29 saved terminal diagnostics said valid=true with no errors. The current checker allows entire QUDT namespaces and checks some declared datatypes, but does not resolve every unit constant against property metadata or reject class-valued ObjectProperties used as literal datatypes.

## What was actually executed

536 original requirement runs were joined through their original generation manifests, not fallback context paths. The retained eligible artifacts are 246 NLTL_v2 and 221 Single-shot shapes (467 total). NLTL_v2: 268 generator calls plus 60 syntax-repair calls across 36 requirements; zero semantic-validator or matcher calls. Single-shot: 268 generator calls; zero syntax-repair, semantic-validator, matcher or regeneration calls. Transport retries are not extra logical calls. Original ineligible outputs stay NO_VERDICT.

The full repair implementation and semantic reviewer already exist; this work does not recommend adding another generic reviewer. They did not run on these evaluated ablation artifacts. In the evaluated NLTL_v2 route, deterministic non-syntax errors are explicitly terminal and are not repair feedback. Saved generic tracker text occasionally says a semantic validator accepted a candidate; the role traces and mode-specific diagnostics contradict that canned text, so it is not treated as evidence. See execution_trace_audit.json and implementation_provenance.json.

## Family counts

Each workflow has one retained generated shape file per requirement. Affected cases below are directly demonstrated lower bounds, including positives; reviewed negative exposure counts in parentheses do **not** assert every exposed case failed because of that site. Families overlap (especially wrong unit namespaces and unit errors) and must not be added. The JSON/CSV ledgers retain all IDs, paths and exact metadata. String compatibility sites are runtime issues, not claimed violations of RDF 1.1 string semantics.

| Family | NLTL_v2 shapes / demonstrated cases (negative exposure) | Single-shot shapes / demonstrated cases (negative exposure) | Requirements across workflows |
|---|---:|---:|---:|
| Wrong IRI/namespace or SHACL term kind | 16 / 14 (40) | 12 / 5 (24) | 23 |
| SPARQL binding/scope | 1 / 1 (2) | 0 / 0 (0) | 1 |
| Owner/path against explicit contract | 0 / 0 (0) | 1 / 5 (5) | 1 |
| Unit/literal, including runtime compatibility | 27 / 28 (61) | 20 / 19 (61) | 38 |
| AND/OR and applicability branches | 4 / 9 (10) | 3 / 8 (9) | 6 |
| Reversed comparisons / arithmetic | 0 / 0 (0) | 1 / 3 (3) | 1 |
| Missing obligation / readiness | 1 / 2 (4) | 3 / 4 (9) | 3 |
| Excessive scope / closed lists | 2 / 1 (7) | 4 / 3 (10) | 4 |

The unit/literal row includes 15/12 plain-versus-typed-string compatibility artifacts; these are separated in static_findings_with_diagnostic_evidence.json. Pure unit faults cover 16/10 shapes across 22 requirements; adding the three term-kind artifacts gives the 29-shape recommendation. No additional unsupported arithmetic or cardinality blame is inferred. TRF-017’s missing additional-power operand is a source/context contradiction, not counted as a confirmed generator-only aggregation defect.

Every one of the 355 current mismatch workflow/case rows has a disposition: 56 have case-specific mechanisms bound by source review or diagnostic comparisons in this investigation, 110 have confirmed static sites on their shape without automatically assigning case causality, and 189 remain mechanism-unestablished. These are conservative confirmed families, not an exhaustive re-adjudication of every mismatch. Prior generic cause labels are never promoted to proof.

## Representative code, meaning and loop gap

| Family | Concrete evidence | Effect and missed check |
|---|---|---|
| Namespace/kind | TRF-018: `sh:path qudt:unit; sh:hasValue qudt:KiloW` versus supplied `recommendedUnit=http://qudt.org/vocab/unit/KiloW`. TRF-066: `sh:path nltl:iceClass; sh:datatype nltl:iceClassValue`, although iceClass is an ObjectProperty whose controlled values are IRIs. | Canonical valid graphs fail; wrong unit joins can also suppress negative violations. The check runs but accepts namespace prefixes rather than term roles. All 29 saved diagnostics passed. |
| Binding/scope | TRF-017 NLTL_v2 binds `?restriction` and `?maximumValue` outside UNION, then filters them inside independent branch algebra. The branch-local required comparisons have no local binding for those names. | Restricted-output defect F02 passes. Parse/smoke success is not a binding proof; sparse smoke data does not establish source-valid comparison behavior. Two exact algebra sites are saved; no speculative scope flags are counted. |
| Owner/path | TRF-036 Single-shot targets parameter sets and branches on `sh:path nltl:iceClass`. Explicit termOwners says ship; the complete path is `^hasIceClassDesignParameterSet/iceClass`. | Valid parameter sets fail. The term-level owner was supplied correctly; primary target owner=parameterSet does not relocate the selector. Existing checks do not propagate focus scope through branches/paths. Five reviewed pairs and four positives recover after only this path change. |
| Literal | IMO-031 `sh:in ("Administration" ...)` with supplied xsd:string data; the recorded rdflib/pySHACL Core exact-term comparison distinguishes the simple literal and explicit xsd:string. | Valid approval values fail. This is an engine compatibility issue shared by both workflows, not proof that plain strings violate RDF 1.1. Normalize equivalently for both, with exact changes logged. |
| AND/OR | IMO26-014: `daylight=true OR daylight=false OR count>=2`, rather than `daylight=true OR (daylight=false AND count>=2)`. Single-shot IMO-110/114/TRF-076 use consecutive `FILTER NOT EXISTS` blocks for separate missing obligations, requiring all of them to fail before reporting a violation. | Defective ships pass. An independent source-contract truth table is absent; parse/meta/smoke checks do not test which rows should be violations. |
| Comparison | I2-004 Single-shot selects `caseValue=duiValue` with `NOT EXISTS(otherValue>duiValue)` as a violation. | It reports the valid maximum and misses a non-maximum. Inverting that validity predicate recovers three reviewed pairs and three positives. No arithmetic checker result is inferred merely from a message. |
| Obligation | TRF-062 checks clearance presence but never implements clearance ≥ h0/minimumClearance. IMO26-005 Single-shot hasValue Approved requires one approved value, not every system’s approval. TRF-001 missing date is a representation-readiness gap, not a universal regulatory date mandate. | Defects pass. Relevant source/fields are supplied for these examples, but the obligation-to-constraint check is absent. Free-text comparison models are not executable completeness certificates. |
| Excessive scope | TRF-018 rejects iceClass II globally, although the explicit comparison model applies its floors only to IA/IB/IC/IA Super. Four other global Category-A/B closed-list artifacts similarly turn conditional scope into a global data restriction. | Out-of-scope valid ships fail. TRF-018-P06 still fails after unit repair; this residual defect is not erased to improve gains. No new maxCount/cardinality rule is invented. |

Full original shape excerpts, paths, source clauses, contract objects and SHAs are in manual_confirmations.json and the static finding ledgers. They distinguish an original generated shape defect from a supplied context defect.

## Separate diagnostic arms

Small repairs were selected for transparent local mechanisms across I2, IMO, IMO26 and TRAFICOM: eight requirements, 12 transformed shape copies representing 11 distinct original generated artifacts, and 130 changed-shape/data executions with saved negative, repaired and positive reports. Unchanged counterpart results were reused. Every transformation is in diagnostic_transformations.json. The additional-power sum arm is explicitly provisional and excluded from strict gain estimates.

| Diagnostic arm | NLTL_v2 strict recoveries / reviewed pairs; positive recoveries | Single-shot strict recoveries / reviewed pairs; positive recoveries | Regressions / limits |
|---|---|---|---|
| Canonical unit/string operands (4 requirements) | +16 / 16; +12 / 13 positives | +8 / 16; +7 / 13 positives | No positive regressions or strict losses. Four Single-shot TRF-076 negatives become accepted: ordinary rejection losses, exposing the existing conjunction bug. Not strict losses because their original rejections had unrelated errors. |
| Explicit TRF-036 selector path | +0 / 5; +0 / 4 | +5 / 5; +4 / 4 | No regressions; NLTL_v2 already uses the right join. |
| I2-004 violation polarity | +0 / 3; +0 / 3 | +3 / 3; +3 / 3 | No regressions. |
| IMO26-014 paired branch | +4 / 4; +0 / 3 | +0 / 4; +0 / 3 | Single-shot’s four pairs and three positives stay original NO_VERDICT; its malformed candidate is not run or credited. |
| TRF-017 scope only | +1 / 2; +0 / 4 | unchanged | Two NLTL_v2 positives and one repaired counterfactual change pass→fail: scope repair exposes the omitted additional-power law. |
| TRF-017 scope + sum hypothesis | no certified strict gain | unchanged | Full source contains additional power, but the supplied contract and allow-list omit it and its requirement-specific owner is not explicit. The hypothetical ship binding is not approved; these reports are provisional sensitivity evidence only. |

After deduplicating overlapping gains, the four fully supported arms recover 20 NLTL_v2 and 16 Single-shot strict cases on the same 28 reviewed case IDs (including four original Single-shot no-verdicts), and 12/14 positive cases respectively. Four Single-shot ordinary negative agreements are lost. This deliberately selected development subset is not an unbiased estimate of future pipeline accuracy or full-benchmark strict accuracy. The scope-only arm is not folded into these gains.

## Ranked additions inside the loop

1. **Canonical operand and term-kind checker** after Turtle extraction, alongside validate_turtle, before the candidate reaches acceptance or repair selection. Inputs: original locked compact term metadata (kind, range, datatype, recommendedUnit), complete path context and parsed SPARQL IRIs. New checks: resolve unit constants against their owning QuantityProperty; reject schema-namespace unit names and ObjectProperty→sh:datatype mismatches; run an engine string-identity compatibility probe. Missing unit metadata causes an unresolved finding, not a guessed mandatory unit. Feedback: exact constraint location, actual/expected IRI or term kind, metadata pointer and smallest permissible edit. Example `UNIT_CONSTANT_MISMATCH: calculatedRequiredPower/@node/qudt:unit; actual=qudt:KiloW; expected=unit:KiloW; evidence=term.recommendedUnit; preserve numeric value and unrelated constraints`. A proper-namespace scale mismatch (e.g. metres vs millimetres) must require conversion/formula review, never a blind IRI substitution. **29 clear faulty shapes / 24 requirements; another 27 compatibility artifacts overlap partially.**

2. **Source-approved branch/query witnesses plus definite-binding analysis.** Insert after parseQuery and before final acceptance, and repeat after repair. New information is an independent approved obligation model: applicability guard, AND/OR connective, comparison polarity, boundary and mandatory clauses. Compile tiny synthetic witnesses from that model, never benchmark fixtures. Include one-clause-at-a-time violations and a source-valid control; require the query to return violation rows exactly where specified. For the already formalized subset this is deterministic. General natural-language models cannot safely be auto-compiled: require source/contract reconciliation first, explicitly blocking contradictions such as TRF-017. Feedback gives the failing source obligation, branch algebra, unbound variable or valid-state-as-violation witness, not a held-out case ID or label. The scope scanner proves one NLTL_v2 artifact; manual source review binds seven further Boolean artifacts and one reversed-comparison artifact (nine distinct artifacts / eight requirements, not nine independent per-case failures). The current full semantic reviewer already exists; another generic LLM reviewer is not the proposed addition.

3. **Explicit-contract path checker.** Carry focus class and path through sh:node, property paths and logical branches, checking termOwners/modelPaths and subclass compatibility. Insert with the operand checker and send the full required/observed path into existing structured repair feedback. Demonstrated clear owner defect: one Single-shot shape / one requirement, five pairs. Current evidence does not support earlier broad owner-blame counts. Broad domains are typing assertions, requiredOwner fallback is not evidence, and unknown owners must remain unresolved. The earlier fallback fix already exists; this is path enforcement, not repeating that fix.

For the existing FULL_REPAIR_V2 runner, these become concrete static_issues/currentIssues and existing repair-memory guards. For the evaluated NoSemanticValidatorRunner, non-syntax findings currently have no repair route: either apply a narrowly certified deterministic representation correction shared by both workflows, or explicitly change that controller in a new experiment to route bounded issues to repair. Do not send semantic changes through its syntax-only prompt or assume its extra loop already handles them. No such controller change is made here.

## Cost, comparative benefit and uncertainty

No checker requires an LLM call; added review inference cost is zero. AST/metadata checks reuse parsing and add local CPU work. Source-witness execution needs a bounded small number of synthetic validations per approved model; actual diagnostic executions here average 1.24 seconds each (161.7 summed seconds for 130 calls, four workers), not an API cost estimate. The optional subsequent generation repair consumes existing repair budget/tokens; automated repair success, token overhead and dollar cost have not been measured. Manual diagnostic recovery is an upper-bound opportunity, not a measured loop recovery rate.

Canonical/schema/runtime corrections benefit both methods and must be applied equally. NLTL_v2 can specifically consume structured semantic findings only if its active repair controller supports them; the evaluated extra calls were syntax-only. There is **no measured meaningful extra advantage** for NLTL_v2’s repair loop from these diagnostics. Unequal recovered case counts reflect existing errors and the selected development cases, not proof that its loop is better. Single-shot benefits more from the demonstrated owner/polarity corrections.

No inspected fixture, counterfactual, expected label, validator report or case ID may be supplied to the proposed generation loop. All inspected cases are now development evidence; a new experiment needs separately held-out, frozen evaluation evidence. Input ownership ambiguity is blocked, never strengthened to make a shape pass.

## Preserved measured results and reproducibility

The authoritative 553-case strict subset, its 651 blockers and one exclusion are unchanged. Ordinary agreement remains NLTL_v2 1640/2159 and Single-shot 1425/2159; diagnostic gains above do not alter these figures. TRF-050-F05 remains a strict match for both methods. The 28 invalid historical repair claims and all 52 underspecified-owner blockers stay governed by the latest reconciliation.

Read diagnostic_case_results.csv, diagnostic_reason_proofs.json, diagnostic_summary.csv and deduplicated_diagnostic_gains.json for counts and every report path. Main source and shape files were never changed. The saved test command is in README.md.

Verification: 13 new read-only/synthetic checks and 19 applicable existing scoring/branch checks pass. The historical test that asserts every wrong-owner consequence is unrelated is superseded by the ownership reconciliation and was not reused. No completed benchmark pair was replayed by these checks.
