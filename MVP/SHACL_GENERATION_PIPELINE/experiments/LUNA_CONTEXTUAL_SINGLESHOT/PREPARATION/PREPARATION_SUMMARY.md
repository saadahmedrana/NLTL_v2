# LUNA_CONTEXTUAL_SINGLESHOT preparation summary

## Outcome

The contextual single-shot ablation is implemented and smoke-tested. Formal RUN_01 through RUN_10 have not been started.

The ablation reuses the full pipeline's R13 context loading, scoped vocabulary, dependency contract, node/path information, formula/table context, few-shot retrieval, prompt factory, generator instructions, Luna model and generator settings. It makes one logical generator call, stores the response text, and then performs read-only extraction and deterministic diagnostics. It never calls the semantic validator, vocabulary matcher or syntax-repair model, and never regenerates.

## Integrity

- `experiments/FINAL_LUNA_MAIN/`: unchanged
- `FINAL_LOCK_R13`: unchanged
- Frozen queue: 268 unique IDs, byte-identical copy
- First request: byte-identical to the stored formal FULL-pipeline prompt for `IMO26-014`
- Full offline regression suite: 113 tests, PASS
- Full R13 doctor: PASS

## Smoke test

The one authorized development call used `IMO26-014` and Luna. It made one generator call and zero downstream LLM calls. Extraction, Turtle parsing, deterministic SHACL validation and vocabulary diagnostics all passed. The response and all diagnostic artifacts were retained under `SMOKE_TEST/`.

## Formal RUN_01 command (not executed)

```bash
cd "/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/SHACL_GENERATION_PIPELINE" && ../.venv/bin/python run_pipeline.py --config experiments/LUNA_CONTEXTUAL_SINGLESHOT/CONFIGS/pipeline.luna-contextual-singleshot-run01.json contextual-single-shot-batch --queue experiments/LUNA_CONTEXTUAL_SINGLESHOT/QUEUES/luna_contextual_singleshot_268_frozen.json
```

## Methodological boundaries

- `SINGLESHOT_CAPTURED_DIAGNOSTIC_PASS` means the unmodified output passed deterministic harness checks; it is not semantic-validator acceptance and not hidden-RDF accuracy.
- The saved raw artifact is the exact model output text extracted from the Responses API envelope, matching the existing full-pipeline `generator_raw.txt` convention. The HTTP JSON envelope itself is not persisted.
- Existing transport retry behavior is preserved for infrastructure reliability. The architecture permits one logical generator call per requirement; telemetry separately records physical transport attempts. The smoke test required one physical attempt.
