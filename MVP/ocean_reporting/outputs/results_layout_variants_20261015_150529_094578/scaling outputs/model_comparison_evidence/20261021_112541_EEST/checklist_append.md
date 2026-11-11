

## 21 October 2026: four-model results-evidence verification

Evidence-only update; no manuscript or figure changes. This section records evidence completion independently of the broader manuscript-revision tasks above, whose statuses are preserved.

Evidence package: /Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP/outputs/model_comparison_evidence/20261021_112541_EEST/
Audit: RESULTS_EVIDENCE_AUDIT.md. Summary: model_comparison_summary.csv. Requirement detail: model_comparison_per_requirement.csv.

- [x] Four-model behavioural accuracy verified against raw evidence. SELF_REPAIR_FINAL requirement-macro accuracy on retained 373 cases: Luna 72.032468%, Sol 82.193434%, Gemini 73.537013%, GPT-OSS 47.041919%. Independently reproduced the model-inclusive manuscript's displayed values; legacy 381-case results saved separately.
- [x] Shared 50-requirement cohort and case identities verified. Locked sample membership and independent assignment manifests match all four models and both stages. Luna is restricted to the selected 50 FULL_REPAIR_V2 requirements.
- [x] Legacy/current case-count discrepancy resolved or disclosed. Recovered exact eight excluded sample case IDs using the manuscript archive's retained 2,160-case exports, yielding 373 sample cases; expected labels and RDF hashes match. Case-specific exclusion adjudication and original report_02(1).zip remain unavailable. The later main-study-only manuscript omits model results.
- [x] Runtime and accuracy paired to corresponding outputs. All 200 generation event intervals match the runtime workbook. Accepted artifact hashes match evaluations. GPT-OSS IMO-112/TRF-059 evaluation run IDs are missing; unique final-scope requirement runs and identical exception messages establish their failed-run timing links. Missing evaluation IDs remain NA.
- [x] Timing boundaries documented. run_started to run_finished includes enabled generation/checks/repairs; excludes earlier context/few-shot preparation, later tracker export and separate post-generation RDF evaluation. Completed unsuccessful runs remain included.
- [x] Model sample selection and representativeness documented. Metadata-only deterministic stratified selection, seed and allocations retained. Sample modes 20/15/15 overrepresent calculation/readiness relative to 190/41/37 in the full benchmark. Reported macro values describe the sample; no population or repeated-run uncertainty claim.
- [x] Acceptance, executable coverage, and accuracy distinguished. Acceptance 43/47/46/28 out of 50 is separate from expected-verdict agreement; pooled and requirement-macro accuracy are distinguished in the audit.
- [ ] Accuracy-versus-median-runtime figure pending verified evidence. Required numeric evidence is now verified with the stated provenance qualifications; figure creation remains pending by instruction.

Remaining provenance questions: recover the per-case benchmark-exclusion review decisions if needed for submission, and identify the manuscript branch into which the model comparison should be reinstated. Do not substitute FIRST_GENERATION accuracy for final-stage accuracy or pair it with full-repair runtime as initial-response latency.
