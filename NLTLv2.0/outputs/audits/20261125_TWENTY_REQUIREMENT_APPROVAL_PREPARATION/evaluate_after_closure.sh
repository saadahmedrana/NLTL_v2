#!/usr/bin/env bash
set -euo pipefail
cd '/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0'
R="$PWD"
A="$R/outputs/audits/20261125_TWENTY_REQUIREMENT_APPROVAL_PREPARATION"
PY='/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2-env/bin/python'
export PYTHONPATH="$R/src"
unset NLTL_ALLOW_MODEL_CALLS
MASTER="$R/outputs/experiments/20261125_20_10_SHARED_START_01"
"$PY" -c 'import json,sys; p=json.load(open(sys.argv[1])); assert p["all_started_dispatches_closed"] is True' "$MASTER/queue_status.json"
while IFS=$'\t' read -r model rid manifest runid; do
  if test ! -d "$R/outputs/experiments/$runid"; then echo "NOT_RUN $model $rid (planned denominator retained in queue manifest)"; continue; fi
  echo "OFFLINE EVALUATION $model $rid"
  "$PY" "$R/evaluation/evaluate_hosted_shared_start.py" --project "$R" --run-id "$runid"
done < "$A/jobs.tsv"
