# Required inputs for a new regulation

1. A record in `data/requirements/requirements.json`, with a unique ID, authority/edition, clause and verbatim source excerpt. Cite real source material, not a manually encoded solution:

```json
{
  "NEW-001": {
    "id": "NEW-001",
    "source": "Authority and edition",
    "clause": "4.2",
    "text": "Verbatim regulatory passage...",
    "source_file": "data/requirements/new_source.txt",
    "source_sha256": "SHA-256 of that file",
    "supporting_sources": [
      {"file": "data/requirements/referenced_source.txt", "sha256": "SHA-256"}
    ]
  }
}
```

The supporting list is optional, but referenced provisions needed to interpret the obligation must be supplied or left unresolved. For existing records, `source_catalog.json` supplies the document and hash by source title. SHA fields are checked when supplied; actual hashes are always recorded. An excerpt alone is not assumed to establish complete parent context. Original extraction/normalized fields are preserved as material but only ID/source/clause/text are copied into the requirement context; normalization is not used as an answer.

2. A declared ontology and genuine term metadata under `schema/`. Existing regulations may reuse the unchanged R13 ontology and registry. New vocabulary requires an explicit declaration/mapping change, not invented IRIs. Property kinds, datatypes and property-specific input units belong here. A unit IRI is not a substitute for numeric conversion.

3. Optional schema-only representation metadata in `schema/representation_bindings.json`: `terms`, `owners`, `model_paths`, `target_owner`. These are data-model choices, not regulatory solutions. `terms` is a context selection, not an obligation list. Owner/path declarations must have source/schema provenance; broad RDFS domains are not exclusive placement rules. Without a per-requirement entry, the full shared metadata is available and unknown ownership is explicit. Numeric bounds, formulas, expected compliance, witness vectors, applicability truth tables and change permissions are not accepted mapping fields.

4. Common model settings/configuration: same initial source/schema/settings for Single-shot and NLTL. Do not include evaluation resources or problem-specific solved examples. Credentials stay external and are loaded only by explicitly opted-in live transport; no credentials are required for scripted offline tests.

Not required and forbidden as production inputs: case labels, positive/negative fixtures, intended-only repaired counterparts, gold shapes, manually encoded solution profiles, per-regulation behavioral witnesses or bespoke correction permissions. Independent evaluation may use its own reviewed oracles/fixtures after workflow completion, but never as feedback to generation, review, repair, acceptance or budget selection.
