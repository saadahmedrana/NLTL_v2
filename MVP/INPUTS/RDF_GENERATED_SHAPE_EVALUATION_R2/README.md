# Generated-shape RDF evaluation pack R2

This pack tests the frozen SHACL generated for `IMO-057` and `IMO-088` against
small, requirement-level RDF graphs. It is separate from both SHACL generation
and the earlier hand-authored RDF pilot.

- `evaluation_manifest.json` links each RDF variant to the exact generated
  shape run, binds both files by SHA-256, and records the expected outcome.
- `IMO-057/` tests pump-to-compartment modelling, the strict above-freezing
  boundary, the required Celsius unit, and required containment evidence.
- `IMO-088/` tests the 24-hour-daylight exception, the exact equipment
  threshold, the 360-degree boundary, and the approved-alternative branch.

The RDF files contain benchmark facts only. Expected results and deliberate
violations are stored in the manifest so they are not visible to SHACL. The
evaluator also verifies and loads the locked R2 ontology for inference.

Run from `SHACL_GENERATION_PIPELINE`:

```text
../.venv/bin/python run_pipeline.py evaluate \
  --manifest ../INPUTS/RDF_GENERATED_SHAPE_EVALUATION_R2/evaluation_manifest.json
```
