# I2 Behavioral Benchmark Batch E

Requirements: 4
Cases: 36

I2-014
I2-015
I2-017
I2-018

Generated SHACL was not inspected during fixture construction. I2-018 Table-3 cases use the bottom-structure-frame row (PPFs=1.0), which is deterministically testable using the frozen R13 contract without inventing an absent spacing selector.

Run:

python3 scripts/validate_i2_batch_e.py
