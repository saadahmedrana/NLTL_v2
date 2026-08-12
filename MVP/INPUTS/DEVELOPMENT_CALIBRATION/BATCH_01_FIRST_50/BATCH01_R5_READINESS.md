# Batch 01 R5 readiness

Status: **ready for the targeted 32-requirement live rerun**.

R5 is a development calibration revision, not the final benchmark lock. It preserves the R2 lock and R3/R4 evidence while consolidating only issues demonstrated by the R4 generation and RDF evaluation.

## R5 repairs

- Restored canonical `rdfs:domain` metadata when registry and ontology records are merged, and exposed domains to the generator.
- Added clause-backed controlled values for electric and hydraulic propulsion machinery, the exact `tankBottom` class, an explicit salinity unit individual, and separate deck-strip actual/required section-modulus and shear-area terms.
- Added verified TRAFICOM table evidence for Tables 3-1, 3-2, 3-3, 4-1, 4-6, 4-7, and 4-8.
- Strengthened generator and semantic-validator instructions for domain-correct targeting, numerical tolerance for derived decimals, portable date comparisons, and bounded SHACL-SPARQL.
- Added a deterministic complexity gate for excessive `UNION` and `FILTER NOT EXISTS` branching.
- Rebuilt all 150 visible calibration RDF fixtures with domain-aware property placement and explicit node structures for waterlines, design-parameter sets, direct-analysis cases, frame ends, and frame attachments.

## Verified state

- Development vocabulary: `VOCAB-DEV-2026-08-12-BATCH01-R5`
- Registry terms: 1,061
- Canonical terms including ontology infrastructure: 1,114
- Batch requirements: 50
- RDF fixtures: 150; Turtle parse and vocabulary validation: PASS
- Pipeline doctor: PASS
- Offline unit tests: 28/28 PASS
- Live API calls made while preparing R5: 0

## Targeted rerun

The queue contains the union of the 10 unresolved R4 generations and the 22 R4-accepted requirements whose RDF expectations did not all match: 32 unique requirements. This rerun is the gate before scaling to the remaining 190 eligible requirements.

