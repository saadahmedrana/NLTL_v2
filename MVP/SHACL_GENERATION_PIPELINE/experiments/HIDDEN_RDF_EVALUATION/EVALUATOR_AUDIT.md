# Hidden RDF evaluator audit

Audit date: 2026-09-02  
Mode: offline, read-only inspection  
API/LLM calls made: 0  
Decision: **STOPPED BEFORE EVALUATION**

## Conclusion

The repository contains a deterministic RDF evaluator and several useful RDF fixture packs, but it does **not** contain a formal, independent hidden-RDF benchmark covering the frozen R13 experiment.

The largest available fixture set is explicitly identified as visible development/calibration material and was used during vocabulary, graph-model, and pipeline development. The other available sets are small pilot or targeted confirmation/regression packs. Treating any union of these assets as the journal's formal hidden evaluation would violate the requested independence rule and would cover only a minority of the 268 eligible requirements.

Accordingly, no generated SHACL was executed, no benchmark was frozen, no accuracy metric was calculated, and no ZIP was created.

## Existing evaluator implementation

Primary evaluator:

- `SHACL_GENERATION_PIPELINE/src/nltl_pipeline/evaluator/bulk.py`
- SHA256: `f4306ff7a2520fc40eb52ca1eb3753cf6084d632d0e6865e7aec2b366119cdb9`
- CLI entry: `SHACL_GENERATION_PIPELINE/src/nltl_pipeline/cli.py`, `evaluate` subcommand
- Manifest loader: `EvaluationManifest.load`
- Evaluation engine: `BulkRdfEvaluator.evaluate`

Supporting generation-time static validator:

- `SHACL_GENERATION_PIPELINE/src/nltl_pipeline/validation/shacl.py`
- SHA256: `2e2cf8072f8299f6d052dd3a7ffba99c73aa49118c05a1c77b2f09828af39403`

Runtime versions available in the project environment:

- pySHACL 0.31.0
- RDFLib 7.6.0

### How test records are matched

`EvaluationManifest.load` accepts either:

1. an `items` array in which each item explicitly contains `requirement_ids`, `shape_file`, `data_file`, and `expected_conforms`; or
2. a pilot `cases` structure whose referenced `case.json` files provide the requirement mapping and variants.

The mapping is therefore manifest-driven. The evaluator does not infer a requirement from RDF content.

### Expected outcome representation

The expected result is the Boolean field `expected_conforms` or `expectedConforms`. The evaluator compares it with pySHACL's Boolean conformance result and stores `expected_match`.

### Loading generated SHACL

The current bulk evaluator loads the Turtle path supplied in each manifest item. Existing evaluation manifests generally bind one historical shape file, so a new read-only evaluation harness would be needed to pair each formal run's final/captured output with the same fixed RDF tests without modifying the existing manifests.

### pySHACL settings

For executable items, `BulkRdfEvaluator.evaluate` calls pySHACL with:

- `ont_graph`: ontology from the selected pipeline configuration
- `inference="rdfs"`
- `meta_shacl=True`
- `advanced=True`

It parses both SHACL and data as Turtle and requires a real RDFLib report graph. Exceptions are recorded as execution failures.

### Isolation from generation

The evaluator is a separate CLI path. Its implementation contains no API client, LLM invocation, repair, regeneration, validator feedback, or vocabulary mutation. It writes only evaluation reports and a tracker under a caller-selected output root. No code path in `BulkRdfEvaluator.evaluate` feeds results back into generation.

## RDF assets actually present

### 1. Batch 01 development calibration fixtures

- Catalog: `INPUTS/DEVELOPMENT_CALIBRATION/BATCH_01_FIRST_50/rdf_fixtures/fixture_catalog.json`
- Catalog SHA256: `fb83257da850f99be3d8f8c692c7a70eb0e53698dd5fdcf92b0afffd2438b0eb`
- Declared status: `DEVELOPMENT_CALIBRATION_FIXTURES`
- Coverage: 50 TRAFICOM requirements
- Graphs: 150 (50 PASS, 50 FAIL, 50 BOUNDARY)
- Every catalog record has `calibrationOnly: true`.
- The accompanying README states: “These files are visible development fixtures, not hidden final-evaluation data.”

The development reports show that these fixtures were executed during R3–R8 development and that fixture/schema alignments, ownership, constants, and hashes were changed in response to calibration findings. Examples are documented in `BATCH01_R3_POSTRUN_REPORT.md`, `BATCH01_R5_RESULTS.md`, `BATCH01_R6_READINESS.md`, `BATCH01_R6_RESULTS.md`, `BATCH01_R7_READINESS.md`, and `BATCH01_R8_STABILIZATION.md`.

