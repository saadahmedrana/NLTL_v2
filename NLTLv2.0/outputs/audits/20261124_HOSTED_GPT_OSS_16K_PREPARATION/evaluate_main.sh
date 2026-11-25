#!/bin/bash
set -euo pipefail
NLTL_ROOT='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
NLTL_PY='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
NLTL_PREP="$NLTL_ROOT/outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION"
NLTL_DEPS="$NLTL_ROOT/outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION/tokenizer_runtime"
# OFFLINE: separate phase; refuses missing dispatch closure or overwriting evaluation.
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$NLTL_PREP/runtime/src:$NLTL_DEPS"
"$NLTL_PY" -B "$NLTL_ROOT/evaluation/evaluate_hosted_shared_start.py" --project "$NLTL_ROOT" --run-id 20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01
# Preserve a separately named main summary under results; never overwrite prior results.
cp -n "$NLTL_ROOT/outputs/experiments/20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01/evaluation/selected_results.json" "$NLTL_ROOT/results/hosted_gpt_oss_v0112_main_selected_results.json"
