# Batch 01 R7 results

R7 is development calibration, not final benchmark accuracy.

## Generation and telemetry

- Requirements run: 12
- LLM-validator accepted: 8
- Semantic attempts: 26
- API calls: 55
- Input/output/total tokens: 623,514 / 163,109 / 786,623
- Wall-clock time: 36.58 minutes

## Deterministic RDF gate

- Evaluations executed: 24/24
- Expected outcomes matched: 18/24
- R7 RDF-clean requirements: TRF-014, TRF-020, TRF-026, TRF-046, TRF-049
- R7 unresolved requirements: TRF-011, TRF-022, TRF-025, TRF-027, TRF-030, TRF-037, TRF-042

TRF-022 and TRF-027 expose brittle exact-decimal `sh:hasValue` behavior in addition to generated logic checks; this should be normalized in the final benchmark serialization policy. TRF-030 is a genuine over-constraint: every direct-analysis case was forced to carry both vertical and horizontal positions, and reference-position facts were required even though the regulation permits separate checks.

## Decision

Stop first-50 prompt tuning here. Carry these seven unresolved cases into the broader discovery ledger, distinguish true missing vocabulary from generator/validator errors, and do not report the development results as final benchmark accuracy.
