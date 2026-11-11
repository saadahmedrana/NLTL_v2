# All-case assessment of the reviewed-requirement universe

**The full requested reduced benchmark is not ready to freeze.** The authoritative 553-case snapshot has **157 distinct requirements**, not the 158 claimed in earlier prose. The machine-readable reconciliation already records 157. That snapshot is preserved byte for byte. No extra requirement is selected to repair the count.

The actual universe contains **1,290 retained cases: 606 positives and 684 negatives**. Of the negatives, 553 belong to the classified snapshot and 131 do not: 26 have prior verified pairs with pending violation semantics/execution, while 105 have source/repair blockers. A pending generated-shape reason does not invalidate a fixture.

All twelve TRF-130 cases (two positives, ten negatives) are additionally inventoried as a **separate historical supplement**, because that requirement dropped out when counterfactual validity was withdrawn. They are not silently restored to the current snapshot. Including that named supplement would give 158 requirements / 1,302 cases, but it remains unresolved and is not proposed for retention.

## Verification, screening and scope

Every case was inventoried and checked against its retained independent authoring oracle; all labels agree. That is a consistency screen, not a certificate: those oracles share authoring assumptions and can miss omitted applicability, source exceptions or contract inputs. A fresh source-only review was therefore kept separate from the screen and from all workflow verdicts.

**163 positives and 47 negative gold expectations are certified in the reviewed represented models; 46 negatives have an independently valid intended-only repair.** The remaining 443 positives and 637 negative gold expectations are not certified to this assessment’s freeze standard. These figures do not overwrite the earlier 553 classifications. Source validity, repair readiness and historical strict classification have separate columns.

There are 209 source/schema/pair-ready cases: the proposed 37-case core, plus 172 verified cases deferred because their requirement coverage is incomplete. Of 1,081 cases lacking the complete case certificate, 1,044 are not yet audited to the freeze standard, 36 have explicit source/schema/applicability unresolved issues, and one has verified gold FAIL but no accepted repair. “Not audited” is not a declaration that the fixture is invalid.

Verification is of the represented source/contract model, not real-vessel regulatory approval. Table-8 NA/PASS denotes faithful lookup encoding; it does not approve use of a not-applicable plating combination. The unrepresented single-strake exception remains a stated coverage limitation. Complex engineering evidence/readiness cannot become independently calculated compliance merely because an oracle accepts it.

Ownership checks use explicit termOwners and approved model paths. RDFS domains remain typing assertions, and fallback requiredOwner is never authoritative. Unused legacy indexed concepts are listed separately, rather than inventing owners or turning vocabulary scope into a mandatory input. For example, I2-004’s current case-displacement model does not operate on the unused upperIceWaterline legacy property; I2-042 uses explicitly bound netWebThickness, not the unused generic thickness property. Their missing legacy owners remain recorded outside the represented model.

## Proposed retained core

This is a **proposal only**, not an activated benchmark. Each requirement was selected through source, explicit binding, intended-only repair and finite core branch/obligation checks. Every retained positive and negative case from each selected requirement is included; no valid test is removed because generated SHACL fails it. This is a conservative reviewed mini-core, not a maximal or representative subset.

| Requirement | Verified positives | Verified negatives with repair | Represented core coverage |
|---|---:|---:|---|
| I2-004 | 3 | 3 | Selected UIWL displacement equals max of represented waterline-case displacements. |
| I2-005 | 1 | 4 | A represented bottom/lower-region boundary point has shell inclination exactly 7 degrees. |
| I2-042 | 3 | 4 | For every represented structural member, flangeWidth >= 5 * netWebThickness (minimum, not maximum). |
| IMO-001 | 2 | 3 | designIceCondition=mediumFirstYearIceWithPossibleOldIceInclusions implies shipCategory=A; missing selector is a locked representation-readiness violation. |
| TRF-010 | 6 | 2 | Assigned ice class is one of IA Super, IA, IB, IC, II, III. |
| TRF-035 | 2 | 4 | ruleLength equals classificationSocietyRuleLength, both canonical metre quantities. |

