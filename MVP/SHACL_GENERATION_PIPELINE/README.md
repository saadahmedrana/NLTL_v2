# NLTL vocabulary-grounded SHACL generation pipeline

This directory contains the traceable regulation-to-SHACL pipeline for the
NLTL benchmark. It is deliberately separate from the historical implementation
in `OLD FILES` and treats all benchmark vocabulary and source inputs as
read-only.

The generation pipeline ends when a candidate SHACL graph has passed:

1. deterministic vocabulary retrieval;
2. deterministic few-shot selection;
3. generator-LLM production;
4. Turtle parsing and SHACL structural checks;
5. exact canonical-vocabulary, datatype, range, and unit checks; and
6. semantic validator-LLM review, including the optional vocabulary-matcher
   branch.

The semantic validator receives only the requirement-scoped terms, verified
records for terms used in the candidate, deterministic findings, and mismatch
candidates when applicable. The complete locked vocabulary remains in
the local deterministic gate and is not duplicated into every validator API
prompt. Vocabulary lock R2 repairs the IMO-057 pump-to-compartment node path
while retaining R1 unchanged for audit comparison.

It does **not** execute generated shapes against RDF ship graphs. RDF execution
is kept in the separate bulk evaluator so the final benchmark can freeze shapes
before functional evaluation and avoid leaking hidden expected outcomes into
the repair loop.

## Input contracts

The pipeline reads the locked files in the parent project:

- `benchmark_vocabulary_stage2_LOCK-2026-08-12-R2.lock.json`
- `BENCHMARK_VOCABULARY/STAGE2_R2/registry/term_registry.json`
- `BENCHMARK_VOCABULARY/STAGE2_R2/ontology/nltl_benchmark_vocabulary.ttl`
- `BENCHMARK_VOCABULARY/STAGE2_R2/evidence/stage1_approved.json`
- `BENCHMARK_VOCABULARY/PIPELINE_CONTEXT/R2/requirement_term_index.json`
- `RELEVANT FILES/SHACL_FEW_SHOT_EXAMPLES/few_shot_pairs.jsonl`

Hashes bound by the vocabulary lock are verified before a run starts. The
pipeline never edits these sources.

## Environment file

The live API client reads this file only when a live command is invoked:

`/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env`

Required content is maintained by the user. The pipeline never writes, copies,
prints, or fingerprints the key.

## Offline checks

From this directory, using the project virtual environment:

```text
../.venv/bin/python -m unittest discover -s tests -t . -v
../.venv/bin/python run_pipeline.py doctor
../.venv/bin/python run_pipeline.py offline-smoke --requirement IMO26-014
```

The smoke command uses a local scripted client. It performs no API request.

## Later live use

After the environment file is ready:

```text
../.venv/bin/python run_pipeline.py generate --requirement IMO26-014
```

To run several direct/deterministic requirements:

```text
../.venv/bin/python run_pipeline.py generate-batch --queue inputs/example_queue.json
```

Each run has an isolated folder under `outputs/runs/` with immutable prompt and
response artifacts, JSONL events, CSV exports, a formatted Excel tracker, and—
only on acceptance—the frozen candidate shape.

Live commands print concise progress to the terminal on standard error while
preserving the final JSON result on standard output. Progress includes the
current batch item, API role and duration, token usage, static-validation gate,
repair iteration, matcher activation, retries, final status, and tracker
completion. Prompts, raw responses, API keys, and response bodies are never
printed in these progress lines.

## Separate RDF evaluator

The evaluator accepts either a generic evaluation manifest or the existing RDF
pilot manifest:

```text
../.venv/bin/python run_pipeline.py evaluate \
  --manifest ../INPUTS/RDF_SHIP_GRAPH_PILOT/pilot_manifest.json
```

This command is independent of generation and never calls an LLM.

## Safety and experimental rules

- Unknown or missing benchmark terms cause `VOCABULARY_GAP`; the generator is
  never permitted to coin a replacement during an official run.
- Transport failures, HTTP 429 responses, Aalto gateway/VPN failures, and 5xx
  responses are retried inside the same API call and do not consume a semantic
  repair iteration.
- HTTP 400-series contract errors other than configured gateway authentication
  failures stop the call because repeating the same invalid request would not
  repair it.
- Press `Ctrl+C` to stop a persistent transport retry safely. All completed
  attempts remain in the event log.
- Hidden RDF expected outcomes are never supplied to the generator or semantic
  validator.
