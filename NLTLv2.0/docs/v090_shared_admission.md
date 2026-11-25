# v0.9.0 — caller-admitted population (interpretation A)

Decision provenance: the user explicitly chose interpretation A for the current research pipeline on 23 November 2026. This authorizes a shared admission boundary; it does not attest particular historical inputs or choose governing editions for them.

## Exact declaration

An invocation supplies `--admission data/admissions/<name>.json` (or config `admission_file`). Exactly these keys are accepted:

```json
{
  "format_version": 1,
  "admission_id": "",
  "interpretation": "A",
  "population_description": "",
  "focus_set": {
    "mode": "COMPLETE_CLASS_POPULATION",
    "owner_class": "https://w3id.org/nltl/vocab#ship",
    "nodes": []
  },
  "eligibility_assertion": "EXTERNALLY_ADMITTED",
  "provenance": {
    "declarant": "",
    "reference": "",
    "basis": ""
  },
  "source_editions": [
    {
      "document_id": "UR I2",
      "edition": "Rev.4 (December 2019)",
      "file": "data/requirements/IACS_I2_full.txt",
      "sha256": "7ad8d57459782b70809da479380584a57cf259c66d9ff286811c0248b02732d2",
      "selection_provenance": ""
    },
    {
      "document_id": "UR I1",
      "edition": "Rev.2 (April 2016)",
      "file": "data/requirements/IACS_I1_Rev2_2016.txt",
      "sha256": "9ec1b5957c0967641d1e20f7edd92da71aed427e576fe383ddf152ea45e3acf9",
      "selection_provenance": ""
    }
  ]
}
```

This is the actual **pending template**, not an approved admission. Empty strings/nodes make it invalid. The retained I2/I1 descriptors are edition candidates, not a governing-edition decision. A caller must fill a unique admission_id, precise eligible population description, actual absolute node IRIs, declarant/reference/basis, and each edition's selection_provenance. Include the primary represented source and relevant edition selections; an unprovided/ambiguous material dependency remains explicit. Remove unused edition descriptors only with a documented caller scope decision. The owner_class identifies the representation population, not a legal qualification selector. No Boolean eligibility field is invented.

`format_version=1`, `interpretation=A`, `eligibility_assertion=EXTERNALLY_ADMITTED`, `focus_set.mode=COMPLETE_CLASS_POPULATION` are required assertions. No defaults supply missing input. The class must be declared in the locked ontology; nodes must be unique nonempty absolute IRIs. Edition identity/file/hash must match exactly one catalogued authoritative retained source and its bytes. Provenance strings must be supplied; identity/truth of caller attestation is not independently verified. Unknown/missing catalog edition metadata remains unresolved rather than being invented.

## Boundary and responsibilities

The full admitted record class population in each validation graph must equal the explicitly listed nodes, including RDFS-inferred instances. A class target is supported only behind this mandatory data guard; extra/unidentified instances stop with NO_VERDICT. Data or invocation supplies identity, never labels or expected outcomes. Caller admission of Polar Class/construction-date eligibility and applicable editions replaces an obligation to re-certify those facts from RDF. Regulatory text remains visible. Conditional obligations inside the represented clause, schema paths, operands, units, arithmetic/query logic and effective activation still require checks/review. Vocabulary existence alone proves no applicability binding.

Generation loads no data graphs. Admission preflight happens before either workflow, and CLI preflight precedes live transport/credential initialization. Missing/invalid input produces UNRESOLVED_ADMISSION and zero calls. Single-shot then makes one generation call with no checker/reviewer/repair. NLTL uses the identical initial context/settings and carries the exact declaration into every review, format retry and latest-code repair; declaration/source hash or rendered-admission changes prevent dispatch. No eligibility selectors are invented and no shape is activated automatically. Target checks and activation checks are separate from full query review/execution. Existing bounded retrieval/review/repair limits are unchanged.

Source resolution can use an explicitly caller-selected edition for an otherwise unversioned reference. An explicit cited revision conflicting with the caller-selected edition stays `CALLER_EDITION_REFERENCE_CONFLICT`; neither is silently overridden. The record remains `RETRIEVED_CALLER_SELECTED_EDITION` with qualification: the original citation did not establish that edition. This is research-invocation provenance, not a legal edition ruling. Missing I3/PR29 or other dependencies are assessed for represented materiality, not automatically ignored or promoted to blockers.

## Independent evaluation

`evaluation.independent.validate_admitted_graph(data, shape, schema, requirement_id, declaration)` validates caller metadata, exact RDFS population and supported shape target boundary **before** ordinary SHACL evaluation. Both original Single-shot and unchanged NLTL shapes use that guard; it never triggers repair. The paired evaluator takes common `admissions[case_id].fixture` and `.counterfactual` declaration paths shared by workflows; missing admission preserves each case as NO_VERDICT. A generated explicit targetNode shape cannot silently be reused for different graph identities. There is no automatic substitution of evaluation node IDs into generation.

Historical reference controls intentionally remain separate, conditional mathematical/software controls. Their passing does not certify admission or grant new workflow accuracy. No historical scores/labels/fixtures were rewritten. The scope inventory records 37 fixtures and 20 counterparts across six requirements (I2-004: six plus three), all lacking per-input caller/edition admission records. Historical docs explicitly state the eligible-population precondition (`docs/history/six_requirement_preflight.md:15`); this gives nominal research-scope consistency, not verified per-input admission. No case is declared ineligible from this absence. I2-042's separate welded-profile ambiguity remains deferred.

## Prepared operational check — NOT dispatched

`configs/v090_bounded_live_check.json`: fresh I2-004 NLTL, at most two candidates including initial generation, early acceptance, no seed/regeneration, up to four review rounds with one format retry each, existing two retrieval rounds. Structured output disabled. The pending declaration intentionally blocks dispatch until the caller provides actual nodes/provenance and edition selection. No external cases/labels/counterparts are allowed as production inputs. Reusing a historical case for evaluation requires a separately documented external admission decision, never inference from its label.

```sh
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . check
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . smoke
# After caller completes and verifies its own declaration (pending template currently unresolved):
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . check --requirement I2-004 --admission data/admissions/i2_004_pending.json
# Prepared only. Requires separate authorization/live opt-in; not executed:
NLTL_ALLOW_MODEL_CALLS=YES ../NLTLv2-env/bin/python -m nltlv2 --project . run --config configs/v090_bounded_live_check.json --requirement I2-004 --admission data/admissions/i2_004_pending.json --experiment-id UNIQUE_ID --allow-model-calls
```

Admission is a deliberately narrow shared input mechanism, not a regulatory solution contract. Limits: no legal/identity certification of caller attestations, no automatic proof of query correctness, only complete-class/exact-node boundaries supported; component/custom/subclass targeting needs an evidenced extension rather than silent widening. Scoped validation consumers must use the guard API. No evaluation resource is accessible through GenerationProject; the trusted application boundary is not a hostile-code OS sandbox.
