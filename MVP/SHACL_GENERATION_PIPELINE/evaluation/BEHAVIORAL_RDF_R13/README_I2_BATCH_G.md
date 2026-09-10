# I2 Behavioral Benchmark Batch G

Requirements: 8
Cases: 56

I2-004
I2-005
I2-041
I2-042
I2-046
I2-047
I2-066
I2-067

Generated SHACL was not inspected during fixture construction. I2-041 is evaluated as frozen R13 COMPLEX_READINESS: the benchmark checks required owners, paths, quantities and units but does not execute the source square-root inequality.

Run:

python3 scripts/validate_i2_batch_g.py
