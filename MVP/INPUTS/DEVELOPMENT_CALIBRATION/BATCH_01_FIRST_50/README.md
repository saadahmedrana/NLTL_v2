# Development calibration Batch 01 - first 50 eligible requirements

This folder is the active vocabulary-development batch. The requirements are
the first 50 generation-eligible records in the locked R2 evidence order. Batch
membership is fixed for traceability, but the vocabulary is intentionally not
frozen during this development phase.

Workflow:

1. Audit every explicit operand and hidden dependency before fixture creation.
2. Resolve missing terms, node models, datatypes, units, and controlled values.
3. Create pass/fail and boundary RDF fixtures before fresh SHACL generation.
4. Bind fixtures and generated shapes by SHA-256.
5. Execute with the standalone evaluator and classify every mismatch.
6. Rerun all earlier Batch 01 regression cases after any vocabulary revision.

Development fixtures are calibration material and will not be presented as
unbiased final benchmark results.

