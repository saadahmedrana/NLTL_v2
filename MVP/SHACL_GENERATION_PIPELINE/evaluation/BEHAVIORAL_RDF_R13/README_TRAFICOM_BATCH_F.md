# TRAFICOM Behavioral Benchmark Batch F

Requirements: 13
Cases: 102

TRF-053, TRF-054, TRF-055, TRF-056, TRF-057, TRF-058, TRF-059, TRF-060, TRF-062, TRF-063, TRF-064, TRF-066, TRF-067

Scope: TRAFICOM 2021 sections 4.5.1-4.6.2, 4.8 and selected complete Chapter 5 rudder requirements.
TRF-061 and TRF-065 are intentionally excluded because frozen R13 does not classify them COMPLETE.

Generated SHACL was not inspected during fixture construction.
TRF-060 is COMPLEX_READINESS with formulaExecutionRequired=false; its cases test the frozen interface/table/owner/unit contract rather than executing the advanced section-modulus calculation.

Per-requirement cases: {"TRF-053": 8, "TRF-054": 8, "TRF-055": 9, "TRF-056": 8, "TRF-057": 7, "TRF-058": 6, "TRF-059": 10, "TRF-060": 10, "TRF-062": 6, "TRF-063": 8, "TRF-064": 9, "TRF-066": 7, "TRF-067": 6}

Validate with:

python3 scripts/validate_traficom_batch_f.py
