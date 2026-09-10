# I2 Behavioral Benchmark Batch H

Requirement: I2-048
Cases: 152

Dedicated exhaustive IACS Table 8 benchmark. It contains one source-grounded PASS fixture for every one of the 126 frozen R13 Table-8 selector cells, eight lower-exclusive thickness-boundary checks, same-family higher-grade controls, a zero-case universal-scope control, and targeted selector/cardinality/table/rank failures. Existing Pilot-02 I2-048 files are not modified; Batch-H case IDs and specification filename are batch-specific.

Run:

python3 scripts/validate_i2_batch_h.py
