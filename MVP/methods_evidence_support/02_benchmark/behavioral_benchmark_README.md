# Pilot 02 — Behavioral RDF R13

Purpose: independent behavioral test fixtures for ten harder frozen R13 requirements.

Requirements:
I2-014, I2-015, I2-021, I2-041, I2-046, I2-047, I2-048, I2-066, IMO26-007, IMO26-011

Case count: 65

Independence rule:
- Fixtures/specifications/manifest are authored without inspecting generated SHACL.
- No reference SHACL is included.
- After validation/freeze, generated experiment artifacts may be evaluated against these fixtures.
- Do not modify fixtures after exposure to generated SHACL; create a new benchmark version instead.

Run:
`python3 scripts/validate_pilot_02.py`
