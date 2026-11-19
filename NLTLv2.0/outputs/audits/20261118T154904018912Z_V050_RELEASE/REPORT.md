# NLTLv2.0 v0.5.0 — offline release

Implemented source-backed numeric-value equality controls and independently validated, candidate-bound exact-clause change permissions. No model calls, generations, batch/study runs or historical score changes.

- Complete suite: **194 tests passed**, zero failures/errors.
- Separate independent reference controls: **37/37** (17 positive, 20 intended negative), with **20/20 repaired counterparts passing**. These are reference controls, not measured automatic repair accuracy.
- Config/mapping validation: passed for all ten configurations. Offline-installed code matched all 22 source modules.
- Original ontology hash: `ba247e3973b6afc36a9160ca170a31f863ceb3b0df497e07b7b3101dc7f347e4`; unchanged. Base source/witness contracts, external fixtures and historical outputs retained.

## Unchanged replay evidence

I2-005 NLTL v2: the old nine internal controls reported no finding. The expanded 14 controls detect two valid lexical-equivalent decimal rejections, attributed to the exact numeric `sh:hasValue`. Unequal numbers and non-decimal types remain rejected. Exact RDF-term matching remains supported outside numeric-value obligations.

IMO-001 v1/v3/v5: the same two source-valid nonapplicable branch controls expose the excessive selector closure. Exact removal is permitted, preserving readiness and conditional logic. Historical v3→v4 and v5→v6 pass the new preservation guard. v1→v2 additionally rewrites the query; its selector removal is authorized, while the unvalidated compound query edit remains guarded. No permission demands restoration of the unsupported selector.

Unauthorized datatype/readiness/target/conditional changes, duplicate-scope deletions, stale/tampered permissions and model-issued deletion claims remain blocked. Explicit preservation conflicts stop dispatch. A legitimate independently reproduced SPARQL behavioral repair remains supported; list/class failures cannot authorize query rewrites.

## Evidence and prepared diagnostics

Full replay: `outputs/audits/20261118T153920633317Z_V050_UNCHANGED_REPLAY/summary.json`. Complete original logs, source/schema evidence, full candidate/version/hash and permissions are in `outputs/audits/20261118T153920633317Z_V050_UNCHANGED_REPLAY/I2-005_v2/repair_request.rendered.txt` and `outputs/audits/20261118T153920633317Z_V050_UNCHANGED_REPLAY/IMO-001_v5/repair_request.rendered.txt`. Scripted routing packets are also in `outputs/smoke_tests/20261118T153859085307Z_V050_COMPLETE/test_scripted_production_repairs_latest_packet_I2-005/` and its IMO-001 counterpart.

The two configs in `configs/` use exact historical I2-005 v2 and IMO-001 v5 seeds: zero initial generations, at most two repairs, first internal acceptance, no regeneration. They have **not** been dispatched. See `docs/v050_numeric_preservation.md` for commands and limits.

Remaining limits: finite witnesses are not proofs; arbitrary logical encodings/query equivalence are not established. Whole-graph preservation is conservative about compound edits. Real model repair effectiveness remains untested for this version.

Active installation also verified as v0.5.0: all 22 installed modules match source, all 210 bundle hashes and 89 tested-input hashes match, and all 4,576 pre-existing output files remain unchanged. Active `nltlv2 check` passed. See `active_installed_identity.json` and `active_configuration_check.json`.
