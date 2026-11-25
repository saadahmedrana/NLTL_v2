# NLTLv2.0 v0.10.0 — focused source-grounded review and repair

The production route retains source/schema-only inputs, approved common research scope, canonical quantity/type/unit/path context, activation checks, immutable latest candidates and bounded review/retrieval/repair. Single-shot uses the identical initial context/settings and makes one generation call. Evaluation stays separate and now requires dispatch closure bound to frozen selection and candidate hashes.

Review protocol 2 uses concise request-local evidence IDs and candidate-bound line/character ranges. The server maps evidence to immutable content/provenance hashes and extracts exact code. Source quotations remain exact when asserted; valid citations do not prove a model interpretation. Packets carry code and relevant evidence once. Format retries add feedback to the unchanged packet and never register failed-review issues. One change-group assessment covers removal/replacement.

Generic Meta-SHACL validates the submitted graph against built-in structural shapes without executing submitted queries. SPARQL checks use actual standard/custom-validator pre-binding context. Property paths and numeric-operand traversals have distinct roles. No requirement-specific solution, compliance witness, bespoke repair permission or regeneration was introduced.

See [implementation, 17-item ledger, packet sizes and limitations](outputs/audits/20261124_FOCUSED_SIMPLIFICATION/REPORT.txt), [machine-readable verification](outputs/audits/20261124_FOCUSED_SIMPLIFICATION/verification.json), and [complete representative packets](outputs/audits/20261124_FOCUSED_SIMPLIFICATION/software_packets/complete_review_retry_repair_recheck/). This is offline software evidence, not new model or comparative-performance evidence. Historical candidates, runs, scores, fixtures, ontology, approved scope and tracker remain unchanged.

Offline checks from this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src ../NLTLv2-env/bin/python -B -m nltlv2 --project . check
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src ../NLTLv2-env/bin/python -B -m nltlv2 --project . smoke --skip-core
```

The prepared exact-seed development continuation is [offline-only and undispatched](outputs/audits/20261124_FOCUSED_SIMPLIFICATION/prepared_continuation/continuation_config.json): zero initial generations, at most one repair/two candidates, four primary reviews, one format retry per review, two retrieval rounds and early acceptance. Normal generation CLI rejects this offline specification. No new live continuation executor was added. Future authorization is separate; all preparation uses existing production routes with no model transport.

## v0.10.1 reviewer-error routing correction

The property/path validator is unchanged. A proven internal pairing inconsistency can use the existing shared response-correction allowance; unknown paths and genuine representation contradictions remain blocking. Candidate/request integrity failures stay terminal. Comparisons can explicitly pair each operand with its own declared property/path/role. Invalid reviewer proposals never become accepted issues or repair feedback. See [offline routing verification and unchanged-response replay](outputs/audits/20261124_REVIEWER_ROUTING/REPORT.txt). The prior 17-item retention ledger and historical v0.10.0 run remain unchanged. The next continuation is prepared only, with no model transport or authorization.
