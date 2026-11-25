# v0.7.0 I2-004 bounded operational check

The authorized one-requirement NLTL run stopped after **one fresh candidate** with **UNRESOLVED_CONTEXT**. No candidate was internally accepted. No repair, reviewer, format retry, capability probe, Single-shot or further requirement/study call was made. This was an early material-context stop, not exhaustion of the two-candidate cap. Frozen v0.7.0 was not changed or rerun.

## Preflight and request integrity

Installed/source v0.7.0 modules matched byte-for-byte. Base Git revision was `495f8c69e7213fac6d83cf28613cf9821b5794c3`; v0.7.0 remains a modified/untracked working-tree refinement, not a clean committed tag. Exact Git state and binary working/index diff, complete code/prompts/configs, projected source-only data, full required source document, schema inputs, rendered context and hashes were saved before dispatch. The source-only snapshot produced exactly the same context as active v0.7.0. Examples: none.

The base config stayed unchanged. Recorded runtime overlay enabled only the authorized live run and cleared proposal-only metadata; limits remained two candidates, initial generation once, at most one code repair, and one format retry per reviewer response. Structured output remained disabled and no capability probe occurred. The established external environment path/endpoint metadata are recorded without secret values in preflight.json; credentials were not copied.

GenerationProject and a runtime filesystem audit denied reads of evaluation, test witnesses, solution profiles, provenance and historical outputs before provider dispatch. Denied-read tests returned no contents. The runtime snapshot contains no evaluation/gold/seed inputs. Every dispatch verifies frozen/installed code and snapshot hashes. The pre-dispatch software integrity dry run accepted a full latest candidate and rejected a truncated candidate. There were **zero actual repair requests**, so live latest-code repair handling was not exercised. Raw model responses were retained independently; they never replace previous_candidate in a repair packet.

## 1. Quantity context and canonical correction

The supplied context explicitly declared numeric predicate `http://qudt.org/schema/qudt/numericValue`, unit predicate `http://qudt.org/schema/qudt/unit`, decimal datatype and kt unit metadata. Candidate 1 used `qudt:numericValue`, `xsd:decimal` and `unit:KiloTON_Metric` correctly, with no `qudt:value` use or canonical-identifier finding. This verifies correct identifiers in this fresh output, **not** live correction quality: no identifier repair occurred. Quantity enforcement is present as code but inactive under the root.

## 2–3. Reviewer evidence and retry

No reviewer request was dispatched, so valid reviewer quotations/schema assertions and retry correction cannot be assessed. There was no reviewer field failure to report. Empty reviewer/normalization/retry ledgers are explicit in reviewer_interface_outcome.json rather than represented as successes.

The exact deterministic failures were:

- `ACTIVATION_ERROR`: “No active constraints reachable from submitted targets.”
- `UNRESOLVED_CONTEXT`, assessment `MATERIAL_ACTIVATION_UNCERTAINTY`: “Reachable enforcement is deactivated.”

Both are bound to candidate 1 SHA-256 `26f4d0bfbbc3d9ad5bc08df3be0ec3db8aee241f2b1a80728b0bd2fac650972a` in findings_01.json, with original diagnostic, evidence and suggested resolution.

## 4. Constraint preservation

There is only one candidate, so there is no inter-candidate deletion, repair diff or removal assessment. Numeric, datatype, unit and two SPARQL constraints remain in the original code. However, the root explicitly sets `sh:deactivated true`, making those constraints ineffective. No manual edit, automatic activation or target assumption was applied.

## 5. Activation, execution and remaining source gap

The candidate declares `sh:targetClass nltl:ship` but deactivates the root because the supplied parent source states: **“This UR applies to Polar Class ships according to UR I1.”** The model identified material applicability uncertainty rather than silently claiming active enforcement. The new deterministic activation guard prevented vacuous internal acceptance. Internal execution probing and semantic review were skipped because blocking findings already existed.

Independent pySHACL validation can parse and process the unchanged deactivated graph, but this does not establish execution of its inactive constraints. There is **no selected shape** to call active/executable.

The selected context contains no Polar Class applicability terms or approved I2-004 target/precondition binding. Broader locked ontology does contain `polarClass`, its value class/individuals and `polarClassRequirementsApplicable`; their existence does not itself settle this requirement’s representation/application contract. Applicability_evidence.json records exact ontology/source evidence and distinguishes absence from supplied context from absence from the ontology. The source selector’s unresolved-reference list was empty despite the UR I1 citation; no autonomous expanded-span retrieval occurred. No contract was strengthened from fixture outcomes.

## 6. Independent results, primary versus diagnostic

All six reviewed cases and three intended-only counterparts were evaluated **after dispatch closed** using unchanged saved code and reviewed oracle inputs. All primary cases remain; no exclusions.

| Outcome | Candidate 1, diagnostic only | Selected workflow |
|---|---:|---:|
| Positive acceptance | 3/3 | 0/3, all NO_VERDICT |
| Strict intended detection | 0/3 | 0/3, all NO_VERDICT |
| Missed intended defects | 3/3 | 0 executable classifications |
| Unrelated rejection | 0/3 | 0 |
| Unresolved attribution | 0/3 | 0 |
| Total NO_VERDICT | 0/6 | **6/6** |
| Repaired counterpart acceptance | 3/3, vacuous | No selected counterpart verdicts |
| Ordinary agreement | 3/6 | 0/6; six no verdicts |

A deactivated graph passes both valid and defective fixtures, so positive/counterpart passes are not evidence of effective enforcement. Initial-to-selected-final recoveries/regressions are unassessable because no selected final exists. No rejected candidate was credited as workflow success.

### Read-only latent query diagnostic

After the main independent evaluation, the exact saved SELECT texts were executed separately with `$this` bound to each reviewed positive ship. **The shape was never edited or activated.** The second query returned violations for I2-004-G-P01 and I2-004-G-P02 (two rows each), and none for P03. Its outer-bound `?case` in the correlated NOT EXISTS requires each represented case to equal the ship value, instead of allowing a lower nonmaximal case while selecting the maximum. The first query returned no rows for all three positives. These branch observations are diagnostic only and do not alter actual deactivated SHACL results or primary denominators. They show why removing deactivation alone would not certify the generated logic. Exact queries, bindings, hashes and rows are retained in query_branch_diagnostics.json.

## Resources and preservation

**1 successful provider call:** initial generation only. **12,325 input + 3,117 output = 15,442 reported tokens** (output includes 1,718 reasoning tokens). Provider request time **21.59 s**; frozen workflow **21.83 s**; dispatch loop **22.14 s**. Independent evaluation: 9.70 s. No additional attempts or capability requests were sent.

All pre-existing output files (7,090) were hash-verified unchanged; frozen implementation, original inputs and installed package hashes remained exact. Source selection/manifests and source-file-open events are retained in source_retrievals.json and source_selection_manifest.json. No expanded source spans were requested.

## Conclusion

Quantity serialization appeared correctly in the fresh candidate and the activation guard blocked ineffective output. Live reviewer validation, repair delivery and destructive-change assessment remain unexercised. The check exposed an unresolved applicability/context gap plus a latent equality-query defect. Resolve source/schema applicability evidence and assess the general query/review path before another authorized live check; do not infer eligibility or fixes from benchmark labels. This run establishes neither workflow superiority nor a general accuracy/budget result. The authorized check is finished; no batch or 50-requirement study was started.
