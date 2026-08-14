# Batch 02 — Remaining 190 readiness

Generated: 2026-08-13T09:12:53.389512Z

## Scope

- Active development vocabulary: `VOCAB-DEV-2026-08-13-BATCH01-R8.1-POSTCONFIRMATION`
- Generation-eligible requirements: 240
- Batch 01 exclusions: 50
- Remaining queue: 190
- Ready without flags: 190
- Ready with review flags: 0
- Blocked: 0

`READY_WITH_REVIEW_FLAGS` is not a confirmed vocabulary gap. It means the static audit found either a cross-owner relationship without a one-hop path or a quantity without one fixed recommended unit; both can be legitimate and must be interpreted per requirement.

## Safe launch

Run from `SHACL_GENERATION_PIPELINE` and explicitly select the R8.1 development configuration:

```bash
../.venv/bin/python run_pipeline.py --config config/pipeline.dev-batch01.json generate-batch --queue ../INPUTS/DEVELOPMENT_CALIBRATION/BATCH_02_REMAINING_190/generation_queue.json
```

The queue embeds the R8.1 development vocabulary ID. The pipeline will abort before API calls if a different vocabulary is active.
