# All retained negative tests: intended-failure audit

Authoritative baseline: `20261108T124921Z`. The original 50 specifications and results are unchanged. No new generation/API calls, baseline rerun, fixture corrections or exclusions.

All **1,154 additional cases** have terminal records. Across the 1,205 retained negatives: **474 fully classified**, **730 blocked**, **1 excluded**. 268 distinct requirements were examined; fully classified cases cover 158 requirements.

There are **675 source/schema-verified pairs** across 186 requirements. 201 of these still have an unresolved violation-semantics or execution blocker. The remaining 529 blocked cases lack a verified source/repair pair.

## Unchanged generated shapes

Common denominator: **675 source-verified negative cases per workflow**, including original no-verdicts and unresolved semantic reviews. Unresolved receives no strict credit. These are reviewed-subset results, not full-benchmark strict accuracy.

| Workflow | Strict match | Unrelated/additional failure | Missed defect | No verdict | Unresolved |
|---|---:|---:|---:|---:|---:|
| NLTL_v2 | 211 (31.3%) | 197 (29.2%) | 55 (8.1%) | 31 (4.6%) | 181 (26.8%) |
| Single-shot | 214 (31.7%) | 165 (24.4%) | 39 (5.8%) | 92 (13.6%) | 165 (24.4%) |

The fully classified common subset contains 474 cases for both workflows. Its separate counts and denominators are in `strict_summary.csv`; cases with a semantic blocker in either workflow remain visible above, including the other workflow’s completed result.

## Ordinary Figure 6

Unchanged: no new fixture input was established that warrants a correction. After the existing identical TRF-002-F02 exclusion, each workflow retains **2,159 cases / 268 requirements**, including **955 expected PASS / 1,204 expected FAIL**. NLTL_v2 ordinary agreement is **1,634/2,159** (requirement mean **76.6965%**); Single-shot is **1,429/2,159** (requirement mean **68.8808%**). Ordinary results include all valid blocked tests. Original/corrected Figure 6 files are copied unchanged, with expected-class denominators.

## Causes and examples

- **Intended match:** NLTL_v2 I2-048-H-F003 lacks case-owned asBuiltPlateThickness. Adding only the source-builder thickness selector (17.5 mm) gives an independently valid fixture and full-shape PASS; the missing-field violation matches.
- **Owner mismatch:** NLTL_v2 I2-023-F04 repairs only the misplaced selectedHullAreaFactor. The valid repair still fails because the shape requires yieldStrength on ship; the canonical fixture carries it on the structural member.
- **Unit/runtime problem:** Single-shot TRF-080-F01 repairs only the incorrect multiplied cycle count. The valid counterfactual still rejects because the shape expects http://qudt.org/schema/qudt/UNITLESS while the contract uses http://qudt.org/vocab/unit/UNITLESS.
- **Generated defect:** the preserved Single-shot I2-004-G-F02 audit shows an inverted displacement query rejecting the valid restored 12 kt maximum; NLTL_v2 IMO26-014-A-F01 accepts insufficient illumination through its daylight=false OR branch.
- **Fixture/oracle defect:** the historical TRF-001 universal-provision omission remains corrected in the versioned benchmark. No new ambiguous source/schema discrepancy was silently repaired or excluded. IMO-097 rescue-boat versus ontology lifeboat range remains blocked.
- **Unresolved meaning:** NLTL_v2 I2-004-G-F01 rejects the negative and accepts its repair, but the query’s maximum-displacement/tolerance semantics lack a new admissible-semantics review. Verdict change alone receives no strict credit.
- **No verdict:** Single-shot IMO26-009 retains its historical malformed-Turtle no-verdict outcome; offline diagnostics never restore eligibility.

