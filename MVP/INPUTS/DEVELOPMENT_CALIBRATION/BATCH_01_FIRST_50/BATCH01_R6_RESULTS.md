# Batch 01 R6 results

R6 is development calibration, not final benchmark accuracy.

## Generation and cost telemetry

- Requirements run: 22
- Accepted: 10
- Maximum-attempt results: 10
- Vocabulary gaps: 2
- Semantic attempts: 50
- API calls: 110
- Input/output/total tokens: 1,115,314 / 292,990 / 1,408,304
- Batch wall-clock time: 68.81 minutes
- Transport retries: none; every API call completed in one transport attempt.

## RDF regression gate

- Executed: 30/30
- Expected outcomes matched: 30/30
- Clean accepted requirements: TRF-012, TRF-015, TRF-034, TRF-041, TRF-043, TRF-044, TRF-047, TRF-051, TRF-054, TRF-055

Before the final rerun, three fixture-alignment defects were corrected and rehashed: TRF-044 rounded formula outputs, TRF-051 contradictory `inLieuOfFrame`, and TRF-054 decimal lexical form `0.80`. No generated SHACL was edited.

## R7 work queue

- `TRF-011` — Add a bounded envelope-aggregation pattern to the generation guidance.
- `TRF-014` — Clarify the pre-2007 marking/dry-docking alternatives as a semantic obligation.
- `TRF-020` — Index the existing length, breadth, draught, and waterline operand relationships explicitly.
- `TRF-022` — Choose and document a portable trigonometric calculation strategy supported by the evaluator.
- `TRF-025` — Add the existing coefficientG3 term to the TRF-025 requirement scope.
- `TRF-026` — Add an explicit applicability-branch pattern for IA Super and bulbous-bow evidence.
- `TRF-027` — Require exactly one controlled iceClass before conditional applicability branches.
- `TRF-030` — Add a canonical case-specific load-length/area-factor pairing relation.
- `TRF-037` — Add the maximum-as-cap formula obligation using IF(raw > 1, 1, raw).
- `TRF-042` — Standardize tolerance fallback and evidenceState range validation.
- `TRF-046` — Clarify that the ice-belt-limit condition qualifies permission branches only.
- `TRF-049` — Reinforce frameAttachment ownership and subclass-target behavior.

R7 should address only these 12 requirements. The 20 first-batch shapes already proven clean under R5/R6 migration and R6 evaluation do not need another API call during development.
