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

## Five-case live confirmation

Session: `SESSION-BATCH-20260813T084039739274Z`

- Generation: four of five accepted. `TRF-037`, `TRF-042`, `TRF-022`, and `TRF-025` were accepted; `TRF-030` reached the three-attempt semantic repair limit.
- Calls: 22 total API calls, split into 11 generator and 11 validator calls. No vocabulary-matcher call was activated.
- Usage: 342,399 total tokens recorded by the API responses.
- API elapsed time: 953.51 seconds summed across calls. This is call time, not parallel wall-clock time.
- Vocabulary result: the two prior context/index gaps were confirmed fixed. No confirmation requirement ended as a vocabulary gap or term-resolution failure.

The separate RDF evaluation executed all 12 accepted-shape/fixture combinations. The first evaluation exposed fixture/schema incompatibilities rather than new missing names: the `TRF-037` fixtures still used the retired ship-owned `ca` model, and C1/C2 unit metadata was absent. After repairing those development assets, 11 of 12 expected outcomes matched. The remaining `TRF-022` failure exposed an unsupported construction-date applicability branch in the generated R8 shape.

## R8.1 post-confirmation correction

Active development identifier: `VOCAB-DEV-2026-08-13-BATCH01-R8.1-POSTCONFIRMATION`

R8.1 preserves the exact R8 hash-bound artifacts used by the live confirmation and applies three separately traceable corrections:

- assign QUDT `unit:N` to `brashIceResistanceCoefficientC1` and `brashIceResistanceCoefficientC2`, derived from the verified formula dimensions;
- remove the over-strong `TRF-030` coordinate exclusivity declaration;
- remove `constructionStageDate` from the `TRF-022` scoped requirement index because clause 3.2.2 has no date applicability condition.

No new vocabulary term was added. R8.1 doctor passes, all 313 context packs build, all 150 RDF fixtures parse, and 36/36 pipeline tests pass. The R8 generated shapes remain bound to R8 and are not relabeled as R8.1 outputs.
