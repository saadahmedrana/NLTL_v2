# IMO-057 R5 deterministic confirmation fixtures

These four graphs are provenance-preserving harness copies of the IMO-057 fixtures in `INPUTS/RDF_GENERATED_SHAPE_EVALUATION_R2/IMO-057/`.

The original pump classes, compartment relationships, temperature values, datatypes, units, omitted-compartment condition, and expected outcomes are unchanged. The only added assertions are the R5 target-path bindings `test:ship a nltl:ship` and `test:ship nltl:hasComponent <pump>`, because the accepted R5 shape begins at `nltl:ship` and traverses `nltl:hasComponent` before checking each pump.

The original files and R2 manifest remain unchanged. The R5 manifest binds these copies to `VOCAB-LOCK-2026-08-19-R5`, its ontology hash, and the accepted R5 IMO-057 shape hash.
