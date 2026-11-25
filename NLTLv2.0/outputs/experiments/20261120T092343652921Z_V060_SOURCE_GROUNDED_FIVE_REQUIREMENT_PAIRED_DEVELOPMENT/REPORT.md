# v0.6.0 source-grounded paired development pilot

This fresh pilot completed after the earlier, separately preserved HTTP403 attempt. Only this new batch is analyzed here. All 23 provider requests succeeded; no infrastructure/integrity/conflict stop occurred. Frozen implementation, base configs, prompts and source/schema inputs were not edited. No 50-requirement study was started.

## Preflight and isolation

Local and remote main matched `495f8c69e7213fac6d83cf28613cf9821b5794c3`. Installed/source modules matched byte-for-byte. The only pre-existing untracked change was the preserved blocked-run output directory; tracked code was clean. Snapshot and original-input hashes remain unchanged. No few-shot examples were supplied or restored. The complete actual provider request bodies for the first generation were byte-equivalent after JSON parsing for each paired workflow. Model: `gpt-5.6-luna-2026-07-09`; endpoint and external credential location are recorded without key values in `preflight.json`.

Production ran from a source-only snapshot with the frozen GenerationProject capability and filesystem audit denying evaluation, witnesses, solution profiles, bespoke permissions, provenance and prior shape/history access. The snapshot projects out ignored preparation fields while preserving exactly the same rendered context as the original frozen implementation. Execution probes use only schema-derived empty targets and ignore conformance; there are no requirement-specific expected outcomes. Independent evaluation began only after `dispatch_closed.json` was saved.

## Primary workflow results

All 30 reviewed cases remain for both workflows: 14 positives and 16 intended negatives, with 16 repaired counterparts. No exclusions. Four NLTL requirements have no internally accepted candidate and therefore remain NO_VERDICT; their last rejected candidates are never substituted.

| Metric | Single-shot | NLTL |
|---|---:|---:|
| Positive acceptance | 10/14 (71.4%) | 2/14 (14.3%) |
| Strict intended detection | 2/16 (12.5%) | 0/16 (0%) |
| Missed intended defects | 7/16 | 3/16 |
| Unrelated/additional rejection | 7/16 | 0/16 |
| Unresolved attribution | 0/16 | 0/16 |
| Negative NO_VERDICT | 0/16 | 13/16 |
| Positive NO_VERDICT | 0/14 | 12/14 |
| Total NO_VERDICT | 0/30 | 25/30 |
| Ordinary verdict agreement | 19/30 (63.3%) | 2/30 (6.7%) |

Ordinary agreement is distinct from strict detection: Single-shot gets ordinary negative agreement for seven I2 rejections that also reject valid positives/repaired counterparts, so those seven get no strict credit. These are development outcomes, not general superiority estimates. No full-benchmark strict accuracy is claimed.

| Requirement | Single-shot positive/strict negative | NLTL positive/strict negative | NLTL NO_VERDICT | NLTL outcome |
|---|---|---|---:|---|
| I2-004 | 0/3; 0/3 | 0/3; 0/3 | 6/6 | REVIEWER_FORMAT_FAILURE, 2 candidates |
| I2-005 | 0/1; 0/4 | 0/1; 0/4 | 5/5 | REVIEWER_FORMAT_FAILURE, 2 candidates |
| IMO-001 | 2/2; 0/3 | 2/2; 0/3 | 0/5 | ACCEPTED, 1 candidates |
| TRF-010 | 6/6; 0/2 | 0/6; 0/2 | 8/8 | REVIEWER_FORMAT_FAILURE, 1 candidates |
| TRF-035 | 2/2; 2/4 | 0/2; 0/4 | 6/6 | REVIEWER_FORMAT_FAILURE, 3 candidates |

Full per-requirement missed/unrelated/unresolved/no-verdict counts and exact case IDs are in `evaluation/primary_workflow_results.json` and `evaluation/case_results.csv`. Repaired counterpart and original validation reports are retained for every candidate/case that parsed. Five originally conservative attributions were independently adjudicated using exact constraint semantics and pair reports in `evaluation/attribution_adjudications.json`; nested sh:node unit reports were recognized as wrappers, not unrelated failures.

## False acceptance and review interface

**IMO-001 was accepted on candidate 1 despite having no SHACL target.** Its property constraints are never invoked. All two positives and three negatives pass; all three intended defects are missed. Single-shot also produced an untargeted shape. The accepted reviewer JSON explicitly lists target/application uncertainty in `unchecked` yet says ACCEPT. The acceptance path therefore did not gate material applicability uncertainty or non-vacuous enforcement. Counterpart passes here are vacuous, not evidence of detection.

The other four NLTL requirements failed reviewer format/grounding validation after exactly one configured format retry. Seven raw responses used `exact_source_excerpt` / `exact_candidate_excerpt` instead of required `source_excerpt` / `candidate_excerpt`. The final TRF-035 retry used the required field names but failed `UNSUPPORTED_SCHEMA_EVIDENCE`. These were complete JSON objects, not parser syntax errors or reported truncation. No raw reviewer issue was accepted into repair feedback; no semantic repair was dispatched. Only IMO-001 review validated structurally. The frozen code was not patched or its response normalization relaxed during the run.