- NLTL_v2: UNRESOLVED: 298 mismatch/unresolved records across 106 requirements; examples: I2-004, I2-011, I2-034, I2-042, I2-046, I2-055, I2-060, I2-066. Full requirement lists are in `fault_causes_by_requirement.csv`.
- Single-shot: GENERATED_SHAPE_DEFECT: 41 mismatch/unresolved records across 25 requirements; examples: I2-004, I2-006, I2-062, IMO-005, IMO-011, IMO-017, IMO-027, IMO-066. Full requirement lists are in `fault_causes_by_requirement.csv`.
- NLTL_v2: CONTEXT_SCHEMA_MISMATCH: 58 mismatch/unresolved records across 11 requirements; examples: I2-006, I2-008, I2-022, I2-023, I2-040, IMO-035, IMO-049, TRF-014. Full requirement lists are in `fault_causes_by_requirement.csv`.
- Single-shot: CONTEXT_SCHEMA_MISMATCH: 55 mismatch/unresolved records across 12 requirements; examples: I2-008, I2-023, I2-024, I2-031, I2-040, I2-052, I2-064, IMO-016. Full requirement lists are in `fault_causes_by_requirement.csv`.
- Single-shot: UNRESOLVED: 260 mismatch/unresolved records across 90 requirements; examples: I2-011, I2-022, I2-042, I2-048, I2-066, IMO-004, IMO-007, IMO-009. Full requirement lists are in `fault_causes_by_requirement.csv`.
- NLTL_v2: RUNTIME_LITERAL_UNIT_PROBLEM: 22 mismatch/unresolved records across 6 requirements; examples: I2-021, I2-024, IMO-117, TRF-018, TRF-055, TRF-080. Full requirement lists are in `fault_causes_by_requirement.csv`.
- NLTL_v2: GENERATED_SHAPE_DEFECT: 55 mismatch/unresolved records across 30 requirements; examples: I2-048, I2-062, IMO-003, IMO-004, IMO-005, IMO-027, IMO-048, IMO-055. Full requirement lists are in `fault_causes_by_requirement.csv`.
- Single-shot: RUNTIME_LITERAL_UNIT_PROBLEM: 13 mismatch/unresolved records across 3 requirements; examples: I2-055, TRF-035, TRF-080. Full requirement lists are in `fault_causes_by_requirement.csv`.
- STRICT_INTENDED_MATCH: `I2-001-F01` / NLTL_v2; full evidence in `records/I2-001-F01.json`.
- UNRESOLVED_REASON: `I2-004-G-F01` / NLTL_v2; full evidence in `records/I2-004-G-F01.json`.
- MISSED_INTENDED_DEFECT: `I2-004-G-F01` / Single-shot; full evidence in `records/I2-004-G-F01.json`.
- MISMATCH_UNRELATED_OR_ADDITIONAL_FAILURE: `I2-004-G-F02` / Single-shot; full evidence in `records/I2-004-G-F02.json`.
- NO_VERDICT: `I2-009-F02` / NLTL_v2; full evidence in `records/I2-009-F02.json`.

The previous 50-case counts (NLTL_v2: 32 strict / 13 unrelated / 5 missed; Single-shot: 31 strict / 2 unrelated / 3 missed / 14 no verdict) are preserved. Exact additions by status are in `previous50_comparison.csv`.

## Remaining blockers

- VIOLATION_SEMANTICS_UNESTABLISHED: 346 blocker entries. Entries can overlap within a case.
- INTENDED_ONLY_REPAIR_NOT_ESTABLISHED: 308 blocker entries. Entries can overlap within a case.
- SOURCE_EXPECTATION_RECONCILIATION_REQUIRED: 202 blocker entries. Entries can overlap within a case.
- PARENT_PROFILE_SCOPE_UNESTABLISHED: 5 blocker entries. Entries can overlap within a case.
- OMITTED_SOURCE_ACCEPTANCE_CRITERIA: 7 blocker entries. Entries can overlap within a case.
- REPAIRED_SCHEMA_RECHECK_FAILED: 3 blocker entries. Entries can overlap within a case.
- PREVIOUS_CASE_SPECIFIC_BLOCKER: 8 blocker entries. Entries can overlap within a case.
- PARENT_APPLICABILITY_UNESTABLISHED: 7 blocker entries. Entries can overlap within a case.

Every blocked case has its own source clause, intended rationale, evidence path and failed gate in `records/` and `unresolved_blockers.csv`. Examples include omitted parent applicability (IMO26-010/011), omitted source acceptance criteria (I2-065), unresolved welded-profile scope (I2-043), source equation/table reconciliation, multi-field/default replay discrepancies and logical/SPARQL semantics not yet established. Missing authority or applicability assertions are not invented.

## Artifacts and resume

`full_case_ledger.csv` covers all 4,320 workflow/case rows. `reviewed_failure_specs_additional.json` contains independently verified pairs and exact RDF deltas; prior50 are referenced separately. `cases/` saves each pair, unchanged shape bytes and reports. Historical no-verdict cases have no new offline validation/credit. `diagnostic_results.json` references the preserved diagnostic arm, with no new transformations.

```bash
.venv/bin/python evaluation_audit/audit_all.py --phase report
.venv/bin/python evaluation_audit/audit_all.py --phase all --workers 6
# Only after adding concrete source/repair evidence for blocked cases:
.venv/bin/python evaluation_audit/audit_all.py --phase all --retry-blocked --workers 6
.venv/bin/python -m unittest discover -s evaluation_audit -v
```

Each finished case is checkpointed atomically. Repaired validations are cached by graph, shape and environment hashes; unchanged negative reports are reused from the authoritative baseline. Report generation refuses pending cases and checks preserved input hashes. Retrying blockers archives the previous record.