**Total: six requirements, 37 cases (17 positive / 20 negative).** Exact IDs, labels, fixture hashes and counterfactual paths are in proposed_selection.json, proposed_retained_cases.csv and PROPOSED_frozen_case_manifest.json. Both workflows receive exactly the same IDs. No new exclusions are proposed. All other cases remain either deferred or unresolved in the complete ledger.

A finite core matrix establishes coverage of stated represented branches; it is not exhaustive mutation or robustness coverage. The branch specifications disclose missing ties, multiple values, mixed-member inventories, malformed quantity subfields and other untested combinations. No extra uniqueness, cardinality, ownership or engineering obligation was invented to fill those gaps.

## Coverage that remains insufficient

- **I2-048:** all 126 source table cells have positive witnesses and all seven Polar Classes are represented. Positive cell coverage does not establish negative coverage of each table branch. F006 is a valid duplicate-material negative under explicit maxCount=1 but has no existing reviewed intended-only repair. Footnote-2 is not modeled. All 152 cases remain inventoried; 137 positives and 15 gold negatives are certified within the generic model, with only 14 negative repairs ready. The requirement is deferred as a whole.
- **TRF-001:** the corrected universal provisions are present consistently. There is no negative isolating omission of either required universal provision, so a shape could ignore them and still pass those tests. Three positives and two negatives are valid but requirement coverage is partial.
- **TRF-036:** four table-row positives and five repaired negatives are verified on canonical ship-owned iceClass. F05 (class II, absent from Table 4-1) has no source-established failure expectation or valid supplied repair. Wrong-parameter controls are missing for IA Super and IC. It is unresolved, not excluded or relabeled to match code.
- **TRF-050:** both crossing/no-crossing positive branches and five negative repairs are verified. F05 remains an intentional wrong-owner mutation; its RDFS-induced targets are not called unrelated fixture errors. A wrong-weld negative inside the crossing exception and a missing-crossing-selector negative are absent. This requirement is deferred for branch coverage.
- **TRF-058:** all six fixtures lack an explicit supportedStringerOutsideIceBelt selector, and the contract supplies no approved derivation or absence-means-false policy. Oracle acceptance is insufficient; applicability remains unresolved. No flag is added and no shape is blamed for demanding one.
- **TRF-017:** full source includes additional propulsion power, but the normalized contract/allowed vocabulary omits that operand and its requirement-specific owner is not bound.
- **TRF-030 / I2-024:** population/paired-case readiness and declared-input scope require further source/contract reconciliation, respectively.
- **Other 146 requirements:** no complete source/schema branch certificate was established here. Their cases are explicitly NOT_AUDITED_TO_FREEZE_STANDARD or carry identified binding/source blockers. Previously accepted negative pairs are not promoted into reviewed positives.

The full ambiguity_and_review_blockers.json distinguishes source expectation, fixture/applicability, schema binding, repair and review-not-completed reasons for every affected case. No requirement without a reviewed matrix is claimed branch-complete.

## Per-requirement counts

“Verified N” is gold expectation; “N+repair” also has source/schema-certified intended-only repair. “Old 553 N” is historical strict-snapshot membership, not certification of this requirement’s positives. Counts are within the stated representation scope.

