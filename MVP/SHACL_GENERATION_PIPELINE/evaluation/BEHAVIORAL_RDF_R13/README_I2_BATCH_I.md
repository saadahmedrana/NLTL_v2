# I2 Behavioral Benchmark Batch I

Requirements: 5
Cases: 61

I2-050, I2-051, I2-052, I2-054, I2-055

Batch I closes the remaining IACS I2 longitudinal-strength group in the frozen R13 mapping. I2-050, I2-052 and I2-054 are intentionally readiness-only because R13 sets formulaExecutionRequired=false; their advanced source equations/interpolation are therefore not executed by the behavioral oracle. I2-051 executes the frozen positive-shear branch, including MN-to-kN conversion between F_IB and F_I. I2-055 checks the generic frozen designStress <= permissibleStress criterion together with satisfied status.

Audit note: the frozen R13 registry currently assigns upperIceWaterlineDraughtDUI the unit metre even though the IACS source defines D_UI as displacement. This batch does not alter R13; I2-050 is readiness-only and tests the frozen interface exactly. The discrepancy should be reported separately as a vocabulary-contract limitation, not repaired from benchmark outcomes.

Run:

python3 scripts/validate_i2_batch_i.py
