# GPT-5.6 Sol frozen R13 behavioral evaluation

This preparation selects only batch session `SESSION-BATCH-20260823T232935794597Z`, whose
recorded generator model is `gpt-5.6-sol-2026-07-09`. The immutable manifest contains all
268 frozen R13 requirements: 250 retained accepted final artifacts and 18 explicit generation
errors. Failed generations are evaluated as unavailable/no-verdict cases; no candidate output
is substituted.

The wrapper verifies the manifest, source configuration, selected per-requirement metadata,
recorded API-call models, authoritative RUN_01 settings, ontology, and frozen 2,186-case
benchmark before execution. It refuses to overwrite the fixed Sol-specific result directory.

Run from the repository root:

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/sol_r13_gpt56/run_sol_r13_behavioral.py
```

For validation without running behavioral cases, add `--preflight-only`.