Some raw diagnoses correctly identified deletion of numeric/unit/max-selection obligations and TRF-010’s missing enumeration. However, several suggestions also proposed restoring the undeclared `qudt:value` predicate and exact-term `sh:hasValue "7"^^xsd:decimal`; exact-one cardinality assertions were not independently established. These suggestions are recorded as unsupported/uncertain corrections, not verified findings, and were never sent as repair feedback. See `finding_origin_and_review_audit.json`.

## Deterministic checks and actual edits

- I2-004 and I2-005 each received two canonical-identifier findings for the same undeclared `qudt:value` use (duplicate check perspectives, not two independent defects). I2-005 also received a nonblocking numeric-term-identity review notice. The actual generic feedback did not name the canonical replacement. Each targeted repair removed numeric/unit constraints; I2-004 also removed its maximum-selection query. Canonical errors disappeared through deletion, not a correct value-path substitution.
- TRF-035’s first syntax repair corrected the unmatched list delimiter and made candidate 2 parse. This is a useful software repair, but the candidate still used `qudt:value` and over-rejected positives/counterparts. Its next canonical repair removed numeric constraints and the classification-society restriction; candidate 3 executed but missed every reviewed negative. Source scope of the additional restriction remains uncertain. No candidate was accepted.
- No SPARQL legality/binding finding or unit-scale repair occurred in this batch. Execution-only probes did not and should not establish regulatory behavior. All exact parser/checker logs, latest-candidate/hash integrity packets, diffs and finding transitions are retained.

## Context gaps established from saved requests

The per-requirement generation/review context omitted the canonical quantity predicate `qudt:numericValue` from both selected schema terms and ontology evidence. `quantityEncoding` supplied a datatype but not the numeric-value predicate. The checker nevertheless rejected `qudt:value`, and feedback offered no evidenced replacement. This is a shared context/checker mismatch, not a reason to infer a handwritten solution.

TRF-010’s complete six-item source enumeration was present, but the named value individuals declared in the locked ontology were not included in rendered schema context (the locked registry has no rows for them). Both fresh shapes explicitly declined to invent IRIs and did not enforce the closed set. Reviewer cardinality concerns about maxCount=1 remain unresolved; no cardinality contract is invented here. TRF-035’s equality versus alternative property representation also remains an interpretation/scope issue in representation-only context; evaluation retains its previously approved oracle rather than relabeling cases.

## Initial versus selected final, and rejected diagnostics

Only IMO-001 has a selected final, and it is identical to the initial candidate: zero deduplicated recoveries and zero regressions on those five cases. The other 25 cases have no selected NLTL final, so code-recovery/regression comparison is unassessable. Do not interpret this as no source-level regression in repair.

Diagnostic last-candidate changes, **not workflow successes**:

| Requirement | Initial to last diagnostic positive acceptance | Last strict negatives | Counterparts passing | Important remaining loss |
|---|---:|---:|---:|---|
| I2-004 | 0/3 → 3/3 | 1/3 | 3/3 | Maximum selection and numeric/unit enforcement deleted |
| I2-005 | 0/1 → 1/1 | 1/4 | 4/4 | 7-degree numeric/unit enforcement deleted |
| TRF-010 | 6/6 → 6/6 | 1/2 | 2/2 | Closed enumeration absent |
| TRF-035 | No verdict → 2/2 | 0/4 | 4/4 | Equality and numeric-value enforcement absent |

The diagnostic I2 gains are six deduplicated case-level strict-success changes (three positives plus one negative for I2-004; one positive plus one negative for I2-005), with no previously strict-credit case loss in those pairs. They do not outweigh source-obligation deletion and earn no selected-workflow credit. TRF-035 initial syntax failure makes initial-to-last behavioral comparison unassessable.

## Budgets 2–6 from identical saved prefixes

Every budget selects only IMO-001 v1. All have positive acceptance 2/14, strict detection 0/16, missed negatives 3/16, negative no-verdict 13/16, total no-verdict 25/30. No candidate was chosen using evaluation scores.

| Budget | Calls in saved prefixes (including review/retries) | Input tokens | Output tokens | Provider seconds |
|---|---:|---:|---:|---:|
| 2 | 15 | 506,498 | 26,212 | 184.58 |
| 3 | 18 | 688,396 | 34,143 | 233.96 |
| 4 | 18 | 688,396 | 34,143 | 233.96 |
| 5 | 18 | 688,396 | 34,143 | 233.96 |
| 6 | 18 | 688,396 | 34,143 | 233.96 |

## Actual resources

**23 successful provider calls:** 10 initial generations, 4 code repairs (1 syntax, 3 targeted), 5 initial reviews and 4 auxiliary format retries. Saved candidates: 14 (5 Single-shot, 9 NLTL). **858,189 input + 40,210 output = 898,399 provider-reported tokens.** Provider request time 281.71 s; dispatch loop 288.53 s; independent validation 118.26 s. Large retained full-source context contributes to input usage. This total excludes the earlier blocked attempt; it is not silently pooled.

All candidate/raw response/request files, original diagnostics, finish reasons, per-call usage, stable transitions, full repair packets and diffs are under the requirement/workflow folders. Candidate-level results remain diagnostic where rejected. No implementation or historical score was changed.

## Recommendation

Fix the demonstrated general reviewer protocol/grounding interface, schema-context closure (quantity operands and relevant controlled values), and acceptance of untargeted/materially unresolved shapes before further live expansion. Then verify offline and use a newly authorized bounded diagnostic/pilot. Do not proceed to the 50-requirement study or select an optimal budget from these five development requirements. These source-grounded results must remain separate from test-guided versions.
