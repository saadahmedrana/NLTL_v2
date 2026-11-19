# Prepared pilot and iteration study — not run

Credentials stay external. The previously established external environment location is retained by the user, not copied into this project. Set `NLTL_ENV_FILE` to its external path. Required keys are `AALTO_API_KEY` and `AALTO_RESPONSES_BASE_URL` (the complete Responses endpoint, exactly as in the original client). The program does not read this file on import, configuration checks or offline tests. It refuses a credentials path inside the project. Never commit/copy the file or paste its contents into logs.

A live request requires both `NLTL_ALLOW_MODEL_CALLS=YES` and the explicit CLI flag. These commands are prepared, not executed:

```sh
export NLTL_ENV_FILE='/external/location/NLTL_v2.env'
export NLTL_ALLOW_MODEL_CALLS=YES
../NLTLv2-env/bin/python -m nltlv2 run --config configs/single_shot.json \
  --requirement TRF-010 --experiment-id PILOT_SINGLE_T010 --allow-model-calls
../NLTLv2-env/bin/python -m nltlv2 run --config configs/nltl.json \
  --requirement TRF-010 --experiment-id PILOT_NLTL_T010 --allow-model-calls
```

The selected model identifier and token settings derive from FULL_REPAIR_V2 RUN_01; current availability is unverified. The live adapter deliberately fails on provider/network errors rather than silently repeating a generation call. Full raw provider responses and finish reasons are retained. Full code and independently captured findings are checked again at dispatch. The shared initial request contains the same regulation, schema context, two examples and generation settings for both methods.

Use a new experiment ID for every run. Save submitted shape paths (relative to this project root) and original no-verdict status in a manifest such as:

```json
{"workflows":{"NLTL":{"TRF-010":{"shape":"outputs/experiments/PILOT_NLTL_T010/candidate_01.ttl","original_no_verdict":false}},"Single-shot":{"TRF-010":{"shape":"outputs/experiments/PILOT_SINGLE_T010/candidate_01.ttl","original_no_verdict":false}}},"excluded_case_ids":{"NLTL":[],"Single-shot":[]}}
```

For NLTL, use `run.json`'s first accepted `evaluation_candidate`, never an evaluation-selected candidate. No accepted candidate means NO_VERDICT: omit its shape entry or set original_no_verdict=true. For Single-shot, use its original extracted response; malformed Turtle receives no executable verdict. This manifest must reflect run history, not merely file existence. Evaluation never triggers repairs:

```sh
../NLTLv2-env/bin/python -m nltlv2 evaluate \
  --shape-manifest configs/PILOT_SUBMISSIONS.json --experiment-id PILOT_NLTL_T010
```

The prepared review queue stratifies by source, verification mode, branch indicators and structural complexity with a recorded seed, without reading scores, generated code or workflow outcomes. Only six requirements currently have defensible represented development coverage. The 50-item queue must undergo source/schema/fixture/branch/counterfactual review before it can become a study selection. The gap is 44; the study remains blocked. No automatic study dispatcher is provided that could bypass this review gate.

`configs/iteration_study.json` defines maximum six candidate attempts and budgets 2–6. Budget is not included in prompts or transition rules. Analyze common saved prefixes, select the first internally accepted candidate within each budget and assign NO_VERDICT if none was accepted. Do not score the last rejected candidate as an accepted workflow result. Auxiliary reviewer format retries are separately counted, including their tokens/runtime. Measure strict negative detection and positive acceptance separately, ordinary agreement, executable coverage/no-verdicts, unresolved attribution, regressions, acceptance by attempt, request/token use and elapsed time. Evaluate all selected prefix candidates externally, preserving original labels and common exclusions; never feed those results back into repair. Choose a budget using predeclared accuracy/cost/stability criteria, not whichever increases the advantage over Single-shot. Saved-history analysis is prepared; no real performance estimates exist yet.

Figures/tables must be stored as `results/figures/<experiment_id>/` and `results/tables/<experiment_id>/`. Shape-transformation diagnostic arms must be explicitly labelled and never combined with unchanged-shape results. Shared runtime/schema corrections must be applied identically to both methods, with a transformation ledger.
