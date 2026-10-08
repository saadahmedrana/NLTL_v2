NLTL manual audit package

Send one batches/BATCH_XX.txt file together with NLTL_Manual_Audit_ready.xlsx for review. Record Q1-Q7 grades and evidence only in the workbook's amber manual-input cells. Use filters; do not sort or delete rows in CaseReview, RawResults, or RequirementScores.

The same two frozen RDF cases are shown for all three architectures. Two cases do not validate the full requirement. V2_FALLBACK25 is retrospective audit evidence and does not alter official V2 results.

Eligible run pools: V2_FALLBACK25=[RUN_01], NO_SEMANTIC=[RUN_01], SINGLESHOT=[RUN_01]. No later run had a complete compatible 268-requirement / 2,186-case evaluation.

Architecture discrepancies are recorded in audit_selection.json. Reproduce packets with:
MVP/.venv/bin/python3 MVP/SHACL_GENERATION_PIPELINE/evaluation/manual_audit/AUDIT_20260915/scripts/package_audit.py

The 25 explicit gaps are absent generated SHACL specimens. No evaluation command is provided because evaluation cannot create a missing generation artifact.
