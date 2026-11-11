# Ownership / strict intended-failure reconciliation

A versioned revision of the latest semantic audit. Original shapes, benchmark, reports, labels and exclusions remain frozen. Current classifications are the complete records_after.json snapshot identified by authoritative_run.json/current_case_records; the older all_negatives/records cache is superseded, not silently overwritten. The canonical fixture version changes only owners explicitly assigned by the locked contract. Broad domains and fallback requiredOwner are not ownership evidence.

Confirmed fixture-side findings cover 29 unique cases. Axes overlap: {'intentional_ownership_mutation': 1, 'unintended_original_fixture_defect': 26, 'invalid_repaired_counterfactual': 28}. The old independently-valid repair claim is withdrawn for every invalid supplied counterfactual, before any new strict judgment.

## Strict results on common fully classified subsets

| Version | Workflow | Denominator | Strict | Unrelated/additional | Missed | No verdict |
|---|---|---:|---:|---:|---:|---:|
| before | NLTL_v2 | 611 | 332 | 195 | 54 | 30 |
| before | Single-shot | 611 | 320 | 164 | 38 | 89 |
| after | NLTL_v2 | 553 | 353 | 138 | 54 | 8 |
| after | Single-shot | 553 | 318 | 125 | 38 | 72 |

52 cases with underspecified ownership are unresolved for both workflows (original no-verdict remains NO_VERDICT). No owner mapping, cardinality or test label is strengthened to recover credit. The two previously noted lifeboat-removing counterfactuals also lose their intended-only validity claims.

## TRF-050-F05

Both workflows now receive STRICT_INTENDED_MATCH. The wrong frame-owned weld assertion infers an extra frameAttachmentRecord target. Every reported violation is either the real record missing its required weld, or a legitimate source-backed record obligation applied to that extra inferred record. Restoring only the weld owner removes the extra role and makes the full unchanged shape pass. This is a reviewed causal correspondence, not a general rule that all mutation-caused violations are intended. Cached reports are reused; no unchanged pair is rerun.

## Fixture and oracle review

The independent oracle has two separate gates: explicit canonical owner/type/unit checks on the actual graph, and the retained source-authored regulation logic through a documented inverse-placement view. That view round-trips the original authored graph exactly; it neither validates nor changes generated SHACL. Values, quantity nodes, labels and literal lexical forms are preserved. The original oracle alone is no longer advertised as certifying ownership.

All TRF-130 candidate repairs remain unresolved: the contract lists maximumContinuousRatingPower but neither supplies its value nor settles its relationship to the stored aggregate power. The old oracle misses this input. No MCR value, mandatory cardinality or equivalence to aggregate power is invented. Two structural chest counterfactuals also change an extra shared-input assertion after canonicalization. Their already executed repaired validations are diagnostic only, never strict credit. If canonicalizing a structural counterfactual changes more than the intended semantic field, the new candidate remains unresolved. Pair candidates, oracle outcomes, exact correction/repair deltas and both reports are saved.

## Ordinary verdict agreement, separate from strict credit

- NLTL_v2: 1634/2159 -> 1640/2159; requirement mean 76.6965% -> 76.9204%.
- Single-shot: 1429/2159 -> 1425/2159; requirement mean 68.8808% -> 68.7316%.

Only changed benchmark inputs were revalidated, including 12 positive fixtures. The full unchanged baseline was not rerun. New Figure 6 files include expected-class denominators. This is ordinary verdict agreement on the owner-projected fixture version, not certification that every source expectation is fully adjudicated; the TRF-130 declared-input scope and underspecified owner cases remain unresolved for strict scoring. Valid unresolved tests stay in the ordinary denominator; no exclusions are added.

## Artifacts

`fixture_finding_reconciliation.csv` separates intentional mutations, unintended original defects and invalid supplied repairs. `pair_reviews/` records withdrawal and candidate validity. `fixture_corrections.*` gives exact RDF changes and source/contract pointers. `records_before.json`, `records_after.json` and `classification_changes.csv` version the decisions; `validation/` saves only new changed-input executions. `strict_before_after.csv` and `common_subset_case_ids.json` expose matching denominators for both workflows. strict_fixed_intersection_before_after.csv additionally compares both versions on an identical case intersection, separating changed classifications from denominator changes. These are reviewed-subset strict results, not full-benchmark strict accuracy.
