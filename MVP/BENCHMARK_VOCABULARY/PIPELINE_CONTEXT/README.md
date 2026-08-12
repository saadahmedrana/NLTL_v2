# LLM vocabulary context layer

This directory turns the locked Stage 2 vocabulary into deterministic context inputs for the future NL-to-SHACL pipeline. It does **not** generate regulatory SHACL.

## Recommended context strategy

Use two layers:

1. `master/vocabulary_master.jsonld` is the complete, versioned source for all 821 canonical terms. Keep it for audit, interoperability, retrieval, and offline validation.
2. A requirement-scoped context pack is the prompt input. It contains only the terms linked to the selected requirement, or the exact union for an integrated ship case, together with datatypes, units, aliases, ranges, mappings, and applicable node patterns.

`context_assets_manifest.json` binds the master JSON-LD, requirement index, and pack schema to the locked Stage 2 workbook and registry hashes.

Do not place all 821 terms in every LLM prompt. That increases token use and makes incorrect term selection more likely. Full-master access is appropriate for retrieval and validation, while prompt-time generation should use a small allow-list.

## Pack contents

Each pack contains:

- the Stage 2 lock ID and hashes;
- verified requirement metadata and, by default, the verified source text;
- the exact allowed canonical terms;
- a JSON-LD context restricted to those terms;
- only the node patterns needed by those term kinds;
- a usage policy that prohibits synonyms, new URIs, datatype changes, unit changes, and unverified mappings;
- a deterministic size estimate.

The requirement text tells the future model what rule to encode. The vocabulary pack tells it how every concept must be named and represented. The pack itself contains no precomputed threshold result, compliance answer, or expected pass/fail label.

## Commands

Build the master JSON-LD vocabulary and the 313-entry requirement index:

```text
python3 BENCHMARK_VOCABULARY/PIPELINE_CONTEXT/context_pack.py build
```

Build a pack for one requirement:

```text
python3 BENCHMARK_VOCABULARY/PIPELINE_CONTEXT/context_pack.py pack --requirement TRF-016 --output BENCHMARK_VOCABULARY/PIPELINE_CONTEXT/examples/TRF-016.context.json
```

Build an integrated-case pack by repeating `--requirement`:

```text
python3 BENCHMARK_VOCABULARY/PIPELINE_CONTEXT/context_pack.py pack --requirement TRF-016 --requirement IMO26-007 --requirement IMO-093 --output BENCHMARK_VOCABULARY/PIPELINE_CONTEXT/examples/integrated.context.json
```

Use `--vocabulary-only` when the model needs naming/schema context but should not receive requirement wording. Use `--include-evidence` only for difficult cases because evidence excerpts make prompts larger.

## Pipeline boundary

The next pipeline stage should:

1. select one or more requirement IDs;
2. generate a context pack;
3. prompt the LLM with the verified requirement wording plus this closed vocabulary allow-list;
4. reject or flag output containing a URI outside the pack unless it is an approved RDF/QUDT/W3C infrastructure URI;
5. validate generated SHACL syntax and execute the benchmark cases separately.
