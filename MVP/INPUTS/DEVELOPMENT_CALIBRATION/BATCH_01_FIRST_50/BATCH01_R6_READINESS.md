# Batch 01 R6 readiness

R6 is a development revision, not the final frozen benchmark vocabulary. It closes the ownership and missing-term gaps observed in R5 and adds explicit semantic obligations for requirements where presence-only SHACL was insufficient.

## Deterministic migration result

The 15 shapes accepted in R5 were evaluated against the R6 PASS, FAIL, and BOUNDARY RDF fixtures without making API calls.

- RDF evaluations executed: 45/45
- Expected outcomes matched: 36/45
- Requirements clean across all three variants: 10/15
- Accepted shapes requiring regeneration: 5/15 (`TRF-011`, `TRF-034`, `TRF-037`, `TRF-041`, `TRF-054`)

The 10 verified-clean shapes are excluded from the R6 API queue. The queue contains the 5 accepted-but-incorrect shapes plus the 17 requirements that R5 did not accept, for 22 total generator targets.

## What R6 fixes

- Requirement-scoped target and property ownership, so values are attached to the correct engineering entity.
- Explicit concepts for waterline reference positions, transverse-frame types, strengthened-part and attachment relations, and qualitative approval/exception evidence.
- Formula-ready PASS and boundary fixture values for the affected structural calculations.
- Generator and validator instructions that reject generic targets, missing semantic obligations, presence-only approximations, and fragile nested SPARQL patterns.

## Leakage boundary

R6 is calibration work used to complete the vocabulary. After the vocabulary is judged complete, the final study must create a new fixed lock and rerun every simulation from scratch against fixtures not shown to the generator.
