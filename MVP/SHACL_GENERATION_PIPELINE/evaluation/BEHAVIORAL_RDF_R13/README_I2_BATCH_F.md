# I2 Behavioral Benchmark Batch F

Requirements: 7
Cases: 48

I2-021
I2-026
I2-030
I2-031
I2-032
I2-034
I2-035

Generated SHACL was not inspected during fixture construction. COMPLEX_READINESS I2-030 checks selectors, operands, paths, results and interpolation readiness without executing nonlinear section-modulus equations. I2-035 includes loadPatchHeight because the source piecewise b/s equation requires it and the term exists in frozen R13, even though the I2-035 dependency-contract operand list omits it; the contract itself is not modified.

Run:

python3 scripts/validate_i2_batch_f.py
