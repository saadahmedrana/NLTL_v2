#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON="$PIPELINE_DIR/../.venv/bin/python"
PREFLIGHT="$SCRIPT_DIR/PREPARATION/preflight_06_to_10.py"
QUEUE="$SCRIPT_DIR/QUEUES/luna_no_semantic_validator_268_frozen.json"

export PYTHONPATH="$PIPELINE_DIR/src"

if [[ "${1:-}" == "--check" ]]; then
  cd "$PIPELINE_DIR"
  "$PYTHON" "$PREFLIGHT" --check
  exit $?
fi
if [[ $# -ne 0 ]]; then
  echo "Usage: bash experiments/LUNA_NO_SEMANTIC_VALIDATOR/run_formal_06_to_10.sh [--check]" >&2
  exit 2
fi

interrupted=0
on_interrupt() {
  interrupted=1
  echo "INTERRUPTED: stopping formal continuation; no later run will start." >&2
  exit 130
}
trap on_interrupt INT TERM

cd "$PIPELINE_DIR"
declare -a completion_lines=()

for number in 06 07 08 09 10; do
  numeric=$((10#$number))
  run_name="RUN_$number"
  config="$SCRIPT_DIR/CONFIGS/pipeline.luna-no-semantic-validator-run$number.json"
  output="$SCRIPT_DIR/$run_name"

  "$PYTHON" "$PREFLIGHT" --run "$numeric" || {
    echo "$run_name PRE-RUN CHECK FAILED; stopping sequence." >&2
    exit 3
  }
  utc_start="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  local_start="$(date '+%Y-%m-%dT%H:%M:%S%z')"
  echo "$run_name START utc=$utc_start local=$local_start"

  set +e
  "$PYTHON" run_pipeline.py \
    --config "$config" \
    no-semantic-validator-batch \
    --queue "$QUEUE" 2>&1 | tee "$output/terminal.log"
  command_status=${PIPESTATUS[0]}
  set -e

  if [[ $interrupted -ne 0 || $command_status -ne 0 ]]; then
    echo "$run_name FAILED/INTERRUPTED exit_status=$command_status; stopping sequence." >&2
    exit "$command_status"
  fi
  "$PYTHON" "$PREFLIGHT" --verify-completed "$numeric" || {
    echo "$run_name COMPLETION CHECK FAILED; stopping sequence." >&2
    exit 4
  }
  utc_finish="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  local_finish="$(date '+%Y-%m-%dT%H:%M:%S%z')"
  line="$run_name COMPLETE utc=$utc_finish local=$local_finish exit_status=$command_status"
  completion_lines+=("$line")
  echo "$line"
done

echo "FORMAL CONTINUATION COMPLETE"
printf '%s\n' "${completion_lines[@]}"
