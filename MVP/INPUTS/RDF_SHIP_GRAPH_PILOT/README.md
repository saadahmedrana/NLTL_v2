# RDF ship graph pilot

This folder contains a small, extensible pilot for testing RDF ship designs against requirement-specific SHACL. It contains two requirement-level cases and two integrated ship-level cases. Every case has one conforming graph and one graph with exactly one deliberate value change that causes non-conformance.

## Contents

- `requirement_level/` - isolated requirement cases.
- `integrated/` - ship graphs assessed against several requirements together.
- `pilot_manifest.json` - machine-readable case and file catalog.
- `rdf_ship_graph_pilot_tracker.xlsx` - editable human review and traceability tracker.
- `VALIDATION_REPORT.md` and `validation_report.json` - executable QA results.

Each case directory contains:

- `case.json` - requirement mapping, source pages, expected outcomes, and deliberate violation.
- `*_shapes.ttl` - the requirement-specific SHACL used only for pilot validation.
- `*_pass.ttl` - ship graph expected to conform.
- `*_fail.ttl` - graph expected not to conform.

## Modelling contract

- Canonical vocabulary: `https://w3id.org/nltl/vocab#`.
- Pilot instance identifiers: `urn:nltl:rdf-pilot:`.
- Graphs contain ship facts only. Expected outcomes and deliberate violations are kept in metadata, not encoded into the ship graph.
- Every failing graph differs from its paired passing graph at one subject-predicate value only.
- No new NLTL class or property is coined in this pilot.

## Pilot scope

| Case | Level | Requirements | Intended failing condition |
|---|---|---|---|
| `RQ-IMO-075` | Requirement | IMO-075 | Capacity is 54 for 50 persons; 55 is the minimum integer capacity meeting 110% |
| `RQ-IMO26-014` | Requirement | IMO26-014 | Only one visual-ice-detection illumination means is recorded when the daylight exception does not apply |
| `INT-001` | Integrated | IMO-075, IMO-085 | Applicable Category A ship has neither enclosed nor protectively designed bridge wings |
| `INT-002` | Integrated | IMO26-007, IMO26-011, IMO26-014 | The one-device echo-sounding alternative has only one independent transducer |

For IMO-075, the pilot validates the deterministic capacity and accessibility portions. The phrase "as close as practical" is retained in traceability but is not assigned an invented numerical distance threshold.

## Extension workflow

1. Copy the structure of the nearest existing case.
2. Add the requirement and exact source trace to `case.json` and the tracker.
3. Use only terms from the locked registry or ontology infrastructure.
4. Create a passing graph first.
5. Create the failing graph by changing one fact only.
6. Run `validate_pilot.py` and record the validation run in the tracker.
7. Obtain human review before marking a case `Locked`.

The current pilot is deliberately small. It can be extended after the RDF-generation pipeline reliably reproduces these patterns.
