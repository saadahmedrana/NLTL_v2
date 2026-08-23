# R9 five-category verification policy

The category policy is based on the source requirement and intrinsic verification method. It is independent of whether any particular LLM model previously succeeded or failed to generate a SHACL shape.

- Static -> DIRECT_STATIC: direct static RDF checks without deriving an engineering result.
- Static Calculation -> DIRECT_CALCULATION: +, -, *, /, comparisons, min/max, simple piecewise branches, integer powers, fixed constants, and ordinary table lookup/selection. A fixed sqrt(3) constant alone is not Complex.
- Complex -> COMPLEX_READINESS: verify applicability, inputs, owners/paths, units/datatypes, analysis case/method/evidence, outputs/results, and explicit DIRECT_CHECK residuals; do not reconstruct the advanced engineering procedure.
- Dynamic -> DYNAMIC_DEFERRED: preserve runtime/transient semantics; R9 adds no runtime solver.
- Physical Test -> PHYSICAL_TEST_DEFERRED: preserve physical evidence semantics; R9 adds no test solver.
