#!/bin/bash
set -euo pipefail
NLTL_ROOT='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
NLTL_PY='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
NLTL_PREP="$NLTL_ROOT/outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION"
NLTL_DEPS="$NLTL_ROOT/outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION/tokenizer_runtime"
# MODEL CALLS: only execute when you choose to launch the prepared main experiment.
"$NLTL_PY" -B -c 'import json,sys; m=json.load(open(sys.argv[1])); assert m["dispatch_ready"],"MAIN_NOT_READY"; print("Launching fixed shared-start development queue; at most50 inference calls.",flush=True)' "$NLTL_PREP/main_manifest.json"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$NLTL_PREP/runtime/src:$NLTL_DEPS"
export NLTL_ALLOW_MODEL_CALLS=YES
export NLTL_ENV_FILE="${NLTL_ENV_FILE:-/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env}"
exec "$NLTL_PY" -B -m nltlv2.hosted_pilot --project "$NLTL_ROOT" --manifest outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION/main_manifest.json --run-id 20261124_V0112_HOSTED_GPT_OSS_SHARED_START_MAIN_01 --allow-model-calls > "$NLTL_PREP/main_dispatch.stdout.txt" 2> "$NLTL_PREP/main_dispatch.stderr.txt"