These graphs are therefore **development/calibration RDF**, not formal hidden evaluation data.

### 2. Generated-shape R2 confirmation pack

- Manifest: `INPUTS/RDF_GENERATED_SHAPE_EVALUATION_R2/evaluation_manifest.json`
- SHA256: `a331533411652b8caf5b9bd786b3ff45439bdca0f8af116e10c1ec212d2f1e04`
- Coverage: 2 requirements, 10 graphs
- Scope in manifest: regression and boundary tests for two repaired pilot generations
- Vocabulary binding: R2, not frozen R13

This is a targeted historical confirmation pack, not a 268-requirement formal hidden set.

### 3. R4 generated-shape confirmation pack

- Manifest: `INPUTS/RDF_R4_GENERATED_SHAPE_CONFIRMATION/evaluation_manifest.json`
- SHA256: `32ceee85ec5ee83cbd80fe11a89114a811a056946a0afe9b12335eff572b29bf`
- Coverage: 2 requirements, 7 graphs
- Scope: targeted confirmation of two generated shapes used to close development gaps

This is development confirmation evidence, not a formal hidden set.

### 4. R5 IMO-057 confirmation pack

- Manifest: `INPUTS/RDF_R5_IMO057_CONFIRMATION/evaluation_manifest.json`
- SHA256: `b8bf27ff1e0cd67b522381d569671494cc4ee8ce62ecd94e96735f027ad0f961`
- Coverage: 1 requirement, 4 graphs
- Purpose: targeted confirmation of the IMO-057 ownership correction

This is development confirmation evidence and duplicates requirement coverage present in the R2 pack.

### 5. RDF ship-graph pilot

- Manifest: `INPUTS/RDF_SHIP_GRAPH_PILOT/pilot_manifest.json`
- SHA256: `a51b816026a267dafcbea8ce5b84e58af126e8a1faf050c7631a264bc9e09158`
- Declared status: `Pilot - reviewable`
- Cases: 4; graphs: 8
- Requirement-level cases: 2
- Integrated cases: 2
- Unique requirement IDs represented across both levels: 5
- Includes hand-authored pilot SHACL alongside the RDF graphs.

The README explicitly calls this a small pilot intended for extension and human review. It is not designated as the formal hidden benchmark.

## Coverage finding

Across all candidate RDF packs, the union is only 59 unique requirement IDs before checking formal admissibility. The largest 50-requirement subset is explicitly calibration-only. No repository manifest designates a formal hidden R13 benchmark, and no formal hidden set covers all 268 eligible requirements.

The requested benchmark coverage statistics and architecture accuracy denominators therefore cannot be produced honestly from the current assets.

## Formal experiment artifacts

The generation experiments are present and remain untouched:

- FULL: ten completed formal runs
- NO SEMANTIC FEEDBACK: ten completed formal runs
- CONTEXTUAL SINGLE-SHOT: one completed formal run (`RUN_01`); `RUN_02`–`RUN_10` currently have no completed batch result

The absence of ten single-shot repetitions would make that condition preliminary even after a valid hidden benchmark exists.

## Leakage/independence checks performed

- Searches of formal experiment artifacts found no direct path/name references to the RDF fixture packs or expected-outcome keys.
- The bulk evaluator itself is deterministic and offline.
- However, formal independence is not established for the available RDF data because the 150-graph set was explicitly visible development material and influenced vocabulary/fixture/model corrections before the final R13 runs.
- Pilot and targeted confirmation packs were also created and executed during development.

The problem is not that the completed formal prompts visibly contain RDF files. The problem is that no separately frozen, withheld test set exists that can validly serve as the requested journal ground truth.

## Required next step

Before behavioral comparison, create and independently review a new formal RDF benchmark that:

1. is source-grounded and generated/adjudicated without consulting the formal model outputs;
2. is frozen and hashed before any architecture is evaluated;
3. distinguishes PASS, FAIL, boundary, missing-evidence, incorrect-unit/value, applicability, and other relevant variants;
4. covers a declared subset or all 268 requirements;
5. has expected outcomes reviewed independently of the generated shapes;
6. is never used to revise R13, prompts, pipeline behavior, or the completed formal outputs.

Once that set exists, the same offline evaluator settings and end-to-end denominator rules can be applied consistently across all three architectures.
