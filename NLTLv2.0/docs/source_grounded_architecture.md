# Architecture, trust and coverage

## Production dependency boundary

`Runner → Schema (original source + ontology + representation metadata), checks, SPARQL analysis, change_review, requests, Tracker, transport`.

There is no import or resource dependency on the former development oracle, enumeration-answer gate, permission engine, per-regulation source-solution profile, preflight/study selector or evaluation module. The original mixed R13 requirement index is retained as provenance; only term associations, explicit owners/paths and target declarations were migrated. Verified representation edges were retained, without transferring law constants, formulas, active-term pruning, applicability interpretations or pass/fail logic. Full original source documents supply regulatory content.

## Checks and review

General checks retain exact parser logs, canonical namespaces/term kinds, declared datatypes and quantity units, supported complete paths and SPARQL parsing/projection/binding analysis. Unit conversion and unresolved ownership are not guessed. Numeric RDF-term identity is a source-review notice, not a per-regulation equality oracle. Explicit subclass-compatible paths use declared hierarchy and mapping edges. Complex SPARQL path attribution remains limited; static warnings are not confirmed failures.

Generic empty-target probes check whether generated SHACL executes locally, ignoring conformance. They are not behavioral tests with expected verdicts. External SERVICE/dataset access is blocked; JavaScript/rule execution is outside the supported validation scope and is reported as unresolved rather than silently ignored. Supported parser/engine errors are repairable within the attempt budget; infrastructure, integrity, uncertain resource and schema-review conflicts stop dispatch.

Semantic review compares original source, current candidate and schema. On revisions it also receives the complete previous candidate and structural/text diff. Every functional change group requires an exact grounded assessment, and every unresolved prior issue needs an explicit reconciliation. No code location or query edit alone resolves an issue. Source-supported removal/replacement can be accepted without restoring a known excessive old constraint. Deterministic clear-schema conflicts stop the loop; model suggestions cannot override them.

Grounding validates quotation containment, candidate/version/hash and structured accounting. It does **not** prove entailment, legal interpretation, completeness, equivalence or the correctness of a model repair. Issues are `MODEL_INTERPRETATION` with `confirmed=false`; model-resolved issues remain interpretations. Missing constraints use real insertion anchors rather than imaginary offending tokens. `unchecked` scope and UNRESOLVED decisions are retained. ACCEPT is an internal operational decision, not independently certified compliance.

Each attempt saves requests, raw responses and finish reasons, code/hash, diagnostics, change groups, full diffs, issue transitions, timings and acceptance. Reviewer format retries are bounded, separate from candidate attempts. Single-shot never runs candidate checks or semantic review and keeps its original response. Budget-prefix analysis uses first acceptance and records total attempt time separately from provider time; no study dispatch route is included.

## Evaluation and tests

`evaluation/independent.py` contains the retained external oracles/reference controls. `evaluation/run_reference_controls.py` runs them in a separate process after software tests/workflow closure. Production never imports it. Fixtures, labels and repaired counterparts are unchanged. Tests contain synthetic local scripted responses and one copy of useful legacy witness/example data; the production resource allowlist denies both evaluation and tests, as well as historical/provenance catalogs.

The software suite demonstrates a novel requirement with no profile, identical paired initial requests, one-call Single-shot, exact diagnostics and latest-code integrity, canonical/type/unit checks, projection failures and valid controls, source-grounded removal and explicit change review, uncertainty/conflict handling, reconciliation, regressions, bounded failure and separate evaluation. Scripted reviews verify orchestration, not the quality of future real model interpretation.

## Remaining limitations

There is no independent general proof of regulatory implementation. The model reviewer may make unsupported interpretations even when its quotes are real; post-run independent evaluation remains necessary. Full source documents may be large and cross-reference completeness needs careful input curation. Static SPARQL coverage is bounded and complex encodings can remain unresolved. Registry/ontology/mapping ambiguities remain visible; the ontology is not declared final. Historical results use older methodology and cannot be pooled with v0.6.0.
