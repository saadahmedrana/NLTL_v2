# v0.8.0 context resolution and controller

`context_resolution.py` is a local resolver used by the existing runner. There is no master agent, framework, dashboard or new tracker. `tracking.py` is byte-identical to v0.7.0.

## Source inputs and trust

The catalog may declare document_id/aliases, authority, edition/revision, file, SHA-256 and provenance (optionally an original PDF path/hash). These are document identity facts, not regulatory logic. Referring revisions must match exactly; incompatible publisher/edition, missing files/sections/hashes/provenance and multiple matching documents are explicit. A sole unversioned reference may supply the available edition, but it remains RETRIEVED_EDITION_UNSPECIFIED and does not resolve temporal applicability. PDF publisher/edition were checked from rendered pages of the retained copy, not authenticated against a current online source. Catalog entries lacking edition/provenance remain unusable for authoritative dependency resolution until those facts are established.

References are found from supplied source, not evaluation data: UR identifiers and optional revision/clause, bare identifiers such as C3.2.1, PR identifiers and numbered references in retrieved documents. Clause headings are not misread as dependencies. Registered-source retrieval uses relevant application/scope/definition passages, lexical relevance, necessary parent context and recursive references. Context manifests record exact character/line/page locations, document and passage hashes, cycles, skips and limits. Whole passages that exceed budgets are deferred, never arbitrarily cut. Hash-pinned sources are read once by the resolver and cached; already included spans are not repeated. Source/provenance hashes join the runner’s per-dispatch integrity checks. Unprocessed/deferred references stay explicit.

## Schema evidence

Lexical/IRI search and generic ontology closure retrieve relevant properties/classes/individuals with labels and exact triples even without registry rows. Current-requirement bindings are distinguished from other-requirement mappings. Domains type subjects; they are not exclusive placement or legal eligibility. A declared Boolean applicability property is not automatically the correct switch. Retrieval does not modify termOwners, modelPaths, target_owner or the candidate. Relevant declarations may still be insufficient to settle a representation decision. Lexical relevance can include distractors and requires review.

## Controller transitions

1. CHECK_COMPLETE: keep all exact deterministic findings and current code.
2. For activation/context blockers or detected source dependencies: RETRIEVE_CONTEXT → EVIDENCE_ADDED, explicit missing/incompatible/limit state, or no new evidence.
3. REVIEW the full same candidate, its diagnostics, resolved evidence and unresolved gaps. REQUEST_EVIDENCE triggers bounded retrieval and re-review with the same candidate version/hash. Genuine uncertainty does not become a parser error.
4. REPAIR_PROPOSED is permitted only after source-grounded review classifies every static context/activation blocker as REPAIRABLE_CODE; no material semantic uncertainty may remain. This is an unverified model interpretation, not bespoke permission or an automatic target edit. The normal bounded repair route receives full latest code and original findings.
5. ACCEPTED requires no static/semantic blocker and valid review. ACCEPT cannot erase deactivation or targeting uncertainty. Every remaining retrieval gap requires explicit materiality assessment (unchecked.scope equals gap_id); material gaps block acceptance.
6. Missing information/unsupported bindings end UNRESOLVED_CONTEXT; identical repeated requests end REPEATED_EVIDENCE_REQUEST; context/review limits end CONTEXT_LIMIT_EXHAUSTED. No new code is selected for these outcomes. Hard candidate parse/canonical/query errors remain repairable within the candidate cap. Infrastructure, integrity, conflict and uncertain resource failures remain stop conditions.

Default caps: candidates 6; retrieval rounds 2/run; requests 3/round; documents 6/run; dependency lookups 24/run; dependency depth 3; passages 6/round; retrieved source characters 16,000/round and 32,000/run; schema terms 24/round and triples 300/round; review rounds 3/candidate and 8/run; configured format retries (default 1) separate. Thus default provider bound is at most 6 code requests + 8 reviews × 2 including format retry = 22, not a promised call count. The prepared two-candidate check lowers run reviews to 4, bounding provider requests at 10. No separate capability probe or regeneration.

## Review protocol

Existing strict field aliases, quote checks, deletion assessments and full-code integrity remain. Optional evidence_requests are bounded registered-source/schema queries, never arbitrary filesystem/URL access. REQUEST_EVIDENCE may have no regulatory issues because asking for evidence is not a claim. context_assessments cite exact source/current code/schema and a stable finding_key with REPAIRABLE_CODE, MISSING_INFORMATION or UNRESOLVED. A reviewer cannot infer a missing contract from fixtures or approve its own unsupported interpretation as verified fact. Rounds preserve previous semantic issue IDs and require reconciliation; the tracker itself is unchanged.

Source/schema context improvement is separate from query correctness. Every review still receives the full code and must inspect all obligations/branches. No external compliance fixture, label, counterpart or historical query diagnosis enters production. The saved-candidate software replay uses scripted uncertainty responses and is not a model-performance result or repair solution.

## Remaining limitations

The retained UR I1 Rev.2 supplies application/definition information, but the unversioned I2 reference, missing I3/PR29, and the current requirement’s missing approved applicability binding remain open. No contract is invented. General reference/heading extraction and lexical schema retrieval are bounded heuristics, not proof of document completeness or semantic relevance. Exact quotations do not prove legal interpretation, eligibility, arithmetic or full SHACL correctness. Unsupported constructs/extensions remain unresolved. A real reviewer can still err; software controls establish routing/integrity, not model repair quality.
