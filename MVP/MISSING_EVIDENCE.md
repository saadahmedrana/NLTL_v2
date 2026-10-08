# Missing evidence and author-confirmation checklist

This file lists matters that cannot safely be inferred from the saved repository records inspected on 2026-09-30.

1. **Meaning of the final V2 label.** Confirm that the paper intentionally defines `V2_FALLBACK25` as official revised `FULL_REPAIR_V2/RUN_01` results plus the 25 rejected attempt-4 diagnostic candidates. It is not a saved pipeline configuration or generation-time fallback. State the retrospective substitution rule explicitly.

2. **Generation source revisions.** Supply a clean commit or source archive for revised V2, NO_SEMANTIC, SINGLESHOT, and the three non-Luna model controls. Evaluation manifests record commits, but some checkouts were dirty and are not complete generation snapshots.

3. **Runtime service identity.** Confirm the actual endpoint URL used by each run, gateway/provider deployment, model backend/version snapshot, and any server-side defaults. Configured/expected Aalto URLs and exposed model IDs are available; runtime URLs were environment-derived. No temperature, top-p, or random seed was sent or recorded.

4. **Regulatory-corpus preparation.** Document how clauses were extracted from the source PDFs, who performed/reviewed extraction, rules for splitting/merging clauses, duplicate handling, language/edition filters, and the reasons for pre-lock exclusions. The final R13 statuses and direct-benchmark inclusion rule are available, but not the full upstream decision trail.

5. **Fixture authorship and independent verification.** Identify fixture authors/reviewers, reviewer counts and qualifications, whether review was independent/blinded, and how disagreements were resolved. The repository proves locked provenance and no inspection of generated SHACL, not personnel or inter-rater reliability.

6. **Proposed benchmark changes.** Resolve the 26 proposed `RDF_EDIT` items in the final audit workbook. There are zero agreed/applied label changes and zero agreed reruns. Any later corrections require a new locked benchmark and fresh execution; old verdicts cannot be reused.

7. **Human audit.** Provide completed human-review sheets, reviewer identities/counts/qualifications, blinding procedure, adjudication record, and inter-rater statistics if a human expert audit is to be claimed. Current main-audit entries are marked `AI-assisted draft`; the scaling audit names `ChatGPT blind audit` as reviewer.

8. **Unassessable artifacts.** Confirm the intended paper treatment of the scaling audit's 16 MISSING and 5 UNPARSEABLE slots and reconcile it with final verdict totals. Do not assume all unparseable artifacts were classified NOT_ASSESSABLE.

9. **Runtime measurement.** Define whether reported elapsed time is summed API wall time, batch elapsed time, or end-to-end wall-clock time, and how concurrent/retried calls are handled. Saved historical summaries provide summed timings; revised V2 has per-call telemetry but no frozen aggregate timing/cost summary.

10. **Cost basis.** Confirm billing currency/date/source and actual charged prices. The saved Luna estimate uses USD 1/M input and USD 6/M output tokens and is described as indicative, not an Aalto invoice. Revised-V2 and cross-model aggregate costs/prices are unavailable.

11. **Execution environment.** Record operating system/container image, CPU/GPU, RAM, Python environment lock, and complete installed-package freeze. Only Python 3.13.5, RDFLib 7.6.0, pySHACL 0.31.0, declared dependency files, and model-comparison evaluator version 1.1.0 are saved.

12. **Replication/statistics scope.** Confirm that model-comparison claims are descriptive: one frozen sample and one run per model/mode were found, with no repeats or inferential statistical tests. If repeats or tests exist elsewhere, provide their manifests and scripts.

13. **External information-boundary assurance.** Repository prompts, payload construction, and separated generation/evaluation folders show no expected labels or RDF fixtures sent to generation/validation/repair. A service-side access/log attestation is absent if stronger leakage claims are needed.

14. **Terminology.** The workbook's “macro” field is equal-weight mean per-requirement accuracy, not macro-F1. Confirm manuscript terminology. Also distinguish generation-time `meta_shacl_valid` (Meta-SHACL plus runtime-smoke composite) from behavioural conformance.

15. **Source-family naming.** Confirm the publication-ready names/editions for `I2`, TRAFICOM, `IMO`, and `IMO26`; the evidence bundle preserves repository labels but does not infer full bibliographic citations.
