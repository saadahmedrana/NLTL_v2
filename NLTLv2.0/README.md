# NLTLv2.0

An independent refinement of FULL_REPAIR_V2 RUN_01. Historical pipeline files, scores and outputs are unchanged. No generations or paid API calls were made to implement or test this project.

Run from this directory. Python 3.11+ is required; the isolated test used Python 3.13.5. All resources resolve relative to this project root. Keep the project directory when installing the code: the wheel provides code, while this directory provides the locked data/configuration bundle.

```sh
python3 -m venv ../NLTLv2-env
../NLTLv2-env/bin/python -m pip install -r requirements-lock.txt
../NLTLv2-env/bin/python -m pip install --no-deps .
../NLTLv2-env/bin/python -m nltlv2 check
../NLTLv2-env/bin/python -m nltlv2 smoke
```

`smoke` blocks socket creation/DNS/connections and never loads credentials. It saves a timestamped directory under `outputs/smoke_tests/`, including complete requests, raw scripted responses, candidates, hashes, findings, diffs and reports. A destination cannot be reused. `check` verifies configuration, mappings, snapshot counts and fixture hashes. `schema-audit` writes a fresh report under `outputs/audits/`.

**Methods.** Single-shot means one generation call, which includes the same two synthetic few-shot examples as NLTL. It has no checker, reviewer, matcher, repair or regeneration. Wrapper extraction is shared; malformed responses are retained. NLTL checks each candidate, runs source/contract-evidenced review and repairs the immediately preceding full candidate. Initial generation plus every code revision counts toward the six-candidate limit. Only reviewer JSON format retries are auxiliary; they do not generate code. Fresh regeneration is disabled. No internal evaluation scores select candidates.

**Evidence.** R13 was renamed to `schema/Schema_for_NLTL.ttl` byte for byte; ontology IRIs are unchanged. See `schema/schema_changes.json`, `docs/migration_manifest.json` and `docs/limitations.md`. The schema is not final: unresolved ownership and declaration gaps remain. Locked domains are typing assertions, never exclusive owner rules.

**Evaluation.** The preserved 553-negative snapshot spans 157 requirements. Their inventory has 1,290 cases: 606 positive and 684 negative. TRF-130's additional 12 cases are separately identified. Individual review states are retained; being in an inventory does not certify a fixture. The six-requirement development core has 37 cases (17 positive, 20 negative), with 20 intended-only repaired counterparts. It is not a representative held-out benchmark. The bundled regression checks use explicitly source-authored reference controls; their passing results do not measure automatic generation or repair quality. No historical generated shapes or output trees were copied.

The external evaluator reports ordinary agreement, positive acceptance, strict intended detection, unrelated/additional rejection, missed defects, no executable verdict and unresolved attribution separately. Unreviewed violation semantics stay unresolved. Original no-verdict outcomes cannot gain offline credit. Evaluation fixtures, labels and counterparts are never loaded by the generation/repair modules. Approved internal runtime probes contain only schema-derived synthetic empty targets; conformance of those probes is ignored.

Mappings are in `mappings/requirement_mapping.xlsx`, with JSON/CSV sources and a data dictionary. Empty fixture references explicitly mean not bundled. Every core input required for offline tests is bundled.

Prepared commands for later work (not executed):

```sh
# Prepare a performance-blind review queue; does not start a study.
../NLTLv2-env/bin/python -m nltlv2 prepare-study
# After a separately authorized live pilot: see docs/later_pilot.md.
# Analyze saved histories only; never selects candidates using evaluation scores.
../NLTLv2-env/bin/python -m nltlv2 analyze-budgets \
  outputs/experiments/PILOT_ID/run.json --experiment-id PILOT_BUDGET_ANALYSIS
```

Only six development requirements are presently ready; the gap to 50 is 44. The prepared queue is not a certified selection. External credentials configuration, isolation reproduction and checker limits are documented under `docs/`.
