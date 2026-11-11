# Reviewed negative audit: first 50

Authoritative completed run: `20261108T124921Z`. The earlier `20261108T113918056821Z` has identical baseline verdicts, ordinary metrics and 14-case strict classifications; `20261108T124705Z` is incomplete. See `run_reconciliation.json` in the authoritative run.

Reviewed **50 negative cases across 19 requirements**, including the original 14. Distribution: IACS 13, TRAFICOM 14, Polar Code 17, 2026 supplement 6. Both workflows use the identical case specifications. All 36 additions have exactly the intended independent-oracle defect and no defects after the exact repair. Scope is each frozen requirement/representation, not full-vessel regulatory compliance.

| Workflow | Strict matches | Unrelated/additional | Missed | No verdict | Unresolved |
|---|---:|---:|---:|---:|---:|
| NLTL_v2 | 32/50 (64%) | 13 | 5 | 0 | 0 |
| Single-shot | 31/50 (62%) | 2 | 3 | 14 | 0 |

Single-shot has 36 originally eligible cases; 14 remain NO_VERDICT. Candidate execution never restores eligibility. The 50-case denominator includes those no-verdict cases. This purposive batch cannot estimate benchmark-wide strict accuracy.

Changes from the 14-case audit: all original classifications remain unchanged.
- NLTL_v2: 8/14 becomes 32/50; added 36 contribute 24 matches, 7 unrelated/additional failures, 5 misses, and 0 no verdicts. This is a change of review scope, not an improvement to the workflow.
- Single-shot: 7/14 becomes 31/50; added 36 contribute 24 matches, 2 unrelated/additional failures, 2 misses, and 8 no verdicts. This is a change of review scope, not an improvement to the workflow.

Ordinary verdict agreement is unchanged and separate, reusing the completed corrected-fixture baseline:
- NLTL_v2: 1634/2159 ordinary agreement; requirement mean 76.6965% over 268 requirements.
- Single-shot: 1429/2159 ordinary agreement; requirement mean 68.8808% over 268 requirements.
- On the reviewed negative subset alone, NLTL_v2 has 45/50 ordinary correct rejections, distinct from strict credit above.
- On the reviewed negative subset alone, Single-shot has 33/50 ordinary correct rejections, distinct from strict credit above.

The only exclusion remains TRF-002-F02, identically for both workflows; no new fixture corrections or exclusions were made. All other valid failures remain in the ordinary denominator.

Concrete failure examples:
- Strict match: IMO-010-F01, both workflows. Rescue time 4.99 days violates the 5-day source minimum; changing only that value to 5 passes the independent oracle and the unchanged full shape.
- Unrelated/additional failure: NLTL_v2 TRF-018-F01. The intended 999 kW class-floor defect is accompanied by generated constraints demanding the wrong unit IRI. Repairing only MCR to 1000 still fails.
- Repaired fixture still fails: Single-shot I2-004-G-F02. Restoring the source-derived maximum 12 kt produces a valid fixture that the inverted SELECT query rejects.
- Missed defect: NLTL_v2 IMO26-014-A-F01. Daylight=false alone satisfies a broken OR, even with only one required illumination means.
- No verdict: Single-shot IMO26-009-A-F01. The retained candidate has malformed Turtle; its original ineligibility is preserved. The diagnostic parse error is recorded, not converted to a FAIL verdict.

Likely causes (each strict mismatch has a row in `strict_mismatch_causes.csv`):
- Context/schema mismatch: NLTL_v2 IMO-049 uses machineryComponentType on ship rather than linked components; I2-006 imposes an incompatible exact basis string. Plain/typed string problems are secondary causes.
- Generated shape defect: the inverted I2-004 query, missing additional-power term / UNION-scope issue in TRF-017, and broken daylight OR.
- Runtime/literal/unit problem: TRF-018 uses schema/qudt/KiloW instead of vocab/unit/KiloW.
- Fixture/oracle defect: no confirmed new defect among the 36 admitted fixtures. The historical original-fixture TRF-001 arm supplies the concrete example: omitted universal provisions. Deferred 2026 applicability/count fixtures are blockers, not credited shape failures or new exclusions.
- Unresolved: no unresolved scored strict reason in this batch. Original no-verdict output quality remains unscored; deferred fixture expectations require review.

Diagnostics stay separate:
- NLTL_v2: 42/50 after diagnostic probes; 10 cases have actual shape transformations. Original no-verdict cases remain no verdict. These counts do not alter main accuracy.
- Single-shot: 31/50 after diagnostic probes; 6 cases have actual shape transformations. Original no-verdict cases remain no verdict. These counts do not alter main accuracy.

The new TRF-018 probe changes only the two wrong power-unit constants. The retained IMO-049 probe changes owner paths and literal typing. No other regulatory logic or cardinalities are changed. Zero-transformation candidate runs and parse/runtime failures are explicitly recorded in `diagnostic_results.csv`. Applicable-branch cause probes are explanatory only.

Remaining blockers:
- IMO26-007-A-F01: Echo-sounder count fields describe one independent echo-sounding device while echoSoundingDeviceCount is zero. Cross-count consistency is not enforced by the frozen branch oracle; review before defining a one-defect repair.
- IMO26-007-A-F03: Missing date is accompanied by independentEchoSoundingDeviceCount=2 and echoSoundingDeviceCount=0; source/representation count consistency needs adjudication.
- IMO26-010-A-F01: Full source 9-1.3.2.1.4 applies additionally to ice-strengthened ships. This applicability assertion is absent in the fixture and frozen single-clause text.
- IMO26-010-A-F02: Missing projection selector plus omitted parent ice-strengthening applicability; cannot certify a clean single-defect case without review.
- IMO26-011-A-F03: Missing category selector plus omitted parent ice-strengthening applicability from 9-1.3.2.1.4.
- IMO26-011-A-F04: Missing date selector plus omitted parent ice-strengthening applicability from 9-1.3.2.1.4.
- TRF-017-F03: A source-independent actual restricted-output value is not recorded. A counterfactual equal to stored total could satisfy the comparison, but would require an explicit missing-result policy; deferred in favor of directly calculable F01/F02.
- TRF-018-F04: The missing externally calculated power result cannot be independently reconstructed from this sparse fixture. Deferred pending formula/input or counterfactual readiness-policy review; the class-floor and supplied-comparator tests are reviewed instead.
- In total, 1154 retained negatives remain NOT_AUDITED, including the deferred candidates above. The original 26 membership exclusions still lack case-specific adjudication records.

Verification: unchanged baseline hash and source inputs; 86 eligible reviewed negative verdicts agree with the saved corrected baseline; every saved negative/repaired pair has exactly the declared RDF delta; main shapes are unchanged; same exclusions across workflows. No LLM/API calls and no full-baseline rerun.
