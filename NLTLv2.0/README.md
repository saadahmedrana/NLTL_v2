# NLTLv2.0 v0.6.0 — source-grounded pipeline

This is a forward refactor. The tested parsing, canonical/type/unit checks, SPARQL analysis, latest-code feedback, request integrity, diagnostics, diffs, issue tracking and bounded retries are retained. Production does not load regulatory solution profiles, expected verdicts, behavioral witnesses, gold shapes or bespoke change permissions. No model calls were made for this refactor.

**Flow.** Both methods receive the same original source documents and declared schema/mappings, with the same generation settings. Single-shot makes one generation request and only extracts its original response. NLTL checks a candidate, probes only local execution on schema-derived empty targets (ignoring conformance), then performs source/schema semantic review. A repair receives the full latest code/version/hash and original diagnostics. Subsequent reviews inspect both candidates, account for every structural change and reconcile prior issues. Source-backed removal of an excessive restriction is permitted through review; an old constraint is not automatically required. Model interpretations are labelled as such, never independently verified facts. Material uncertainty stops the loop. A model ACCEPT is not proof of regulatory correctness.

The initial request includes no handwritten SHACL examples. Curated examples and legacy witnesses remain test-only. This changes the experimental setup; do not pool v0.6.0 results with historical versions.

## Offline verification

From this folder, using the existing environment:

```sh
../NLTLv2-env/bin/python -m nltlv2 --project . check
../NLTLv2-env/bin/python -m nltlv2 --project . smoke
```

`smoke` runs scripted local responses with real checks and a novel requirement without a solution profile. Network calls are blocked; no credentials are loaded. The 37-case/20-counterpart source-authored external reference-control suite runs in a separate process afterward. Its success measures the independent evaluator controls, not automatic generation quality. Results go to a fresh `outputs/smoke_tests/<run_id>/` directory. Existing destinations cannot be overwritten.

Dependencies remain pinned in `requirements-lock.txt`; Python 3.11+ is required. Install code with `../NLTLv2-env/bin/python -m pip install --no-deps .` after dependencies/build tools are available. Keep this project directory: installed code uses its relative source/schema resources.

## A new regulation

See [required inputs](docs/new_regulation_inputs.md). Add an ID, source citation/clause, exact regulatory excerpt and authoritative source file under `data/requirements/`. Supply supporting source files when cross-references matter. The shared ontology and datatype/unit metadata must declare the vocabulary. Optional representation mappings select terms and declare owners/paths; they must not encode regulatory formulas, limits, applicability algorithms or expected verdicts. No per-requirement Python function or gold SHACL is required.

The source catalog resolves existing source titles to retained original documents. Full documents are supplied unless the input set itself is carefully curated; they can be large. Missing source or a hash mismatch prevents dispatch. Unknown mappings and unsupported constructs remain uncertain; there is no fallback owner `ship`.

## Operational limits

`configs/nltl.json`: at most six candidates including the initial generation, first internal acceptance, no fresh regeneration. Format retries apply only to reviewer JSON and are counted separately. `configs/single_shot.json`: exactly one generation request and no review/repair. Real provider use still requires the external environment location, `NLTL_ALLOW_MODEL_CALLS=YES`, and explicit `--allow-model-calls`. Nothing here dispatches those calls. External credentials are never copied or read by offline checks.

Independent evaluation code, fixtures, labels and counterparts stay under `evaluation/` and are denied to generation resources. Test witnesses are under `tests/data/` and also denied. Mapping catalogs, historical source-preparation material and past outputs cannot be read through the generation capability. `GenerationProject` is a trusted-code resource boundary, not an OS sandbox for arbitrary untrusted Python.

Historical experiments and their snapshots/reports remain unchanged under `outputs/`. Earlier documentation is labelled historical under `docs/history/`; earlier workbook/catalog material is preserved under `mappings/historical_v050/`. Those are evidence, not alternate production modes. Seeded/preflight/study dispatch configs and test-guided runtime modules were removed. The 50-requirement preparation was not resumed.

See [architecture and coverage](docs/source_grounded_architecture.md) and the new refactor audit under `outputs/audits/` for the recovery patch, selective recovery archive, dependency audit, exact cleanup ledger, space accounting and verification.
