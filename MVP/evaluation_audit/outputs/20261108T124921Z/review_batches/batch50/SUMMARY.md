# First 50 reviewed negative tests

Authoritative completed run: **20261108T124921Z**. The earlier completed run has identical baseline verdicts, ordinary metrics and original 14-case strict classifications; the intermediate run is incomplete. [Reconciliation](../../run_reconciliation.json).

**50 negatives across 19 requirements**, including the original 14: IACS 13, TRAFICOM 14, Polar Code 17, 2026 supplement 6. Each workflow uses the same source-backed fixture/repair specification.

| Workflow | Strict matches | Unrelated/additional | Missed | No verdict |
|---|---:|---:|---:|---:|
| NLTL_v2 | 32/50 | 13 | 5 | 0 |
| Single-shot | 31/50 | 2 | 3 | 14 |

All original 14 classifications are unchanged. The additional 36 contribute 24 strict matches per workflow. This expands the reviewed sample; it does not establish benchmark-wide strict accuracy. Single-shot’s 14 no-verdict cases remain uncredited.

Ordinary agreement remains separate: 45/50 and 33/50 correct rejections on this negative subset. The unchanged full corrected baseline retains requirement means of **76.6965% NLTL_v2 / 68.8808% Single-shot** across 268 requirements and 2,159 cases each. The full baseline was not rerun.

Concrete examples and likely causes:

- **Strict match:** IMO-010-F01, both workflows. Changing only rescue time from 4.99 to 5 days makes the independently valid counterfactual pass.
- **Unrelated failure / unit problem:** NLTL_v2 TRF-018-F01 demands the wrong `KiloW` namespace. Repairing only the 999 kW floor defect still rejects.
- **Repaired graph still rejected / generated defect:** Single-shot I2-004-G-F02’s inverted query rejects the valid restored 12 kt maximum.
- **Missed defect / generated defect:** NLTL_v2 IMO26-014-A-F01’s broken OR accepts one illumination means because daylight=false alone passes.
- **Context/schema mismatch:** NLTL_v2 IMO-049 requires component type on ship instead of linked components; literal typing adds failures.
- **Fixture/oracle defect:** historical original-fixture TRF-001 omitted universal provisions. Its correction is preserved; no new admitted fixture defect or exclusion was found.
- **No verdict:** Single-shot IMO26-009 has malformed retained Turtle. Offline errors are recorded without restoring workflow eligibility. No scored strict reason remains unresolved; deferred fixture expectations do.

Diagnostics remain separate: **42/50 NLTL_v2 / 31/50 Single-shot** after logged probes, with 10 and 6 cases actually transformed. Only IMO-049 owner/string constraints and TRF-018 unit constants are changed. Diagnostic results never alter main accuracy.

Remaining blockers: two IMO26-007 count-consistency cases; four IMO26-010/011 cases missing parent ice-strengthening applicability; TRF-017-F03 and TRF-018-F04 need missing-result counterfactual review. These eight stay NOT_AUDITED, with no new exclusions. In total **1,154 retained negatives remain unaudited**. [Case-specific blockers](review_blockers.csv).

Checks: 300 exact RDF fixture deltas; unchanged main shape bytes; all 86 eligible reviewed negative verdicts agree with the saved baseline; identical exclusions. [Test results](test_results.json) record 25 audit checks and 14 retrieval checks passing. No LLM/API calls or shape generations.

[Full report](REPORT.md) · [Cause ledger](strict_mismatch_causes.csv) · [Updated case ledger](full_case_ledger.csv) · [Diagnostics](diagnostic_results.csv)
