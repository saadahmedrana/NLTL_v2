# R3 vocabulary stress test

This is a development-only, non-scored stress test of candidate lock `VOCAB-LOCK-2026-08-14-R3`.

The first sweep runs every one of the 238 generation-eligible requirements once with GPT-5.6 Luna as generator, GPT-5.6 Terra as semantic validator, and GPT-5.6 Luna as vocabulary matcher. Semantic repair is capped at one attempt so the sweep measures gap signals without paying for repeated SHACL repair.

Classification policy:

- Existing R3 term missed, invented, or misused by a model: generator/pipeline error; not a vocabulary gap.
- Model request not grounded in the verified regulation: generator error; not a vocabulary gap.
- No valid R3 representation for a source-confirmed required concept, value, relationship, or structure: suspected genuine gap requiring manual/source inspection.
- No ontology edit is permitted from model feedback alone.

The output directory is `SHACL_GENERATION_PIPELINE/outputs/vocabulary_stress_r3`, separate from development R1-R13 and the future scored experiment.
