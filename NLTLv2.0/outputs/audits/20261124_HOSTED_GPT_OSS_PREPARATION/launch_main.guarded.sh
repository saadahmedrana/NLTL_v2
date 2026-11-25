#!/bin/bash
set -euo pipefail
NLTL_ROOT='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
NLTL_PY='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
NLTL_AUDIT="$NLTL_ROOT/outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION"
# Offline gate: currently exits2. No provider process is constructed if blocked.
"$NLTL_PY" -B -c 'import json,sys; m=json.load(open(sys.argv[1])); print("READY" if m["dispatch_ready"] else "BLOCKED: "+m["blocker"],flush=True); sys.exit(0 if m["dispatch_ready"] else 2)' "$NLTL_AUDIT/main_manifest.blocked.json"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$NLTL_AUDIT/runtime/src"
export NLTL_ALLOW_MODEL_CALLS=YES
export NLTL_ENV_FILE="${NLTL_ENV_FILE:-/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env}"
exec "$NLTL_PY" -B -m nltlv2.hosted_pilot --project "$NLTL_ROOT" --manifest outputs/audits/20261124_HOSTED_GPT_OSS_PREPARATION/main_manifest.blocked.json --run-id 20261124_V0110_HOSTED_GPT_OSS_SHARED_START_MAIN_01 --allow-model-calls > "$NLTL_AUDIT/main_dispatch.stdout.txt" 2> "$NLTL_AUDIT/main_dispatch.stderr.txt"
