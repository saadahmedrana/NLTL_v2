# Isolated loop-defect investigation

Start with RECOMMENDATION.md; REPORT.md gives family counts, trace evidence and diagnostic limitations. These files do not supersede the authoritative measured audit.

Environment is the existing MVP `.venv`: Python 3.13.5, rdflib 7.6.0, pyshacl 0.31.0. No installation or API access is required. From the MVP workspace, run the read-only checks:

```sh
.venv/bin/python evaluation_audit/loop_defect_investigations/20261111T000135001516Z/test_investigation.py
```

The isolated scripts document scanning and diagnostics. Completed validations are fingerprint-checkpointed in diagnostics/; do not rerun setup merely to reproduce unchanged outputs. `diagnose.py run` uses the saved jobs and caches. `build_results.py` only reads cached results and metadata. No pipeline modules are changed or automatically imported into generation.

Source/contract evidence predates and is independent of generated constraint semantics. Diagnostic repairs were chosen using development evidence. Never use this directory’s fixtures, reports, labels, case IDs or recovery results as generator/repair inputs. The source-approved witness proposal must build fresh synthetic witnesses from independently approved contracts, never copy evaluation fixtures.

The scope-and-additional-power arm has no approved requirement-specific owner for the omitted operand. It is provisional sensitivity evidence, not a certified repair, and is excluded from strict gain counts. Main records and scores are unchanged.
