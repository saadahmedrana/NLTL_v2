# v0.7.0 source-grounded context, review and activation

Implemented without model calls or credential reads. Both historical v0.6.0 pilot directories and all earlier scores/reports are hash-identical. Source, ontology/IRIs, registry, fixtures and counterparts were not changed. The Git recovery point and selective original-file archives are in this audit; no whole-project backup or rollback was used.

## Changes

- Context traverses actual schema ranges/classes and relevant named individuals with labels/types even when registry rows are absent. Explicit JSON-LD numeric/unit predicates and datatype serialization are supplied to both workflows identically. Broad ancestors do not pull in every ontology term and are not exclusive owners. Missing numeric/unit declarations are rejected rather than invented.
- `qudt:value` receives the unambiguous declared `qudt:numericValue` replacement with exact declaration evidence, version/hash, original diagnostic and real code location. Feedback says repair, not deletion, and grants no numeric conversion. Duplicate identifier findings were consolidated.
- Functional deletion groups retain exact removed triples and require explicit source-grounded removal/replacement/regression/uncertainty assessments. This permits a supported removal of an excessive old constraint without handwritten permission profiles. Model assessments remain unverified interpretations.
- Four documented field-name aliases normalize without changing quotation values. Conflicting aliases/duplicates reject. Raw and normalized objects are retained. Errors distinguish structure/truncation, bad source/current/previous quotations and unsupported schema assertions and identify exact JSON paths/expected structures. Material interpretive uncertainty is a blocking finding, not a format retry.
- Activation checks cover core targets, implicit class targeting, references/nested shapes, reachable active constraints and deactivated enforcement. Nested shapes need no separate target. Trivial minCount=0/closed=false alone cannot establish enforcement. Supported logical false constraints are not blanket-rejected. No correct target is invented. Execution probes only exercise routes and engine legality, ignoring compliance outcomes.
- Deterministic source selection includes anchored clauses, numbered parents, scope/definitions and explicit references. Exact included/omitted spans/hashes and ambiguous/missing references are recorded; supporting sources and ambiguous primary anchors remain full text. Complete source remains available by verified span retrieval, preserving CRLF as well as LF. There is no blind token truncation.

## Saved reviewer replay

Nine actual saved reviews were replayed against their original requests/candidate versions. Alias normalization alone does not make false or paraphrased quotations valid. Eight remain invalid: four non-verbatim source quotations and four unsupported schema assertions. IMO-001’s structurally valid ACCEPT is blocked by material targeting uncertainty. Independently, its actual untargeted candidate now receives ACTIVATION_ERROR. No historical candidate receives new workflow credit.

- I2-004 response 003: INVALID_SOURCE_QUOTATION at $.issues[0].source_excerpt
- I2-004 response 004: INVALID_SOURCE_QUOTATION at $.issues[0].source_excerpt
- I2-005 response 003: UNSUPPORTED_SCHEMA_ASSERTION at $.issues[0].evidence_excerpt
- I2-005 response 004: UNSUPPORTED_SCHEMA_ASSERTION at $.issues[0].evidence_excerpt
- IMO-001 response 002: valid JSON/evidence structure, but material targeting uncertainty blocks acceptance
- TRF-010 response 002: INVALID_SOURCE_QUOTATION at $.issues[0].source_excerpt
- TRF-010 response 003: INVALID_SOURCE_QUOTATION at $.issues[0].source_excerpt
- TRF-035 response 004: UNSUPPORTED_SCHEMA_ASSERTION at $.issues[0].evidence_excerpt
- TRF-035 response 005: UNSUPPORTED_SCHEMA_ASSERTION at $.issues[0].evidence_excerpt

Exact original-response paths/hashes, normalized responses and first actionable invalid-field diagnostics are in `reviewer_replay.json` and `replay/`. Complete saved candidate checker replays and actual destructive diffs are separately retained.

## Prompt-size accounting

Exact initial rendered system+user UTF-8 bytes (same corrected context/settings for both methods):

| Requirement | v0.6.0 bytes | v0.7.0 bytes | Reduction |
|---|---:|---:|---:|
| I2-004 | 80859 | 38315 | 52.6% |
| I2-005 | 74772 | 32574 | 56.4% |
| IMO-001 | 163663 | 61272 | 62.6% |
| TRF-010 | 192638 | 82905 | 57.0% |
| TRF-035 | 203337 | 96164 | 52.7% |

`prompt_sizes.json` separately records source, schema, full code, diagnostics and system/JSON overhead; `source_repetition_accounting.json` measures repeated identical source blocks across the measured requests. Counts are bytes/characters, not guessed provider tokens. Historical review/repair comparisons are like-for-like source/schema substitutions, not predictions of an entire future model history. Actual complete scripted v0.7 requests include the new response schema and removal protocol and carry individual `_sizes.json` files. Previous raw code is preserved in artifacts instead of duplicated in every repair request.

## Verification

**102 software tests passed; zero failures/errors.** The earlier complete v0.7 verification also passed all **37 independent reference cases (17 positive, 20 intended negative) and 20 repaired counterparts** in a separate offline process. Final additions affect only activation/no-op and exact-byte source retrieval; reference inputs/ontology/oracles were unchanged and their validations were not redundantly rerun. Tests exercise novel requirements with evaluation/witness reads denied, identical paired requests, one-call Single-shot, source-backed excessive-constraint removal, latest-code integrity, alias conflicts, strict quotations, material uncertainty, supported nested/implicit/explicit targets, non-vacuous activation, numeric/unit metadata and precise feedback, destructive-change accounting, source-reference retrieval and bounded retries.

Software tests use scripted responses, not new LLM generations or regulatory compliance witnesses. Reference controls test the independent evaluator and do not establish model repair quality. Installed/source byte identity and every pre-existing output hash were verified.

## Provider and limitations

Azure documents reviewer structured output through `text.format` with JSON schema: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs . Transport support is implemented and locally tested behind an explicit documented capability declaration. Current Aalto gateway/model support could not be verified from public documentation; default remains bounded JSON with one format retry. No provider capability probe or model call occurred.

Exact quotations do not prove entailment; a reviewer may still misinterpret source or incorrectly mark uncertainty nonmaterial. Source selection does not prove completeness of implicit definitions/external references: unresolved material dependencies must block acceptance and can require broader source retrieval. Static activation checks are structural and not a general satisfiability/non-vacuity proof for arbitrary SHACL/SPARQL expressions. Complex/custom targets and unsupported execution forms remain unresolved. Shared schema contradictions, qualitative applicability and cardinality ambiguities are not strengthened into new contracts. No study scores or performance advantage are established.

## Proposed bounded live check — NOT DISPATCHED

Use `configs/v070_bounded_live_check.json`: **one fresh I2-004 NLTL run, at most two candidates including initial generation, one bounded reviewer format retry, early acceptance, no seed or fresh regeneration**. This is an operational development check, not a workflow comparison. Use a fresh experiment ID, snapshot first, enforce the existing production data boundary, and evaluate afterward independently. Do not rerun for a preferred result; initial acceptance may leave repair unexercised. Explicit future model authorization and live opt-in are required. The 50-requirement study remains unstarted.

## Evidence and commands

Complete canonical/activation repair packets: `packets/I2-004_complete_repair.json` and `packets/IMO-001_complete_repair.json` (also rendered text). The real scripted source-grounded repair/review packet set is indexed by `representative_packet_index.json`.

```sh
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . check
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . smoke
```
