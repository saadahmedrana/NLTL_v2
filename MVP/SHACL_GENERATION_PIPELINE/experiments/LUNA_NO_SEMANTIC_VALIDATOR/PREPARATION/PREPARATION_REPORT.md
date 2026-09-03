# LUNA_NO_SEMANTIC_VALIDATOR preparation report

## Outcome

The isolated ablation implementation and all offline checks pass. Formal execution has not started. The required development mini-test was attempted but could not reach the model because the gateway returned persistent 403/401 responses; it remains incomplete and must be rerun after credentials/access are restored.

## Operational definition

The condition retains the identical first generator input and the FULL pipeline's independent syntax-only repair route. It removes semantic-validator calls, semantic ACCEPT/REVISE feedback, matcher calls (which have no independent trigger), and semantic generator attempts 2–4. Deterministic checks classify the final syntax-usable candidate but do not trigger regeneration and do not claim semantic acceptance.

## Equivalence and safety

- First-call equivalence: PASS, byte-identical for IMO26-014; SHA256 `f2a5e27eb8cad09e70830390e9648ff8ff3680fa857690e8222148e3f6e50d08`.
- Frozen queue equality: PASS; both files SHA256 `d6b540573dd7b6af5c59e369b2f37b86a864eefd81ea44ef49f137af07bd7331`.
- Full regression suite: PASS, 119/119.
- Contextual-single-shot regression: PASS, 4/4.
- New ablation tests: PASS, 6/6.
- R13 doctor: PASS, 268 eligible.
- Formal preflight: PASS with zero API calls; five output directories empty.
- `FINAL_LUNA_MAIN` and `LUNA_CONTEXTUAL_SINGLESHOT` were not written, renamed, cleaned, or regenerated.

## Mini-test blocker

IMO-088 began one logical generator call. Ten physical attempts returned five 403 and five 401 responses. No generator response, token usage, cost, extraction, parsing, or deterministic result exists. TRF-081 and TRF-012 did not start. The interrupted artifacts are retained under `MINI_TEST`; no formal directory was touched.

Do not treat this transport failure as model or requirement performance. Complete the three-case mini-test before starting formal repetitions.

## Formal launcher

The launcher is prepared and its `--check` mode passes:

```bash
bash experiments/LUNA_NO_SEMANTIC_VALIDATOR/run_formal_01_to_05.sh --check
```

After the development mini-test completes successfully, the single formal command will be:

```bash
bash experiments/LUNA_NO_SEMANTIC_VALIDATOR/run_formal_01_to_05.sh
```

It runs sequentially, stops on batch-level interruption/nonzero exit, preserves ordinary requirement-level failures, refuses nonempty/completed outputs, verifies the queue before every run, and never proceeds after Ctrl+C.
