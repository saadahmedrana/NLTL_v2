# Saved-evidence semantics continuation

Resolved **137 of 201 case blockers** (261 workflow blockers). **64** cases remain semantically unresolved. The **529** source/repair blockers and prior single exclusion are untouched.

Common fully classified subset: **611 negatives across 171 requirements** for both workflows. Historical no-verdicts remain uncredited. These are subset results, not full-benchmark strict accuracy.

| Workflow | Strict match | Unrelated/additional | Missed | No verdict |
|---|---:|---:|---:|---:|
| NLTL_v2 | 332 (54.3%) | 195 (31.9%) | 54 (8.8%) | 30 (4.9%) |
| Single-shot | 320 (52.4%) | 164 (26.8%) | 38 (6.2%) | 89 (14.6%) |

No SHACL validation or SPARQL query execution was run. Existing completed records, both fixture files, shapes, validation reports, full ordinary metrics and historical reports are hash-checked and unchanged. Only formerly unresolved workflow statuses are updated. Source guards choose branches before counterfactual acceptance is checked. Unsupported/inference-dependent constructs, unbound alternatives, complex tables and applicability-repair concerns remain unresolved.

Examples: both I2-042 queries explicitly test flangeWidth < 5*netWebThickness; conditional IMO-018/030 branches fail only on the intended obligation under fixed selectors; the local I2-048 PC3/17.5-mm/material-One/normal-strength Table-8 cell was traced to D and the exact missing/wrong-grade/rank/family disjunct. TRF-050-F05 receives unrelated/additional-failure classification in both workflows because shellPlateButtCrossing is wrongly required on the frame even though it is already supplied on the attachment record. One confirmed unrelated report is enough to deny strict credit; other unresolved leaves remain visible.

The unresolved inventory is `remaining_semantic_cases.csv`. In particular, IMO-072-F01 and IMO-073-F02 supplied counterfactuals remove the lifeboat instead of providing its missing assertion. Applicability-changing counterfactuals and complex unbound branch/query combinations also remain unresolved. These concerns are preserved in the 201-case semantic-review arm; none is silently added to or removed from the separate 529 source/repair blockers.

Every one of the 201 cases has an evidence record in `cases/`, including the complete inspected SELECT or branch/leaf trace where resolved. `before/` preserves each changed parent record; `updates.json` contains the delta. The frozen inspected implementation and exact SELECT bindings are saved here. No message text or historic blank-node ID is a matching criterion.
