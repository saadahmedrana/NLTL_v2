# NLTL benchmark vocabulary - Stage 2

This directory contains the controlled vocabulary input contract for the future SHACL-generation pipeline, derived from the 313 locked requirements and 823 approved Stage 1 candidate lineages.

Primary artifacts:

- `benchmark_vocabulary_stage2.xlsx` - editable review workbook.
- `STAGE2_REPORT.md` - decisions, counts, risks, and validation summary.
- `ontology/nltl_benchmark_vocabulary.ttl` and `.rdf` - equivalent OWL/RDFS serializations.
- `context/nltl_benchmark_context.jsonld` - protected JSON-LD context.
- `shacl/schema_only_shapes.ttl` - structural QA only; the pipeline will generate requirement-specific regulatory SHACL.
- `registry/term_registry.json` and `.csv` - canonical term registry.
- `profiles/*.json` - source and activation allow-lists over the master vocabulary.
- `mappings/haitham_exact_mappings.ttl` - verified SKOS mappings only.
- `examples/` - equivalent illustrative Turtle and JSON-LD graphs.
- `validation/` - machine-readable and human-readable validation results.

The provisional vocabulary base is `https://w3id.org/nltl/vocab#`. Register or replace it before publication.
