# NLTL SHACL few-shot examples

This folder is a generator input library grounded in the locked Stage 2 vocabulary. It contains 10 SHACL pattern cases and two synthetic few-shot examples per case, for 20 examples in total.

The examples teach output structure. They are not regulatory benchmark answers and must not be used as the expected shapes for the 313 locked requirements.

## Folder structure

Each traceable example directory contains:

- `input_requirement.txt` - short synthetic natural-language input.
- `expected_shape.ttl` - minimal expected SHACL output.
- `example_data_pass.ttl` - tiny RDF graph expected to conform.
- `example_data_fail.ttl` - tiny RDF graph expected not to conform.
- `metadata.json` - example ID, retrieval tags, exact vocabulary IRIs, provenance category, and file links.

Top-level files:

- `catalog.json` - machine-readable lookup catalog for the prompt builder.
- `few_shot_pairs.jsonl` - prompt-ready input/output pairs without the QA pass/fail graphs.
- `VALIDATION_REPORT.md` and `validation_report.json` - executable validation evidence.
- `build_few_shots.py` - reproducible library builder.
- `validate_examples.py` - Turtle, vocabulary, style, and pySHACL validator.

## Cases

| Folder | Pattern | Examples |
|---|---|---:|
| `01_boolean_state` | Required Boolean value and cardinality | 2 |
| `02_typed_scalar` | Integer/date datatype and scalar bounds | 2 |
| `03_qudt_quantity` | QUDT quantity node, numeric value, unit, threshold | 2 |
| `04_entity_relation` | Object-property relation to an identified entity | 2 |
| `05_controlled_value` | Regulation-defined controlled IRI | 2 |
| `06_document_approval_evidence` | Approval state and document evidence node | 2 |
| `07_sosa_observation_history` | Timestamped SOSA observation and history | 2 |
| `08_physical_test_evidence` | Test result and provenance-bearing test evidence | 2 |
| `09_comparison_calculation` | Cross-property comparison and SHACL-SPARQL formula | 2 |
| `10_conditional_integrated` | Applicability dependency and multi-condition shape | 2 |

## Prompt use

Do not send all 20 examples to the generator for every requirement. The deterministic context builder should select the case pattern first, then retrieve one or two nearest examples by `caseId` and `retrievalTags`. Feed the generator:

1. the real requirement and extracted dependency terms;
2. the case-specific vocabulary allow-list;
3. the selected example's synthetic input and expected shape;
4. the required output contract.

The pass/fail RDF files belong to QA and regression testing. They do not need to be placed in the generation prompt unless the prompt explicitly teaches validation behavior.

## Grounding decisions

- Canonical vocabulary namespace: `https://w3id.org/nltl-benchmark/vocab#`.
- Synthetic example-data namespace: `urn:nltl:few-shot:`. It is an identifier, not a web link.
- Engineering quantities use the locked QUDT pattern: property to `qudt:QuantityValue`, then exactly one decimal `qudt:numericValue` and one canonical `qudt:unit`.
- Controlled categories and lifecycle states use IRIs, not free-text labels.
- Time/history uses SOSA observations.
- Document and physical-test evidence nodes carry a source and lifecycle state when the evidence-node pattern is used.
- `generatorVocabulary` in each metadata file is safe to give to the generator. `negativeExampleOnlyVocabulary` records values used only to make the failing QA graph.

No new NLTL classes or properties were coined for this library. Registry terms come from `term_registry.json`; generic plumbing such as `ship`, `hasEvidence`, `hasObservation`, and lifecycle-state IRIs comes from the locked ontology infrastructure. Every NLTL IRI in the bundles is checked against that ontology.

There are no Turtle comment lines and no decorative or unrelated links. The `#` character inside the canonical NLTL namespace is required because the locked vocabulary uses an RDF fragment namespace; it is not a comment.

## Validation

From the project root, run:

```text
.venv/bin/python "RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/validate_examples.py"
```

The validator checks all Turtle files, unused prefixes, unapproved external namespaces, exact NLTL vocabulary declarations, metadata coverage, SHACL meta-validation, and expected pass/fail behavior.

Current result: 20/20 intended-pass graphs conform and 20/20 intended-fail graphs do not conform.

## Remaining publication issue

The provisional `w3id.org` vocabulary redirect is still not registered. This does not prevent local parsing or SHACL execution because the examples use the IRI as an identifier and do not dereference it. Before public release, either register that exact namespace or replace it once across the locked vocabulary, context, profiles, few-shot catalog, and pipeline configuration. Do not allow individual generator runs to choose different base namespaces.
