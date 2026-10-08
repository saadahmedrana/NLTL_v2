# I2 Behavioral Benchmark - Batch A

This package adds the first post-Pilot-02 IACS UR I2 behavioral fixtures.

Requirements: 6
Cases: 33

Requirements:
- I2-001
- I2-013
- I2-019
- I2-029
- I2-037
- I2-061

Method:
- authored from IACS UR I2 Rev.4 and frozen R13 contracts
- generated without inspecting generated SHACL
- smallest requirement-level RDF graphs
- fixed PASS/FAIL source oracle
- no LLM calls during evaluation
- Pilot 01/02 fixtures are not modified

After copying this package into:
MVP/SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13/

run:
python3 scripts/validate_i2_batch_a.py
