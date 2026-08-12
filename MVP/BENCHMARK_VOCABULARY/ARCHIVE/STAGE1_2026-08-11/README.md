# Stage 1 historical archive

Archived: 2026-08-12  
Historical stage date: 2026-08-11  
Status: superseded by the locked Stage 2 vocabulary `2.1.0-stage2`

## Preserved contents

- `workbooks/` — original, revised, and naming-audited Stage 1 workbooks.
- `reports/` — corresponding Stage 1 reports and naming audit.
- `exports/` — historical CSV exports from the three Stage 1 iterations.
- `tools/` — historical Stage 1 construction and inspection scripts plus their dependency symlink.

## Workbook checksums

- `benchmark_vocabulary_stage1.xlsx` — `ebf8655c1edfc60cf442acf6403bf955b7900b772f163d09fcf43707fd2773d3`
- `benchmark_vocabulary_stage1_naming_audited.xlsx` — `394fddd7e975eb1f64f4dc31066a6d7be4fd7c941bbfa59f0d4cb0ce2e369a9f`
- `benchmark_vocabulary_stage1_revised.xlsx` — `a15c9c804bef4c3297501ef8e66fe99a926232fd76af2362b63fd8a08cdfe782`

## Cleanup treatment

Large generated `.inspect.ndjson` dumps, workbook preview PNGs, Excel temporary lock files, and Python caches were not archived because they are reproducible QA by-products rather than research inputs or controlled deliverables.

These files are retained for provenance only. The current vocabulary and pipeline must use the locked Stage 2 assets documented in `../../README.md`.
