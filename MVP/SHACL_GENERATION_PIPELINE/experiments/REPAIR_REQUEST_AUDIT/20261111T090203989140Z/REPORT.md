# FULL_REPAIR_V2 RUN_01: repair-request audit

**PASS: offline request integrity. No API calls or environment-secret loading.**

Selected explicitly by the user: `/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/CONFIGS/pipeline.full-repair-v2-run01.json`.
Config SHA-256: `a04cb8f6fc01f740106f6b8edf5ecf9b006706541b5785d7d944ab367e9d0442`.
Runner: `nltl_pipeline.orchestration.runner.PipelineRunner`. The complete resolved config, effective developer prompts and source hashes are preserved in `manifest.json`; audited source snapshots are in `source_snapshot/`.

The exact configured models, prompts and budgets were retained: four candidate attempts, up to three syntax repairs per candidate, and one explicitly labeled final fresh-regeneration escape hatch. Only outputs were isolated and Excel export disabled. No runner, prompt template or experiment config was changed.

## Verified requests

Ten successful scripted scenarios exercised **15 normal code-repair requests**:
- 8 semantic candidate repairs;
- 2 static repairs, including an unresolved canonical match that remains in feedback;
- 3 matcher-assisted repairs, from both static and semantic canonical findings;
- 2 chained syntax repairs, followed by semantic repair of the latest syntax-corrected candidate.

All 15 preserve the full preceding code, byte for byte, including a UTF-8 candidate exceeding 100 KB with head/tail canaries. Normal repairs use full extracted Turtle; syntax repairs use the entire preceding raw response because it may not parse. Each embedded hash is checked against an independently retained preceding local response, saved candidate artifact and attempt metadata—not against a hash recomputed solely from the prompt payload.

Error packets are bound to the same candidate and version. Static feedback is reconstructed from that candidate's actual saved deterministic errors; semantic feedback is reconstructed from the actual local validator response that reviewed that candidate; verified matcher resolutions are the only permitted additions. `ValidatorIssue.source` is intentionally internal metadata: the rendered seven substantive fields must match exactly, and both internal and rendered packet hashes are retained. Historical regression guards remain separately labeled, not misrepresented as current errors.

Four normal repair requests carried canonical findings. They reached matcher-assisted repair when a match was found and static repair with the unresolved finding preserved when no match was found. Datatype errors reached static repair. This tests the existing detectors/routing; **the previously recommended unit/term-kind checker is not installed by this audit**, so detector coverage must not be inferred from request-integrity success.

One actual runner-triggered `FRESH_REGENERATION_ESCAPE_HATCH` request was captured separately. Its developer/user instructions explicitly say fresh regeneration; it intentionally omits previous code. It is never credited as normal repair. Validator and matcher JSON-format retries also retained the same review candidate and are labeled auxiliary format retries, not SHACL code repair.

Complete rendered developer/user requests are saved as JSON and text under every scenario's `runner_output/complete_requests/`, as well as the real runner's original prompt artifacts. Candidate responses and feedback provenance are preserved. `normal_repair_checks.json` gives all 15 per-repair checks; `all_request_checks.csv` inventories every request, including deliberately rejected controls.

## Fail-closed dry-run controls

Five independent injections were rejected before a local response could be returned:
1. absent previous code;
2. a stale earlier candidate;
3. truncated previous code;
4. stale error feedback;
5. normal repair disguised as fresh regeneration.

An integrity failure in a normal scenario raises `RepairRequestIntegrityError` and the command exits nonzero. Failed requests remain saved. Network and environment-file access are explicitly blocked during all scenarios. **25 regression tests passed** (11 new audit tests plus 14 existing runner/prompt tests).

## Scope and concrete configuration notes

This verifies the actual selected runner/renderer at the offline client boundary. It does not claim live provider delivery, model attention or repair quality. The new guard is used by the dry-run tool; it is not silently installed into live production calls. No evaluated regulatory outputs, fixtures, labels, exclusions or verdicts were changed; all returned canaries are local synthetic responses excluded from evaluation.

The configured live output directory already exists and contains **268 prior runs**. It was not written by this audit. This config therefore does not identify an empty new experiment destination; a fresh experiment output/run identity needs to be selected explicitly before a new measured run. The offline audit outputs are isolated from it.

## Command (from MVP)

```sh
.venv/bin/python SHACL_GENERATION_PIPELINE/scripts/audit_repair_requests.py --config SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/CONFIGS/pipeline.full-repair-v2-run01.json
```

No implicit default config is allowed. Each invocation writes a new timestamped bundle. The earlier `085512525383Z` checker-development failure and earlier completed guard versions are preserved; this `090203989140Z` run is the authoritative completed request audit for the selected config.
