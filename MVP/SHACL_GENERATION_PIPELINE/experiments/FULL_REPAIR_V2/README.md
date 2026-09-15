# FULL_REPAIR_V2

This experiment is isolated from historical `FINAL_LUNA_MAIN` (`FULL`),
`LUNA_NO_SEMANTIC_VALIDATOR`, and `LUNA_CONTEXTUAL_SINGLESHOT` outputs.

The architecture generates once, then repairs the immediately previous parseable
candidate with structured current issues and runner-owned regression guards. It has a
four-candidate limit and at most one final fresh-regeneration escape hatch.

Only `final/final_shape.ttl` from a `GENERATION_ACCEPTED` run is official.
`diagnostics/last_candidate.ttl` and `artifacts/attempt_XX/candidate_shape.ttl` are
diagnostic only and are excluded from generated-rule manifests.

Run a batch only after explicit approval, from `SHACL_GENERATION_PIPELINE`:

```sh
PYTHONPATH=src python3 -m nltl_pipeline --config experiments/FULL_REPAIR_V2/CONFIGS/pipeline.full-repair-v2-run01.json generate-batch --queue experiments/FINAL_LUNA_MAIN/QUEUES/luna_main_268_frozen.json
```

Replace both `run01` and the embedded `RUN_01` configuration identity for RUN_02
through RUN_10 by selecting the corresponding prepared config. Do not reuse a config
for a different run.

Build official manifests later without running generation or repair:

```sh
python3 evaluation/run_behavioral_evaluation.py --config FULL_REPAIR_V2 --all-generation-runs --build-manifests-only
```

Run read-only candidate diagnostics later:

```sh
python3 evaluation/run_full_candidate_diagnostics.py --configuration FULL_REPAIR_V2 --all-generation-runs --discover-only
```
