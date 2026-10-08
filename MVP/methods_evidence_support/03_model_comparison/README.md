# FULL_REPAIR_V2 50-requirement model scaling

This experiment freezes one metadata-only, stratified R13 sample and compares the
existing Luna `RUN_01` reference with three new provider runs. Smoke outputs live
under `OUTPUTS/SMOKE` and are never read by the final generation, RDF, or summary
scripts. Final outputs are append-only/resumable at the requirement level: once a
requirement has a control-ledger row, including a rejection or exception, resume
does not replace it.

The frozen sample is 20 `DIRECT_STATIC`, 15 `DIRECT_CALCULATION`, and 15
`COMPLEX_READINESS`. The summary reports the raw 50-requirement sample and
post-stratified estimates using benchmark weights 190/268, 41/268, and 37/268.

## Preconditions

Run commands from `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2`. Export
`AALTO_AI_API_KEY` privately in the current shell; do not put it in a command
history, config file, log, or commit. Also export the two endpoint variables from
the experiment specification. None of the scripts prints or persists the key.

## Commands, in order

The first three commands each make one minimal provider call. All generation and
RDF commands after them are explicit and are not invoked by connectivity checks.

```bash
MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/experiment.py connectivity --model sol
MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/experiment.py connectivity --model gemini
MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/experiment.py connectivity --model gpt_oss

PYTHONPATH=MVP/SHACL_GENERATION_PIPELINE/src MVP/.venv/bin/python -m unittest MVP/SHACL_GENERATION_PIPELINE/tests/test_provider_formats.py MVP/SHACL_GENERATION_PIPELINE/tests/test_api_client.py

MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/experiment.py generate --model sol --scope smoke
MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/experiment.py generate --model gemini --scope smoke
MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/experiment.py generate --model gpt_oss --scope smoke

MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/experiment.py generate --model sol --scope final
MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/experiment.py generate --model gemini --scope final
MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/experiment.py generate --model gpt_oss --scope final

MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/extract_luna_subset.py
MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/run_rdf_evaluation.py --model all
MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/summarize.py
MVP/.venv/bin/python MVP/SHACL_GENERATION_PIPELINE/experiments/MODEL_SCALING_FULL_REPAIR_V2_50/scripts/build_manual_audit_packets.py
```

The RDF command runs only the frozen cases mapped to the selected 50 requirements,
using the authoritative R13 execution module and its RDFS, ontology-inoculation,
and pySHACL settings. Missing or rejected generated artifacts become explicit
no-verdict rows for every mapped case.

## Provider compatibility boundary

The Chat Completions adapter maps the existing pipeline developer instruction to
the OpenAI-compatible `system` message role and uses `max_tokens`, as required by
the configured Aalto chat endpoint. Usage is retained when returned and normalized
from `prompt_tokens`/`completion_tokens`; absent gateway usage remains absent/zero
in aggregate reporting. The adapters intentionally do not add provider-specific
sampling parameters, JSON modes, or prompt changes.
