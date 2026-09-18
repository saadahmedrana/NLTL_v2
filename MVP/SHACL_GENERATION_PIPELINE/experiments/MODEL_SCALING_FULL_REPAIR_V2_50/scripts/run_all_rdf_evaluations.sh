#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--scope" || ( "${2:-}" != "smoke" && "${2:-}" != "final" ) || "$#" -ne 2 ]]; then
  echo "Usage: $0 --scope smoke|final" >&2
  exit 2
fi

scope="$2"
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../../../../../" && pwd)"
python_bin="$repo_root/MVP/.venv/bin/python"
runner="$script_dir/run_rdf_evaluation.py"

for mode in SELF_REPAIR_FINAL FIRST_GENERATION; do
  for model in luna sol gemini gpt_oss; do
    "$python_bin" "$runner" --scope "$scope" --mode "$mode" --model "$model"
  done
done
