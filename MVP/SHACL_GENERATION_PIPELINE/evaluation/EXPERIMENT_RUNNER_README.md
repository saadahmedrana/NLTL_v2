# Frozen R13 behavioral experiment runner

This runner evaluates RUN_01 through RUN_10 generated SHACL against the frozen
268-requirement, 2,186-case systematic benchmark. Pilot 02 is not loaded: systematic input is an
explicit list of family/batch manifests, never a wildcard over every manifest.

## Scientific identity boundary

The benchmark manifest supplies the case identity, expected outcome, source ID,
source clause, RDF path, and (where present) verification mode. Six early I2
requirements have no `verification_mode` field in their frozen manifest rows;
for those rows only, the runner reads `verificationMode` from the frozen R13
dependency contract and records `verification_mode_source` accordingly.

`generation_run` is part of every manifest and ledger identity. Generated-rule
identity is not inferred from a filename, directory name, RDF
URI, or order. A deterministic manifest builder joins and verifies:

1. the configuration's frozen 268-requirement queue;
2. the run's one-row `tables/runs.csv` (`RUN_ID`, `REQUIREMENT_ID`, status);
3. `artifacts/context_pack_initial.json` (`requirement.id`, source sheet);
4. the configuration-specific artifact record and recorded SHA-256 in
   `tables/artifacts.csv`.

The source sheet is deterministically mapped to the benchmark's canonical
`source_id` and checked again at preflight. FULL selects only
`final_accepted_shape`; NO_SEMANTIC selects only a deterministic-pass
`no_semantic_validator_candidate_shape`; SINGLESHOT selects only a
diagnostic-pass `single_shot_extracted_shape`. Non-accepted pipeline outcomes
remain explicit generation errors for every affected case.

FULL and NO_SEMANTIC have populated RUN_01 through RUN_10. SINGLESHOT has a
populated RUN_01 only; RUN_02 through RUN_10 are empty placeholder directories
with no run-specific configuration files. Those absent generations are emitted
as 268 `NOT_GENERATED` manifest rows per run, never skipped or substituted.

## Commands

Run from the repository root with the project environment:

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_behavioral_evaluation.py --build-manifests-only
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_behavioral_evaluation.py --config FULL
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_behavioral_evaluation.py --config NO_SEMANTIC
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_behavioral_evaluation.py --config SINGLESHOT
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_behavioral_evaluation.py --all
```

Those commands remain RUN_01-compatible. Select another run with
`--generation-run RUN_05`. Build all 30 run/configuration manifests without
executing SHACL:

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_behavioral_evaluation.py \
  --build-manifests-only --all-generation-runs
```

Execute the complete ten-run experiment (65,580 ledger rows, including explicit
SINGLESHOT missing-generation rows):

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_behavioral_evaluation.py \
  --all --all-generation-runs --run-id BEHAVIORAL-R13-RUN01-RUN10
```

A development smoke run still performs the complete frozen-benchmark and
generated-manifest preflight:

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_behavioral_evaluation.py \
  --all --all-generation-runs --requirement I2-021 --smoke
```

Resume requires the original run ID and identical generation-run,
configuration, and case selection:

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_behavioral_evaluation.py \
  --all --all-generation-runs --run-id BEHAVIORAL-R13-RUN01-RUN10-... --resume
```

Optional development filters are `--requirement`, `--family`, and `--case` and
are accepted only together with `--smoke`. They alter selection only, never
matching semantics. Rebuild derived summaries:

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/analyze_behavioral_results.py \
  MVP/SHACL_GENERATION_PIPELINE/evaluation/experiment_results/<run_id>/raw_case_results.jsonl
```

For the named complete run above, replace `<run_id>` with
`BEHAVIORAL-R13-RUN01-RUN10`.

Run the synthetic harness tests:

```bash
MVP/.venv/bin/python3 -m unittest MVP/SHACL_GENERATION_PIPELINE/tests/test_behavioral_experiment_runner.py
```

## Outputs and interruption safety

Generated manifests are written under `evaluation/generated_rule_manifests/RUN_NN/`.
Each evaluation has `evaluation/experiment_results/<run_id>/` containing:

- `run_manifest.json`: environment, hashes, exact command and progress;
- `raw_case_results.jsonl`: authoritative append-only case ledger;
- `raw_case_results.csv`: derived convenience export;
- `validation_results.jsonl`: one expanded row per pySHACL validation result;
- `reports/<generation_run>/<configuration>/<requirement>/<case>.ttl` and `.txt`: complete
  pySHACL report graphs and report text for every executed case;
- `tracebacks/`: retained execution exceptions;
- `summaries/`: derived configuration and requirement summaries.

Multi-run summaries include aggregate configuration metrics, per-generation-run
configuration metrics, per-run requirement results, requirement stability across
runs, and within-run pairwise configuration comparisons. No inferential
statistics are introduced.

Each JSONL append is flushed and fsynced. Resume loads all existing
`generation_run + configuration + requirement_id + case_id` keys and refuses
duplicates or keys outside the selected experiment. Finalization proves
the exact expected key set and re-hashes all locked benchmark inputs.

Infrastructure outcomes have null `actual_conforms` and null
`behavioral_match`; they are never recoded as false rejects. Semantic outcomes
are `CORRECT_BEHAVIOR`, `FALSE_ACCEPT`, or `FALSE_REJECT`. Analysis reports both
accuracy among usable executions and end-to-end success including unusable
generated rules.

The pySHACL configuration is identical for all architectures: R13 ontology as
`ont_graph`, RDFS inference, meta-SHACL and advanced mode enabled; imports,
abort-on-first, infos, and warnings are disabled. The project's registered XPath
math functions are loaded exactly as in the existing evaluator.
