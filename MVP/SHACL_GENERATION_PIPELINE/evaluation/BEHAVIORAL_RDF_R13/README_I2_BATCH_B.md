# I2 Behavioral Benchmark Batch B

Requirements: 5
RDF cases: 39

Requirements:
- I2-022
- I2-023
- I2-024
- I2-040
- I2-043

All five are frozen R13 COMPLEX_READINESS requirements with
formulaExecutionRequired=false.

The benchmark therefore checks applicability, required operands,
results, graph paths, owners and units rather than numerically
executing the advanced engineering formula.

Generated SHACL must not be inspected while constructing or
modifying this batch.

Validate with:

python3 scripts/validate_i2_batch_b.py
