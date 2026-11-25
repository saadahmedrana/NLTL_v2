# v0.8.0 — bounded context resolution and controller routing

Implemented offline from v0.7.0. **No model calls, new generations, experiment reruns or tracker changes.** All pre-existing output/score files were hash-verified unchanged. No framework, master agent, dashboard, handwritten applicability solution, compliance witness or regulation-specific runtime check was added.

## General changes

The source selector now identifies UR identifiers, optional revisions/clauses, bare cross-document clause references and PR references. The bounded local resolver follows registered sources and their internal numbered dependencies, records exact character/line/page locations and document/passage/provenance hashes, caches immutable text and deduplicates spans. Missing/ambiguous/incompatible/provenance-unverified references, cycles and deferred/partial/limit states are explicit. It never chooses the latest edition silently or repeatedly attaches whole documents.

Schema retrieval finds declared vocabulary/labels/types, relevant range/class individuals and representation metadata without requiring registry rows. Current requirement bindings and other-requirement associations are distinguished; broad RDFS domains do not establish exclusive ownership or eligibility. Retrieval does not change the contract or candidate.

The existing runner now routes activation/material-context blockers through bounded retrieval and full-code review before declaring them terminal. The reviewer may REQUEST_EVIDENCE, propose a source-grounded code repair, or keep unresolved status. Stable finding keys classify repairable code versus missing information. Material gaps block acceptance; every remaining retrieval gap requires explicit materiality assessment. ACCEPT cannot erase static deactivation or missing activation. Full latest code/hash and all exact diagnostics remain in repair packets. Query review remains independent: the reviewer sees full code/source, with no external fixture results or historical diagnostic solution.

## Applicability evidence and remaining decision

The retained UR I1 publisher-imprint PDF was inspected on both rendered pages, imported unchanged with extracted text and pinned provenance. It identifies Rev.2 (April 2016); its application text and temporal note are now retrievable. UR I2 remains the retained Rev.4 (2019) text. Its UR I1 citation is unversioned, so the resolver reports RETRIEVED_EDITION_UNSPECIFIED rather than claiming the available I1 revision legally governs every instance. Related UR I3 and PR 29 references remain unavailable; their materiality needs review.

The saved-candidate diagnostic retrieves `polarClass`, `polarClassValue`/PC individuals and `polarClassRequirementsApplicable`, with types/labels/declarations and mapping evidence. Their existence does not certify which predicate/path, class or eligibility precondition represents this requirement. Its approved current contract still lacks that applicability binding. No gate was inferred from absent fixture assertions, Boolean defaults or domain declarations. Thus evidence is improved, but applicability is **not declared resolved** and no shape was activated.

## Exact transitions and limits

Saved v0.7 candidate (byte-identical SHA-256 `26f4d0bfbbc3d9ad5bc08df3be0ec3db8aee241f2b1a80728b0bd2fac650972a`):

`CHECK_COMPLETE → RETRIEVE_CONTEXT → EVIDENCE_ADDED → REVIEW → RETRIEVE_CONTEXT → REPEATED_EVIDENCE_REQUEST`

This labelled software replay made one scripted review and zero provider/generation/repair calls. It retrieved two source documents through the cache, adding 12,577 bounded source characters. Repeated unresolved requests stopped explicitly; the inactive original is not credited. Complete rendered review, source/schema ledgers, candidate hash and a full integrity-checked proposed feedback packet (NOT DISPATCHED) are retained.

The separate generic resolvable software control follows:

`CHECK_COMPLETE → RETRIEVE_CONTEXT → EVIDENCE_ADDED → REVIEW → REPAIR_PROPOSED → REPAIR_REQUEST_READY → CHECK_COMPLETE → REVIEW → ACCEPTED`

That control uses an invented software source/explicit test representation, not a regulatory applicability answer. It proves routing, full-code delivery, rechecking and bounded termination, not real model quality.

Default limits: 6 candidates; 2 context rounds/run; 3 top-level requests/round; 6 source documents/run; 24 dependency lookups/run; depth 3; 6 passages and 16,000 new source characters/round (32,000/run); 24 schema terms/300 triples per round; 3 reviews/candidate and 8 reviews/run; one configured format retry/review, separately counted. Repeated identical/no-new-evidence requests stop. Source tampering, integrity/conflict/infrastructure/uncertain resource errors stop. No source retrieval or review grants a fresh-regeneration escape.

## Verification

**136 software tests passed**, zero failures/errors. Controls cover available/missing/ambiguous/incompatible/cyclic references, exact provenance/hash checks, internal reference following, source/lookup/passage limits, deferred references, resolvable versus unresolved contexts, legitimate nested activation versus deactivated roots, evidence requests/re-review, bounded repeats, complete latest-code repair integrity (including cyclic retrieval metadata), source mutation stop and runtime denial of evaluation/witness reads.

The full offline verification also passed the **37 independent reference cases (17 positive, 20 intended negative) and all 20 repaired counterparts**, in a separate process with network blocked. The final change only persisted already-enforced retrieved-input hashes and was rechecked by all 136 software tests; reference inputs/ontology/oracles were unchanged and were not unnecessarily rerun. Reference success does not certify generation/repair correctness. The tracker file and installed/source identity were verified.

No external compliance evaluation of the saved candidate was rerun. No historical query-fix solution entered its review packets. Its latent query defect is not considered fixed merely because evidence is now available; full source-grounded logic review remains required.

## Prepared live check — not dispatched

`configs/v080_bounded_live_check.json`: one fresh I2-004 operational run, at most **2 candidates**, **2 context rounds**, **4 reviews/run** (max 3/candidate), and **one format retry/review**. At most 10 provider requests including one initial generation, one possible repair and review/retries. Stop early on acceptance or explicit unresolved/repeated/budget/failure outcomes. No seed, regeneration, preferred-result rerun, Single-shot batch or 50-requirement study. A legitimate result may remain unresolved. Future explicit model authorization and the existing live opt-in are required. Freeze all catalog-referenced source/provenance files, not just the initially selected primary source, before dispatch.

## Remaining blockers and limitations

Governing cross-document edition and an approved applicability representation still need a source/schema decision; no current eligibility answer is supplied. UR I3/PR29 are missing. Retained source authenticity is based on publisher imprint/provenance, not a current online publisher verification. Reference indexing and lexical schema retrieval are bounded heuristics, not complete legal dependency or semantic-relevance proofs. Other legacy catalog entries without sufficient edition/provenance remain unresolved when referenced. Reviewer quotations do not prove interpretation, materiality or query correctness. No performance advantage or optimal iteration budget is established.

## Artifacts and offline commands

- `representative_packet_index.json`: complete saved-candidate review/feedback and generic resolved review/repair packets.
- `saved_v070_diagnostic/controller_transitions.json`: exact unchanged-candidate transitions.
- `saved_v070_diagnostic/retrieved_input_hashes.json` and `retrieval_ledger.json`: verified source/PDF hashes and exact passage evidence.
- `source_import_manifest.json`, `applicability_evidence_summary.json`, `verification_results.json`, `preservation_verification.json`, `change_manifest.json` and `RECOVERY.md`.

```sh
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . check
PYTHONDONTWRITEBYTECODE=1 ../NLTLv2-env/bin/python -m nltlv2 --project . smoke
```