| Requirement | P total | N total | Verified P | Verified N | N+repair | Old 553 N | Coverage / proposal |
|---|---:|---:|---:|---:|---:|---:|---|
| I2-001 | 3 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-004 | 3 | 3 | 3 | 3 | 3 | 3 | RETAIN_CORE |
| I2-005 | 1 | 4 | 1 | 4 | 4 | 4 | RETAIN_CORE |
| I2-006 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-009 | 4 | 7 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-013 | 1 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-019 | 2 | 4 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-021 | 2 | 4 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-024 | 4 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-034 | 3 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-041 | 3 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-042 | 3 | 4 | 3 | 4 | 4 | 4 | RETAIN_CORE |
| I2-046 | 4 | 6 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-047 | 3 | 5 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-048 | 137 | 15 | 137 | 15 | 14 | 14 | PARTIAL_TABLE_COVERAGE_AND_PENDING_REPAIR |
| I2-055 | 2 | 7 | 0 | 0 | 0 | 6 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-060 | 2 | 4 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-062 | 3 | 3 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-066 | 3 | 4 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| I2-067 | 3 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-001 | 2 | 3 | 2 | 3 | 3 | 3 | RETAIN_CORE |
| IMO-003 | 3 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-004 | 4 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-005 | 2 | 3 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-006 | 4 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-007 | 3 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-008 | 4 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-010 | 2 | 2 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-011 | 3 | 7 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-012 | 2 | 4 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-013 | 4 | 3 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-014 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-017 | 1 | 6 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-018 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-021 | 1 | 7 | 0 | 0 | 0 | 7 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-022 | 1 | 4 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-023 | 1 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-026 | 2 | 2 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-027 | 1 | 6 | 0 | 0 | 0 | 6 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-028 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-030 | 2 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-031 | 2 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-032 | 4 | 5 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-034 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-038 | 4 | 8 | 0 | 0 | 0 | 8 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-041 | 3 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-048 | 2 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-050 | 2 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-055 | 5 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-057 | 6 | 6 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-060 | 4 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-064 | 2 | 6 | 0 | 0 | 0 | 6 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-065 | 3 | 9 | 0 | 0 | 0 | 9 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-066 | 2 | 8 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-068 | 4 | 4 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-069 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-071 | 2 | 4 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-074 | 4 | 2 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-077 | 3 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-078 | 3 | 5 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-079 | 3 | 5 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-082 | 2 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-083 | 3 | 4 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-084 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-085 | 4 | 4 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-086 | 2 | 5 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-087 | 3 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-088 | 4 | 4 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-089 | 2 | 6 | 0 | 0 | 0 | 6 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-095 | 2 | 4 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-096 | 1 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-098 | 3 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-099 | 2 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-100 | 3 | 4 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-101 | 1 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-103 | 5 | 6 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-105 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-106 | 3 | 4 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-107 | 2 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-108 | 6 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-109 | 5 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-110 | 5 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-111 | 6 | 2 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-112 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-113 | 2 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-114 | 6 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-115 | 2 | 5 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-116 | 2 | 5 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-117 | 2 | 7 | 0 | 0 | 0 | 6 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-119 | 6 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-120 | 4 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-121 | 3 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-122 | 1 | 5 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-123 | 2 | 10 | 0 | 0 | 0 | 9 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-124 | 4 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO-125 | 2 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO26-002 | 10 | 6 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO26-005 | 3 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO26-009 | 4 | 4 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO26-012 | 3 | 6 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO26-013 | 3 | 4 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO26-014 | 3 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO26-015 | 2 | 3 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO26-016 | 10 | 5 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO26-017 | 4 | 4 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| IMO26-018 | 3 | 6 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-001 | 3 | 2 | 3 | 2 | 2 | 2 | PARTIAL_BRANCH_COVERAGE |
| TRF-003 | 4 | 3 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-010 | 6 | 2 | 6 | 2 | 2 | 2 | RETAIN_CORE |
| TRF-012 | 1 | 7 | 0 | 0 | 0 | 7 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-013 | 4 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-014 | 5 | 5 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-015 | 3 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-016 | 4 | 6 | 0 | 0 | 0 | 6 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-017 | 4 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-018 | 6 | 5 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-023 | 4 | 4 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-024 | 5 | 3 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-028 | 2 | 6 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-029 | 2 | 5 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-030 | 1 | 12 | 0 | 0 | 0 | 12 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-032 | 4 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-034 | 1 | 7 | 0 | 0 | 0 | 7 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-035 | 2 | 4 | 2 | 4 | 4 | 4 | RETAIN_CORE |
| TRF-036 | 4 | 6 | 4 | 5 | 5 | 5 | PARTIAL_TABLE_BRANCH_CONTROLS_AND_AMBIGUOUS_CASE |
| TRF-040 | 4 | 4 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-045 | 4 | 4 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-049 | 7 | 5 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-050 | 2 | 5 | 2 | 5 | 5 | 5 | PARTIAL_BRANCH_COVERAGE |
| TRF-052 | 7 | 5 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-055 | 4 | 5 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-056 | 3 | 5 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-058 | 2 | 4 | 0 | 0 | 0 | 4 | UNRESOLVED_APPLICABILITY_BINDING |
| TRF-062 | 2 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-063 | 2 | 6 | 0 | 0 | 0 | 6 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-064 | 3 | 6 | 0 | 0 | 0 | 5 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-066 | 3 | 4 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-067 | 3 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-074 | 4 | 3 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-075 | 3 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-076 | 3 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-077 | 3 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-080 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-082 | 2 | 2 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-083 | 2 | 2 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-085 | 2 | 2 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-087 | 2 | 2 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-088 | 2 | 2 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-103 | 2 | 2 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-108 | 2 | 2 | 0 | 0 | 0 | 1 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-112 | 1 | 3 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-116 | 2 | 2 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-126 | 4 | 4 | 0 | 0 | 0 | 4 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-128 | 4 | 5 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-129 | 2 | 3 | 0 | 0 | 0 | 3 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-131 | 2 | 2 | 0 | 0 | 0 | 2 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-133 | 2 | 13 | 0 | 0 | 0 | 13 | NOT_AUDITED_BRANCH_COVERAGE |
| TRF-130 | 2 | 10 | 0 | 0 | 0 | 0 | SEPARATE_SUPPLEMENT_NOT_RETAINED |

