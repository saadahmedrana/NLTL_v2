# Reduced-benchmark readiness assessment

Read REPORT.md and summary.json. The actual snapshot scope is 157 requirements / 1,290 cases; the historical TRF-130 supplement is separately tagged. No evaluation authority pointer or original data was changed.

Environment: existing MVP `.venv`, Python 3.13.5 and rdflib 7.6.0. No setup, network or LLM calls are needed. From MVP, run the read-only checks:

```sh
.venv/bin/python evaluation_audit/reduced_benchmark_assessments/20261111T091619777906Z/test_assessment.py
```

source_inventory.py documents the complete inventory and checkpointed authoring-oracle screen; source_review.py documents fresh source/schema rules; build_report.py computes source-only retention and re-verifies the cached runner audit hashes. Screens are saved per case. Existing oracle screens must not be rerun merely to rebuild reports. No script reads generated SHACL or validation reports to select cases. These commands do not generate or validate new shapes.

proposed_selection.json and PROPOSED_frozen_case_manifest.json are proposals, not activated replacements. Full_case_ledger and per_requirement_review contain every case, not only the 553 historical negatives. No unresolved case is silently converted into an exclusion. Original authoring-oracle agreement is not labeled full source certification. Verified Table-8 cases have a generic lookup scope, including faithful NA encoding; they do not claim full physical-vessel compliance or footnote-2 coverage.

The output is versioned independently of the unchanged 553-case snapshot. Scope/count corrections supersede earlier prose only; no historical classifications are rewritten.
