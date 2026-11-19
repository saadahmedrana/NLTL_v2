# v0.6.0 source-grounded refactor

The active pipeline uses original regulatory source, unchanged ontology/registry and representation-only mappings. No handwritten solution profiles, compliance witnesses, expected verdicts, gold examples or bespoke change permissions are production inputs. Single-shot makes one generation call; NLTL adds general deterministic checks, execution-only probes and evidence-quoted source/schema review with bounded targeted repair. Both initial requests/settings are identical. Evaluation runs separately.

## Recovery and preservation

Git revision and pre-refactor working/index changes are recorded in this audit. User edits were not reset; no commit or whole-project backup was created. A 23,416-byte selective archive and byte-identical historical copies support recovery via `recovery_index.json`. All 5,892 original output files and relocated materials were hash-verified unchanged. Original ontology, registry, quantity context, requirement records and source documents were preserved. Historical scores were not recomputed or edited.

## Exact cleanup accounting

See `cleanup_ledger.json` for every path, reason, bytes and SHA-256. Initial cleanup deleted 82 obsolete files/cache entries (620,774 bytes); post-install cache cleanup removed 120,251 further bytes. Total gross file bytes deleted: **741,025**. Forty files (7,898,911 bytes) were relocated, not counted as space freed. Added implementation, recovery and verification reports consume space; this is not a claim that overall project footprint fell by the gross deletion amount.

Removed production modules: `development_checks`, `constraint_changes`, `enumerations`, `preflight`, `replay`, `replay_changes`, `mappings` and the installed evaluator. General reusable checks remain. Old seeded diagnostic, paired-study and preparation configurations, bespoke permission policy, duplicated smoke inputs and build caches were removed. The independent evaluator is now under `evaluation/`, not installed/imported by production.

Legacy witnesses and curated examples each have one active test-only copy under `tests/data/`. Mixed source-preparation indexes, earlier profiles and controlled-value annotations are provenance-only; schema bindings contain only terms, owners, target owner and model paths. Earlier workbook/catalogs and documentation were relocated unchanged to clearly historical folders. Uncertain workbook preview and inspection files were retained and listed in the ledger. Immutable historical snapshots may still contain their original copies.

## Verification

61 offline software tests passed with no failures/errors. A novel synthetic requirement completed the production route without a solution profile, with reads of evaluation/test/witness data denied. Scripted tests verify source-grounded changes, exact latest-code packets, conflicting feedback, explicit uncertainty, finding reconciliation, bounded attempts, one-call Single-shot and identical initial settings. The saved nested SELECT error is detected and valid query controls pass. A separate process passed 17 positive and 20 strict negative reference controls plus all 20 repaired counterparts (37 cases, six requirements). These are software/reference controls, not measured automatic repair performance. The portable test-default adjustment was rechecked with all 61 tests; unchanged external controls were not rerun. Installed/source Python modules are byte-identical, and retired modules are absent. No network/model calls or credential reads occurred.

## Required inputs and limitations

See `docs/new_regulation_inputs.md`: unique ID/citation/clause, verbatim source and authoritative supporting documents, declared vocabulary/datatypes/units, optional evidenced representation mappings, and shared configuration. No answer or expected verdict is required.

Grounded quotes do not prove the reviewer's interpretation. Regulatory completeness, arithmetic/branch correctness and semantic equivalence are not generally proved. Unknown schema/applicability stays unresolved; complex unsupported SPARQL is not certified. Full source documents can be large and may need source-based curation before live use. Resource isolation is a trusted-code capability with an offline filesystem-denial test, not an OS sandbox for malicious Python. No live v0.6.0 model quality is established. Removing curated solution examples changes comparability; do not pool with historical pilots. The 50-requirement study was not resumed.

Offline commands from the active folder:

```sh
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . check
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . smoke
```

Representative complete scripted repair packet: `outputs/smoke_tests/20261119T_V060_PORTABLE_TEST_DEFAULTS/source_grounded_repair_representative/`.
