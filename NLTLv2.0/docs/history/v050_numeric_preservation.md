# v0.5.0: numeric values and exact change permissions

No model calls, fresh generations, evaluation-label changes, historical repairs or score changes accompany this release. Scripted responses test routing, not automatic repair quality.

## Numeric equality

The source-backed `constant_equal` operation means numeric equality, not RDF literal identity. The approved source/representation witnesses now derive equivalent decimal spellings plus wrong-datatype controls, in addition to existing unequal/boundary/missing-input controls. The original witness contract remains byte-identical. The required decimal datatype is unchanged; no tolerance or coercion is introduced. `normalize=False` preserves the lexical spelling in synthetic graphs.

The deterministic review associates a `sh:hasValue` violation with its complete explicitly contracted property/node path, a decimal constant, and a source-valid lexical-equivalent synthetic counterexample. It emits the original validation report/log, exact RDF locator, source/contract evidence, current full code/version/hash, and suggests equal inclusive bounds or removal of a redundant term restriction if a numeric comparison already exists. All normal checks rerun after repair. Exact RDF-term obligations, units and identifiers remain valid uses of `sh:hasValue`.

Coverage: the new attributed structural rule handles unconditional named-target `sh:property`/`sh:node` trees and uniquely located constraints. Arbitrary logical encodings and numeric SPARQL equivalence are not proved. Finite witness success is not general correctness. Other equality operations retain their existing behavioral controls; this release does not infer a constant obligation where none is contracted.

## Unsupported restriction removal

An actual `sh:InConstraintComponent` failure on a source-backed valid nonapplicable selector can validate removal of precisely the located selector `sh:in` clause/list. The readiness policy, applicable required-value obligation and explicit path are checked against approved source metadata, not evaluation outcomes.

Permissions include candidate version/SHA, exact RDF locator, predicate/value, contract ID and hashed source/representation evidence. They are generated deterministically, saved in the rendered production packet, checked at the request boundary, and independently recomputed against the preceding candidate before the guard accepts a change. A reviewer label or model-proposed deletion cannot authorize itself. Stale/tampered permissions fail integrity checks.

For these changes the preservation guard compares whole RDF graphs, ignoring only messages/names/descriptions/labels/comments and the specifically authorized edit. This preserves duplicate constraints, datatype, readiness, target scope and conditional query text. The supported numeric replacement permits equal numeric bounds at the same exact locator. It does not authorize tolerance, datatype changes, or arbitrary query rewrites. Additional edits remain repairable preservation findings and persist across subsequent attempts until restored. A preservation instruction demanding restoration of the authorized defective clause is an explicit `PRESERVATION_CONFLICT` and stops dispatch.

Historical IMO-001 v3→v4 and v5→v6 are minimal authorized removals. v1→v2 also rewrites SPARQL; the selector deletion is supported, but this separate query change is not discharged by that permission. It remains guarded, despite passing finite witnesses. This is deliberate conservatism, not a request to restore the unsupported selector restriction.

The original conditional and numeric source/witness JSON is unchanged. The new reusable `data/contracts/constraint_change_policy.json` explicitly cites the locked JSON-LD decimal binding, distinguishes numeric values from exact terms, and records the narrow permission policy. Resource-bearing configs now include that policy for future snapshots; existing model/settings and initial generation context are unchanged. Older paired manifests remain preserved and stale, not dispatch-ready.

Query repairs outside these new permissions retain a narrow independent route: the exact source-backed query counterexample must reproduce an actual SPARQL leaf rejection, the named owning scope must remain, and current internal controls must pass. A list/class failure or semantic-review label alone cannot authorize a query rewrite.

## Prepared live diagnostics (not dispatched)

`configs/i2_005_numeric_repair_diagnostic.json`: historical NLTL v2, SHA `59c60a39431268aed7d5de381bc1283d14cb7d079bd93ec2118b81a2c36c4a9c`.

`configs/imo_001_selector_repair_diagnostic.json`: historical NLTL v5 (already has the later conditional query), exact SHA recorded in config/seed manifest. Choosing v5 isolates selector removal and avoids granting its earlier compound query rewrite.

Both configs: zero initial generation calls; one unchanged seed plus at most two repair calls; first internal acceptance; no regeneration; bounded reviewer-format retries separately counted; explicit live opt-in required. External credentials remain outside the project, unchanged. Independent evaluation runs only after repair completes in a separate process. No evaluation fixture, repaired counterpart or label is available through `GenerationProject`.

Prepared commands, **not executed**:

```sh
nltl --project . run --config configs/i2_005_numeric_repair_diagnostic.json --requirement I2-005 --experiment-id NEW_UNIQUE_I2_NUMERIC --allow-model-calls
nltl --project . run --config configs/imo_001_selector_repair_diagnostic.json --requirement IMO-001 --experiment-id NEW_UNIQUE_IMO_SELECTOR --allow-model-calls
```

The model identifier and endpoint must be reverified before any future separately authorized dispatch. Existing settings are retained, not an assertion of future provider availability.
