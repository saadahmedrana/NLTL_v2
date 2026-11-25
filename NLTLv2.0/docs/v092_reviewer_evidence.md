# v0.9.2 reviewer evidence and retry contract

## Required citations and state

The review packet contains `evidence_catalog.entries`, each with stable content/provenance SHA-256 ID, exact `text`, text hash and kind. SOURCE records preserve passage whitespace and file/document/span provenance. SCHEMA_TEXT records render supplied metadata in sorted JSON. RDF_FACT records render a single supplied ground triple clearly as N-Triples. Caller assertions and execution observations are distinguished from law. No fact is looked up in the ontology during citation validation: RDF_FACT entries are drawn only from context.ontology_evidence actually supplied to that review.

Every grounded source quotation carries `source_evidence_id` plus verbatim `source_excerpt` from that SOURCE entry. Issues and context assessments additionally carry `evidence_id` and `evidence_excerpt` pointing to a supplied entry. For text entries, quotes must be exact nonempty substrings. Only RDF_FACT allows equivalent single-fact Turtle/N-Triples syntax; exact RDF terms must match the referenced entry. Prefix aliases and escaped string serialization may differ. Numeric lexical forms/datatypes/languages cannot change; no numeric-value equivalence or inference is applied. RDF1.1 plain strings and explicit xsd:string denote the same RDF string term. Blank-node equivalence, multi-fact quotations, external JSON-LD contexts and arbitrary ontology facts are unsupported. Blank-node facts are not promoted to ground-fact catalog entries.

Response roots echo `candidate_version`, `candidate_sha256`, and `review_request_id`. The request ID binds the candidate, context/catalog, original prior issues, previous candidate, functional changes and actual execution summary. Missing/stale references are rejected. Literal alias normalization remains bounded and logs raw/normalized responses; it cannot repair quotations or supply IDs. Model interpretations remain unverified, even with valid references.

## Retry and failure collection

Format retries retain a deep copy of the same original review body: complete latest code, hash/version, original prior_issues, catalog and probe summary. `raw_previous_response` is failed output, not accepted state. Retry feedback lists every independently assessable validation error, exact field/path and required citation format; it explicitly lists allowed reconciliation IDs. Empty original prior issues requires empty reconciliations. Unknown reconciliation entries and incomplete/extra reconciliation sets fail. No partially validated issue enters repair or tracker state. A validated regulatory rejection can still supply issues normally; this does not promote a format-failed response.

The validator collects independent errors rather than masking them behind the first quotation error. Invalid outer JSON/types can prevent dependent checks; it does not claim semantic review completeness. Source-grounded semantic adequacy is still a model interpretation; schema-path conflicts are checked separately and cannot be overruled by a well-formed citation.

## Actual execution observation

The production execution probe now captures candidate version/SHA, engine/version, completed/error outcome and verbatim stdout/stderr/error diagnostic. Its reviewer summary excludes the synthetic witness graph and any expected compliance verdict. Execution success is explicitly not a proof of regulatory correctness, complete branches or arithmetic. NOT_RUN and unavailable legacy logs are distinguished. This is the existing execution-only schema probe, not a compliance witness or regulatory solution.

## Historical replay

Both original v0.9.1 responses and generated SHACL remain unchanged. Untouched replay against the new protocol reports seven failures for review2 and twelve for retry3, including absent new metadata/citation IDs. A separately labelled deterministic protocol-only projection adds binding/IDs for already supplied matching evidence, without changing quotations, reasons, decisions, proposed paths, reconciliations or uncertainty:

- Review2 then passes format/grounding but still has two proposed-path conflicts against explicit representation mappings.
- Retry3 still has two invented reconciliation IDs plus a reconciliation-set failure, and the same two path conflicts.

The raw N-Triples quotations correspond to facts actually present in the supplied context, not merely elsewhere in the ontology. Correcting serialization alone therefore does not make either response workflow-usable. All failure fields, projections and conflicts are recorded under the new audit's saved_review_replay directory; none grants historical credit.

## Prepared development continuation — no dispatch

`configs/v092_review_continuation.json` is intentionally method=offline: the normal generation CLI rejects it. It is a bounded continuation specification plus a complete pre-rendered production review packet, not a new live execution framework. The new audit's development_continuation directory contains a byte-identical copy of candidate1 (SHA d8986fa2c5186ae5d619696650e5f56328480bc5c3430465c4fdbc1ef9d94f9a), source/schema context only, a fresh execution-only probe and the rendered request. No failed historical review issues, known diagnostic solution, evaluation fixtures/labels/IDs/counterparts or compliance witnesses enter it.

For a separately authorized future orchestration, use production Runner.review/assess_candidate and targeted repair with zero initial generations, at most one repair (two candidates including seed), two context rounds, four primary reviews and one format retry per review; early acceptance and existing terminal policies apply. No seed edit, regeneration, additional attempts or candidate selection by external scores. Any independent evaluation follows dispatch closure. Label DEVELOPMENT_CONTINUATION, never fresh workflow performance. No live executor or model authorization is enabled by this preparation.

## Offline verification

```sh
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . check
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . smoke --skip-core
```

The full software suite includes exact/alternative citation syntax, altered and unsupplied facts (including facts that exist in schema but were not shown), numeric RDF lexical identity, source whitespace, stale candidate/context bindings, immutable retry state, invented reconciliation, probe delivery and continuation dispatch rejection. Evaluation fixtures and mathematical reference logic are unchanged; no historical experiment is rerun. Original schema, generated SHACL, historical results and tracker are preserved. No model calls or credential reads occur.
