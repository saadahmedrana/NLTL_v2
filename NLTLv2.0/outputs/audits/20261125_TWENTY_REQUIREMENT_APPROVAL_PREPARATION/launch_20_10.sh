#!/usr/bin/env bash
set -euo pipefail
cd '/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
R="$PWD"
A="$R/outputs/audits/20261125_TWENTY_REQUIREMENT_APPROVAL_PREPARATION"
PY='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
export PYTHONPATH="$R/src:$R/outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION/tokenizer_runtime"
export NLTL_ENV_FILE="${NLTL_ENV_FILE:-/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env}"
export NLTL_ALLOW_MODEL_CALLS=YES
"$PY" "$A/seal_preparation.py" --check-only
MASTER="$R/outputs/experiments/20261125_20_10_SHARED_START_01"
test ! -e "$MASTER"
test -f "$A/experiment.dispatch.json"
while IFS=$'\t' read -r model rid manifest runid; do test ! -e "$R/outputs/experiments/$runid"; done < "$A/jobs.tsv"
mkdir -p "$MASTER/logs"
cp "$A/experiment.dispatch.json" "$MASTER/manifest.frozen.json"
finish() { "$PY" "$A/queue_receipt.py" "$MASTER"; }
trap finish EXIT
SECONDS=0
count=0
while IFS=$'\t' read -r model rid manifest runid; do
  if (( 18000 - SECONDS < 600 )); then echo 'STOP: insufficient remaining dispatch allocation; remaining entries NOT_RUN'; break; fi
  echo "START $((count+1))/30 model=$model requirement=$rid done=$count in_progress=1" | tee "$MASTER/progress.txt"
  "$PY" -u -m nltlv2.hosted_pilot --project "$R" --manifest "$manifest" --run-id "$runid" --allow-model-calls 2>&1 | tee "$MASTER/logs/$runid.log"
  "$PY" "$A/check_pair_closure.py" "$runid" "$rid"
  count=$((count+1))
  "$PY" "$A/queue_receipt.py" "$MASTER"
  echo "DONE $count/30 in_progress=0" | tee "$MASTER/progress.txt"
done < "$A/jobs.tsv"