The 158th table row is the explicitly separated TRF-130 supplement. The main totals remain 157 requirements and 1,290 cases. per_requirement_review.csv/json also provide source clauses, every case ID, active and unused unresolved bindings, historical blocker categories and coverage notes.

## Separate runner verification

The selected FULL_REPAIR_V2 RUN_01 configuration and **every code, prompt and locked-input hash** still match the completed request audit. Reusing that version-matched evidence avoids rerunning unchanged tests. It demonstrates **8 semantic repairs, 2 static repairs, 3 matcher-assisted repairs and 2 syntax repairs**, plus a separately labeled fresh-regeneration escape hatch. Four canonical-finding requests retain the finding in actual code-repair payloads. The route is therefore not syntax-only. This is the PipelineRunner / generate-batch entry point; the no-semantic-validator command would choose a different, syntax-only runner even if given a similarly named config. Complete request paths and current hash checks are in runner_route_verification.json.

This verifies routing, not semantic detector quality or successful automated repair. The recommended canonical unit/term-kind checker is not installed by that audit. The configured live RUN_01 output already contains 268 runs; it is not a fresh measured-experiment destination. No API calls or generation were made here.

## Freeze decision and limitations

Do not freeze or publish the whole 157-requirement universe as fully reviewed. The proposed six-requirement core is defensible as a small frozen **represented-model regression benchmark**, with its disclosed limits and pinned artifacts. It is not representative of the original 268-requirement cohort, and the historically chosen review-complete universe may itself carry reviewability bias. Selecting the current proposal did not use workflow accuracy, shape failures or generation eligibility.

These cases have already been inspected during development. Freezing them prevents future drift, but does not make them pristine held-out evidence for an unbiased new experiment. Keep any future unseen evaluation separate. No ordinary verdict counts or strict results were recomputed, and the original 553-case snapshot and exclusions are unchanged.

Verification: 16 read-only and synthetic source-law checks passed, including performance-blind selection, complete case inventory, unchanged input hashes, source-table transcription, same workflow exclusions, unknown-selector handling and canonical/semantic repair routing. No SHACL baseline was replayed.
