# Implementation verification

Implemented in NLTLv2.0 without changing the old pipeline or historical scores.

- 43 offline control tests passed after installation in a separate temporary copy.
- Original repository and external credentials directory were inaccessible under an OS sandbox; network was denied during isolated install and tests.
- 37 development regression cases passed independent source-authored controls: 17 positives accepted; 20 intended negatives rejected and their 20 repaired counterparts accepted. These are reference-control results, not automatic repair quality.
- Configuration, mappings, snapshot counts, resource paths, schema/fixture hashes and workbook integrity passed.
- Full latest-code repair packets, raw diagnostics, response normalization, semantic routing, conflict stops, format retries, regression detection and no-verdict handling were exercised using scripted responses.

Representative complete packets:
- outputs/smoke_tests/20261111T104800834414Z_isolated/test_exact_syntax_and_latest_repair/request_002.rendered.txt
- outputs/smoke_tests/20261111T104800834414Z_isolated/test_semantic_findings_reach_targeted_route/request_003.rendered.txt
- outputs/smoke_tests/20261111T104800834414Z_isolated/test_chained_latest_full_candidate/request_003.rendered.txt

Open issues: 44 additional development requirements need full case/branch/repair review before a 50-requirement study; six missing explicit ontology property-kind declarations and 840 unbound requirement/property occurrences need evidence-based review; TRF-002's earlier-date source exception remains a context blocker. General SPARQL/path equivalence and automatic regulatory reasoning are not proven. No live endpoint/model availability or automatic repair benefit has been tested.

R13 RDF is byte-identical. No exclusions, fixture labels or historical verdicts changed. No paid/model generations, scaling runs or full experiments occurred.

See docs/later_pilot.md for prepared commands and docs/isolation.md for isolation reproduction.
