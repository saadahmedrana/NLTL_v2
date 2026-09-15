# FULL candidate-trajectory diagnostics

This evaluator is read-only and diagnostically separate from the official
behavioral experiment. It never changes or replaces the FULL artifact selected
by the official runner. A requirement whose pipeline status is not
`GENERATION_ACCEPTED` remains an official generation failure even when a
preserved rejected candidate is behaviorally exact.

## Discovery authority

Candidate identity and attempt number come from each FULL run's
`tables/artifacts.csv` `candidate_shape` records. The evaluator verifies the
recorded run ID, requirement ID, path, byte-presence, and SHA-256 before use.
It enriches each candidate with:

- deterministic results from `tables/validation.csv` and the recorded
  `deterministic_validation` JSON artifact;
- semantic-validator reachability from a recorded `validator_raw_response`;
- validator decision and feedback from `tables/iterations.csv`, falling back to
  the preserved validator JSON only when the iteration row is unavailable;
- official acceptance only when the run was accepted, the validator accepted
  that attempt, and its hash equals the recorded `final_accepted_shape` hash.

No attempt is reconstructed. Each requirement-run inventory records preserved
attempt numbers and gaps. The current frozen histories contain 5,155 candidates
and no internal attempt-number gaps; 43 requirement-run histories contain no
candidate graph.

## Execute

From the repository root:

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_full_candidate_diagnostics.py \
  --all-generation-runs \
  --diagnostic-run-id FULL-CANDIDATES-RUN01-RUN10
```

Resume the same immutable selection with:

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_full_candidate_diagnostics.py \
  --all-generation-runs \
  --diagnostic-run-id FULL-CANDIDATES-RUN01-RUN10 \
  --resume
```

Discovery without pySHACL execution:

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_full_candidate_diagnostics.py \
  --all-generation-runs \
  --discover-only \
  --diagnostic-run-id FULL-CANDIDATE-DISCOVERY
```

Development filters require `--smoke`, for example:

```bash
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/run_full_candidate_diagnostics.py \
  --generation-run RUN_01 --requirement I2-001 --smoke
```

## Outputs

Outputs are confined to
`evaluation/candidate_diagnostics/<diagnostic_run_id>/`:

- `diagnostic_run_manifest.json`
- `full_candidate_manifest.jsonl`
- `requirement_candidate_inventory.jsonl`
- `full_candidate_case_results.jsonl` (authoritative case ledger)
- `reports/<generation_run>/<requirement>/<attempt>/<case>.ttl` and `.txt`
- `tracebacks/`
- `summaries/candidate_summary.jsonl` and `.csv`
- `summaries/validator_confusion_candidates.csv` and summary JSON
- `summaries/repair_transitions.csv` and summary JSON
- `summaries/aborted_requirements.csv` and summary JSON

The ledger key is `generation_run + requirement_id + attempt_number + case_id`.
All candidates use the same frozen cases and pySHACL configuration as the
official experiment. Candidate exactness means every frozen case for that
requirement executed and matched its frozen expected result.

Validator confusion statistics include only candidates that both reached the
semantic validator and completed all behavioral cases. Infrastructure failures
are reported as unscorable, not relabeled as behaviorally wrong. Repair
transitions are classified only between consecutive preserved attempt numbers.

"Aborted" means any official FULL status other than `GENERATION_ACCEPTED`; the
summary separately counts `MAX_ATTEMPTS_REACHED` iteration-limit aborts and
breaks all aborts down by pipeline status.

