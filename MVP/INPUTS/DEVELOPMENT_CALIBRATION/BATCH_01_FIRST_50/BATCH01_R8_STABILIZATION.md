# Batch 01 R8 infrastructure stabilization

Status: `READY_FOR_OPTIONAL_CONFIRMATION`

Development identifier: `VOCAB-DEV-2026-08-13-BATCH01-R8-STABILIZATION`

R8 preserves the complete R7 evidence and introduces no new vocabulary term. It separates verified vocabulary/context faults from generator or validator failures so model behaviour is not incorrectly reported as a vocabulary defect.

## Resolved context/index faults

- `TRF-037`: `hasDirectAnalysisCase` and `directAnalysisCase` already existed in R7 but were not supplied to this requirement. They are now indexed. `iceLoadAreaFactorCa` is explicitly owned by `directAnalysisCase`, and the context builder generally expands canonical object-property paths from a requirement target to a different required owner.
- `TRF-042`: `plating` already existed in R7 and was the authoritative target owner, but was not supplied. It is now indexed, and the context builder always supplies the authoritative target-owner class.

## General generator/validator safeguards

- Numeric `sh:hasValue` on `qudt:numericValue` is deterministically rejected because RDF literal equality is lexical-form sensitive. Exact regulatory constants must use equal inclusive bounds; derived results must use explicit tolerance.
- Derived tolerance guidance now requires scaling from the expected formula result, not the reported value.
- `TRF-030` carries a verified exclusive property group for vertical versus horizontal direct-analysis case axes. The deterministic validator rejects a node shape that makes both alternatives mandatory on the same case.
- The generator prompt includes a final Turtle syntax self-check; the existing parser remains authoritative.
- Matcher exhaustion is now reported as `TERM_RESOLUTION_UNRESOLVED`, not automatically as `VOCABULARY_GAP`. A true vocabulary gap requires registry/index audit evidence.

## Verification

- Development vocabulary validation: pass.
- Pipeline unit tests: 36/36 pass.
- Pipeline doctor: pass.
- Offline end-to-end matcher/repair smoke: pass.
- Workbook formula-error scan: zero matches.
- No API calls were made for this stabilization.

R7 generated SHACL files remain historical evidence and were not modified. Any later confirmation run is development-only and must not be reported as final benchmark accuracy.
